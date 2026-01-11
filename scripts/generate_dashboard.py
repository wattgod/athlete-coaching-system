#!/usr/bin/env python3
"""
Dashboard Data Generator - Aggregate all athlete data for dashboard display

Combines data from:
- athlete_state.json (readiness, health gates, PMC, training)
- profile.yaml (goals, blindspots, race calendar)
- weekly_intent.json (weekly planning context)

Generates dashboard_data.json for the web dashboard.

Usage:
    python scripts/generate_dashboard.py matti-rowe
    python scripts/generate_dashboard.py matti-rowe --output /path/to/output.json
"""

import argparse
import json
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Import from existing scripts
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.blindspot_rules import get_blindspot_adjustments, get_blindspot_prompts


# =============================================================================
# ARCHETYPE LIBRARY (copied from recommend_session.py)
# =============================================================================

ARCHETYPES = {
    "key": {
        "vo2max": [
            {"name": "4x4 VO2max", "file": "4x4min_vo2.zwo", "duration_min": 60, "tss_est": 75},
            {"name": "30/30s VO2", "file": "3030s_VO2.zwo", "duration_min": 60, "tss_est": 70},
        ],
        "threshold": [
            {"name": "2x20 Threshold", "file": "2x20_threshold.zwo", "duration_min": 75, "tss_est": 80},
            {"name": "Over/Unders", "file": "Over_Unders.zwo", "duration_min": 60, "tss_est": 75},
        ],
        "gspot": [
            {"name": "G-Spot Intervals", "file": "G_Spot.zwo", "duration_min": 75, "tss_est": 85},
            {"name": "2x30 Z3", "file": "2_x_30_Z3.zwo", "duration_min": 90, "tss_est": 80},
        ],
    },
    "support": {
        "endurance": [
            {"name": "3h Low Endurance", "file": "3h_Low_Endurance.zwo", "duration_min": 180, "tss_est": 120},
            {"name": "90min Z2", "file": "90min_z2.zwo", "duration_min": 90, "tss_est": 60},
        ],
        "sfr": [
            {"name": "SFR Muscle Force", "file": "SFR_muscle_force.zwo", "duration_min": 60, "tss_est": 55},
        ],
    },
    "recovery": {
        "active_recovery": [
            {"name": "60min Active Recovery", "file": "60min_Active_Recovery.zwo", "duration_min": 60, "tss_est": 30},
            {"name": "Complete Rest", "file": None, "duration_min": 0, "tss_est": 0},
        ],
    },
}

PHASE_PRIORITIES = {
    "base": ["endurance", "gspot", "sfr"],
    "build": ["threshold", "vo2max", "gspot"],
    "peak": ["vo2max", "threshold"],
    "taper": ["gspot", "active_recovery"],
    "recovery": ["active_recovery"],
}


# =============================================================================
# DATA LOADERS
# =============================================================================

def load_state(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete state from JSON."""
    state_file = athlete_dir / "athlete_state.json"
    if not state_file.exists():
        return {}
    with open(state_file) as f:
        return json.load(f)


def load_profile(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete profile from YAML."""
    profile_file = athlete_dir / "profile.yaml"
    if not profile_file.exists():
        return {}
    with open(profile_file) as f:
        return yaml.safe_load(f)


def load_weekly_intent(athlete_dir: Path) -> Optional[Dict[str, Any]]:
    """Load weekly intent if it exists."""
    intent_file = athlete_dir / "weekly_intent.json"
    if intent_file.exists():
        with open(intent_file) as f:
            return json.load(f)
    return None


# =============================================================================
# SECTION GENERATORS
# =============================================================================

def generate_readiness_section(state: Dict) -> Dict:
    """Generate readiness hero section data."""
    readiness = state.get("readiness", {})

    score = readiness.get("score", 0)
    recommendation = readiness.get("recommendation", "red")

    # Color mapping
    color_map = {
        "green": "#00FF00",
        "yellow": "#FFFF00",
        "red": "#FF3333",
    }

    # ANS quadrant names
    ans_names = {
        0: "Unknown",
        1: "Q1: Deep Recovery",
        2: "Q2: Ready to Train",
        3: "Q3: Overreach",
        4: "Q4: Overtrained",
    }

    ans_data = readiness.get("ans_quadrant", {})
    quadrant = ans_data.get("quadrant", 0)

    return {
        "score": score,
        "max_score": 100,
        "recommendation": recommendation,
        "color": color_map.get(recommendation, "#FF3333"),
        "key_session_eligible": readiness.get("key_session_eligible", False),
        "session_type_allowed": readiness.get("session_type_allowed", "recovery"),
        "threshold_key": readiness.get("threshold_key_session", 70),
        "threshold_support": readiness.get("threshold_support_session", 45),
        "ans_quadrant": {
            "number": quadrant,
            "name": ans_names.get(quadrant, "Unknown"),
            "status": ans_data.get("status", "unknown"),
            "modifier": ans_data.get("modifier", 0),
        },
        "score_breakdown": readiness.get("score_breakdown", {}),
        "factors": readiness.get("factors", {}),
    }


def generate_health_gates_section(state: Dict) -> Dict:
    """Generate health gates section data."""
    health_gates = state.get("health_gates", {})
    overall = health_gates.get("overall", {})

    gates = []
    for gate_name in ["sleep", "energy", "autonomic", "musculoskeletal", "stress"]:
        gate = health_gates.get(gate_name, {})
        gate_pass = gate.get("gate_pass", True)

        # Get key detail for each gate
        detail = ""
        if gate_name == "sleep":
            hours = gate.get("last_night_hours")
            if hours:
                detail = f"{hours:.1f}h"
        elif gate_name == "autonomic":
            hrv_pct = gate.get("hrv_vs_baseline_pct")
            if hrv_pct:
                detail = f"HRV {hrv_pct}%"
        elif gate_name == "musculoskeletal":
            soreness = gate.get("soreness_level", 0)
            detail = f"soreness: {soreness}/10"
        elif gate_name == "stress":
            stress = gate.get("life_stress_level", 0)
            detail = f"stress: {stress}/10"

        gates.append({
            "name": gate_name,
            "display_name": gate_name.replace("_", " ").title(),
            "pass": gate_pass,
            "detail": detail,
        })

    return {
        "gates": gates,
        "all_pass": overall.get("all_gates_pass", True),
        "intensity_allowed": overall.get("intensity_allowed", True),
        "intensity_recommendation": overall.get("intensity_recommendation", "full"),
        "marginal_gates": overall.get("gates_marginal", []),
    }


def generate_session_section(state: Dict, profile: Dict, weekly_intent: Optional[Dict]) -> Dict:
    """Generate today's session recommendation."""
    readiness = state.get("readiness", {})
    score = readiness.get("score", 0)
    key_threshold = readiness.get("threshold_key_session", 70)
    support_threshold = readiness.get("threshold_support_session", 45)

    health_gates = state.get("health_gates", {})
    gates_pass = health_gates.get("overall", {}).get("all_gates_pass", True)

    # Determine session type
    if not gates_pass:
        session_type = "recovery"
    elif score >= key_threshold:
        session_type = "key"
    elif score >= support_threshold:
        session_type = "support"
    else:
        session_type = "recovery"

    # Get phase
    phase = profile.get("status", {}).get("phase", "base")

    # Select archetype
    archetypes = ARCHETYPES.get(session_type, {})
    priorities = PHASE_PRIORITIES.get(phase, ["endurance"])

    selected_category = None
    for priority in priorities:
        if priority in archetypes:
            selected_category = priority
            break

    if not selected_category and archetypes:
        selected_category = list(archetypes.keys())[0]

    if selected_category:
        workout = random.choice(archetypes[selected_category])
    else:
        workout = {"name": "Rest Day", "duration_min": 0, "tss_est": 0, "file": None}

    # Build rationale
    rationale = []
    if not gates_pass:
        rationale.append("Health gate(s) failed - recovery required")
    elif session_type == "key":
        rationale.append(f"Readiness {score} >= {key_threshold} threshold")
        rationale.append("All health gates passed")
    elif session_type == "support":
        rationale.append(f"Readiness {score} in support range ({support_threshold}-{key_threshold})")
    else:
        rationale.append(f"Readiness {score} < {support_threshold}")

    # Weekly context
    weekly_context = None
    if weekly_intent:
        weekly_context = {
            "key_sessions_target": weekly_intent.get("key_sessions_target", 2),
            "key_sessions_completed": weekly_intent.get("key_sessions_completed", 0),
            "key_sessions_remaining": weekly_intent.get("key_sessions_remaining", 2),
        }

    return {
        "session_type": session_type,
        "workout": {
            "name": workout["name"],
            "duration_min": workout["duration_min"],
            "tss_est": workout["tss_est"],
            "file": workout.get("file"),
            "category": selected_category,
        },
        "rationale": rationale,
        "weekly_context": weekly_context,
    }


def generate_pmc_section(state: Dict) -> Dict:
    """Generate PMC (Performance Management Chart) section."""
    pmc = state.get("performance_management", {})

    ctl = pmc.get("ctl", 0)
    atl = pmc.get("atl", 0)
    tsb = pmc.get("tsb", 0)
    ramp_rate = pmc.get("ramp_rate", 0)

    # TSB status
    if -5 <= tsb <= 15:
        tsb_status = "optimal"
        tsb_label = "Fresh"
    elif tsb < -20:
        tsb_status = "fatigued"
        tsb_label = "Very Fatigued"
    elif tsb < -5:
        tsb_status = "tired"
        tsb_label = "Tired"
    elif tsb > 25:
        tsb_status = "detrained"
        tsb_label = "Detrained"
    else:
        tsb_status = "fresh"
        tsb_label = "Very Fresh"

    return {
        "ctl": round(ctl, 1),
        "atl": round(atl, 1),
        "tsb": round(tsb, 1),
        "ramp_rate": round(ramp_rate, 1),
        "trend": pmc.get("chronic_load_trend", "stable"),
        "tsb_status": tsb_status,
        "tsb_label": tsb_label,
        "tsb_optimal_range": [-5, 15],
    }


def generate_recent_training_section(state: Dict) -> Dict:
    """Generate recent training section."""
    recent = state.get("recent_training", {})
    rolling = recent.get("rolling_7d", {})
    week = recent.get("week_summary", {})

    # Zone distribution with targets
    dist = rolling.get("intensity_distribution", {})
    zone_targets = {"z1_z2": 84, "z3": 6, "z4_plus": 10}

    return {
        "total_tss": rolling.get("total_tss", 0),
        "avg_daily_tss": rolling.get("avg_daily_tss", 0),
        "total_hours": week.get("total_hours", 0),
        "workouts_completed": week.get("workouts_completed", 0),
        "last_workout": recent.get("last_workout"),
        "zone_distribution": {
            "z1_z2": {"actual": dist.get("z1_z2_pct", 0), "target": zone_targets["z1_z2"]},
            "z3": {"actual": dist.get("z3_pct", 0), "target": zone_targets["z3"]},
            "z4_plus": {"actual": dist.get("z4_plus_pct", 0), "target": zone_targets["z4_plus"]},
        },
    }


def generate_blindspots_section(state: Dict, profile: Dict) -> Dict:
    """Generate blindspots and adjustments section."""
    blindspot_adj = state.get("readiness", {}).get("blindspot_adjustments", {})

    # Get prompts for today
    daily_prompts = []
    if profile:
        adjustments = get_blindspot_adjustments(profile)
        prompts = get_blindspot_prompts(profile, context="daily")
        daily_prompts = prompts

    return {
        "active_blindspots": blindspot_adj.get("active_blindspots", []),
        "adjustments": {
            "key_threshold": blindspot_adj.get("adjusted_key_threshold", 65),
            "ramp_rate_max": blindspot_adj.get("adjusted_ramp_rate_max", 7.0),
            "tsb_floor": blindspot_adj.get("adjusted_tsb_floor", -30),
            "min_rest_days": blindspot_adj.get("min_rest_days", 1),
            "rhr_offset": blindspot_adj.get("rhr_offset", 0),
        },
        "daily_reminders": daily_prompts[:3],  # Top 3 reminders
    }


def generate_weekly_intent_section(weekly_intent: Optional[Dict]) -> Optional[Dict]:
    """Generate weekly intent section."""
    if not weekly_intent:
        return None

    return {
        "valid_from": weekly_intent.get("valid_from"),
        "key_sessions": {
            "target": weekly_intent.get("key_sessions_target", 2),
            "completed": weekly_intent.get("key_sessions_completed", 0),
            "remaining": weekly_intent.get("key_sessions_remaining", 2),
        },
        "volume": {
            "aerobic_hours_range": weekly_intent.get("aerobic_volume_hours", [8, 12]),
            "max_tss": weekly_intent.get("max_weekly_tss", 500),
        },
        "priority": weekly_intent.get("priority", "recover > respond > complete"),
        "notes": weekly_intent.get("notes", []),
    }


def generate_race_countdown_section(profile: Dict, state: Dict) -> Optional[Dict]:
    """Generate race countdown for next A-race."""
    events = profile.get("goals", {}).get("events", [])

    # Find next A-race
    a_races = [e for e in events if e.get("priority") == "A"]
    if not a_races:
        return None

    today = datetime.now().date()
    upcoming = []

    for race in a_races:
        date_str = race.get("date")
        if date_str:
            try:
                race_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if race_date > today:
                    days_to = (race_date - today).days
                    upcoming.append({
                        "name": race.get("name", "A Race"),
                        "date": date_str,
                        "days_to": days_to,
                        "weeks_to": days_to // 7,
                        "distance": race.get("distance"),
                    })
            except ValueError:
                continue

    if not upcoming:
        return None

    # Get closest A-race
    upcoming.sort(key=lambda x: x["days_to"])
    target_race = upcoming[0]

    # CTL trajectory
    pmc = state.get("performance_management", {})
    current_ctl = pmc.get("ctl", 0)
    target_ctl = 85  # Target peak CTL for ultra-endurance

    ctl_gap = target_ctl - current_ctl
    weeks_available = target_race["weeks_to"] - 2  # Account for taper

    if weeks_available > 0:
        required_weekly_gain = ctl_gap / weeks_available
    else:
        required_weekly_gain = 0

    return {
        "race": target_race,
        "ctl_trajectory": {
            "current": round(current_ctl, 1),
            "target": target_ctl,
            "gap": round(ctl_gap, 1),
            "pct_complete": round((current_ctl / target_ctl) * 100, 1) if target_ctl > 0 else 0,
            "required_weekly_gain": round(required_weekly_gain, 1),
        },
        "upcoming_races": upcoming[:3],  # Show next 3 A-races
    }


def generate_alerts_section(state: Dict) -> Dict:
    """Generate alerts section."""
    alerts = state.get("alerts", {})

    return {
        "active": alerts.get("active", []),
        "resolved_recently": alerts.get("resolved_recently", []),
    }


def generate_athlete_info_section(profile: Dict) -> Dict:
    """Generate basic athlete info."""
    # Name can be at top level or under athlete key
    name = profile.get("name") or profile.get("athlete", {}).get("name", "Athlete")
    return {
        "name": name,
        "ftp": profile.get("physiology", {}).get("ftp"),
        "weight_kg": profile.get("physiology", {}).get("weight_kg"),
        "phase": profile.get("status", {}).get("phase", "base"),
    }


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_dashboard_data(athlete_dir: Path) -> Dict[str, Any]:
    """Generate complete dashboard data."""
    # Load all data sources
    state = load_state(athlete_dir)
    profile = load_profile(athlete_dir)
    weekly_intent = load_weekly_intent(athlete_dir)

    # Get data date from state metadata (set by import_metrics_export.py)
    data_date = state.get("_meta", {}).get("data_date")
    last_updated = state.get("_meta", {}).get("last_updated")

    # Generate all sections
    dashboard = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "athlete_dir": str(athlete_dir),
            "data_date": data_date,  # Date of underlying WHOOP/metrics data
            "state_updated": last_updated,  # When state was last updated
        },
        "athlete": generate_athlete_info_section(profile),
        "readiness": generate_readiness_section(state),
        "health_gates": generate_health_gates_section(state),
        "session": generate_session_section(state, profile, weekly_intent),
        "pmc": generate_pmc_section(state),
        "recent_training": generate_recent_training_section(state),
        "blindspots": generate_blindspots_section(state, profile),
        "weekly_intent": generate_weekly_intent_section(weekly_intent),
        "race_countdown": generate_race_countdown_section(profile, state),
        "alerts": generate_alerts_section(state),
    }

    return dashboard


def main():
    parser = argparse.ArgumentParser(
        description="Generate dashboard data for athlete"
    )
    parser.add_argument(
        "athlete_name",
        help="Athlete folder name (e.g., matti-rowe)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: athletes/{name}/dashboard_data.json)"
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Output to stdout instead of file"
    )

    args = parser.parse_args()

    # Find athlete directory
    base_dir = Path(__file__).parent.parent
    athlete_dir = base_dir / "athletes" / args.athlete_name

    if not athlete_dir.exists():
        print(f"Error: Athlete directory not found: {athlete_dir}")
        sys.exit(1)

    # Generate dashboard data
    dashboard = generate_dashboard_data(athlete_dir)

    # Output
    if args.stdout:
        print(json.dumps(dashboard, indent=2))
    else:
        output_path = args.output or (athlete_dir / "dashboard_data.json")
        output_path = Path(output_path)

        with open(output_path, "w") as f:
            json.dump(dashboard, f, indent=2)

        print(f"Dashboard data written to: {output_path}")


if __name__ == "__main__":
    main()
