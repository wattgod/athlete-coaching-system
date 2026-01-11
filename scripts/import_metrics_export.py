#!/usr/bin/env python3
"""
Import metrics from Intervals.icu CSV export to athlete_state.json.
Handles WHOOP data: HRV, Pulse (RHR), Sleep Hours, Recovery Score.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def parse_recovery_score(notes: str) -> int | None:
    """Extract WHOOP Recovery Score from Notes field."""
    if "WHOOP Recovery Score:" in notes:
        try:
            return int(notes.split("WHOOP Recovery Score:")[1].strip())
        except (ValueError, IndexError):
            return None
    return None

def import_metrics(csv_path: str, athlete_dir: str) -> dict:
    """Import metrics from CSV and update athlete state."""

    # Group metrics by date
    daily_data = defaultdict(dict)

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = row['Timestamp']
            metric_type = row['Type']
            value = row['Value']

            # Parse date
            date = timestamp.split()[0]

            # Store metrics
            if metric_type == 'HRV':
                daily_data[date]['hrv'] = float(value)
            elif metric_type == 'Pulse':
                # Take morning pulse as RHR (from WHOOP timestamp, not midnight Garmin)
                if '07:' in timestamp or '06:' in timestamp or '08:' in timestamp:
                    daily_data[date]['rhr'] = int(float(value))
            elif metric_type == 'Sleep Hours':
                daily_data[date]['sleep_hours'] = float(value)
            elif metric_type == 'Notes':
                recovery = parse_recovery_score(value)
                if recovery:
                    daily_data[date]['recovery_score'] = recovery
            elif metric_type == 'Time In Deep Sleep':
                daily_data[date]['deep_sleep'] = float(value)
            elif metric_type == 'Time In REM Sleep':
                daily_data[date]['rem_sleep'] = float(value)

    # Get most recent complete day
    sorted_dates = sorted(daily_data.keys(), reverse=True)
    latest_date = None
    latest_data = None

    for date in sorted_dates:
        data = daily_data[date]
        if 'hrv' in data and 'sleep_hours' in data:
            latest_date = date
            latest_data = data
            break

    if not latest_date:
        print("No complete daily data found")
        return {}

    print(f"Most recent complete data: {latest_date}")
    print(f"  HRV: {latest_data.get('hrv', 'N/A')}")
    print(f"  RHR: {latest_data.get('rhr', 'N/A')}")
    print(f"  Sleep: {latest_data.get('sleep_hours', 'N/A')}h")
    print(f"  Recovery: {latest_data.get('recovery_score', 'N/A')}%")

    # Calculate 7-day averages for baselines
    recent_dates = sorted_dates[:7]
    hrv_values = [daily_data[d]['hrv'] for d in recent_dates if 'hrv' in daily_data[d]]
    rhr_values = [daily_data[d]['rhr'] for d in recent_dates if 'rhr' in daily_data[d]]
    sleep_values = [daily_data[d]['sleep_hours'] for d in recent_dates if 'sleep_hours' in daily_data[d]]
    recovery_values = [daily_data[d]['recovery_score'] for d in recent_dates if 'recovery_score' in daily_data[d]]

    hrv_avg = sum(hrv_values) / len(hrv_values) if hrv_values else None
    rhr_avg = sum(rhr_values) / len(rhr_values) if rhr_values else None
    sleep_avg = sum(sleep_values) / len(sleep_values) if sleep_values else None
    recovery_avg = sum(recovery_values) / len(recovery_values) if recovery_values else None

    print(f"\n7-day averages:")
    print(f"  HRV: {hrv_avg:.1f}" if hrv_avg else "  HRV: N/A")
    print(f"  RHR: {rhr_avg:.0f}" if rhr_avg else "  RHR: N/A")
    print(f"  Sleep: {sleep_avg:.1f}h" if sleep_avg else "  Sleep: N/A")
    print(f"  Recovery: {recovery_avg:.0f}%" if recovery_avg else "  Recovery: N/A")

    # Load and update athlete state
    state_path = Path(athlete_dir) / 'athlete_state.json'
    with open(state_path, 'r') as f:
        state = json.load(f)

    # Update fatigue indicators (using 'current' field name for readiness script compatibility)
    if latest_data.get('hrv'):
        state['fatigue_indicators']['hrv']['current'] = round(latest_data['hrv'], 1)
        state['fatigue_indicators']['hrv']['value'] = round(latest_data['hrv'], 1)  # Also set value for display
        if hrv_avg:
            state['fatigue_indicators']['hrv']['baseline'] = round(hrv_avg, 1)
        # Determine trend
        if hrv_avg and latest_data['hrv'] > hrv_avg * 1.1:
            state['fatigue_indicators']['hrv']['trend'] = 'elevated'
        elif hrv_avg and latest_data['hrv'] < hrv_avg * 0.9:
            state['fatigue_indicators']['hrv']['trend'] = 'suppressed'
        else:
            state['fatigue_indicators']['hrv']['trend'] = 'stable'

    if latest_data.get('rhr'):
        # Note: readiness script looks for 'resting_hr' not 'rhr'
        if 'resting_hr' not in state['fatigue_indicators']:
            state['fatigue_indicators']['resting_hr'] = {}
        state['fatigue_indicators']['resting_hr']['current'] = latest_data['rhr']
        state['fatigue_indicators']['resting_hr']['value'] = latest_data['rhr']
        if rhr_avg:
            state['fatigue_indicators']['resting_hr']['baseline'] = round(rhr_avg)
        # Also update rhr for backward compatibility
        state['fatigue_indicators']['rhr']['value'] = latest_data['rhr']
        if rhr_avg:
            state['fatigue_indicators']['rhr']['baseline'] = round(rhr_avg)
        # Determine trend
        if rhr_avg and latest_data['rhr'] > rhr_avg + 5:
            state['fatigue_indicators']['rhr']['trend'] = 'elevated'
            state['fatigue_indicators']['resting_hr']['trend'] = 'elevated'
        elif rhr_avg and latest_data['rhr'] < rhr_avg - 3:
            state['fatigue_indicators']['rhr']['trend'] = 'low'
            state['fatigue_indicators']['resting_hr']['trend'] = 'low'
        else:
            state['fatigue_indicators']['rhr']['trend'] = 'stable'
            state['fatigue_indicators']['resting_hr']['trend'] = 'stable'

    if latest_data.get('sleep_hours'):
        state['fatigue_indicators']['sleep']['hours'] = latest_data['sleep_hours']
        state['fatigue_indicators']['sleep']['last_night_hours'] = latest_data['sleep_hours']
        if sleep_avg:
            state['fatigue_indicators']['sleep']['7d_avg_hours'] = round(sleep_avg, 1)
        # Calculate quality based on deep + REM ratio
        if latest_data.get('deep_sleep') and latest_data.get('rem_sleep'):
            quality_hours = latest_data['deep_sleep'] + latest_data['rem_sleep']
            quality_pct = (quality_hours / latest_data['sleep_hours']) * 100
            if quality_pct >= 45:
                state['fatigue_indicators']['sleep']['quality'] = 'good'
            elif quality_pct >= 35:
                state['fatigue_indicators']['sleep']['quality'] = 'fair'
            else:
                state['fatigue_indicators']['sleep']['quality'] = 'poor'

    # Update WHOOP recovery data
    if latest_data.get('recovery_score'):
        if 'whoop_recovery' not in state['fatigue_indicators']:
            state['fatigue_indicators']['whoop_recovery'] = {}
        state['fatigue_indicators']['whoop_recovery']['current'] = latest_data['recovery_score']
        if recovery_avg:
            state['fatigue_indicators']['whoop_recovery']['baseline'] = round(recovery_avg)

    # Update health gates with actual values
    state['health_gates']['sleep']['last_night_hours'] = latest_data.get('sleep_hours')
    state['health_gates']['sleep']['7d_avg_hours'] = round(sleep_avg, 1) if sleep_avg else None

    if latest_data.get('hrv') and hrv_avg:
        state['health_gates']['autonomic']['hrv_vs_baseline_pct'] = round((latest_data['hrv'] / hrv_avg) * 100)
    if latest_data.get('rhr') and rhr_avg:
        state['health_gates']['autonomic']['rhr_vs_baseline_pct'] = round((latest_data['rhr'] / rhr_avg) * 100)

    # Update readiness factors with actual values
    state['readiness']['factors']['hrv_status']['value'] = round(latest_data.get('hrv', 0), 1) if latest_data.get('hrv') else None
    state['readiness']['factors']['sleep_status']['value'] = latest_data.get('sleep_hours')
    state['readiness']['factors']['recovery_score']['value'] = latest_data.get('recovery_score')

    # Update baselines
    if hrv_avg:
        state['readiness']['factors']['hrv_status']['baseline'] = round(hrv_avg, 1)
    if rhr_avg:
        state['readiness']['factors']['rhr_status']['baseline'] = round(rhr_avg)
    if recovery_avg:
        state['readiness']['factors']['recovery_score']['baseline'] = round(recovery_avg)

    # Update metadata
    state['timestamp'] = datetime.now().isoformat()
    state['_meta']['last_updated'] = datetime.now().isoformat() + 'Z'
    state['_meta']['updated_by'] = 'import_metrics_export'
    state['_meta']['data_date'] = latest_date

    # Save updated state
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\nUpdated {state_path}")
    return latest_data

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_metrics_export.py <metrics.csv> [athlete_dir]")
        print("Example: python import_metrics_export.py /tmp/metrics.csv athletes/matti-rowe")
        sys.exit(1)

    csv_path = sys.argv[1]
    athlete_dir = sys.argv[2] if len(sys.argv) > 2 else 'athletes/matti-rowe'

    import_metrics(csv_path, athlete_dir)
