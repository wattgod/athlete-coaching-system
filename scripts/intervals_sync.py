#!/usr/bin/env python3
"""
Gravel God - Intervals.icu Sync
Downloads all activities from Intervals.icu and runs coaching analysis

Setup:
    1. Get your API key from intervals.icu → Settings → Developer
    2. Set INTERVALS_API_KEY environment variable or edit config.json
    3. Run: python scripts/intervals_sync.py

Usage:
    python scripts/intervals_sync.py                    # Download last 90 days
    python scripts/intervals_sync.py --days 30         # Download last 30 days
    python scripts/intervals_sync.py --all             # Download everything
    python scripts/intervals_sync.py --athlete i12345  # Specific athlete ID
"""

import os
import sys
import json
import gzip
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pwx_parser.parser import PWXParser, load_config
from pwx_parser.gravel_god import GravelGodAnalyzer


class IntervalsSync:
    """Sync activities from Intervals.icu"""

    BASE_URL = "https://intervals.icu/api/v1"

    def __init__(self, api_key, athlete_id="0"):
        """
        Initialize sync client

        Args:
            api_key: Your Intervals.icu API key
            athlete_id: Athlete ID ("0" = yourself, or "i12345" for specific athlete)
        """
        self.api_key = api_key
        self.athlete_id = athlete_id
        self.auth = HTTPBasicAuth("API_KEY", api_key)
        self.session = requests.Session()
        self.session.auth = self.auth

    def get_athlete_info(self):
        """Get athlete profile including FTP, weight, etc."""
        response = self.session.get(f"{self.BASE_URL}/athlete/{self.athlete_id}")
        response.raise_for_status()
        return response.json()

    def get_wellness(self, oldest=None, newest=None):
        """
        Get wellness data including CTL, ATL, TSB (fitness/fatigue/form)

        Returns list of daily wellness records with:
        - ctl (Chronic Training Load / Fitness)
        - atl (Acute Training Load / Fatigue)
        - rampRate
        - ctlLoad (daily CTL contribution)
        """
        params = {}
        if oldest:
            params["oldest"] = oldest
        if newest:
            params["newest"] = newest

        response = self.session.get(
            f"{self.BASE_URL}/athlete/{self.athlete_id}/wellness",
            params=params
        )
        response.raise_for_status()
        return response.json()

    def get_fitness_summary(self):
        """
        Get current fitness summary (CTL, ATL, TSB) for today

        Returns dict with current PMC values
        """
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Get last few days of wellness to find most recent with data
        wellness = self.get_wellness(oldest=yesterday, newest=today)

        if not wellness:
            return None

        # Get most recent record with CTL data
        for record in reversed(wellness):
            if record.get('ctl') is not None:
                return {
                    'date': record.get('id'),  # date is stored as 'id'
                    'ctl': record.get('ctl'),
                    'atl': record.get('atl'),
                    'tsb': record.get('ctl', 0) - record.get('atl', 0),  # TSB = CTL - ATL
                    'ramp_rate': record.get('rampRate'),
                    'weight': record.get('weight'),
                    'restingHR': record.get('restingHR'),
                    'hrv': record.get('hrv'),
                    'sleep_hours': record.get('sleepTime', 0) / 3600 if record.get('sleepTime') else None,
                }

        return None

    def test_connection(self):
        """Test API connection and return athlete info"""
        try:
            response = self.session.get(f"{self.BASE_URL}/athlete/{self.athlete_id}")
            response.raise_for_status()
            athlete = response.json()
            print(f"✓ Connected to Intervals.icu")
            print(f"  Athlete: {athlete.get('name', 'Unknown')}")
            print(f"  ID: {athlete.get('id', self.athlete_id)}")
            return athlete
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print("✗ Authentication failed. Check your API key.")
            else:
                print(f"✗ API error: {e}")
            return None
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return None

    def list_activities(self, oldest=None, newest=None):
        """
        List all activities in date range

        Args:
            oldest: Start date (YYYY-MM-DD)
            newest: End date (YYYY-MM-DD)

        Returns:
            List of activity dicts
        """
        params = {}
        if oldest:
            params["oldest"] = oldest
        if newest:
            params["newest"] = newest

        response = self.session.get(
            f"{self.BASE_URL}/athlete/{self.athlete_id}/activities",
            params=params
        )
        response.raise_for_status()
        return response.json()

    def get_activity_details(self, activity_id):
        """Get full activity details including streams"""
        response = self.session.get(f"{self.BASE_URL}/activity/{activity_id}")
        response.raise_for_status()
        return response.json()

    def get_activity_streams(self, activity_id):
        """Get activity power/HR/cadence streams (second-by-second data)"""
        response = self.session.get(
            f"{self.BASE_URL}/activity/{activity_id}/streams",
            params={"types": "watts,heartrate,cadence,time"}
        )
        response.raise_for_status()
        return response.json()

    def download_fit_file(self, activity_id, output_path):
        """
        Download original FIT file for an activity

        Args:
            activity_id: Activity ID
            output_path: Where to save the file

        Returns:
            True if successful
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/activity/{activity_id}/file"
            )
            response.raise_for_status()

            # Response is gzip-compressed
            with open(output_path, 'wb') as f:
                # Decompress if gzipped
                try:
                    content = gzip.decompress(response.content)
                except:
                    content = response.content
                f.write(content)

            return True
        except Exception as e:
            print(f"  ✗ Failed to download {activity_id}: {e}")
            return False

    def sync_activities(self, output_folder, oldest=None, newest=None, force=False):
        """
        Download all activities to folder

        Args:
            output_folder: Where to save files
            oldest: Start date
            newest: End date
            force: Re-download even if file exists

        Returns:
            List of downloaded file paths
        """
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)

        print(f"\nFetching activity list...")
        activities = self.list_activities(oldest, newest)
        print(f"Found {len(activities)} activities")

        downloaded = []
        skipped = 0
        failed = 0

        for activity in activities:
            activity_id = activity['id']
            date = activity.get('start_date_local', '')[:10]
            name = activity.get('name', 'workout')
            sport = activity.get('type', 'Ride')

            # Only download cycling activities
            if sport not in ['Ride', 'VirtualRide', 'Cycling', 'IndoorCycling']:
                continue

            # Clean filename
            safe_name = "".join(c if c.isalnum() or c in ' -_' else '_' for c in name)
            filename = f"{date}_{safe_name}_{activity_id}.fit"
            filepath = output_folder / filename

            # Skip if already exists
            if filepath.exists() and not force:
                skipped += 1
                continue

            print(f"  Downloading: {date} - {name}...", end=" ")

            if self.download_fit_file(activity_id, filepath):
                print("✓")
                downloaded.append(filepath)
            else:
                failed += 1

        print(f"\n>>> Download complete:")
        print(f"    Downloaded: {len(downloaded)}")
        print(f"    Skipped (existing): {skipped}")
        print(f"    Failed: {failed}")

        return downloaded


def sync_athlete_state(api_key, athlete_id="0", athlete_name=None, days=7):
    """
    Sync PMC and zone distribution to athlete_state.json

    Args:
        api_key: Intervals.icu API key
        athlete_id: Intervals.icu athlete ID
        athlete_name: Local athlete folder name (e.g., "matti-rowe")
        days: Days of activities to analyze for zone distribution

    Returns:
        Dict with synced data, or None on failure
    """
    from pathlib import Path
    from datetime import datetime, timezone

    # Determine athlete name from profile if not provided
    if not athlete_name:
        # Try to find athlete by intervals ID in profiles
        athletes_dir = Path(__file__).parent.parent / "athletes"
        for athlete_dir in athletes_dir.iterdir():
            if athlete_dir.is_dir() and not athlete_dir.name.startswith(('_', '.')):
                profile_path = athlete_dir / "profile.yaml"
                if profile_path.exists():
                    import yaml
                    with open(profile_path) as f:
                        profile = yaml.safe_load(f)
                    intervals_id = profile.get('integrations', {}).get('intervals_icu', {}).get('athlete_id')
                    if intervals_id == athlete_id or (athlete_id == "0" and intervals_id):
                        athlete_name = athlete_dir.name
                        break

    if not athlete_name:
        print(f"Error: Could not find athlete with Intervals ID '{athlete_id}'")
        return None

    print(f"\nSyncing state for athlete: {athlete_name}")

    client = IntervalsSync(api_key, athlete_id)

    # Test connection
    athlete_info = client.test_connection()
    if not athlete_info:
        return None

    # Get FTP from Intervals.icu
    ftp = athlete_info.get('ftp') or athlete_info.get('icu_ftp') or 250

    # Get PMC data
    print("  Fetching PMC data...")
    fitness = client.get_fitness_summary()

    # Get recent activities for zone distribution
    print(f"  Fetching activities (last {days} days)...")
    oldest = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    newest = datetime.now().strftime("%Y-%m-%d")
    activities = client.list_activities(oldest, newest)

    # Filter cycling activities
    cycling_activities = [
        a for a in activities
        if a.get('type') in ['Ride', 'VirtualRide', 'Cycling', 'IndoorCycling']
    ]

    # Calculate zone distribution from activities
    print(f"  Analyzing {len(cycling_activities)} cycling activities...")

    total_seconds = 0
    zone_seconds = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
    total_tss = 0
    workouts_completed = 0

    last_workout = None

    for activity in cycling_activities:
        activity_id = activity['id']

        try:
            streams = client.get_activity_streams(activity_id)
            if not streams:
                continue

            power_stream = next((s for s in streams if s.get('type') == 'watts'), None)
            if not power_stream or not power_stream.get('data'):
                continue

            power_values = [p for p in power_stream['data'] if p and p > 0]
            if not power_values:
                continue

            duration = len(power_values)
            total_seconds += duration

            # Zone distribution
            for p in power_values:
                pct = (p / ftp) * 100
                if pct < 55:
                    zone_seconds[1] += 1
                elif pct < 76:
                    zone_seconds[2] += 1
                elif pct < 91:
                    zone_seconds[3] += 1
                elif pct < 106:
                    zone_seconds[4] += 1
                elif pct < 121:
                    zone_seconds[5] += 1
                elif pct < 151:
                    zone_seconds[6] += 1
                else:
                    zone_seconds[7] += 1

            # Accumulate TSS
            tss = activity.get('icu_training_load') or 0
            total_tss += tss
            workouts_completed += 1

            # Track last workout
            if not last_workout or activity.get('start_date_local', '') > last_workout.get('date', ''):
                last_workout = {
                    'date': activity.get('start_date_local', '')[:10],
                    'name': activity.get('name', 'Workout'),
                    'tss': round(tss, 1),
                    'duration_minutes': round(activity.get('moving_time', 0) / 60, 1),
                    'type': 'threshold' if activity.get('icu_intensity', 0) > 0.85 else 'endurance',
                }

        except Exception as e:
            print(f"    Warning: Could not analyze activity {activity_id}: {e}")
            continue

    # Calculate zone percentages
    if total_seconds > 0:
        z1_z2_pct = round((zone_seconds[1] + zone_seconds[2]) / total_seconds * 100, 1)
        z3_pct = round(zone_seconds[3] / total_seconds * 100, 1)
        z4_plus_pct = round((zone_seconds[4] + zone_seconds[5] + zone_seconds[6] + zone_seconds[7]) / total_seconds * 100, 1)
    else:
        z1_z2_pct = z3_pct = z4_plus_pct = 0

    # Build state update
    state_updates = {
        "performance_management": {
            "ctl": round(fitness.get('ctl', 0), 1) if fitness else None,
            "atl": round(fitness.get('atl', 0), 1) if fitness else None,
            "tsb": round(fitness.get('tsb', 0), 1) if fitness else None,
            "ramp_rate": round(fitness.get('ramp_rate', 0), 1) if fitness and fitness.get('ramp_rate') else None,
            "chronic_load_trend": "building" if fitness and fitness.get('ramp_rate', 0) > 0 else "maintaining",
        },
        "recent_training": {
            "last_workout": last_workout,
            "rolling_7d": {
                "total_tss": round(total_tss, 1),
                "avg_daily_tss": round(total_tss / days, 1),
                "intensity_distribution": {
                    "z1_z2_pct": z1_z2_pct,
                    "z3_pct": z3_pct,
                    "z4_plus_pct": z4_plus_pct,
                }
            },
            "week_summary": {
                "total_tss": round(total_tss, 1),
                "total_hours": round(total_seconds / 3600, 1),
                "workouts_completed": workouts_completed,
            }
        },
    }

    # Add wellness data if available from Intervals
    if fitness and fitness.get('hrv'):
        state_updates["fatigue_indicators"] = {
            "hrv": {
                "current": fitness.get('hrv'),
            },
            "resting_hr": {
                "current": fitness.get('restingHR'),
            },
            "sleep": {
                "last_night_hours": fitness.get('sleep_hours'),
            }
        }

    # Load existing state and merge
    athletes_dir = Path(__file__).parent.parent / "athletes"
    state_path = athletes_dir / athlete_name / "athlete_state.json"

    if state_path.exists():
        with open(state_path) as f:
            state = json.load(f)
    else:
        print(f"  Warning: No existing state file, creating new one")
        template_path = athletes_dir / "_template" / "athlete_state.json"
        with open(template_path) as f:
            state = json.load(f)

    # Deep merge updates
    def deep_merge(base, updates):
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            elif value is not None:
                base[key] = value

    deep_merge(state, state_updates)

    # Update metadata
    state["_meta"]["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state["_meta"]["updated_by"] = "intervals_sync"

    # Save state
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n  Updated {athlete_name}/athlete_state.json:")
    print(f"    CTL: {state_updates['performance_management']['ctl']}")
    print(f"    ATL: {state_updates['performance_management']['atl']}")
    print(f"    TSB: {state_updates['performance_management']['tsb']}")
    print(f"    Zone distribution (7d): Z1-Z2 {z1_z2_pct}% | Z3 {z3_pct}% | Z4+ {z4_plus_pct}%")
    print(f"    Target distribution:    Z1-Z2 84%   | Z3 6%   | Z4+ 10%")

    # Check distribution drift
    z1_z2_drift = z1_z2_pct - 84
    z3_drift = z3_pct - 6
    z4_drift = z4_plus_pct - 10

    if z1_z2_drift < -5:
        print(f"    ⚠️  Too little Z1-Z2 ({z1_z2_drift:+.1f}% from target)")
    if z3_drift > 3:
        print(f"    ⚠️  Too much Z3/G-Spot ({z3_drift:+.1f}% from target)")
    if z4_drift > 5:
        print(f"    ⚠️  Too much intensity ({z4_drift:+.1f}% from target)")

    return state_updates


class IntervalsFITParser:
    """Parse FIT files downloaded from Intervals.icu"""

    def __init__(self, ftp=250, lthr=170):
        self.ftp = ftp
        self.lthr = lthr

    def parse_fit_file(self, filepath):
        """
        Parse FIT file and extract power/HR/cadence data

        Note: FIT is a binary format. For full parsing, we'd need the fitparse library.
        This is a simplified approach using Intervals.icu's streams API instead.
        """
        # FIT parsing requires external library
        # For now, return None and use API streams instead
        return None


def sync_and_analyze(api_key, athlete_id="0", days=90, output_folder="./fit_files",
                     analysis_output="./output", config_file="config.json", all_time=False):
    """
    Complete sync and analysis pipeline

    Args:
        api_key: Intervals.icu API key
        athlete_id: Athlete ID
        days: Number of days to sync
        output_folder: Where to save FIT files
        analysis_output: Where to save analysis results
        config_file: Athlete config file
        all_time: Download all activities (ignores days)
    """
    print("=" * 60)
    print("  GRAVEL GOD - Intervals.icu Sync")
    print("=" * 60)

    # Initialize client
    client = IntervalsSync(api_key, athlete_id)

    # Test connection
    athlete_info = client.test_connection()
    if not athlete_info:
        return False

    # Calculate date range
    newest = datetime.now().strftime("%Y-%m-%d")
    if all_time:
        oldest = "2000-01-01"
        print(f"\nSyncing ALL activities...")
    else:
        oldest = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        print(f"\nSyncing activities from {oldest} to {newest} ({days} days)...")

    # Download activities
    downloaded = client.sync_activities(output_folder, oldest, newest)

    if not downloaded:
        print("\nNo new activities to analyze.")
        # Still run analysis on existing files

    # Now analyze using streams API (more reliable than parsing FIT)
    print("\n" + "=" * 60)
    print("  Running Coaching Analysis...")
    print("=" * 60)

    config = load_config(config_file)
    ftp = config.get('athlete', {}).get('ftp', 250)
    lthr = config.get('athlete', {}).get('lthr', 170)

    # Get activities with streams for analysis
    activities = client.list_activities(oldest, newest)

    results = []
    for activity in activities:
        # Only analyze cycling
        if activity.get('type') not in ['Ride', 'VirtualRide', 'Cycling', 'IndoorCycling']:
            continue

        activity_id = activity['id']

        try:
            # Get streams from API (already parsed!)
            streams = client.get_activity_streams(activity_id)

            if not streams:
                continue

            # Extract data
            power_stream = next((s for s in streams if s.get('type') == 'watts'), None)
            hr_stream = next((s for s in streams if s.get('type') == 'heartrate'), None)
            cadence_stream = next((s for s in streams if s.get('type') == 'cadence'), None)

            if not power_stream or not power_stream.get('data'):
                continue

            power_values = [p for p in power_stream['data'] if p and p > 0]
            hr_values = [h for h in (hr_stream.get('data', []) if hr_stream else []) if h and h > 0]
            cadence_values = [c for c in (cadence_stream.get('data', []) if cadence_stream else []) if c and c > 0]

            if not power_values:
                continue

            # Calculate metrics
            from statistics import mean, stdev

            avg_power = mean(power_values)
            duration_seconds = len(power_values)

            # Normalized Power
            if len(power_values) >= 30:
                rolling = [mean(power_values[i:i+30]) for i in range(len(power_values) - 29)]
                np_value = (sum(p**4 for p in rolling) / len(rolling)) ** 0.25
            else:
                np_value = avg_power

            # Other metrics
            if_value = np_value / ftp
            vi = np_value / avg_power if avg_power > 0 else None
            tss = (duration_seconds * np_value * if_value) / (ftp * 3600) * 100

            # Decoupling
            decoupling = None
            if hr_values and len(hr_values) >= len(power_values) // 2:
                mid = min(len(power_values), len(hr_values)) // 2
                pw = power_values[:mid*2]
                hr = hr_values[:mid*2]

                ef1 = mean(pw[:mid]) / mean(hr[:mid]) if mean(hr[:mid]) > 0 else None
                ef2 = mean(pw[mid:]) / mean(hr[mid:]) if mean(hr[mid:]) > 0 else None

                if ef1 and ef2 and ef1 > 0:
                    decoupling = ((ef1 - ef2) / ef1) * 100

            # Zone distribution
            zones = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
            for p in power_values:
                pct = (p / ftp) * 100
                if pct < 55: zones[1] += 1
                elif pct < 76: zones[2] += 1
                elif pct < 91: zones[3] += 1
                elif pct < 106: zones[4] += 1
                elif pct < 121: zones[5] += 1
                elif pct < 151: zones[6] += 1
                else: zones[7] += 1

            result = {
                'filename': f"{activity.get('start_date_local', '')[:10]}_{activity.get('name', 'workout')}",
                'date': activity.get('start_date_local', '')[:10],
                'name': activity.get('name', ''),
                'duration_seconds': duration_seconds,
                'duration_minutes': round(duration_seconds / 60, 1),
                'avg_power': round(avg_power, 1),
                'max_power': max(power_values),
                'np': round(np_value, 1),
                'if': round(if_value, 3),
                'vi': round(vi, 3) if vi else None,
                'tss': round(tss, 1),
                'decoupling_pct': round(decoupling, 1) if decoupling else None,
                'avg_hr': round(mean(hr_values), 1) if hr_values else None,
                'max_hr': max(hr_values) if hr_values else None,
                'avg_cadence': round(mean(cadence_values), 1) if cadence_values else None,
                'z1_pct': round(zones[1] / duration_seconds * 100, 1),
                'z2_pct': round(zones[2] / duration_seconds * 100, 1),
                'z3_pct': round(zones[3] / duration_seconds * 100, 1),
                'z4_pct': round(zones[4] / duration_seconds * 100, 1),
                'z5_pct': round(zones[5] / duration_seconds * 100, 1),
                'z6_pct': round(zones[6] / duration_seconds * 100, 1),
                'z7_pct': round(zones[7] / duration_seconds * 100, 1),
                # Intervals.icu pre-calculated values (bonus!)
                'icu_np': activity.get('icu_weighted_avg_watts'),
                'icu_tss': activity.get('icu_training_load'),
                'icu_if': activity.get('icu_intensity'),
                'description': activity.get('description', ''),
            }

            results.append(result)
            print(f"  Analyzed: {result['date']} - {result['name'][:30]} | NP: {result['np']}W, VI: {result['vi']}, TSS: {result['tss']}")

        except Exception as e:
            print(f"  ✗ Error analyzing {activity_id}: {e}")
            continue

    if not results:
        print("\nNo activities with power data found.")
        return False

    # Save results
    output_path = Path(analysis_output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Write CSV
    import csv
    csv_path = output_path / "intervals_analysis.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\n>>> Saved: {csv_path}")

    # Run Gravel God analysis
    analyzer = GravelGodAnalyzer(config, results)
    analyzer.generate_reports(output_path)

    print(f"\n>>> Analysis complete!")
    print(f">>> Check {analysis_output}/ for results:")
    print(f"    - intervals_analysis.csv (all metrics)")
    print(f"    - coaching_report.md (recommendations)")
    print(f"    - alerts.json (issues to address)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Sync activities from Intervals.icu and run coaching analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # First time: set your API key
    export INTERVALS_API_KEY="your_key_here"

    # Sync athlete state (PMC + zones) - RECOMMENDED
    python scripts/intervals_sync.py --sync-state --athlete-name matti-rowe

    # Sync last 90 days (default)
    python scripts/intervals_sync.py

    # Sync last 30 days
    python scripts/intervals_sync.py --days 30

    # Sync all time
    python scripts/intervals_sync.py --all

    # Sync specific athlete (if you're a coach)
    python scripts/intervals_sync.py --athlete i12345
        """
    )

    parser.add_argument('--api-key',
                        default=os.environ.get('INTERVALS_API_KEY'),
                        help='Intervals.icu API key (or set INTERVALS_API_KEY env var)')
    parser.add_argument('--athlete', default='0',
                        help='Intervals.icu athlete ID ("0" for yourself)')
    parser.add_argument('--athlete-name',
                        help='Local athlete folder name (e.g., "matti-rowe")')
    parser.add_argument('--days', type=int, default=90,
                        help='Number of days to sync (default: 90)')
    parser.add_argument('--all', action='store_true',
                        help='Sync all activities (ignores --days)')
    parser.add_argument('--output', default='./fit_files',
                        help='Folder to save FIT files')
    parser.add_argument('--analysis', default='./output',
                        help='Folder to save analysis results')
    parser.add_argument('--config', default='config.json',
                        help='Athlete config file')
    parser.add_argument('--sync-state', action='store_true',
                        help='Sync PMC and zones to athlete_state.json (recommended)')

    args = parser.parse_args()

    if not args.api_key:
        print("Error: No API key provided.")
        print()
        print("Get your key from: intervals.icu → Settings → Developer")
        print()
        print("Then either:")
        print("  export INTERVALS_API_KEY='your_key_here'")
        print("  python scripts/intervals_sync.py")
        print()
        print("Or:")
        print("  python scripts/intervals_sync.py --api-key 'your_key_here'")
        sys.exit(1)

    # Sync state mode (PMC + zones to athlete_state.json)
    if args.sync_state:
        result = sync_athlete_state(
            api_key=args.api_key,
            athlete_id=args.athlete,
            athlete_name=args.athlete_name,
            days=min(args.days, 7) if args.days != 90 else 7,  # Default to 7 days for zone calc
        )
        sys.exit(0 if result else 1)

    # Full sync and analyze mode
    success = sync_and_analyze(
        api_key=args.api_key,
        athlete_id=args.athlete,
        days=args.days,
        output_folder=args.output,
        analysis_output=args.analysis,
        config_file=args.config,
        all_time=args.all
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
