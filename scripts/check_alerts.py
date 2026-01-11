#!/usr/bin/env python3
"""
Alert Engine - Monitor athlete metrics and generate alerts

Monitors critical thresholds and updates alerts in athlete_state.json:
- TSB drift (< -20 warning, < -30 critical)
- Ramp rate (> 5 TSS/week warning, > 7 critical)
- Compliance (< 70% warning, < 50% critical)
- Zone distribution drift vs 84/6/10 targets
- Recovery score (< 33% for 2+ days)
- HRV trend (declining for 3+ days)

Usage:
    python scripts/check_alerts.py matti-rowe
    python scripts/check_alerts.py matti-rowe --verbose
    python scripts/check_alerts.py matti-rowe --dry-run
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# ALERT THRESHOLDS
# =============================================================================

THRESHOLDS = {
    "tsb": {
        "warning": -20,      # TSB below this triggers warning
        "critical": -30,     # TSB below this triggers critical
    },
    "ramp_rate": {
        "warning": 5.0,      # TSS/week above this triggers warning
        "critical": 7.0,     # TSS/week above this triggers critical
    },
    "compliance": {
        "warning": 70,       # Below 70% triggers warning
        "critical": 50,      # Below 50% triggers critical
    },
    "zone_drift": {
        "z1_z2_min": 75,     # Z1-Z2 should be at least 75% (target 84%)
        "z3_max": 15,        # Z3 (G-Spot) should be at most 15% (target 6%)
        "z4_plus_max": 20,   # Z4+ should be at most 20% (target 10%)
    },
    "recovery": {
        "low_threshold": 33,      # Recovery score below this is concerning
        "consecutive_days": 2,    # Alert after this many consecutive low days
    },
    "hrv": {
        "decline_pct": 15,        # HRV decline of 15%+ from baseline
        "trend_days": 3,          # Alert after declining for this many days
    },
}

# Alert severity levels
SEVERITY = {
    "info": 1,
    "warning": 2,
    "critical": 3,
}


# =============================================================================
# ALERT CHECKS
# =============================================================================

def check_tsb_alert(state: Dict, verbose: bool = False) -> Optional[Dict]:
    """Check TSB (Training Stress Balance) for concerning levels."""
    pmc = state.get("performance_management", {})
    tsb = pmc.get("tsb")

    if tsb is None:
        return None

    if verbose:
        print(f"  TSB: {tsb}")

    if tsb < THRESHOLDS["tsb"]["critical"]:
        return {
            "type": "tsb_critical",
            "severity": "critical",
            "message": f"TSB critically low at {tsb:.1f} (threshold: {THRESHOLDS['tsb']['critical']})",
            "value": tsb,
            "threshold": THRESHOLDS["tsb"]["critical"],
            "recommendation": "Immediate recovery needed - reduce training load significantly",
        }
    elif tsb < THRESHOLDS["tsb"]["warning"]:
        return {
            "type": "tsb_warning",
            "severity": "warning",
            "message": f"TSB low at {tsb:.1f} (threshold: {THRESHOLDS['tsb']['warning']})",
            "value": tsb,
            "threshold": THRESHOLDS["tsb"]["warning"],
            "recommendation": "Consider reducing intensity and adding recovery days",
        }

    return None


def check_ramp_rate_alert(state: Dict, verbose: bool = False) -> Optional[Dict]:
    """Check ramp rate for excessive load increase."""
    pmc = state.get("performance_management", {})
    ramp_rate = pmc.get("ramp_rate")

    if ramp_rate is None:
        return None

    if verbose:
        print(f"  Ramp rate: {ramp_rate} TSS/week")

    if ramp_rate > THRESHOLDS["ramp_rate"]["critical"]:
        return {
            "type": "ramp_rate_critical",
            "severity": "critical",
            "message": f"Ramp rate critically high at {ramp_rate:.1f} TSS/week (threshold: {THRESHOLDS['ramp_rate']['critical']})",
            "value": ramp_rate,
            "threshold": THRESHOLDS["ramp_rate"]["critical"],
            "recommendation": "High injury/illness risk - back off immediately",
        }
    elif ramp_rate > THRESHOLDS["ramp_rate"]["warning"]:
        return {
            "type": "ramp_rate_warning",
            "severity": "warning",
            "message": f"Ramp rate elevated at {ramp_rate:.1f} TSS/week (threshold: {THRESHOLDS['ramp_rate']['warning']})",
            "value": ramp_rate,
            "threshold": THRESHOLDS["ramp_rate"]["warning"],
            "recommendation": "Monitor closely - avoid adding more load this week",
        }

    return None


def check_compliance_alert(state: Dict, verbose: bool = False) -> Optional[Dict]:
    """Check training compliance rate."""
    compliance = state.get("compliance", {})
    compliance_7d = compliance.get("7_day")

    if compliance_7d is None:
        return None

    if verbose:
        print(f"  Compliance (7d): {compliance_7d}%")

    if compliance_7d < THRESHOLDS["compliance"]["critical"]:
        return {
            "type": "compliance_critical",
            "severity": "critical",
            "message": f"Compliance critically low at {compliance_7d}% (threshold: {THRESHOLDS['compliance']['critical']}%)",
            "value": compliance_7d,
            "threshold": THRESHOLDS["compliance"]["critical"],
            "recommendation": "Review schedule and barriers - consider plan adjustment",
        }
    elif compliance_7d < THRESHOLDS["compliance"]["warning"]:
        return {
            "type": "compliance_warning",
            "severity": "warning",
            "message": f"Compliance low at {compliance_7d}% (threshold: {THRESHOLDS['compliance']['warning']}%)",
            "value": compliance_7d,
            "threshold": THRESHOLDS["compliance"]["warning"],
            "recommendation": "Check for barriers - prioritize key sessions over volume",
        }

    return None


def check_zone_distribution_alert(state: Dict, verbose: bool = False) -> List[Dict]:
    """Check zone distribution against 84/6/10 targets."""
    alerts = []

    recent = state.get("recent_training", {})
    rolling = recent.get("rolling_7d", {})
    distribution = rolling.get("intensity_distribution", {})

    z1_z2 = distribution.get("z1_z2_pct", 0)
    z3 = distribution.get("z3_pct", 0)
    z4_plus = distribution.get("z4_plus_pct", 0)

    if verbose:
        print(f"  Zone distribution: Z1-Z2={z1_z2}%, Z3={z3}%, Z4+={z4_plus}%")

    # Only alert if there's actual training data
    if z1_z2 == 0 and z3 == 0 and z4_plus == 0:
        return alerts

    # Check Z1-Z2 (should be high - target 84%)
    if z1_z2 < THRESHOLDS["zone_drift"]["z1_z2_min"] and z1_z2 > 0:
        alerts.append({
            "type": "zone_drift_low_aerobic",
            "severity": "warning",
            "message": f"Aerobic volume (Z1-Z2) at {z1_z2}% - below {THRESHOLDS['zone_drift']['z1_z2_min']}% minimum",
            "value": z1_z2,
            "target": 84,
            "recommendation": "Add more easy aerobic riding - protect the base",
        })

    # Check Z3 (should be limited - target 6%)
    if z3 > THRESHOLDS["zone_drift"]["z3_max"]:
        alerts.append({
            "type": "zone_drift_high_tempo",
            "severity": "warning",
            "message": f"Tempo zone (Z3) at {z3}% - above {THRESHOLDS['zone_drift']['z3_max']}% maximum",
            "value": z3,
            "target": 6,
            "recommendation": "Too much gray zone - go easier on easy days, harder on hard days",
        })

    # Check Z4+ (should be limited - target 10%)
    if z4_plus > THRESHOLDS["zone_drift"]["z4_plus_max"]:
        alerts.append({
            "type": "zone_drift_high_intensity",
            "severity": "warning",
            "message": f"High intensity (Z4+) at {z4_plus}% - above {THRESHOLDS['zone_drift']['z4_plus_max']}% maximum",
            "value": z4_plus,
            "target": 10,
            "recommendation": "Too much intensity - reduce to protect recovery",
        })

    return alerts


def check_recovery_alert(state: Dict, verbose: bool = False) -> Optional[Dict]:
    """Check WHOOP recovery score for concerning patterns."""
    fatigue = state.get("fatigue_indicators", {})
    whoop = fatigue.get("whoop_recovery", {})
    current = whoop.get("current")

    if current is None:
        return None

    if verbose:
        print(f"  Recovery score: {current}%")

    if current < THRESHOLDS["recovery"]["low_threshold"]:
        return {
            "type": "recovery_low",
            "severity": "warning",
            "message": f"Recovery score low at {current}% (threshold: {THRESHOLDS['recovery']['low_threshold']}%)",
            "value": current,
            "threshold": THRESHOLDS["recovery"]["low_threshold"],
            "recommendation": "Prioritize sleep and reduce training intensity",
        }

    return None


def check_hrv_alert(state: Dict, verbose: bool = False) -> Optional[Dict]:
    """Check HRV for concerning decline."""
    fatigue = state.get("fatigue_indicators", {})
    hrv = fatigue.get("hrv", {})

    current = hrv.get("current")
    baseline = hrv.get("baseline")
    trend = hrv.get("trend")

    if current is None or baseline is None:
        return None

    if verbose:
        print(f"  HRV: {current} (baseline: {baseline}, trend: {trend})")

    pct_of_baseline = (current / baseline) * 100 if baseline > 0 else 100
    decline_pct = 100 - pct_of_baseline

    if decline_pct > THRESHOLDS["hrv"]["decline_pct"]:
        return {
            "type": "hrv_decline",
            "severity": "warning",
            "message": f"HRV declined {decline_pct:.1f}% from baseline ({current:.1f} vs {baseline:.1f})",
            "value": current,
            "baseline": baseline,
            "pct_of_baseline": pct_of_baseline,
            "recommendation": "Monitor recovery - consider reducing load if trend continues",
        }

    return None


# =============================================================================
# ALERT MANAGEMENT
# =============================================================================

def run_all_checks(state: Dict, verbose: bool = False) -> List[Dict]:
    """Run all alert checks and return list of new alerts."""
    if verbose:
        print("\n[Alert Engine - Running Checks]")

    alerts = []

    # Run each check
    tsb_alert = check_tsb_alert(state, verbose)
    if tsb_alert:
        alerts.append(tsb_alert)

    ramp_alert = check_ramp_rate_alert(state, verbose)
    if ramp_alert:
        alerts.append(ramp_alert)

    compliance_alert = check_compliance_alert(state, verbose)
    if compliance_alert:
        alerts.append(compliance_alert)

    zone_alerts = check_zone_distribution_alert(state, verbose)
    alerts.extend(zone_alerts)

    recovery_alert = check_recovery_alert(state, verbose)
    if recovery_alert:
        alerts.append(recovery_alert)

    hrv_alert = check_hrv_alert(state, verbose)
    if hrv_alert:
        alerts.append(hrv_alert)

    # Add timestamp to all alerts
    now = datetime.now(timezone.utc).isoformat()
    for alert in alerts:
        alert["detected_at"] = now

    return alerts


def update_alerts(
    state: Dict,
    new_alerts: List[Dict],
    verbose: bool = False
) -> Tuple[List[Dict], List[Dict]]:
    """
    Update alerts in state.

    Returns (active_alerts, newly_resolved)
    """
    existing = state.get("alerts", {})
    current_active = existing.get("active", [])
    resolved = existing.get("resolved_recently", [])

    # Get types of new alerts
    new_alert_types = {a["type"] for a in new_alerts}

    # Find resolved alerts (were active but no longer triggered)
    newly_resolved = []
    still_active = []

    for alert in current_active:
        alert_type = alert.get("type", "")
        # Check if base type matches (ignore _warning/_critical suffix for matching)
        base_type = alert_type.rsplit("_", 1)[0] if "_" in alert_type else alert_type

        matching_new = [a for a in new_alerts if a["type"].startswith(base_type)]

        if not matching_new:
            # Alert resolved
            resolved_alert = {
                **alert,
                "resolved": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
            newly_resolved.append(resolved_alert)
            if verbose:
                print(f"  Resolved: {alert['type']}")
        else:
            still_active.append(alert)

    # Add new alerts that weren't already active
    for new_alert in new_alerts:
        is_new = True
        for existing_alert in current_active:
            if existing_alert["type"] == new_alert["type"]:
                is_new = False
                break
        if is_new:
            still_active.append(new_alert)
            if verbose:
                print(f"  New alert: {new_alert['type']}")

    # Keep only recent resolved (last 10)
    all_resolved = newly_resolved + resolved
    all_resolved = all_resolved[:10]

    return still_active, all_resolved


def update_state_alerts(
    state: Dict,
    active: List[Dict],
    resolved: List[Dict]
) -> Dict:
    """Update the alerts section in state."""
    state["alerts"] = {
        "active": active,
        "resolved_recently": resolved,
    }

    # Update metadata
    state["_meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    state["_meta"]["updated_by"] = "check_alerts"

    return state


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Check athlete metrics and generate alerts"
    )
    parser.add_argument(
        "athlete_name",
        help="Athlete folder name (e.g., matti-rowe)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed check results"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check but don't update state file"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output alerts as JSON"
    )

    args = parser.parse_args()

    # Find athlete directory
    base_dir = Path(__file__).parent.parent
    athlete_dir = base_dir / "athletes" / args.athlete_name
    state_file = athlete_dir / "athlete_state.json"

    if not state_file.exists():
        print(f"Error: State file not found: {state_file}")
        sys.exit(1)

    try:
        # Load state
        with open(state_file) as f:
            state = json.load(f)

        # Run checks
        new_alerts = run_all_checks(state, args.verbose)

        # Update alerts
        active, resolved = update_alerts(state, new_alerts, args.verbose)

        if args.json:
            print(json.dumps({"active": active, "resolved": resolved}, indent=2))
        else:
            print(f"\n{'='*50}")
            print("ALERT CHECK RESULTS")
            print(f"{'='*50}")

            if active:
                print(f"\n⚠️  ACTIVE ALERTS ({len(active)}):")
                for alert in sorted(active, key=lambda a: SEVERITY.get(a.get("severity", "info"), 0), reverse=True):
                    severity = alert.get("severity", "info").upper()
                    print(f"\n  [{severity}] {alert['type']}")
                    print(f"    {alert['message']}")
                    print(f"    → {alert.get('recommendation', 'No recommendation')}")
            else:
                print("\n✅ No active alerts")

            if resolved and args.verbose:
                print(f"\n📋 Recently resolved ({len(resolved)}):")
                for alert in resolved[:5]:
                    print(f"  - {alert['type']} (resolved: {alert.get('resolved', 'unknown')})")

        # Save if not dry run
        if not args.dry_run:
            state = update_state_alerts(state, active, resolved)
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

            if not args.json:
                print(f"\n✓ Updated {state_file}")
        else:
            if not args.json:
                print("\n[DRY RUN] State not modified")

    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
