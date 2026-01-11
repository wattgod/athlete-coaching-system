#!/usr/bin/env python3
"""
Create athlete profile from questionnaire submission.

Parses the markdown output from athlete-questionnaire.html and generates:
- athletes/{name}/profile.yaml (static profile)
- athletes/{name}/athlete_state.json (initial state)

Usage:
    python scripts/create_profile_from_questionnaire.py response.md
    python scripts/create_profile_from_questionnaire.py --interactive
    cat response.md | python scripts/create_profile_from_questionnaire.py --stdin
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

import yaml


def slugify(name: str) -> str:
    """Convert name to slug (e.g., 'Matti Rowe' -> 'matti-rowe')."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def parse_questionnaire(text: str) -> dict:
    """Parse markdown questionnaire response into structured data."""
    data = {}
    current_section = None

    for line in text.split('\n'):
        line = line.strip()

        # Section headers
        if line.startswith('## '):
            current_section = line[3:].strip().lower().replace(' ', '_')
            data[current_section] = {}
            continue

        # Title line (# Athlete Intake: Name)
        if line.startswith('# Athlete Intake:'):
            data['name'] = line.replace('# Athlete Intake:', '').strip()
            continue

        # Email/Submitted at top level
        if line.startswith('Email:'):
            data['email'] = line.replace('Email:', '').strip()
            continue

        if line.startswith('Submitted:'):
            data['submitted'] = line.replace('Submitted:', '').strip()
            continue

        # Key-value pairs (- Key: Value)
        if line.startswith('- ') and ':' in line:
            kv = line[2:]  # Remove "- "
            key, _, value = kv.partition(':')
            key = key.strip().lower().replace(' ', '_')
            value = value.strip()

            if current_section and current_section in data:
                data[current_section][key] = value
            else:
                data[key] = value

    return data


def parse_height(height_str: str) -> int:
    """Parse height like '5\\'11\"' to cm."""
    match = re.match(r"(\d+)'(\d+)\"?", height_str)
    if match:
        feet, inches = int(match.group(1)), int(match.group(2))
        return int((feet * 12 + inches) * 2.54)
    return 0


def parse_weight_to_kg(weight_str: str) -> float:
    """Parse weight like '175 lbs' to kg."""
    match = re.search(r'(\d+)', weight_str)
    if match:
        lbs = int(match.group(1))
        return round(lbs * 0.453592, 1)
    return 0


def estimate_zones(ftp: int, lthr: int = None) -> dict:
    """Calculate power and HR zones from FTP/LTHR."""
    zones = {
        'power': {
            'z1': [0, int(ftp * 0.55)],
            'z2': [int(ftp * 0.55), int(ftp * 0.75)],
            'z3': [int(ftp * 0.76), int(ftp * 0.90)],
            'z4': [int(ftp * 0.91), int(ftp * 1.05)],
            'z5': [int(ftp * 1.06), int(ftp * 1.20)],
            'z6': [int(ftp * 1.21), int(ftp * 1.50)],
            'z7': [int(ftp * 1.51), 9999],
            'g_spot': [int(ftp * 0.84), int(ftp * 0.97)]
        }
    }

    if lthr:
        zones['heart_rate'] = {
            'z1': [0, int(lthr * 0.70)],
            'z2': [int(lthr * 0.70), int(lthr * 0.85)],
            'z3': [int(lthr * 0.86), int(lthr * 0.95)],
            'z4': [int(lthr * 0.96), int(lthr * 1.05)],
            'z5': [int(lthr * 1.06), 999]
        }

    return zones


def parse_days(days_str: str) -> list:
    """Parse day list like 'Saturday, Sunday' to list."""
    if not days_str or days_str == 'N/A':
        return []
    return [d.strip().lower() for d in days_str.split(',')]


def infer_schedule(hours: int, long_days: list, interval_days: list, off_days: list) -> dict:
    """Build schedule from questionnaire responses."""
    schedule = {}
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    for day in days:
        if day in off_days:
            schedule[day] = "rest"
        elif day in long_days:
            schedule[day] = "3-5hrs"
        elif day in interval_days:
            schedule[day] = "60-90min intensity"
        else:
            schedule[day] = "60-90min easy"

    return schedule


def map_coaching_style(style: str) -> str:
    """Map questionnaire style to system prompt setting."""
    styles = {
        'direct': 'direct',
        'encouraging': 'encouraging',
        'data-driven': 'analytical',
        'balanced': 'balanced'
    }
    return styles.get(style.lower(), 'balanced')


def map_autonomy(autonomy: str) -> str:
    """Map autonomy level to coaching approach."""
    if 'exact' in autonomy.lower():
        return 'prescriptive'
    elif 'high' in autonomy.lower():
        return 'advisory'
    return 'collaborative'


def create_profile(parsed: dict) -> dict:
    """Convert parsed questionnaire to profile.yaml structure."""

    # Extract nested sections
    basic = parsed.get('basic_info', {})
    goals = parsed.get('goals', {})
    fitness = parsed.get('current_fitness', {})
    recovery = parsed.get('recovery_&_baselines', {})
    equipment = parsed.get('equipment_&_data', {})
    schedule = parsed.get('schedule', {})
    work_life = parsed.get('work_&_life', {})
    health = parsed.get('health', {})
    strength = parsed.get('strength', {})
    prefs = parsed.get('coaching_preferences', {})
    mental = parsed.get('mental_game', {})
    additional = parsed.get('additional', {})
    inferred = parsed.get('inferred', {})

    # Parse FTP
    ftp_str = fitness.get('ftp', '0')
    ftp = int(re.search(r'\d+', ftp_str).group()) if re.search(r'\d+', ftp_str) else 0

    # Parse RHR
    rhr_str = recovery.get('resting_hr', '0')
    rhr = int(re.search(r'\d+', rhr_str).group()) if re.search(r'\d+', rhr_str) else 55

    # Parse hours
    hours_str = schedule.get('weekly_hours_available', '10')
    hours = int(re.search(r'\d+', hours_str).group()) if re.search(r'\d+', hours_str) else 10

    # Parse weight
    weight_str = basic.get('weight', '0')
    weight_kg = parse_weight_to_kg(weight_str)

    # Parse days
    long_days = parse_days(schedule.get('long_ride_days', ''))
    interval_days = parse_days(schedule.get('interval_days', ''))
    off_days = parse_days(schedule.get('off_days', 'Flexible'))

    # Build profile
    profile = {
        'name': parsed.get('name', 'Unknown'),
        'email': parsed.get('email', ''),
        'phone': '',
        'timezone': 'America/Denver',  # Default, can be updated
        'start_date': date.today().isoformat(),

        'physiology': {
            'ftp': ftp if ftp > 0 else None,
            'ftp_test_date': None,
            'ftp_test_type': None,
            'lthr': None,
            'max_hr': None,
            'resting_hr': rhr,
            'vo2max_estimated': None,
            'weight_kg': weight_kg if weight_kg > 0 else None,
            'height_cm': parse_height(basic.get('height', "0'0\"")),
        },

        'baselines': {
            'resting_hr': rhr,
            'sleep_hours': float(recovery.get('typical_sleep', '7').replace(' hrs', '')),
            'hrv_baseline': int(recovery.get('hrv_baseline', '0').replace(' ms', '').replace('Unknown', '0') or 0) or None,
            'recovery_speed': recovery.get('recovery_speed', 'normal'),
        },

        'zones': estimate_zones(ftp) if ftp > 0 else {},

        'availability': {
            'hours_per_week': hours,
            'schedule': infer_schedule(hours, long_days, interval_days, off_days),
            'constraints': []
        },

        'goals': {
            'primary_goal': goals.get('primary_goal', ''),
            'primary_event': None,
            'secondary_events': [],
            'outcome_goals': [],
            'process_goals': [],
            'limiters': [],
            'success_definition': goals.get('success', ''),
            'obstacles': goals.get('obstacles', '')
        },

        'background': {
            'years_cycling': int(re.search(r'\d+', fitness.get('years_cycling', '0')).group()) if re.search(r'\d+', fitness.get('years_cycling', '0')) else 0,
            'years_structured_training': int(re.search(r'\d+', fitness.get('years_structured', '0') or '0').group()) if re.search(r'\d+', fitness.get('years_structured', '0') or '0') else 0,
            'previous_coaches': [],
            'recent_training': {
                'current_weekly_volume': fitness.get('current_volume', ''),
                'longest_recent_ride': fitness.get('longest_recent_ride', ''),
            },
            'injury_history': [health.get('past_injuries', '')] if health.get('past_injuries') else [],
            'strengths': [s.strip() for s in (fitness.get('strengths', '') or '').split(',')] if fitness.get('strengths') else [],
            'weaknesses': [w.strip() for w in (fitness.get('weaknesses', '') or '').split(',')] if fitness.get('weaknesses') else [],
        },

        'health': {
            'current_injuries': health.get('current_injuries', 'None'),
            'medical_conditions': health.get('medical_conditions', ''),
            'medications': health.get('medications', ''),
            'overtraining_history': recovery.get('overtraining_history', ''),
        },

        'preferences': {
            'philosophy': 'Polarized',  # Default Nate Wilson approach
            'indoor_outdoor_split': '30/70',
            'trainer_access': equipment.get('indoor_trainer', 'no'),
            'indoor_tolerance': equipment.get('indoor_tolerance', ''),
        },

        'integrations': {
            'intervals_icu': {
                'athlete_id': equipment.get('intervals.icu_id', '') or ''
            },
            'whoop': {
                'enabled': 'whoop' in (equipment.get('devices', '') or '').lower()
            },
            'garmin_connect': {
                'enabled': 'garmin' in (equipment.get('devices', '') or '').lower()
            },
            'training_platform': equipment.get('platform', 'intervals.icu')
        },

        'coaching': {
            'checkin_frequency': prefs.get('check-in_frequency', 'few times week'),
            'feedback_detail': prefs.get('feedback_detail', 'moderate'),
            'autonomy': map_autonomy(prefs.get('autonomy', 'collaborative')),
            'communication_style': map_coaching_style(prefs.get('communication_style', 'balanced')),
        },

        'work_life': {
            'work_hours': work_life.get('work_hours', ''),
            'job_stress': work_life.get('job_stress', ''),
            'life_stress': work_life.get('life_stress', ''),
            'family_situation': work_life.get('family', ''),
            'other_commitments': work_life.get('commitments', ''),
        },

        'mental': {
            'missed_workout_response': mental.get('missed_workout_response', ''),
            'best_training_block': mental.get('best_training_block', ''),
            'quit_triggers': mental.get('quit_triggers', ''),
            'accountability_style': mental.get('accountability_style', ''),
        },

        'inferred': {
            'blindspots': [b.strip() for b in (inferred.get('blindspots', '') or 'None identified').split(',')] if inferred.get('blindspots') != 'None identified' else [],
            'traits': [t.strip() for t in (inferred.get('traits', '') or 'None identified').split(',')] if inferred.get('traits') != 'None identified' else [],
        },

        'strength_training': {
            'current': strength.get('current', 'none'),
            'wants_included': strength.get('include', 'no'),
            'equipment': strength.get('equipment', ''),
        },

        'status': {
            'phase': 'onboarding',
            'week_of_plan': 0,
            'current_focus': ['Initial assessment', 'Baseline establishment'],
            'recent_notes': [
                {
                    'date': date.today().isoformat(),
                    'note': 'Profile created from intake questionnaire'
                }
            ],
            'flags': []
        }
    }

    # Parse race list if present
    if goals.get('races'):
        races = goals['races']
        # Try to parse race entries (format: "Race Name - Date (A/B/C)")
        race_matches = re.findall(r'([^,]+?)(?:\s*-\s*(\d{4}-\d{2}-\d{2}))?(?:\s*\(([ABC])\))?(?:,|$)', races)
        events = []
        for match in race_matches:
            name, race_date, priority = match
            if name.strip():
                events.append({
                    'name': name.strip(),
                    'date': race_date if race_date else None,
                    'priority': priority if priority else 'B'
                })

        if events:
            profile['goals']['primary_event'] = events[0]
            profile['goals']['secondary_events'] = events[1:] if len(events) > 1 else []

    return profile


def create_initial_state(profile: dict) -> dict:
    """Create initial athlete_state.json from profile."""
    return {
        'timestamp': datetime.now().isoformat(),
        'athlete_name': profile['name'],

        'fatigue_indicators': {
            'rhr': {
                'value': profile['baselines']['resting_hr'],
                'baseline': profile['baselines']['resting_hr'],
                'trend': 'stable'
            },
            'hrv': {
                'value': profile['baselines'].get('hrv_baseline'),
                'baseline': profile['baselines'].get('hrv_baseline'),
                'trend': 'unknown'
            },
            'sleep': {
                'hours': profile['baselines']['sleep_hours'],
                'quality': None
            }
        },

        'readiness': {
            'score': 70,  # Start neutral
            'threshold_key_session': 65,
            'key_session_eligible': True,
            'recommendation': 'green',
            'factors': {
                'hrv': 0,
                'sleep': 0,
                'recovery': 0,
                'tsb': 0,
                'rhr': 0
            }
        },

        'health_gates': {
            'sleep': {'gate_pass': True, 'reason': 'Initial assessment'},
            'energy': {'gate_pass': True, 'reason': 'Initial assessment'},
            'autonomic': {'gate_pass': True, 'reason': 'Initial assessment'},
            'musculoskeletal': {'gate_pass': True, 'reason': 'Initial assessment'},
            'stress': {'gate_pass': True, 'reason': 'Initial assessment'},
            'overall': {'intensity_allowed': True}
        },

        'performance_management': {
            'ctl': 0,
            'atl': 0,
            'tsb': 0,
            'ramp_rate': 0
        },

        'subjective': {
            'fatigue': None,
            'soreness': None,
            'stress': None,
            'motivation': None,
            'last_checkin': None
        },

        'alerts': {
            'active': [],
            'resolved_recently': []
        }
    }


def clean_none_values(obj):
    """Recursively remove None values and empty strings for cleaner YAML."""
    if isinstance(obj, dict):
        return {k: clean_none_values(v) for k, v in obj.items()
                if v is not None and v != '' and v != []}
    elif isinstance(obj, list):
        return [clean_none_values(item) for item in obj if item is not None and item != '']
    return obj


def main():
    parser = argparse.ArgumentParser(description='Create athlete profile from questionnaire')
    parser.add_argument('file', nargs='?', help='Questionnaire response file (markdown)')
    parser.add_argument('--stdin', action='store_true', help='Read from stdin')
    parser.add_argument('--interactive', action='store_true', help='Paste response interactively')
    parser.add_argument('--output-dir', default='athletes', help='Output directory')
    parser.add_argument('--dry-run', action='store_true', help='Show output without writing files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')

    args = parser.parse_args()

    # Get input text
    if args.stdin:
        text = sys.stdin.read()
    elif args.interactive:
        print("Paste questionnaire response (end with Ctrl+D):")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        text = '\n'.join(lines)
    elif args.file:
        with open(args.file, 'r') as f:
            text = f.read()
    else:
        parser.print_help()
        sys.exit(1)

    # Parse questionnaire
    parsed = parse_questionnaire(text)

    if args.verbose:
        print("=== Parsed Data ===")
        print(json.dumps(parsed, indent=2, default=str))
        print()

    # Create profile
    profile = create_profile(parsed)

    # Clean up empty values
    profile = clean_none_values(profile)

    if args.verbose:
        print("=== Generated Profile ===")
        print(yaml.dump(profile, default_flow_style=False, sort_keys=False))
        print()

    # Create initial state
    state = create_initial_state(profile)

    if args.dry_run:
        print("=== Profile (dry run) ===")
        print(yaml.dump(profile, default_flow_style=False, sort_keys=False))
        print("\n=== State (dry run) ===")
        print(json.dumps(state, indent=2, default=str))
        return

    # Create athlete directory
    athlete_slug = slugify(profile['name'])
    athlete_dir = Path(args.output_dir) / athlete_slug
    athlete_dir.mkdir(parents=True, exist_ok=True)

    # Write profile.yaml
    profile_path = athlete_dir / 'profile.yaml'
    with open(profile_path, 'w') as f:
        f.write(f"# Athlete Profile: {profile['name']}\n")
        f.write(f"# Created: {date.today().isoformat()}\n\n")
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False)

    print(f"Created: {profile_path}")

    # Write athlete_state.json
    state_path = athlete_dir / 'athlete_state.json'
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"Created: {state_path}")

    # Summary
    print(f"\n✓ Profile created for {profile['name']}")
    print(f"  Directory: {athlete_dir}")
    if profile.get('integrations', {}).get('intervals_icu', {}).get('athlete_id'):
        print(f"  Intervals.icu ID: {profile['integrations']['intervals_icu']['athlete_id']}")
    if profile.get('integrations', {}).get('whoop', {}).get('enabled'):
        print(f"  WHOOP: Enabled")

    blindspots = profile.get('inferred', {}).get('blindspots', [])
    if blindspots:
        print(f"  Blindspots: {', '.join(blindspots)}")

    print(f"\nNext steps:")
    print(f"  1. Review {profile_path} and add missing values")
    print(f"  2. Run: python scripts/intervals_sync.py --sync-state --athlete-name {athlete_slug}")
    print(f"  3. Run: python scripts/calculate_readiness.py {athlete_slug}")


if __name__ == '__main__':
    main()
