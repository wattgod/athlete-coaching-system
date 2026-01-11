#!/usr/bin/env python3
"""
Weekly Review Generator - Summarize the past week and suggest adjustments

Generates a weekly review that includes:
- Training summary (TSS, hours, workouts)
- Compliance analysis
- Zone distribution vs 84/6/10 targets
- Wins and flags identification
- Suggestions for the coming week

Usage:
    python scripts/weekly_review.py matti-rowe
    python scripts/weekly_review.py matti-rowe --verbose
    python scripts/weekly_review.py matti-rowe --json
    python scripts/weekly_review.py matti-rowe --save
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

# Zone distribution targets (Nate Wilson methodology)
ZONE_TARGETS = {
    "z1_z2": 84,   # Aerobic base
    "z3": 6,       # G-Spot / Tempo
    "z4_plus": 10, # Threshold and above
}

# Acceptable drift from targets
ZONE_TOLERANCE = {
    "z1_z2": 10,   # 74-94% acceptable
    "z3": 5,       # 1-11% acceptable
    "z4_plus": 5,  # 5-15% acceptable
}

# Compliance thresholds
COMPLIANCE_THRESHOLDS = {
    "excellent": 90,
    "good": 80,
    "fair": 70,
    "poor": 50,
}

# TSB ranges for assessment
TSB_RANGES = {
    "fresh": (5, 25),
    "optimal": (-10, 5),
    "tired": (-20, -10),
    "exhausted": (-50, -20),
}


# =============================================================================
# DATA LOADING
# =============================================================================

def load_state(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete state from JSON."""
    state_file = athlete_dir / "athlete_state.json"
    if not state_file.exists():
        raise FileNotFoundError(f"State not found: {state_file}")

    with open(state_file) as f:
        return json.load(f)


def load_weekly_intent(athlete_dir: Path) -> Optional[Dict[str, Any]]:
    """Load weekly intent if available."""
    intent_file = athlete_dir / "weekly_intent.json"
    if intent_file.exists():
        with open(intent_file) as f:
            return json.load(f)
    return None


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_training_load(state: Dict) -> Dict[str, Any]:
    """Analyze training load from the past week."""
    recent = state.get("recent_training", {})
    week = recent.get("week_summary", {})
    rolling = recent.get("rolling_7d", {})
    pmc = state.get("performance_management", {})

    return {
        "total_tss": week.get("total_tss", 0) or rolling.get("total_tss", 0),
        "total_hours": week.get("total_hours", 0),
        "workouts_completed": week.get("workouts_completed", 0),
        "workouts_planned": week.get("workouts_planned", 0),
        "avg_daily_tss": rolling.get("avg_daily_tss", 0),
        "ctl": pmc.get("ctl", 0),
        "atl": pmc.get("atl", 0),
        "tsb": pmc.get("tsb", 0),
        "ramp_rate": pmc.get("ramp_rate", 0),
        "ctl_trend": pmc.get("chronic_load_trend", "unknown"),
    }


def analyze_compliance(state: Dict) -> Dict[str, Any]:
    """Analyze training compliance."""
    compliance = state.get("compliance", {})

    pct_7d = compliance.get("7_day", 0)
    pct_14d = compliance.get("14_day", 0)
    pct_30d = compliance.get("30_day", 0)
    streak = compliance.get("streak_days", 0)
    missed = compliance.get("missed_workouts_7d", [])

    # Determine rating
    if pct_7d >= COMPLIANCE_THRESHOLDS["excellent"]:
        rating = "excellent"
    elif pct_7d >= COMPLIANCE_THRESHOLDS["good"]:
        rating = "good"
    elif pct_7d >= COMPLIANCE_THRESHOLDS["fair"]:
        rating = "fair"
    else:
        rating = "poor"

    # Trend analysis
    if pct_7d > pct_30d + 5:
        trend = "improving"
    elif pct_7d < pct_30d - 5:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "pct_7d": pct_7d,
        "pct_14d": pct_14d,
        "pct_30d": pct_30d,
        "streak_days": streak,
        "missed_workouts": missed,
        "rating": rating,
        "trend": trend,
    }


def analyze_zone_distribution(state: Dict) -> Dict[str, Any]:
    """Analyze zone distribution vs targets."""
    recent = state.get("recent_training", {})
    rolling = recent.get("rolling_7d", {})
    distribution = rolling.get("intensity_distribution", {})

    z1_z2 = distribution.get("z1_z2_pct", 0)
    z3 = distribution.get("z3_pct", 0)
    z4_plus = distribution.get("z4_plus_pct", 0)

    # Calculate drift from targets
    z1_z2_drift = z1_z2 - ZONE_TARGETS["z1_z2"]
    z3_drift = z3 - ZONE_TARGETS["z3"]
    z4_plus_drift = z4_plus - ZONE_TARGETS["z4_plus"]

    # Check if within tolerance
    z1_z2_ok = abs(z1_z2_drift) <= ZONE_TOLERANCE["z1_z2"]
    z3_ok = abs(z3_drift) <= ZONE_TOLERANCE["z3"]
    z4_plus_ok = abs(z4_plus_drift) <= ZONE_TOLERANCE["z4_plus"]

    # Identify issues
    issues = []
    if z1_z2 > 0:  # Only if we have data
        if not z1_z2_ok:
            if z1_z2_drift < 0:
                issues.append("Low aerobic volume - add more Z1-Z2 riding")
            else:
                issues.append("High aerobic volume - room for more intensity")

        if not z3_ok and z3_drift > 0:
            issues.append("Too much tempo/gray zone - polarize more")

        if not z4_plus_ok and z4_plus_drift > 0:
            issues.append("Too much high intensity - protect recovery")

    return {
        "z1_z2": {"actual": z1_z2, "target": ZONE_TARGETS["z1_z2"], "drift": z1_z2_drift, "ok": z1_z2_ok},
        "z3": {"actual": z3, "target": ZONE_TARGETS["z3"], "drift": z3_drift, "ok": z3_ok},
        "z4_plus": {"actual": z4_plus, "target": ZONE_TARGETS["z4_plus"], "drift": z4_plus_drift, "ok": z4_plus_ok},
        "has_data": z1_z2 > 0 or z3 > 0 or z4_plus > 0,
        "all_ok": z1_z2_ok and z3_ok and z4_plus_ok,
        "issues": issues,
    }


def analyze_recovery(state: Dict) -> Dict[str, Any]:
    """Analyze recovery metrics."""
    fatigue = state.get("fatigue_indicators", {})
    readiness = state.get("readiness", {})

    hrv = fatigue.get("hrv", {})
    rhr = fatigue.get("resting_hr", {})
    sleep = fatigue.get("sleep", {})
    whoop = fatigue.get("whoop_recovery", {})

    return {
        "readiness_score": readiness.get("score", 0),
        "readiness_color": readiness.get("recommendation", "unknown"),
        "hrv": {
            "current": hrv.get("current"),
            "baseline": hrv.get("baseline"),
            "trend": hrv.get("trend", "unknown"),
            "pct_baseline": (hrv.get("current", 0) / hrv.get("baseline", 1) * 100) if hrv.get("baseline") else None,
        },
        "rhr": {
            "current": rhr.get("current"),
            "baseline": rhr.get("baseline"),
            "trend": rhr.get("trend", "unknown"),
        },
        "sleep": {
            "last_night": sleep.get("last_night_hours"),
            "avg_7d": sleep.get("7d_avg_hours"),
            "quality": sleep.get("quality", "unknown"),
        },
        "recovery_score": whoop.get("current"),
        "recovery_trend": whoop.get("trend", "unknown"),
    }


def identify_wins(load: Dict, compliance: Dict, zones: Dict, recovery: Dict) -> List[str]:
    """Identify positive highlights from the week."""
    wins = []

    # Compliance wins
    if compliance["rating"] == "excellent":
        wins.append(f"Excellent compliance at {compliance['pct_7d']}%")
    elif compliance["streak_days"] >= 5:
        wins.append(f"Strong consistency - {compliance['streak_days']} day streak")

    # Load wins
    if load["ctl_trend"] == "building" and load["ramp_rate"] <= 5:
        wins.append("CTL building at sustainable ramp rate")
    if load["tsb"] > -10 and load["tsb"] < 10:
        wins.append("TSB in optimal training range")

    # Zone wins
    if zones["has_data"] and zones["all_ok"]:
        wins.append("Zone distribution on target (84/6/10)")

    # Recovery wins
    if recovery["hrv"]["trend"] == "recovering":
        wins.append("HRV trending upward - good recovery")
    if recovery["readiness_score"] >= 80:
        wins.append(f"High readiness score ({recovery['readiness_score']})")
    if recovery["sleep"]["avg_7d"] and recovery["sleep"]["avg_7d"] >= 8:
        wins.append(f"Strong sleep averaging {recovery['sleep']['avg_7d']:.1f} hours")

    return wins


def identify_flags(load: Dict, compliance: Dict, zones: Dict, recovery: Dict, state: Dict) -> List[str]:
    """Identify concerns or areas needing attention."""
    flags = []

    # Compliance flags
    if compliance["rating"] == "poor":
        flags.append(f"Low compliance at {compliance['pct_7d']}% - review barriers")
    if compliance["missed_workouts"]:
        missed_str = ", ".join(compliance["missed_workouts"][:3])
        flags.append(f"Missed: {missed_str}")

    # Load flags
    if load["ramp_rate"] > 5:
        flags.append(f"Ramp rate elevated at {load['ramp_rate']:.1f} TSS/week")
    if load["tsb"] < -20:
        flags.append(f"TSB critically low at {load['tsb']:.1f}")
    elif load["tsb"] < -10:
        flags.append(f"TSB low at {load['tsb']:.1f} - fatigue accumulating")

    # Zone flags
    flags.extend(zones["issues"])

    # Recovery flags
    if recovery["hrv"]["trend"] == "declining":
        flags.append("HRV declining - monitor recovery")
    if recovery["readiness_score"] < 50:
        flags.append(f"Low readiness score ({recovery['readiness_score']})")
    if recovery["sleep"]["avg_7d"] and recovery["sleep"]["avg_7d"] < 7:
        flags.append(f"Sleep deficit - averaging only {recovery['sleep']['avg_7d']:.1f} hours")

    # Check active alerts
    alerts = state.get("alerts", {}).get("active", [])
    for alert in alerts:
        if alert.get("severity") == "critical":
            flags.append(f"CRITICAL: {alert.get('message', 'Unknown alert')}")

    return flags


def generate_suggestions(load: Dict, compliance: Dict, zones: Dict, recovery: Dict, intent: Optional[Dict]) -> List[str]:
    """Generate suggestions for the coming week."""
    suggestions = []

    # Based on TSB
    if load["tsb"] < -15:
        suggestions.append("Consider a recovery-focused week - reduce volume 20-30%")
    elif load["tsb"] > 10:
        suggestions.append("Fresh legs available - good week for a key session block")

    # Based on compliance
    if compliance["rating"] == "poor":
        suggestions.append("Simplify the schedule - fewer sessions, higher priority on key workouts")
    if compliance["trend"] == "declining":
        suggestions.append("Check for life stress or schedule conflicts affecting training")

    # Based on zones
    if zones["issues"]:
        if any("gray zone" in i.lower() for i in zones["issues"]):
            suggestions.append("On easy days, keep power in Z2 or below - no tempo creep")
        if any("high intensity" in i.lower() for i in zones["issues"]):
            suggestions.append("Limit high intensity to 2 key sessions max this week")

    # Based on recovery
    if recovery["hrv"]["trend"] == "declining":
        suggestions.append("Add an extra rest day or reduce tomorrow's intensity")
    if recovery["sleep"]["avg_7d"] and recovery["sleep"]["avg_7d"] < 7.5:
        suggestions.append("Prioritize sleep - aim for 8+ hours for better adaptation")

    # Based on intent
    if intent:
        key_remaining = intent.get("key_sessions_remaining", 0)
        if key_remaining > 0:
            suggestions.append(f"Target {key_remaining} key session(s) when readiness permits")

    # Default suggestion
    if not suggestions:
        suggestions.append("Maintain current approach - training and recovery well balanced")

    return suggestions


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_review(state: Dict, intent: Optional[Dict], verbose: bool = False) -> Dict[str, Any]:
    """Generate the complete weekly review."""
    if verbose:
        print("\n[Weekly Review Generator]")
        print("  Analyzing training data...")

    # Run all analyses
    load = analyze_training_load(state)
    compliance = analyze_compliance(state)
    zones = analyze_zone_distribution(state)
    recovery = analyze_recovery(state)

    if verbose:
        print(f"  Load: {load['total_tss']} TSS, {load['total_hours']:.1f} hours")
        print(f"  Compliance: {compliance['pct_7d']}% ({compliance['rating']})")
        print(f"  TSB: {load['tsb']:.1f}")

    # Identify wins and flags
    wins = identify_wins(load, compliance, zones, recovery)
    flags = identify_flags(load, compliance, zones, recovery, state)

    if verbose:
        print(f"  Wins: {len(wins)}, Flags: {len(flags)}")

    # Generate suggestions
    suggestions = generate_suggestions(load, compliance, zones, recovery, intent)

    # Build review
    review = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "weekly_review",
            "week_ending": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "summary": {
            "total_tss": load["total_tss"],
            "total_hours": load["total_hours"],
            "workouts_completed": load["workouts_completed"],
            "workouts_planned": load["workouts_planned"],
            "compliance_pct": compliance["pct_7d"],
            "compliance_rating": compliance["rating"],
        },
        "load_status": {
            "ctl": load["ctl"],
            "atl": load["atl"],
            "tsb": load["tsb"],
            "ramp_rate": load["ramp_rate"],
            "trend": load["ctl_trend"],
        },
        "zone_distribution": {
            "z1_z2_pct": zones["z1_z2"]["actual"],
            "z3_pct": zones["z3"]["actual"],
            "z4_plus_pct": zones["z4_plus"]["actual"],
            "on_target": zones["all_ok"],
            "issues": zones["issues"],
        },
        "recovery_status": {
            "readiness_score": recovery["readiness_score"],
            "hrv_trend": recovery["hrv"]["trend"],
            "sleep_avg": recovery["sleep"]["avg_7d"],
        },
        "wins": wins,
        "flags": flags,
        "suggestions": suggestions,
    }

    return review


def format_review_text(review: Dict) -> str:
    """Format review as readable text."""
    lines = []

    lines.append("=" * 60)
    lines.append(f"WEEKLY REVIEW - Week Ending {review['_meta']['week_ending']}")
    lines.append("=" * 60)

    # Summary
    s = review["summary"]
    lines.append(f"\nTRAINING SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  TSS:        {s['total_tss']}")
    lines.append(f"  Hours:      {s['total_hours']:.1f}")
    lines.append(f"  Workouts:   {s['workouts_completed']}/{s['workouts_planned']}")
    lines.append(f"  Compliance: {s['compliance_pct']}% ({s['compliance_rating'].upper()})")

    # Load status
    l = review["load_status"]
    lines.append(f"\nLOAD STATUS")
    lines.append("-" * 40)
    lines.append(f"  CTL: {l['ctl']:.1f}  ATL: {l['atl']:.1f}  TSB: {l['tsb']:.1f}")
    lines.append(f"  Ramp rate: {l['ramp_rate']:.1f} TSS/week")
    lines.append(f"  Trend: {l['trend']}")

    # Zone distribution
    z = review["zone_distribution"]
    lines.append(f"\nZONE DISTRIBUTION (Target: 84/6/10)")
    lines.append("-" * 40)
    if z["z1_z2_pct"] > 0 or z["z3_pct"] > 0 or z["z4_plus_pct"] > 0:
        lines.append(f"  Z1-Z2: {z['z1_z2_pct']}%  Z3: {z['z3_pct']}%  Z4+: {z['z4_plus_pct']}%")
        status = "ON TARGET" if z["on_target"] else "DRIFT DETECTED"
        lines.append(f"  Status: {status}")
    else:
        lines.append("  No zone data available")

    # Wins
    if review["wins"]:
        lines.append(f"\n✅ WINS")
        lines.append("-" * 40)
        for win in review["wins"]:
            lines.append(f"  • {win}")

    # Flags
    if review["flags"]:
        lines.append(f"\n⚠️  FLAGS")
        lines.append("-" * 40)
        for flag in review["flags"]:
            lines.append(f"  • {flag}")

    # Suggestions
    lines.append(f"\n📋 NEXT WEEK SUGGESTIONS")
    lines.append("-" * 40)
    for suggestion in review["suggestions"]:
        lines.append(f"  → {suggestion}")

    lines.append("")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly training review"
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
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save review to weekly_review.json"
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
        state = load_state(athlete_dir)
        intent = load_weekly_intent(athlete_dir)

        # Generate review
        review = generate_review(state, intent, args.verbose)

        # Output
        if args.json:
            print(json.dumps(review, indent=2))
        else:
            print(format_review_text(review))

        # Save if requested
        if args.save:
            output_file = athlete_dir / "weekly_review.json"
            with open(output_file, "w") as f:
                json.dump(review, f, indent=2)
            print(f"✓ Saved to {output_file}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating review: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
