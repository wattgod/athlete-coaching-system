#!/usr/bin/env python3
"""
Race Countdown Dashboard - Track progress toward A-race

Displays:
- Days until A-race
- Current CTL and trajectory to target
- Key milestones (peak week, taper start, etc.)
- Risk factors assessment
- Readiness trend

Usage:
    python scripts/race_countdown.py matti-rowe
    python scripts/race_countdown.py matti-rowe --verbose
    python scripts/race_countdown.py matti-rowe --json
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# =============================================================================
# CONFIGURATION
# =============================================================================

# CTL targets by weeks out from race
CTL_TRAJECTORY = {
    # weeks_out: minimum_ctl_pct (percentage of target)
    16: 50,   # 16 weeks out: 50% of target CTL
    12: 65,   # 12 weeks out: 65% of target CTL
    8: 80,    # 8 weeks out: 80% of target CTL
    4: 95,    # 4 weeks out: 95% of target CTL (peak)
    2: 90,    # 2 weeks out: 90% (start of taper)
    1: 85,    # 1 week out: 85% (deep taper)
    0: 80,    # Race week: 80% (fresh but fit)
}

# Default target CTL for gravel events
DEFAULT_TARGET_CTL = {
    "100_mile": 70,
    "200_mile": 85,
    "ultra": 100,
}

# Milestone definitions (weeks before race)
MILESTONES = {
    "peak_volume": 6,      # Peak training volume week
    "peak_intensity": 4,   # Peak intensity week
    "taper_start": 2,      # Begin taper
    "race_week": 0,        # Race week
}

# Risk thresholds
RISK_THRESHOLDS = {
    "ctl_behind_pct": 15,      # CTL more than 15% behind trajectory
    "compliance_low": 70,      # Compliance below 70%
    "tsb_low": -20,            # TSB below -20
    "ramp_rate_high": 7,       # Ramp rate above 7
    "readiness_low": 50,       # Readiness below 50
}


# =============================================================================
# DATA LOADING
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


# =============================================================================
# RACE ANALYSIS
# =============================================================================

def get_race_info(profile: Dict) -> Optional[Dict[str, Any]]:
    """Extract A-race information from profile."""
    goals = profile.get("goals", {})
    primary = goals.get("primary_event", {})

    if not primary:
        return None

    race_date_str = primary.get("date")
    if not race_date_str:
        return None

    try:
        race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    today = datetime.now(timezone.utc).date()
    days_out = (race_date - today).days
    weeks_out = days_out / 7

    return {
        "name": primary.get("name", "A Race"),
        "date": race_date_str,
        "race_date": race_date,
        "days_out": days_out,
        "weeks_out": weeks_out,
        "distance_km": primary.get("distance_km"),
        "elevation_m": primary.get("elevation_m"),
        "target_time": primary.get("target_time"),
        "priority": primary.get("priority", "A"),
    }


def calculate_target_ctl(race_info: Dict) -> int:
    """Calculate target CTL for the race."""
    distance = race_info.get("distance_km", 0)

    if distance >= 300:
        return DEFAULT_TARGET_CTL["ultra"]
    elif distance >= 250:
        return DEFAULT_TARGET_CTL["200_mile"]
    else:
        return DEFAULT_TARGET_CTL["100_mile"]


def get_ctl_trajectory_target(weeks_out: float, target_ctl: int) -> int:
    """Get the expected CTL for current weeks out."""
    # Find the appropriate trajectory point
    sorted_weeks = sorted(CTL_TRAJECTORY.keys(), reverse=True)

    for week_marker in sorted_weeks:
        if weeks_out >= week_marker:
            pct = CTL_TRAJECTORY[week_marker]
            return int(target_ctl * pct / 100)

    # Race week or past
    return int(target_ctl * CTL_TRAJECTORY[0] / 100)


def calculate_milestones(race_info: Dict) -> List[Dict[str, Any]]:
    """Calculate key milestone dates."""
    race_date = race_info["race_date"]
    today = datetime.now(timezone.utc).date()
    milestones = []

    for name, weeks_before in sorted(MILESTONES.items(), key=lambda x: -x[1]):
        milestone_date = race_date - timedelta(weeks=weeks_before)
        days_until = (milestone_date - today).days

        status = "upcoming"
        if days_until < 0:
            status = "passed"
        elif days_until == 0:
            status = "today"
        elif days_until <= 7:
            status = "this_week"

        milestones.append({
            "name": name.replace("_", " ").title(),
            "date": milestone_date.strftime("%Y-%m-%d"),
            "weeks_before_race": weeks_before,
            "days_until": days_until,
            "status": status,
        })

    return milestones


def assess_risks(
    race_info: Dict,
    state: Dict,
    current_ctl: float,
    target_ctl: int,
    trajectory_ctl: int,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """Assess risk factors for race preparation."""
    risks = []

    # CTL trajectory risk
    if current_ctl < trajectory_ctl:
        behind_pct = ((trajectory_ctl - current_ctl) / trajectory_ctl) * 100 if trajectory_ctl > 0 else 0
        if behind_pct > RISK_THRESHOLDS["ctl_behind_pct"]:
            risks.append({
                "type": "ctl_behind",
                "severity": "high" if behind_pct > 25 else "medium",
                "message": f"CTL {behind_pct:.0f}% behind trajectory ({current_ctl:.0f} vs {trajectory_ctl} target)",
                "recommendation": "Increase training volume if recovery allows",
            })

    # TSB risk
    pmc = state.get("performance_management", {})
    tsb = pmc.get("tsb", 0)
    if tsb < RISK_THRESHOLDS["tsb_low"]:
        risks.append({
            "type": "fatigue_high",
            "severity": "high",
            "message": f"TSB critically low at {tsb:.1f}",
            "recommendation": "Add recovery days before continuing build",
        })

    # Ramp rate risk
    ramp = pmc.get("ramp_rate", 0)
    if ramp > RISK_THRESHOLDS["ramp_rate_high"]:
        risks.append({
            "type": "ramp_too_fast",
            "severity": "medium",
            "message": f"Ramp rate high at {ramp:.1f} TSS/week",
            "recommendation": "Slow the build to reduce injury/illness risk",
        })

    # Compliance risk
    compliance = state.get("compliance", {}).get("7_day", 100)
    if compliance < RISK_THRESHOLDS["compliance_low"]:
        risks.append({
            "type": "compliance_low",
            "severity": "medium",
            "message": f"Training compliance at {compliance}%",
            "recommendation": "Review schedule barriers - consistency is key",
        })

    # Readiness risk
    readiness = state.get("readiness", {}).get("score", 100)
    if readiness < RISK_THRESHOLDS["readiness_low"]:
        risks.append({
            "type": "readiness_low",
            "severity": "medium",
            "message": f"Readiness low at {readiness}",
            "recommendation": "Focus on recovery before adding training load",
        })

    # Time risk
    weeks_out = race_info["weeks_out"]
    if weeks_out < 8 and current_ctl < target_ctl * 0.7:
        risks.append({
            "type": "time_short",
            "severity": "high",
            "message": f"Only {weeks_out:.1f} weeks to race with CTL at {(current_ctl/target_ctl)*100:.0f}% of target",
            "recommendation": "Adjust race goals or consider aggressive but risky build",
        })

    return risks


def calculate_ctl_projection(
    current_ctl: float,
    target_ctl: int,
    weeks_out: float,
    current_ramp: float
) -> Dict[str, Any]:
    """Project CTL at race day based on current trajectory."""
    if weeks_out <= 0:
        return {
            "projected_ctl": current_ctl,
            "will_reach_target": current_ctl >= target_ctl * 0.8,
            "gap": target_ctl - current_ctl,
        }

    # Simple projection: current CTL + (ramp_rate * weeks)
    # Account for taper in last 2 weeks
    build_weeks = max(0, weeks_out - 2)
    projected_ctl = current_ctl + (current_ramp * build_weeks)

    # Taper typically drops CTL ~10-15%
    if weeks_out <= 2:
        projected_ctl = current_ctl * 0.9

    return {
        "projected_ctl": round(projected_ctl, 1),
        "will_reach_target": projected_ctl >= target_ctl * 0.8,
        "gap": round(target_ctl - projected_ctl, 1),
        "required_ramp": round((target_ctl - current_ctl) / build_weeks, 1) if build_weeks > 0 else 0,
    }


# =============================================================================
# DASHBOARD GENERATION
# =============================================================================

def generate_dashboard(profile: Dict, state: Dict, verbose: bool = False) -> Dict[str, Any]:
    """Generate the race countdown dashboard."""
    if verbose:
        print("\n[Race Countdown Dashboard]")

    # Get race info
    race_info = get_race_info(profile)
    if not race_info:
        raise ValueError("No A-race found in profile")

    if verbose:
        print(f"  Race: {race_info['name']} on {race_info['date']}")
        print(f"  Days out: {race_info['days_out']}")

    # Get current metrics
    pmc = state.get("performance_management", {})
    current_ctl = pmc.get("ctl", 0)
    current_atl = pmc.get("atl", 0)
    current_tsb = pmc.get("tsb", 0)
    current_ramp = pmc.get("ramp_rate", 0)

    # Calculate targets
    target_ctl = calculate_target_ctl(race_info)
    trajectory_ctl = get_ctl_trajectory_target(race_info["weeks_out"], target_ctl)

    if verbose:
        print(f"  Current CTL: {current_ctl}, Target: {target_ctl}, Trajectory: {trajectory_ctl}")

    # Calculate milestones
    milestones = calculate_milestones(race_info)

    # Assess risks
    risks = assess_risks(race_info, state, current_ctl, target_ctl, trajectory_ctl, verbose)

    # Project CTL
    projection = calculate_ctl_projection(current_ctl, target_ctl, race_info["weeks_out"], current_ramp)

    # Get readiness
    readiness = state.get("readiness", {})

    # Build dashboard
    dashboard = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "race_countdown",
        },
        "race": {
            "name": race_info["name"],
            "date": race_info["date"],
            "days_out": race_info["days_out"],
            "weeks_out": round(race_info["weeks_out"], 1),
            "distance_km": race_info["distance_km"],
            "elevation_m": race_info["elevation_m"],
            "target_time": race_info["target_time"],
        },
        "fitness": {
            "current_ctl": current_ctl,
            "target_ctl": target_ctl,
            "trajectory_ctl": trajectory_ctl,
            "ctl_pct_of_target": round((current_ctl / target_ctl) * 100, 1) if target_ctl > 0 else 0,
            "on_track": current_ctl >= trajectory_ctl,
            "atl": current_atl,
            "tsb": current_tsb,
            "ramp_rate": current_ramp,
        },
        "projection": projection,
        "milestones": milestones,
        "risks": risks,
        "readiness": {
            "score": readiness.get("score", 0),
            "color": readiness.get("recommendation", "unknown"),
            "key_session_eligible": readiness.get("key_session_eligible", False),
        },
    }

    return dashboard


def format_dashboard_text(dashboard: Dict) -> str:
    """Format dashboard as readable text."""
    lines = []

    race = dashboard["race"]
    fitness = dashboard["fitness"]
    proj = dashboard["projection"]

    # Header
    lines.append("=" * 60)
    lines.append(f"🏁 RACE COUNTDOWN: {race['name']}")
    lines.append("=" * 60)

    # Countdown
    lines.append(f"\n📅 {race['date']} | {race['days_out']} DAYS | {race['weeks_out']} WEEKS")
    if race.get("distance_km"):
        lines.append(f"   {race['distance_km']}km | {race.get('elevation_m', '?')}m elevation")
    if race.get("target_time"):
        lines.append(f"   Target: {race['target_time']}")

    # Fitness status
    lines.append(f"\n💪 FITNESS STATUS")
    lines.append("-" * 40)

    ctl_bar = "█" * int(fitness["ctl_pct_of_target"] / 5) + "░" * (20 - int(fitness["ctl_pct_of_target"] / 5))
    track_status = "✅ ON TRACK" if fitness["on_track"] else "⚠️  BEHIND"

    lines.append(f"  CTL: {fitness['current_ctl']:.1f} / {fitness['target_ctl']} ({fitness['ctl_pct_of_target']:.0f}%)")
    lines.append(f"  [{ctl_bar}] {track_status}")
    lines.append(f"  Trajectory target: {fitness['trajectory_ctl']} CTL")
    lines.append(f"  ATL: {fitness['atl']:.1f} | TSB: {fitness['tsb']:.1f} | Ramp: {fitness['ramp_rate']:.1f}/wk")

    # Projection
    lines.append(f"\n📈 PROJECTION")
    lines.append("-" * 40)
    if proj["will_reach_target"]:
        lines.append(f"  Projected race-day CTL: {proj['projected_ctl']:.0f} ✅")
    else:
        lines.append(f"  Projected race-day CTL: {proj['projected_ctl']:.0f} ⚠️")
        lines.append(f"  Gap to target: {proj['gap']:.0f} CTL")
        if proj.get("required_ramp", 0) > 0:
            lines.append(f"  Required ramp: {proj['required_ramp']:.1f} TSS/week")

    # Milestones
    lines.append(f"\n🎯 MILESTONES")
    lines.append("-" * 40)
    for m in dashboard["milestones"]:
        if m["status"] == "passed":
            icon = "✓"
        elif m["status"] == "today":
            icon = "→"
        elif m["status"] == "this_week":
            icon = "●"
        else:
            icon = "○"

        if m["days_until"] >= 0:
            lines.append(f"  {icon} {m['name']}: {m['date']} ({m['days_until']} days)")
        else:
            lines.append(f"  {icon} {m['name']}: {m['date']} (passed)")

    # Risks
    if dashboard["risks"]:
        lines.append(f"\n⚠️  RISK FACTORS ({len(dashboard['risks'])})")
        lines.append("-" * 40)
        for risk in dashboard["risks"]:
            severity_icon = "🔴" if risk["severity"] == "high" else "🟡"
            lines.append(f"  {severity_icon} {risk['message']}")
            lines.append(f"     → {risk['recommendation']}")
    else:
        lines.append(f"\n✅ NO MAJOR RISKS IDENTIFIED")

    # Readiness
    r = dashboard["readiness"]
    lines.append(f"\n📊 TODAY'S READINESS: {r['score']} ({r['color'].upper()})")
    if r["key_session_eligible"]:
        lines.append("   Key session eligible ✓")

    lines.append("")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Race countdown dashboard"
    )
    parser.add_argument(
        "athlete_name",
        help="Athlete folder name (e.g., matti-rowe)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show analysis details"
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
        # Load data
        profile = load_profile(athlete_dir)
        state = load_state(athlete_dir)

        # Generate dashboard
        dashboard = generate_dashboard(profile, state, args.verbose)

        # Output
        if args.json:
            print(json.dumps(dashboard, indent=2))
        else:
            print(format_dashboard_text(dashboard))

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating dashboard: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
