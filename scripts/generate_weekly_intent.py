#!/usr/bin/env python3
"""
Weekly Intent Generator - Generate weekly training intent based on athlete state

Implements the Weekly Planning Engine from knowledge/frameworks/WEEKLY_PLANNING_ENGINE.md

The weekly intent is NOT a fixed schedule. It defines:
- Key session targets (readiness-gated)
- Volume ranges (not fixed numbers)
- Priority rules

Usage:
    python scripts/generate_weekly_intent.py matti-rowe
    python scripts/generate_weekly_intent.py matti-rowe --verbose
    python scripts/generate_weekly_intent.py matti-rowe --dry-run
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_CONFIG = {
    # Base key sessions per week (adjusted by TSB/readiness)
    "base_key_sessions": 2,

    # TSB thresholds for adjusting key sessions
    "tsb_thresholds": {
        "fresh": 5,          # TSB > 5: can handle more intensity
        "neutral_low": -5,   # TSB -5 to 5: normal load
        "tired": -15,        # TSB -15 to -5: reduce intensity
        "exhausted": -25,    # TSB < -25: recovery mode
    },

    # Readiness thresholds
    "readiness_thresholds": {
        "high": 75,    # Above this: full capacity
        "moderate": 60, # 60-75: normal capacity
        "low": 45,      # 45-60: reduced capacity
    },

    # Volume adjustment factors
    "volume_factors": {
        "fresh": 1.1,      # Can handle 10% more volume
        "normal": 1.0,     # Normal volume
        "tired": 0.85,     # Reduce by 15%
        "exhausted": 0.7,  # Reduce by 30%
    },

    # Training phases affect volume/intensity balance
    "phase_modifiers": {
        "base": {"volume_bias": 1.1, "intensity_bias": 0.8},
        "build": {"volume_bias": 1.0, "intensity_bias": 1.0},
        "peak": {"volume_bias": 0.9, "intensity_bias": 1.1},
        "taper": {"volume_bias": 0.6, "intensity_bias": 0.9},
        "recovery": {"volume_bias": 0.5, "intensity_bias": 0.3},
    },
}


# =============================================================================
# INTENT GENERATION
# =============================================================================

def load_profile(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete profile from YAML."""
    profile_file = athlete_dir / "profile.yaml"
    if not profile_file.exists():
        raise FileNotFoundError(f"Profile not found: {profile_file}")

    with open(profile_file) as f:
        return yaml.safe_load(f)


def load_state(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete state from JSON."""
    state_file = athlete_dir / "athlete_state.json"
    if not state_file.exists():
        raise FileNotFoundError(f"State not found: {state_file}")

    with open(state_file) as f:
        return json.load(f)


def determine_fatigue_status(tsb: float, config: Dict) -> str:
    """Determine fatigue status from TSB."""
    thresholds = config["tsb_thresholds"]

    if tsb > thresholds["fresh"]:
        return "fresh"
    elif tsb > thresholds["neutral_low"]:
        return "normal"
    elif tsb > thresholds["tired"]:
        return "tired"
    else:
        return "exhausted"


def determine_readiness_status(score: float, config: Dict) -> str:
    """Determine readiness status from score."""
    thresholds = config["readiness_thresholds"]

    if score >= thresholds["high"]:
        return "high"
    elif score >= thresholds["moderate"]:
        return "moderate"
    elif score >= thresholds["low"]:
        return "low"
    else:
        return "very_low"


def calculate_key_sessions_target(
    fatigue_status: str,
    readiness_status: str,
    phase: str,
    config: Dict,
    verbose: bool = False
) -> int:
    """Calculate target number of key sessions for the week."""
    base = config["base_key_sessions"]

    # Adjust based on fatigue
    fatigue_adjustments = {
        "fresh": 1,
        "normal": 0,
        "tired": -1,
        "exhausted": -2,
    }

    # Adjust based on readiness
    readiness_adjustments = {
        "high": 0,
        "moderate": 0,
        "low": -1,
        "very_low": -2,
    }

    # Phase-based limits
    phase_limits = {
        "base": 2,
        "build": 3,
        "peak": 2,
        "taper": 1,
        "recovery": 0,
    }

    adjustment = fatigue_adjustments.get(fatigue_status, 0)
    adjustment += readiness_adjustments.get(readiness_status, 0)

    target = base + adjustment

    # Apply phase limit
    phase_limit = phase_limits.get(phase, 2)
    target = min(target, phase_limit)

    # Never below 0
    target = max(0, target)

    if verbose:
        print(f"  Key sessions: base={base}, fatigue_adj={fatigue_adjustments.get(fatigue_status, 0)}, "
              f"readiness_adj={readiness_adjustments.get(readiness_status, 0)}, phase_limit={phase_limit} → {target}")

    return target


def calculate_volume_range(
    base_hours: float,
    fatigue_status: str,
    phase: str,
    config: Dict,
    verbose: bool = False
) -> tuple:
    """Calculate aerobic volume range for the week."""
    # Get volume adjustment factor
    volume_factor = config["volume_factors"].get(fatigue_status, 1.0)

    # Get phase modifier
    phase_mod = config["phase_modifiers"].get(phase, {"volume_bias": 1.0})
    volume_bias = phase_mod.get("volume_bias", 1.0)

    # Calculate adjusted base
    adjusted_base = base_hours * volume_factor * volume_bias

    # Create range (±15% of adjusted base)
    min_hours = round(adjusted_base * 0.85, 1)
    max_hours = round(adjusted_base * 1.15, 1)

    if verbose:
        print(f"  Volume: base={base_hours}h, fatigue_factor={volume_factor}, "
              f"phase_bias={volume_bias} → [{min_hours}, {max_hours}]h")

    return (min_hours, max_hours)


def calculate_max_tss(
    base_hours: float,
    ftp: int,
    fatigue_status: str,
    config: Dict
) -> int:
    """Estimate max weekly TSS based on hours and fatigue."""
    # Rough estimate: 1 hour at IF 0.7 ≈ 50 TSS
    base_tss = base_hours * 50

    # Adjust for fatigue
    volume_factor = config["volume_factors"].get(fatigue_status, 1.0)
    max_tss = int(base_tss * volume_factor)

    return max_tss


def generate_weekly_intent(
    profile: Dict,
    state: Dict,
    config: Dict = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """Generate weekly intent based on profile and current state."""
    if config is None:
        config = DEFAULT_CONFIG

    # Extract relevant data
    availability = profile.get("availability", {})
    base_hours = availability.get("hours_per_week", 10)
    phase = profile.get("status", {}).get("phase", "base")
    ftp = profile.get("physiology", {}).get("ftp", 300)

    # Get current metrics
    readiness = state.get("readiness", {})
    readiness_score = readiness.get("score", 70)

    pmc = state.get("performance_management", {})
    tsb = pmc.get("tsb", 0)
    ctl = pmc.get("ctl", 0)
    atl = pmc.get("atl", 0)
    ramp_rate = pmc.get("ramp_rate", 0)

    if verbose:
        print(f"\n[Weekly Intent Generator]")
        print(f"  Athlete phase: {phase}")
        print(f"  Base hours: {base_hours}")
        print(f"  Current readiness: {readiness_score}")
        print(f"  Current TSB: {tsb}")
        print(f"  CTL: {ctl}, ATL: {atl}, Ramp rate: {ramp_rate}")

    # Determine status
    fatigue_status = determine_fatigue_status(tsb, config)
    readiness_status = determine_readiness_status(readiness_score, config)

    if verbose:
        print(f"  Fatigue status: {fatigue_status}")
        print(f"  Readiness status: {readiness_status}")

    # Calculate targets
    key_sessions = calculate_key_sessions_target(
        fatigue_status, readiness_status, phase, config, verbose
    )

    volume_range = calculate_volume_range(
        base_hours, fatigue_status, phase, config, verbose
    )

    max_tss = calculate_max_tss(base_hours, ftp, fatigue_status, config)

    # Determine priority rule
    if fatigue_status in ["tired", "exhausted"] or readiness_status in ["low", "very_low"]:
        priority = "recover > respond > complete"
    else:
        priority = "respond > complete"

    # Build intent
    intent = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "generate_weekly_intent",
            "valid_for_week_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "key_sessions_target": key_sessions,
        "key_sessions_completed": 0,
        "key_sessions_remaining": key_sessions,
        "aerobic_volume_hours": list(volume_range),
        "max_weekly_tss": max_tss,
        "priority": priority,
        "phase": phase,
        "context": {
            "fatigue_status": fatigue_status,
            "readiness_status": readiness_status,
            "tsb_at_generation": tsb,
            "readiness_at_generation": readiness_score,
            "ramp_rate": ramp_rate,
        },
        "constraints": [],
        "notes": [],
    }

    # Add constraints based on status
    if fatigue_status == "exhausted":
        intent["constraints"].append("No key sessions until TSB > -15")
        intent["notes"].append("Recovery week - focus on sleep and easy spinning")
    elif fatigue_status == "tired":
        intent["constraints"].append("Max 1 key session early in week")
        intent["notes"].append("Accumulating fatigue - protect recovery")

    if ramp_rate > 5:
        intent["constraints"].append("Ramp rate elevated - avoid adding load")
        intent["notes"].append(f"Ramp rate {ramp_rate:.1f} TSS/week exceeds 5 TSS/week target")

    if readiness_status == "very_low":
        intent["constraints"].append("All sessions recovery until readiness > 45")

    if verbose:
        print(f"\n  Generated intent:")
        print(f"    Key sessions: {key_sessions}")
        print(f"    Volume range: {volume_range[0]}-{volume_range[1]} hours")
        print(f"    Max TSS: {max_tss}")
        print(f"    Priority: {priority}")
        if intent["constraints"]:
            print(f"    Constraints: {intent['constraints']}")

    return intent


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly training intent based on athlete state"
    )
    parser.add_argument(
        "athlete_name",
        help="Athlete folder name (e.g., matti-rowe)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed calculation steps"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate but don't save the intent file"
    )
    parser.add_argument(
        "--output",
        help="Custom output path (default: athletes/{name}/weekly_intent.json)"
    )

    args = parser.parse_args()

    # Find athlete directory
    base_dir = Path(__file__).parent.parent
    athlete_dir = base_dir / "athletes" / args.athlete_name

    if not athlete_dir.exists():
        print(f"Error: Athlete directory not found: {athlete_dir}")
        sys.exit(1)

    try:
        # Load data
        profile = load_profile(athlete_dir)
        state = load_state(athlete_dir)

        # Generate intent
        intent = generate_weekly_intent(profile, state, verbose=args.verbose)

        # Output
        if args.dry_run:
            print("\n[DRY RUN] Would write:")
            print(json.dumps(intent, indent=2))
        else:
            output_path = Path(args.output) if args.output else athlete_dir / "weekly_intent.json"

            with open(output_path, "w") as f:
                json.dump(intent, f, indent=2)

            print(f"\nWeekly intent saved to: {output_path}")
            print(f"  Key sessions target: {intent['key_sessions_target']}")
            print(f"  Volume range: {intent['aerobic_volume_hours'][0]}-{intent['aerobic_volume_hours'][1]} hours")
            print(f"  Priority: {intent['priority']}")

            if intent["constraints"]:
                print(f"  Constraints:")
                for c in intent["constraints"]:
                    print(f"    - {c}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating intent: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
