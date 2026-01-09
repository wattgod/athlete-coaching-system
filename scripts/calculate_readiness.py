#!/usr/bin/env python3
"""
Readiness Calculator - Compute readiness score from athlete state

Implements the Readiness Engine from knowledge/frameworks/READINESS_ENGINE.md
and Health Gates from knowledge/frameworks/HEALTH_RECOVERY_ENGINE.md

Usage:
    python scripts/calculate_readiness.py matti-rowe
    python scripts/calculate_readiness.py matti-rowe --dry-run
    python scripts/calculate_readiness.py matti-rowe --verbose
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.profile_manager import read_state, get_athlete_path

# =============================================================================
# CONFIGURATION - Adjust these for individual athletes
# =============================================================================

DEFAULT_CONFIG = {
    # Factor weights (must sum to 1.0)
    "weights": {
        "hrv": 0.25,
        "sleep": 0.20,
        "recovery": 0.20,
        "tsb": 0.20,
        "rhr": 0.15,
    },
    # Thresholds
    "thresholds": {
        "key_session": 65,      # Minimum score for key sessions
        "support_session": 40,  # Minimum score for support sessions
    },
    # Health gate thresholds
    "health_gates": {
        "sleep_min_hours": 7.0,
        "sleep_debt_max_hours": 5.0,  # Max cumulative debt over 7 days
        "hrv_min_pct_baseline": 80.0,  # HRV must be >= 80% of baseline
        "rhr_max_pct_baseline": 110.0,  # RHR must be <= 110% of baseline
        "soreness_max": 7,  # Max soreness level (1-10)
        "stress_max": 7,    # Max life stress level (1-10)
    },
    # TSB optimal range for scoring
    "tsb_optimal": {
        "min": -5,
        "max": 15,
        "worst_low": -30,  # TSB below this = 0 contribution
        "worst_high": 30,  # TSB above this = reduced contribution (overtapered)
    },
}


# =============================================================================
# FACTOR CALCULATIONS
# =============================================================================

def calculate_hrv_contribution(
    current: Optional[float],
    baseline: Optional[float],
    weight: float
) -> Tuple[float, str, Dict]:
    """
    Calculate HRV factor contribution.

    Score based on % of baseline:
    - 100%+ of baseline = full contribution
    - 80-100% = proportional
    - <80% = reduced with penalty
    """
    if current is None or baseline is None or baseline == 0:
        return 0.0, "unknown", {"value": current, "baseline": baseline}

    pct_baseline = (current / baseline) * 100

    if pct_baseline >= 100:
        score = 100
        impact = "positive"
    elif pct_baseline >= 90:
        score = 80 + (pct_baseline - 90) * 2  # 80-100
        impact = "neutral"
    elif pct_baseline >= 80:
        score = 60 + (pct_baseline - 80) * 2  # 60-80
        impact = "slight_negative"
    elif pct_baseline >= 70:
        score = 40 + (pct_baseline - 70) * 2  # 40-60
        impact = "moderate_negative"
    else:
        score = max(0, pct_baseline * 0.57)  # 0-40
        impact = "severe_negative"

    contribution = (score / 100) * weight * 100

    return contribution, impact, {
        "value": current,
        "baseline": baseline,
        "pct_of_baseline": round(pct_baseline, 1),
        "impact": impact,
        "weight": weight,
        "contribution": round(contribution, 1),
    }


def calculate_sleep_contribution(
    last_night: Optional[float],
    avg_7d: Optional[float],
    target: float,
    weight: float
) -> Tuple[float, str, Dict]:
    """
    Calculate sleep factor contribution.

    Score based on:
    - Last night vs target (primary)
    - 7-day average vs target (secondary)
    - Sleep debt accumulation
    """
    if last_night is None:
        return 0.0, "unknown", {"value": None, "target": target}

    # Primary: last night
    pct_target = (last_night / target) * 100

    # Calculate debt (negative if under target)
    debt_hours = 0
    if avg_7d is not None:
        debt_hours = max(0, (target - avg_7d) * 7)  # Cumulative weekly debt

    if pct_target >= 100:
        score = 100
        impact = "positive"
        debt_status = "ok"
    elif pct_target >= 87.5:  # 7/8 hours
        score = 80 + (pct_target - 87.5) * 1.6
        impact = "neutral"
        debt_status = "ok"
    elif pct_target >= 75:  # 6/8 hours
        score = 50 + (pct_target - 75) * 2.4
        impact = "slight_negative"
        debt_status = "mild_debt"
    else:
        score = max(0, pct_target * 0.67)
        impact = "moderate_negative"
        debt_status = "significant_debt"

    # Penalty for accumulated debt
    if debt_hours > 5:
        score = score * 0.9
        debt_status = "significant_debt"

    contribution = (score / 100) * weight * 100

    return contribution, impact, {
        "value": last_night,
        "target": target,
        "debt_hours_7d": round(debt_hours, 1),
        "impact": impact,
        "weight": weight,
        "contribution": round(contribution, 1),
    }


def calculate_recovery_contribution(
    current: Optional[float],
    baseline: float,
    weight: float
) -> Tuple[float, str, Dict]:
    """
    Calculate WHOOP recovery score contribution.

    WHOOP recovery is already 0-100, so we use it directly
    with some normalization to our baseline expectation.
    """
    if current is None:
        return 0.0, "unknown", {"value": None, "baseline": baseline}

    # WHOOP recovery is 0-100
    # We expect good athletes to have baseline around 60-70
    if current >= baseline:
        score = min(100, 70 + (current - baseline))
        impact = "positive"
    elif current >= baseline * 0.8:
        score = 50 + (current - baseline * 0.8) / (baseline * 0.2) * 20
        impact = "neutral"
    elif current >= baseline * 0.6:
        score = 30 + (current - baseline * 0.6) / (baseline * 0.2) * 20
        impact = "slight_negative"
    elif current >= baseline * 0.4:
        score = 10 + (current - baseline * 0.4) / (baseline * 0.2) * 20
        impact = "moderate_negative"
    else:
        score = max(0, current / baseline * 10)
        impact = "severe_negative"

    contribution = (score / 100) * weight * 100

    return contribution, impact, {
        "value": current,
        "baseline": baseline,
        "impact": impact,
        "weight": weight,
        "contribution": round(contribution, 1),
    }


def calculate_tsb_contribution(
    tsb: Optional[float],
    optimal_range: Dict,
    weight: float
) -> Tuple[float, str, Dict]:
    """
    Calculate TSB factor contribution.

    Optimal TSB is slightly negative to slightly positive (-5 to +15).
    Too negative = fatigued, too positive = detrained.
    """
    if tsb is None:
        return 0.0, "unknown", {"value": None, "optimal_range": [optimal_range["min"], optimal_range["max"]]}

    opt_min = optimal_range["min"]
    opt_max = optimal_range["max"]
    worst_low = optimal_range["worst_low"]
    worst_high = optimal_range["worst_high"]

    if opt_min <= tsb <= opt_max:
        # In optimal range
        score = 100
        impact = "positive"
    elif tsb < opt_min:
        # Fatigued
        if tsb >= worst_low:
            score = 100 * (tsb - worst_low) / (opt_min - worst_low)
            impact = "slight_negative" if tsb >= (opt_min + worst_low) / 2 else "moderate_negative"
        else:
            score = 0
            impact = "severe_negative"
    else:
        # Overtapered (less penalty than fatigue)
        if tsb <= worst_high:
            score = 100 - 30 * (tsb - opt_max) / (worst_high - opt_max)
            impact = "slight_negative"
        else:
            score = 70
            impact = "neutral"  # Being fresh is never terrible

    contribution = (score / 100) * weight * 100

    return contribution, impact, {
        "value": tsb,
        "optimal_range": [opt_min, opt_max],
        "impact": impact,
        "weight": weight,
        "contribution": round(contribution, 1),
    }


def calculate_rhr_contribution(
    current: Optional[float],
    baseline: Optional[float],
    weight: float
) -> Tuple[float, str, Dict]:
    """
    Calculate RHR factor contribution.

    Lower RHR relative to baseline = better recovery.
    Elevated RHR = stress/fatigue signal.
    """
    if current is None or baseline is None or baseline == 0:
        return 0.0, "unknown", {"value": current, "baseline": baseline}

    pct_elevation = ((current - baseline) / baseline) * 100

    if pct_elevation <= 0:
        # At or below baseline - excellent
        score = 100
        impact = "positive"
    elif pct_elevation <= 5:
        score = 90 - pct_elevation * 2  # 80-90
        impact = "neutral"
    elif pct_elevation <= 10:
        score = 80 - (pct_elevation - 5) * 4  # 60-80
        impact = "slight_negative"
    elif pct_elevation <= 15:
        score = 60 - (pct_elevation - 10) * 4  # 40-60
        impact = "moderate_negative"
    else:
        score = max(0, 40 - (pct_elevation - 15) * 2)
        impact = "severe_negative"

    contribution = (score / 100) * weight * 100

    return contribution, impact, {
        "value": current,
        "baseline": baseline,
        "pct_elevation": round(pct_elevation, 1),
        "impact": impact,
        "weight": weight,
        "contribution": round(contribution, 1),
    }


# =============================================================================
# HEALTH GATES
# =============================================================================

def check_health_gates(state: Dict, config: Dict) -> Dict:
    """
    Check all health gates and return gate status.

    Gates are binary pass/fail checks that can block intensity
    regardless of readiness score.
    """
    thresholds = config["health_gates"]
    gates = {}
    marginal_gates = []

    # Sleep gate
    sleep_data = state.get("fatigue_indicators", {}).get("sleep", {})
    last_night = sleep_data.get("last_night_hours")
    avg_7d = sleep_data.get("7d_avg_hours")

    sleep_pass = True
    sleep_debt_status = "ok"
    if last_night is not None:
        if last_night < thresholds["sleep_min_hours"]:
            sleep_pass = False
            sleep_debt_status = "insufficient"
        elif last_night < thresholds["sleep_min_hours"] + 0.5:
            marginal_gates.append("sleep")
            sleep_debt_status = "marginal"

    gates["sleep"] = {
        "last_night_hours": last_night,
        "7d_avg_hours": avg_7d,
        "debt_status": sleep_debt_status,
        "min_threshold": thresholds["sleep_min_hours"],
        "gate_pass": sleep_pass,
    }

    # Energy gate (from weight trend, appetite if available)
    energy_pass = True
    weight_trend = state.get("health_gates", {}).get("energy", {}).get("weight_trend", "stable")
    appetite = state.get("health_gates", {}).get("energy", {}).get("appetite", "normal")

    if weight_trend == "declining_fast":
        energy_pass = False
    elif weight_trend == "declining":
        marginal_gates.append("energy")

    gates["energy"] = {
        "weight_trend": weight_trend,
        "appetite": appetite,
        "energy_level": "moderate" if energy_pass else "low",
        "gate_pass": energy_pass,
    }

    # Autonomic gate (HRV + RHR)
    hrv_data = state.get("fatigue_indicators", {}).get("hrv", {})
    rhr_data = state.get("fatigue_indicators", {}).get("resting_hr", {})

    hrv_current = hrv_data.get("current")
    hrv_baseline = hrv_data.get("baseline")
    rhr_current = rhr_data.get("current")
    rhr_baseline = rhr_data.get("baseline")

    hrv_pct = (hrv_current / hrv_baseline * 100) if hrv_current and hrv_baseline else 100
    rhr_pct = (rhr_current / rhr_baseline * 100) if rhr_current and rhr_baseline else 100

    autonomic_pass = True
    autonomic_note = None

    if hrv_pct < thresholds["hrv_min_pct_baseline"]:
        autonomic_pass = False
        autonomic_note = f"HRV at {hrv_pct:.0f}% of baseline (min: {thresholds['hrv_min_pct_baseline']}%)"
    elif hrv_pct < thresholds["hrv_min_pct_baseline"] + 10:
        marginal_gates.append("autonomic")
        autonomic_note = "HRV recovering but not yet at baseline"

    if rhr_pct > thresholds["rhr_max_pct_baseline"]:
        autonomic_pass = False
        autonomic_note = f"RHR elevated to {rhr_pct:.0f}% of baseline"

    gates["autonomic"] = {
        "hrv_vs_baseline_pct": round(hrv_pct, 1),
        "rhr_vs_baseline_pct": round(rhr_pct, 1),
        "trend": hrv_data.get("trend", "unknown"),
        "gate_pass": autonomic_pass,
        "note": autonomic_note,
    }

    # Musculoskeletal gate
    msk_data = state.get("health_gates", {}).get("musculoskeletal", {})
    injury_signals = msk_data.get("injury_signals", [])
    soreness_level = msk_data.get("soreness_level", 0)
    soreness_asymmetry = msk_data.get("soreness_asymmetry", False)

    msk_pass = True
    if len(injury_signals) > 0:
        msk_pass = False
    elif soreness_level > thresholds["soreness_max"]:
        msk_pass = False
    elif soreness_asymmetry:
        marginal_gates.append("musculoskeletal")
    elif soreness_level > thresholds["soreness_max"] - 2:
        marginal_gates.append("musculoskeletal")

    gates["musculoskeletal"] = {
        "injury_signals": injury_signals,
        "soreness_level": soreness_level,
        "soreness_asymmetry": soreness_asymmetry,
        "gate_pass": msk_pass,
    }

    # Stress gate
    stress_data = state.get("health_gates", {}).get("stress", {})
    life_stress = stress_data.get("life_stress_level", 3)
    cognitive_fatigue = stress_data.get("cognitive_fatigue", "low")
    perceived_fatigue = state.get("fatigue_indicators", {}).get("perceived_fatigue", 3)

    stress_pass = True
    if life_stress > thresholds["stress_max"]:
        stress_pass = False
    elif life_stress > thresholds["stress_max"] - 2:
        marginal_gates.append("stress")

    if cognitive_fatigue == "high":
        stress_pass = False
    elif cognitive_fatigue == "moderate":
        if "stress" not in marginal_gates:
            marginal_gates.append("stress")

    gates["stress"] = {
        "life_stress_level": life_stress,
        "cognitive_fatigue": cognitive_fatigue,
        "perceived_fatigue": perceived_fatigue,
        "gate_pass": stress_pass,
    }

    # Overall gate status
    all_pass = all(g["gate_pass"] for g in gates.values())

    # Intensity recommendation based on gates
    if not all_pass:
        intensity_rec = "recovery_only"
    elif len(marginal_gates) >= 2:
        intensity_rec = "low"
    elif len(marginal_gates) == 1:
        intensity_rec = "moderate"
    else:
        intensity_rec = "full"

    gates["overall"] = {
        "all_gates_pass": all_pass,
        "gates_marginal": marginal_gates,
        "intensity_allowed": all_pass,
        "intensity_recommendation": intensity_rec,
    }

    return gates


# =============================================================================
# MAIN CALCULATION
# =============================================================================

def calculate_readiness(state: Dict, config: Optional[Dict] = None) -> Dict:
    """
    Calculate full readiness score and health gates.

    Args:
        state: Current athlete_state.json data
        config: Optional config overrides

    Returns:
        Dict with 'readiness' and 'health_gates' sections
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    weights = cfg["weights"]
    thresholds = cfg["thresholds"]

    # Extract data from state
    fatigue = state.get("fatigue_indicators", {})
    pmc = state.get("performance_management", {})
    whoop = state.get("whoop_daily", {})

    # HRV data
    hrv_data = fatigue.get("hrv", {})
    hrv_current = hrv_data.get("current") or whoop.get("hrv")
    hrv_baseline = hrv_data.get("baseline", 45.0)

    # Sleep data
    sleep_data = fatigue.get("sleep", {})
    sleep_last = sleep_data.get("last_night_hours") or whoop.get("sleep_hours")
    sleep_avg = sleep_data.get("7d_avg_hours")

    # Recovery score
    recovery_data = fatigue.get("whoop_recovery", {})
    recovery_current = recovery_data.get("current") or whoop.get("recovery_score")
    recovery_baseline = recovery_data.get("baseline", 65)

    # TSB
    tsb = pmc.get("tsb")

    # RHR data
    rhr_data = fatigue.get("resting_hr", {})
    rhr_current = rhr_data.get("current") or whoop.get("resting_hr")
    rhr_baseline = rhr_data.get("baseline", 52)

    # Calculate each factor
    factors = {}
    total_contribution = 0.0

    hrv_contrib, hrv_impact, factors["hrv_status"] = calculate_hrv_contribution(
        hrv_current, hrv_baseline, weights["hrv"]
    )
    total_contribution += hrv_contrib

    sleep_contrib, sleep_impact, factors["sleep_status"] = calculate_sleep_contribution(
        sleep_last, sleep_avg, 8.0, weights["sleep"]
    )
    total_contribution += sleep_contrib

    recovery_contrib, recovery_impact, factors["recovery_score"] = calculate_recovery_contribution(
        recovery_current, recovery_baseline, weights["recovery"]
    )
    total_contribution += recovery_contrib

    tsb_contrib, tsb_impact, factors["tsb_status"] = calculate_tsb_contribution(
        tsb, cfg["tsb_optimal"], weights["tsb"]
    )
    total_contribution += tsb_contrib

    rhr_contrib, rhr_impact, factors["rhr_status"] = calculate_rhr_contribution(
        rhr_current, rhr_baseline, weights["rhr"]
    )
    total_contribution += rhr_contrib

    # Check health gates
    health_gates = check_health_gates(state, cfg)

    # Apply gate penalties to score
    gate_penalty = 0
    if not health_gates["overall"]["all_gates_pass"]:
        gate_penalty = 20  # Hard penalty for failed gates
    elif len(health_gates["overall"]["gates_marginal"]) >= 2:
        gate_penalty = 10
    elif len(health_gates["overall"]["gates_marginal"]) == 1:
        gate_penalty = 5

    raw_score = total_contribution
    final_score = max(0, min(100, raw_score - gate_penalty))

    # Determine recommendation
    if final_score >= thresholds["key_session"]:
        recommendation = "green"
        key_eligible = True
        session_allowed = "key"
    elif final_score >= thresholds["support_session"]:
        recommendation = "yellow"
        key_eligible = False
        session_allowed = "support"
    else:
        recommendation = "red"
        key_eligible = False
        session_allowed = "recovery"

    # Override if gates failed
    if not health_gates["overall"]["all_gates_pass"]:
        recommendation = "red"
        key_eligible = False
        session_allowed = "recovery"

    readiness = {
        "score": round(final_score),
        "threshold_key_session": thresholds["key_session"],
        "threshold_support_session": thresholds["support_session"],
        "recommendation": recommendation,
        "key_session_eligible": key_eligible,
        "session_type_allowed": session_allowed,
        "factors": factors,
        "score_breakdown": {
            "raw_score": round(raw_score, 1),
            "gate_penalties": gate_penalty,
            "final_score": round(final_score),
        },
    }

    return {
        "readiness": readiness,
        "health_gates": health_gates,
    }


def update_athlete_readiness(athlete_name: str, dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Calculate and update readiness for an athlete.

    Args:
        athlete_name: Athlete directory name
        dry_run: If True, print but don't write
        verbose: If True, print detailed output

    Returns:
        True if successful
    """
    state = read_state(athlete_name)
    if state is None:
        print(f"Error: Could not read state for athlete '{athlete_name}'")
        return False

    result = calculate_readiness(state)

    if verbose:
        print(f"\n{'='*60}")
        print(f"READINESS CALCULATION: {athlete_name}")
        print(f"{'='*60}")
        print(f"\nReadiness Score: {result['readiness']['score']}")
        print(f"Recommendation: {result['readiness']['recommendation'].upper()}")
        print(f"Key Session Eligible: {result['readiness']['key_session_eligible']}")
        print(f"\nFactor Contributions:")
        for name, factor in result['readiness']['factors'].items():
            print(f"  {name}: {factor.get('contribution', 'N/A')} ({factor.get('impact', 'unknown')})")
        print(f"\nScore Breakdown:")
        print(f"  Raw Score: {result['readiness']['score_breakdown']['raw_score']}")
        print(f"  Gate Penalties: -{result['readiness']['score_breakdown']['gate_penalties']}")
        print(f"  Final Score: {result['readiness']['score_breakdown']['final_score']}")
        print(f"\nHealth Gates:")
        for name, gate in result['health_gates'].items():
            if name != "overall":
                status = "PASS" if gate.get("gate_pass") else "FAIL"
                print(f"  {name}: {status}")
        print(f"\nOverall: {'ALL PASS' if result['health_gates']['overall']['all_gates_pass'] else 'BLOCKED'}")
        if result['health_gates']['overall']['gates_marginal']:
            print(f"Marginal: {result['health_gates']['overall']['gates_marginal']}")
        print()

    if dry_run:
        print("DRY RUN - No changes written")
        print(json.dumps(result, indent=2))
        return True

    # Update state with new readiness data
    state["readiness"] = result["readiness"]
    state["health_gates"] = result["health_gates"]
    state["_meta"]["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state["_meta"]["updated_by"] = "calculate_readiness"

    state_path = get_athlete_path(athlete_name) / "athlete_state.json"
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Updated readiness for {athlete_name}: score={result['readiness']['score']}, rec={result['readiness']['recommendation']}")
    return True


def main():
    """CLI interface for readiness calculator."""
    parser = argparse.ArgumentParser(
        description="Calculate readiness score for an athlete",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/calculate_readiness.py matti-rowe
  python scripts/calculate_readiness.py matti-rowe --verbose
  python scripts/calculate_readiness.py matti-rowe --dry-run
        """
    )

    parser.add_argument("athlete", help="Athlete name (directory name)")
    parser.add_argument("--dry-run", action="store_true", help="Print results without saving")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed calculation")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.json:
        state = read_state(args.athlete)
        if state is None:
            print(f"Error: Could not read state for athlete '{args.athlete}'")
            sys.exit(1)
        result = calculate_readiness(state)
        print(json.dumps(result, indent=2))
    else:
        success = update_athlete_readiness(
            args.athlete,
            dry_run=args.dry_run,
            verbose=args.verbose or args.dry_run
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
