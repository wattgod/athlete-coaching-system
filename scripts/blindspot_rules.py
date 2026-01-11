#!/usr/bin/env python3
"""
Blindspot Rules Engine

Centralizes coaching adjustments based on athlete blindspots.
Each blindspot modifies thresholds, triggers alerts, and adds prompts.

Usage:
    from blindspot_rules import get_blindspot_adjustments, get_blindspot_prompts

    adjustments = get_blindspot_adjustments(profile)
    prompts = get_blindspot_prompts(profile, state)
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class BlindspotAdjustments:
    """Threshold adjustments based on blindspots."""
    # Readiness thresholds
    key_session_threshold: int = 65  # Default, may increase
    ramp_rate_max: float = 7.0       # TSS/day max
    tsb_floor: int = -30             # Warning threshold

    # Recovery requirements
    min_rest_days_per_week: int = 1
    max_weekly_hours: int = 20

    # Health gate weights (multipliers)
    sleep_gate_weight: float = 1.0
    musculoskeletal_gate_weight: float = 1.0
    stress_gate_weight: float = 1.0

    # RHR adjustment (for caffeine users)
    rhr_baseline_offset: int = 0

    # HRV interpretation
    hrv_discount_after_alcohol: float = 0.5  # Discount factor

    # Fueling rules
    min_ride_duration_fasted: int = 90  # Max minutes for fasted ride

    # Active blindspots for reference
    active_blindspots: List[str] = field(default_factory=list)


# Blindspot rule definitions
BLINDSPOT_RULES = {
    "Movement Quality Gap": {
        "description": "No consistent strength training",
        "adjustments": {
            "musculoskeletal_gate_weight": 1.2,  # 20% more sensitive
        },
        "alerts": [
            {
                "type": "strength_reminder",
                "condition": "days_since_strength > 7",
                "severity": "warning",
                "message": "7+ days without strength work. Schedule a session."
            }
        ],
        "prompts": {
            "daily": "Include 10-15min mobility/strength work today",
            "weekly": "Schedule 2 dedicated strength sessions this week"
        }
    },

    "Injury Management": {
        "description": "Active injury requiring management",
        "adjustments": {
            "musculoskeletal_gate_weight": 1.5,  # 50% more sensitive
            "max_weekly_hours": 14,
        },
        "alerts": [
            {
                "type": "injury_volume_warning",
                "condition": "weekly_hours > 14",
                "severity": "warning",
                "message": "High volume week with active injury. Monitor closely."
            }
        ],
        "prompts": {
            "pre_ride": "Hip flexor mobility check before riding",
            "post_ride": "Targeted hip/QL stretching protocol"
        }
    },

    "Overtraining Risk": {
        "description": "History of overtraining episodes",
        "adjustments": {
            "key_session_threshold": 70,  # Stricter (was 65)
            "ramp_rate_max": 5.0,         # Conservative (was 7)
            "tsb_floor": -20,             # Earlier warning (was -30)
            "min_rest_days_per_week": 2,  # More recovery
        },
        "alerts": [
            {
                "type": "overtraining_tsb_warning",
                "condition": "tsb < -20",
                "severity": "warning",
                "message": "TSB below -20. Given OT history, prioritize recovery."
            },
            {
                "type": "overtraining_ramp_warning",
                "condition": "ramp_rate > 5",
                "severity": "warning",
                "message": "Ramp rate too aggressive. History of OT - slow down."
            }
        ],
        "prompts": {
            "daily": "Listen to fatigue signals. You have OT history.",
            "recovery": "Full recovery is non-negotiable with your history"
        }
    },

    "Alcohol Recovery Impact": {
        "description": "Alcohol affects recovery quality",
        "adjustments": {
            "hrv_discount_after_alcohol": 0.5,
            "sleep_gate_weight": 1.3,  # Sleep more affected
        },
        "alerts": [
            {
                "type": "alcohol_weekly_warning",
                "condition": "weekly_drinks > 10",
                "severity": "warning",
                "message": "10+ drinks this week. Recovery is compromised."
            }
        ],
        "prompts": {
            "checkin": "Any alcohol last night? (affects HRV interpretation)",
            "post_alcohol": "Z2 max today. Alcohol suppresses recovery.",
            "weekly": "Each drink costs ~1hr of quality recovery"
        },
        "rules": {
            "post_drinking_max_intensity": "Z2",
            "hrv_interpretation": "Discount low HRV readings if alcohol reported"
        }
    },

    "Weight Management Stress": {
        "description": "Chronic dieting/weight concerns affect performance",
        "adjustments": {
            "min_ride_duration_fasted": 60,  # Shorter fasted rides only
            "stress_gate_weight": 1.2,
        },
        "alerts": [
            {
                "type": "underfueling_warning",
                "condition": "power_decline_with_high_rpe",
                "severity": "warning",
                "message": "Power declining with high RPE. Check fueling."
            }
        ],
        "prompts": {
            "fueling": "Fuel the work. Performance > scale.",
            "pre_ride": "Eat before rides >90min. No fasted long rides.",
            "mental": "Fast comes from fitness, not starvation."
        },
        "rules": {
            "no_fasted_rides_over": 90,  # minutes
            "messaging_focus": "performance_not_weight"
        }
    },

    "Caffeine Dependency": {
        "description": "Regular caffeine use affects baselines",
        "adjustments": {
            "rhr_baseline_offset": 4,  # Add 4bpm to expected RHR
            "sleep_gate_weight": 1.2,
        },
        "alerts": [
            {
                "type": "caffeine_sleep_warning",
                "condition": "sleep_quality < 5 and caffeine_after_noon",
                "severity": "info",
                "message": "Poor sleep + afternoon caffeine. Cut off by noon."
            }
        ],
        "prompts": {
            "daily": "Caffeine cutoff: noon. Affects sleep quality.",
            "rhr_note": "RHR baseline adjusted +4bpm for caffeine use"
        },
        "rules": {
            "rhr_adjustment": 4,
            "caffeine_cutoff_hour": 12
        }
    },

    "Recovery Deficit": {
        "description": "Chronic poor sleep/recovery",
        "adjustments": {
            "key_session_threshold": 70,
            "sleep_gate_weight": 1.5,
        },
        "alerts": [
            {
                "type": "sleep_deficit_warning",
                "condition": "avg_sleep_7d < 6",
                "severity": "warning",
                "message": "Sleep deficit accumulating. Prioritize rest."
            }
        ],
        "prompts": {
            "daily": "Sleep is your #1 performance enhancer",
            "evening": "Screens off 1hr before bed"
        }
    },

    "Life Stress Overload": {
        "description": "High external stress load",
        "adjustments": {
            "key_session_threshold": 70,
            "stress_gate_weight": 1.5,
            "ramp_rate_max": 5.0,
        },
        "alerts": [
            {
                "type": "stress_overload_warning",
                "condition": "stress_score > 7",
                "severity": "warning",
                "message": "High life stress. Training should relieve, not add stress."
            }
        ],
        "prompts": {
            "daily": "Training should be a stress outlet, not another source",
            "high_stress": "Consider Z2 only today. Life stress counts."
        }
    },

    "Time-Crunched": {
        "description": "Limited training time available",
        "adjustments": {
            "max_weekly_hours": 8,
        },
        "prompts": {
            "daily": "Quality > quantity. Make every minute count.",
            "planning": "2 key sessions + endurance. That's the formula."
        }
    },

    "Masters Recovery": {
        "description": "Age 45+ requires extended recovery",
        "adjustments": {
            "min_rest_days_per_week": 2,
            "key_session_threshold": 68,
            "ramp_rate_max": 5.0,
        },
        "prompts": {
            "daily": "Recovery takes longer. Respect the process.",
            "post_intensity": "48-72hrs before next intensity"
        }
    },

    "Extended Recovery Needs": {
        "description": "Age 55+ requires significant recovery time",
        "adjustments": {
            "min_rest_days_per_week": 2,
            "key_session_threshold": 72,
            "ramp_rate_max": 4.0,
        },
        "prompts": {
            "daily": "One hard day, two easy days. Non-negotiable.",
            "weekly": "Max 2 intensity sessions per week"
        }
    },

    "Sleep Disorder": {
        "description": "Chronic sleep issues or medication",
        "adjustments": {
            "sleep_gate_weight": 2.0,  # Double weight
            "key_session_threshold": 70,
        },
        "prompts": {
            "daily": "Sleep quality gates everything. Prioritize it.",
            "checkin": "How was sleep? This is critical for you."
        }
    }
}


def get_blindspot_adjustments(profile: Dict) -> BlindspotAdjustments:
    """
    Calculate combined adjustments based on athlete's blindspots.

    Args:
        profile: Athlete profile dict with 'inferred.blindspots' list

    Returns:
        BlindspotAdjustments with all thresholds modified
    """
    adjustments = BlindspotAdjustments()

    # Get blindspots from profile
    blindspots = profile.get('inferred', {}).get('blindspots', [])
    adjustments.active_blindspots = blindspots

    for blindspot in blindspots:
        if blindspot not in BLINDSPOT_RULES:
            continue

        rules = BLINDSPOT_RULES[blindspot].get('adjustments', {})

        # Apply adjustments (take most conservative value)
        if 'key_session_threshold' in rules:
            adjustments.key_session_threshold = max(
                adjustments.key_session_threshold,
                rules['key_session_threshold']
            )

        if 'ramp_rate_max' in rules:
            adjustments.ramp_rate_max = min(
                adjustments.ramp_rate_max,
                rules['ramp_rate_max']
            )

        if 'tsb_floor' in rules:
            adjustments.tsb_floor = max(
                adjustments.tsb_floor,
                rules['tsb_floor']
            )

        if 'min_rest_days_per_week' in rules:
            adjustments.min_rest_days_per_week = max(
                adjustments.min_rest_days_per_week,
                rules['min_rest_days_per_week']
            )

        if 'max_weekly_hours' in rules:
            adjustments.max_weekly_hours = min(
                adjustments.max_weekly_hours,
                rules['max_weekly_hours']
            )

        # Weights are multiplicative
        if 'sleep_gate_weight' in rules:
            adjustments.sleep_gate_weight *= rules['sleep_gate_weight']

        if 'musculoskeletal_gate_weight' in rules:
            adjustments.musculoskeletal_gate_weight *= rules['musculoskeletal_gate_weight']

        if 'stress_gate_weight' in rules:
            adjustments.stress_gate_weight *= rules['stress_gate_weight']

        if 'rhr_baseline_offset' in rules:
            adjustments.rhr_baseline_offset += rules['rhr_baseline_offset']

        if 'min_ride_duration_fasted' in rules:
            adjustments.min_ride_duration_fasted = min(
                adjustments.min_ride_duration_fasted,
                rules['min_ride_duration_fasted']
            )

    return adjustments


def get_blindspot_prompts(profile: Dict, state: Optional[Dict] = None, context: str = 'daily') -> List[str]:
    """
    Get relevant prompts based on blindspots and current context.

    Args:
        profile: Athlete profile dict
        state: Current athlete state (optional, for conditional prompts)
        context: One of 'daily', 'pre_ride', 'post_ride', 'weekly', 'checkin', 'recovery'

    Returns:
        List of prompt strings
    """
    prompts = []
    blindspots = profile.get('inferred', {}).get('blindspots', [])

    for blindspot in blindspots:
        if blindspot not in BLINDSPOT_RULES:
            continue

        blindspot_prompts = BLINDSPOT_RULES[blindspot].get('prompts', {})

        # Get prompt for this context
        if context in blindspot_prompts:
            prompts.append(blindspot_prompts[context])

        # Always include daily prompts
        if context != 'daily' and 'daily' in blindspot_prompts:
            # Only add daily if it's different from context-specific
            if blindspot_prompts.get('daily') != blindspot_prompts.get(context):
                pass  # Skip to avoid duplicate messaging

    return prompts


def get_blindspot_alerts(profile: Dict, state: Dict) -> List[Dict]:
    """
    Check blindspot-specific alert conditions.

    Args:
        profile: Athlete profile dict
        state: Current athlete state

    Returns:
        List of triggered alerts
    """
    triggered_alerts = []
    blindspots = profile.get('inferred', {}).get('blindspots', [])

    # Extract state values
    tsb = state.get('performance_management', {}).get('tsb', 0)
    ramp_rate = state.get('performance_management', {}).get('ramp_rate', 0)
    weekly_hours = state.get('recent_training', {}).get('weekly_hours', 0)
    stress_score = state.get('subjective', {}).get('stress', 5)
    sleep_quality = state.get('subjective', {}).get('sleep_quality') or state.get('fatigue_indicators', {}).get('sleep', {}).get('quality', 5)

    for blindspot in blindspots:
        if blindspot not in BLINDSPOT_RULES:
            continue

        alerts = BLINDSPOT_RULES[blindspot].get('alerts', [])

        for alert in alerts:
            condition = alert.get('condition', '')
            triggered = False

            # Evaluate conditions
            if 'tsb < -20' in condition and tsb < -20:
                triggered = True
            elif 'ramp_rate > 5' in condition and ramp_rate > 5:
                triggered = True
            elif 'weekly_hours > 14' in condition and weekly_hours > 14:
                triggered = True
            elif 'stress_score > 7' in condition and stress_score and stress_score > 7:
                triggered = True
            elif 'sleep_quality < 5' in condition and sleep_quality and sleep_quality < 5:
                triggered = True

            if triggered:
                triggered_alerts.append({
                    'type': alert['type'],
                    'severity': alert['severity'],
                    'message': alert['message'],
                    'blindspot': blindspot
                })

    return triggered_alerts


def format_blindspot_summary(profile: Dict) -> str:
    """
    Format a summary of active blindspots and their implications.

    Args:
        profile: Athlete profile dict

    Returns:
        Formatted markdown summary
    """
    blindspots = profile.get('inferred', {}).get('blindspots', [])

    if not blindspots:
        return "No blindspots identified."

    adjustments = get_blindspot_adjustments(profile)

    lines = ["## Active Blindspots\n"]

    for blindspot in blindspots:
        if blindspot in BLINDSPOT_RULES:
            desc = BLINDSPOT_RULES[blindspot].get('description', '')
            lines.append(f"- **{blindspot}**: {desc}")

    lines.append("\n## Adjusted Thresholds\n")
    lines.append(f"- Key session readiness: ≥{adjustments.key_session_threshold}")
    lines.append(f"- Max ramp rate: {adjustments.ramp_rate_max} TSS/day")
    lines.append(f"- TSB warning floor: {adjustments.tsb_floor}")
    lines.append(f"- Min rest days/week: {adjustments.min_rest_days_per_week}")

    if adjustments.rhr_baseline_offset > 0:
        lines.append(f"- RHR baseline: +{adjustments.rhr_baseline_offset} bpm (caffeine)")

    return "\n".join(lines)


if __name__ == '__main__':
    # Test with sample profile
    import json
    import yaml
    from pathlib import Path

    profile_path = Path('athletes/matti-rowe/profile.yaml')
    if profile_path.exists():
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        print("=== Blindspot Analysis ===\n")
        print(format_blindspot_summary(profile))

        print("\n=== Daily Prompts ===")
        for prompt in get_blindspot_prompts(profile, context='daily'):
            print(f"- {prompt}")

        print("\n=== Pre-Ride Prompts ===")
        for prompt in get_blindspot_prompts(profile, context='pre_ride'):
            print(f"- {prompt}")

        # Test adjustments
        adj = get_blindspot_adjustments(profile)
        print(f"\n=== Adjustments ===")
        print(f"Key session threshold: {adj.key_session_threshold}")
        print(f"Ramp rate max: {adj.ramp_rate_max}")
        print(f"TSB floor: {adj.tsb_floor}")
        print(f"Min rest days: {adj.min_rest_days_per_week}")
