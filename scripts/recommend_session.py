#!/usr/bin/env python3
"""
Daily Session Recommender - Recommend today's session based on readiness

Implements readiness-gated session selection from WEEKLY_PLANNING_ENGINE.md:
- Score >= 70: Key session eligible (VO2max, Threshold, G-Spot)
- Score 45-70: Support session (Endurance, Cadence Work, Easy Tempo)
- Score < 45: Recovery only

Health gates override readiness - any gate fail blocks intensity.

Usage:
    python scripts/recommend_session.py matti-rowe
    python scripts/recommend_session.py matti-rowe --verbose
    python scripts/recommend_session.py matti-rowe --json
"""

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# ARCHETYPE LIBRARY
# =============================================================================

# Organized by session type - these map to ZWO files in knowledge/archetypes/
ARCHETYPES = {
    "key": {
        "vo2max": [
            {"name": "4x4 VO2max", "file": "4x4min_vo2.zwo", "duration_min": 60, "tss_est": 75},
            {"name": "30/30s VO2", "file": "3030s_VO2.zwo", "duration_min": 60, "tss_est": 70},
            {"name": "6x4m VO2 Spaced", "file": "6x4m_VO2_Spaced_Through.zwo", "duration_min": 75, "tss_est": 85},
            {"name": "3x10min VO2 Buffers", "file": "3x10min_vo2_buffers_5x3030.zwo", "duration_min": 90, "tss_est": 95},
        ],
        "threshold": [
            {"name": "2x20 Threshold", "file": "2x20_threshold.zwo", "duration_min": 75, "tss_est": 80},
            {"name": "Over/Unders", "file": "Over_Unders.zwo", "duration_min": 60, "tss_est": 75},
            {"name": "TT Efforts", "file": "154_TT_Efforts_Gila.zwo", "duration_min": 90, "tss_est": 90},
        ],
        "gspot": [
            {"name": "G-Spot Intervals", "file": "G_Spot.zwo", "duration_min": 75, "tss_est": 85},
            {"name": "2x30 Z3", "file": "2_x_30_Z3.zwo", "duration_min": 90, "tss_est": 80},
            {"name": "Tempo Blocks", "file": "tempo_blocks.zwo", "duration_min": 60, "tss_est": 65},
        ],
        "durability": [
            {"name": "4hr Endurance w/ Surges", "file": "4hr_endurance_w_surges.zwo", "duration_min": 240, "tss_est": 180},
            {"name": "5hr Endurance w/ Surges", "file": "5hr_endurance_w_surges.zwo", "duration_min": 300, "tss_est": 220},
        ],
    },
    "support": {
        "endurance": [
            {"name": "3h Low Endurance", "file": "3h_Low_Endurance.zwo", "duration_min": 180, "tss_est": 120},
            {"name": "4h Steady Endurance", "file": "4h_Steady_Endurance_cadence_late.zwo", "duration_min": 240, "tss_est": 160},
            {"name": "90min Z2", "file": "90min_z2.zwo", "duration_min": 90, "tss_est": 60},
        ],
        "sfr": [
            {"name": "SFR Muscle Force", "file": "SFR_muscle_force.zwo", "duration_min": 60, "tss_est": 55},
            {"name": "Low Cadence Strength", "file": "low_cadence_strength.zwo", "duration_min": 75, "tss_est": 65},
        ],
        "cadence": [
            {"name": "High Cadence Drills", "file": "high_cadence_drills.zwo", "duration_min": 60, "tss_est": 50},
            {"name": "Spin-ups", "file": "spinups.zwo", "duration_min": 45, "tss_est": 35},
        ],
    },
    "recovery": {
        "active_recovery": [
            {"name": "60min Active Recovery", "file": "60min_Active_Recovery.zwo", "duration_min": 60, "tss_est": 30},
            {"name": "60min Z1 Recovery", "file": "60min_z1_recovery.zwo", "duration_min": 60, "tss_est": 25},
            {"name": "Active Recovery Flush", "file": "Active_Recovery_Flush.zwo", "duration_min": 45, "tss_est": 20},
        ],
        "rest": [
            {"name": "Complete Rest", "file": None, "duration_min": 0, "tss_est": 0},
        ],
    },
}

# Session type priorities based on training phase
PHASE_PRIORITIES = {
    "base": ["endurance", "gspot", "sfr"],
    "build": ["threshold", "vo2max", "gspot"],
    "peak": ["vo2max", "threshold", "durability"],
    "taper": ["gspot", "active_recovery", "endurance"],
    "recovery": ["active_recovery", "rest"],
}


# =============================================================================
# RECOMMENDATION ENGINE
# =============================================================================

def load_state(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete state from JSON."""
    state_file = athlete_dir / "athlete_state.json"
    if not state_file.exists():
        raise FileNotFoundError(f"State not found: {state_file}")

    with open(state_file) as f:
        return json.load(f)


def load_profile(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete profile from YAML."""
    import yaml
    profile_file = athlete_dir / "profile.yaml"
    if not profile_file.exists():
        raise FileNotFoundError(f"Profile not found: {profile_file}")

    with open(profile_file) as f:
        return yaml.safe_load(f)


def load_weekly_intent(athlete_dir: Path) -> Optional[Dict[str, Any]]:
    """Load weekly intent if it exists."""
    intent_file = athlete_dir / "weekly_intent.json"
    if intent_file.exists():
        with open(intent_file) as f:
            return json.load(f)
    return None


def check_health_gates(state: Dict) -> Tuple[bool, List[str]]:
    """Check all health gates. Returns (all_pass, failed_gates)."""
    health_gates = state.get("health_gates", {})
    overall = health_gates.get("overall", {})

    if overall.get("all_gates_pass", True):
        return True, []

    # Find which gates failed
    failed = []
    for gate_name in ["sleep", "energy", "autonomic", "musculoskeletal", "stress"]:
        gate = health_gates.get(gate_name, {})
        if not gate.get("gate_pass", True):
            failed.append(gate_name)

    return False, failed


def determine_session_type(
    readiness_score: float,
    gates_pass: bool,
    key_threshold: float = 70,
    support_threshold: float = 45,
    verbose: bool = False
) -> str:
    """Determine session type based on readiness and gates."""
    # Gate failure blocks intensity regardless of score
    if not gates_pass:
        if verbose:
            print("  Health gate failed - recovery only")
        return "recovery"

    if readiness_score >= key_threshold:
        return "key"
    elif readiness_score >= support_threshold:
        return "support"
    else:
        return "recovery"


def select_archetype(
    session_type: str,
    phase: str,
    weekly_intent: Optional[Dict] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """Select specific workout archetype based on session type and phase."""
    archetypes = ARCHETYPES.get(session_type, {})

    if not archetypes:
        # Fallback to recovery
        return ARCHETYPES["recovery"]["active_recovery"][0]

    # Get phase priorities for subcategory selection
    priorities = PHASE_PRIORITIES.get(phase, ["endurance"])

    # Find first matching subcategory in archetypes
    selected_category = None
    for priority in priorities:
        if priority in archetypes:
            selected_category = priority
            break

    if not selected_category:
        # Use first available category
        selected_category = list(archetypes.keys())[0]

    if verbose:
        print(f"  Selected category: {selected_category} (phase: {phase})")

    # Check weekly intent for key session constraints
    if session_type == "key" and weekly_intent:
        remaining = weekly_intent.get("key_sessions_remaining", 2)
        if remaining <= 0:
            if verbose:
                print("  Weekly key sessions exhausted - switching to support")
            return select_archetype("support", phase, None, verbose)

    # Pick random workout from category (could be smarter in future)
    options = archetypes[selected_category]
    selected = random.choice(options)

    return {
        **selected,
        "category": selected_category,
        "session_type": session_type,
    }


def generate_recommendation(
    state: Dict,
    profile: Dict,
    weekly_intent: Optional[Dict] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """Generate session recommendation."""
    # Extract data
    readiness = state.get("readiness", {})
    readiness_score = readiness.get("score", 70)
    key_threshold = readiness.get("threshold_key_session", 70)
    support_threshold = readiness.get("threshold_support_session", 45)
    recommendation_color = readiness.get("recommendation", "yellow")

    phase = profile.get("status", {}).get("phase", "base")

    if verbose:
        print(f"\n[Daily Session Recommender]")
        print(f"  Readiness score: {readiness_score}")
        print(f"  Thresholds: key={key_threshold}, support={support_threshold}")
        print(f"  Phase: {phase}")

    # Check health gates
    gates_pass, failed_gates = check_health_gates(state)

    if verbose:
        if gates_pass:
            print("  Health gates: ALL PASS")
        else:
            print(f"  Health gates: FAILED - {failed_gates}")

    # Determine session type
    session_type = determine_session_type(
        readiness_score, gates_pass, key_threshold, support_threshold, verbose
    )

    if verbose:
        print(f"  Session type: {session_type.upper()}")

    # Select archetype
    archetype = select_archetype(session_type, phase, weekly_intent, verbose)

    # Build recommendation
    recommendation = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "recommend_session",
        },
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "session_type": session_type,
        "archetype": archetype,
        "readiness": {
            "score": readiness_score,
            "color": recommendation_color,
            "gates_pass": gates_pass,
            "failed_gates": failed_gates,
        },
        "rationale": [],
    }

    # Build rationale
    if not gates_pass:
        recommendation["rationale"].append(f"Health gate(s) failed: {', '.join(failed_gates)}")
        recommendation["rationale"].append("Intensity blocked - recovery session required")
    elif session_type == "key":
        recommendation["rationale"].append(f"Readiness {readiness_score} >= {key_threshold} threshold")
        recommendation["rationale"].append("All health gates passed - key session eligible")
    elif session_type == "support":
        recommendation["rationale"].append(f"Readiness {readiness_score} between {support_threshold}-{key_threshold}")
        recommendation["rationale"].append("Support session - build volume without intensity stress")
    else:
        recommendation["rationale"].append(f"Readiness {readiness_score} < {support_threshold}")
        recommendation["rationale"].append("Recovery required - prioritize sleep and easy movement")

    # Add weekly context if available
    if weekly_intent:
        key_remaining = weekly_intent.get("key_sessions_remaining", 0)
        recommendation["weekly_context"] = {
            "key_sessions_target": weekly_intent.get("key_sessions_target", 2),
            "key_sessions_remaining": key_remaining,
            "priority": weekly_intent.get("priority", "respond > complete"),
        }

        if session_type == "key" and key_remaining > 0:
            recommendation["rationale"].append(f"Key session {weekly_intent['key_sessions_target'] - key_remaining + 1} of {weekly_intent['key_sessions_target']} this week")

    if verbose:
        print(f"\n  Recommended: {archetype['name']}")
        print(f"  Duration: {archetype['duration_min']} min")
        print(f"  Est. TSS: {archetype['tss_est']}")

    return recommendation


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Recommend daily session based on readiness and health gates"
    )
    parser.add_argument(
        "athlete_name",
        help="Athlete folder name (e.g., matti-rowe)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed decision process"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON only"
    )

    args = parser.parse_args()

    # Find athlete directory
    base_dir = Path(__file__).parent.parent
    athlete_dir = base_dir / "athletes" / args.athlete_name

    if not athlete_dir.exists():
        print(f"Error: Athlete directory not found: {athlete_dir}")
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print("Error: pyyaml required. Install with: pip install pyyaml")
        sys.exit(1)

    try:
        # Load data
        state = load_state(athlete_dir)
        profile = load_profile(athlete_dir)
        weekly_intent = load_weekly_intent(athlete_dir)

        # Generate recommendation
        recommendation = generate_recommendation(
            state, profile, weekly_intent, verbose=args.verbose
        )

        # Output
        if args.json:
            print(json.dumps(recommendation, indent=2))
        else:
            archetype = recommendation["archetype"]
            readiness = recommendation["readiness"]

            print(f"\n{'='*50}")
            print(f"SESSION RECOMMENDATION - {recommendation['date']}")
            print(f"{'='*50}")
            print(f"\nType: {recommendation['session_type'].upper()}")
            print(f"Workout: {archetype['name']}")
            print(f"Duration: {archetype['duration_min']} min")
            print(f"Est. TSS: {archetype['tss_est']}")

            if archetype.get("file"):
                print(f"ZWO File: {archetype['file']}")

            print(f"\nReadiness: {readiness['score']} ({readiness['color'].upper()})")
            print(f"Gates: {'PASS' if readiness['gates_pass'] else 'FAIL'}")

            if not readiness['gates_pass']:
                print(f"  Failed: {', '.join(readiness['failed_gates'])}")

            print(f"\nRationale:")
            for r in recommendation["rationale"]:
                print(f"  • {r}")

            if "weekly_context" in recommendation:
                ctx = recommendation["weekly_context"]
                print(f"\nWeekly Context:")
                print(f"  Key sessions: {ctx['key_sessions_target'] - ctx['key_sessions_remaining']}/{ctx['key_sessions_target']} completed")
                print(f"  Priority: {ctx['priority']}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating recommendation: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
