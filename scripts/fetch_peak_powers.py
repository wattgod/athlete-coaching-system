#!/usr/bin/env python3
"""
Fetch Peak Powers from Intervals.icu

Calculates peak 3min, 5min, 20min powers from activity streams
for use in Banister trainability model.

Setup:
    export INTERVALS_API_KEY="your_key_here"
    python scripts/fetch_peak_powers.py

Or with inline key:
    python scripts/fetch_peak_powers.py --api-key "your_key"
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
import numpy as np
import pandas as pd
from scipy.optimize import minimize


class IntervalsPeakPowers:
    """Fetch and calculate peak powers from Intervals.icu"""

    BASE_URL = "https://intervals.icu/api/v1"

    def __init__(self, api_key, athlete_id="0"):
        self.api_key = api_key
        self.athlete_id = athlete_id
        self.auth = HTTPBasicAuth("API_KEY", api_key)
        self.session = requests.Session()
        self.session.auth = self.auth

    def test_connection(self):
        """Test API connection"""
        try:
            response = self.session.get(f"{self.BASE_URL}/athlete/{self.athlete_id}")
            response.raise_for_status()
            athlete = response.json()
            print(f"✓ Connected: {athlete.get('name', 'Unknown')}")
            return athlete
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return None

    def list_activities(self, oldest, newest):
        """List activities in date range"""
        response = self.session.get(
            f"{self.BASE_URL}/athlete/{self.athlete_id}/activities",
            params={"oldest": oldest, "newest": newest}
        )
        response.raise_for_status()
        return response.json()

    def get_power_stream(self, activity_id):
        """Get second-by-second power data"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/activity/{activity_id}/streams",
                params={"types": "watts"}
            )
            response.raise_for_status()
            streams = response.json()

            for stream in streams:
                if stream.get('type') == 'watts':
                    return [w if w else 0 for w in stream.get('data', [])]
            return None
        except:
            return None

    def calculate_peak_power(self, power_data, duration_seconds):
        """
        Calculate peak average power for given duration.

        Uses rolling window to find best effort.
        """
        if not power_data or len(power_data) < duration_seconds:
            return None

        power = np.array(power_data)

        # Rolling average
        rolling = np.convolve(power, np.ones(duration_seconds)/duration_seconds, mode='valid')

        return float(np.max(rolling))

    def fetch_all_peak_powers(self, oldest, newest, durations=[180, 300, 1200]):
        """
        Fetch peak powers for all activities in date range.

        Args:
            oldest: Start date (YYYY-MM-DD)
            newest: End date (YYYY-MM-DD)
            durations: List of durations in seconds [3min, 5min, 20min]

        Returns:
            DataFrame with date, TSS, and peak powers
        """
        print(f"\nFetching activities from {oldest} to {newest}...")
        activities = self.list_activities(oldest, newest)

        # Filter to cycling
        cycling = [a for a in activities if a.get('type') in
                   ['Ride', 'VirtualRide', 'Cycling', 'IndoorCycling']]
        print(f"Found {len(cycling)} cycling activities")

        results = []
        for i, activity in enumerate(cycling):
            activity_id = activity['id']
            date = activity.get('start_date_local', '')[:10]
            tss = activity.get('icu_training_load', 0) or 0

            # Progress
            if (i + 1) % 20 == 0:
                print(f"  Processing {i+1}/{len(cycling)}...")

            # Get power stream
            power = self.get_power_stream(activity_id)
            if not power or len(power) < 180:  # Need at least 3 min of data
                continue

            row = {
                'date': date,
                'activity_id': activity_id,
                'name': activity.get('name', ''),
                'tss': tss,
                'duration_min': len(power) / 60
            }

            # Calculate peak powers
            for duration in durations:
                duration_name = f"peak_{duration//60}min"
                peak = self.calculate_peak_power(power, duration)
                row[duration_name] = round(peak, 1) if peak else None

            results.append(row)

        df = pd.DataFrame(results)
        print(f"\nExtracted peak powers from {len(df)} activities")

        return df


def run_banister_with_peaks(daily_tss, peak_powers, duration_col='peak_5min'):
    """
    Run Banister model using peak power as performance metric.

    Args:
        daily_tss: DataFrame with date, Load (TSS)
        peak_powers: DataFrame with date, peak_Xmin columns
        duration_col: Which peak power column to use

    Returns:
        Dict with model parameters
    """
    # Merge
    peak_df = peak_powers[['date', duration_col]].copy()
    peak_df.columns = ['date', 'Performance']
    peak_df['date'] = pd.to_datetime(peak_df['date']).dt.date

    daily_tss['date'] = pd.to_datetime(daily_tss['date']).dt.date

    merged = pd.merge(daily_tss, peak_df, on='date', how='left')
    merged = merged.sort_values('date').reset_index(drop=True)

    loads = merged['Load'].fillna(0).values
    perfs = merged['Performance'].values

    perf_count = (~pd.isna(perfs)).sum()
    print(f"\nPerformance data points ({duration_col}): {perf_count}")

    if perf_count < 15:
        print(f"Not enough {duration_col} data for model")
        return None

    # Banister update function
    def update_load(prev, load, tau):
        decay = np.exp(-1/tau)
        return load * (1-decay) + prev * decay

    def objective(params):
        tau1, tau2, k1, k2, p0 = params
        ctl, atl = 50.0, 50.0
        errors = []

        for i in range(len(loads)):
            ctl = update_load(ctl, loads[i], tau1)
            atl = update_load(atl, loads[i], tau2)

            if not np.isnan(perfs[i]):
                pred = k1 * ctl - k2 * atl + p0
                errors.append((pred - perfs[i])**2)

        return np.sqrt(np.mean(errors))

    # Optimize
    result = minimize(
        objective,
        [42, 7, 1.0, 1.0, 250],  # tau1, tau2, k1, k2, p0
        bounds=[(15, 80), (3, 20), (0.01, 10), (0.01, 10), (0, 500)],
        method='L-BFGS-B'
    )

    tau1, tau2, k1, k2, p0 = result.x

    # Classify
    if k1 > 0.3:
        responder = "Quick Responder"
    elif k1 >= 0.1:
        responder = "Medium Responder"
    else:
        responder = "Slow Responder"

    return {
        'metric': duration_col,
        'n': perf_count,
        'tau1': tau1,
        'tau2': tau2,
        'k1': k1,
        'k2': k2,
        'p0': p0,
        'rmse': result.fun,
        'responder': responder,
        'perf_mean': np.nanmean(perfs),
        'perf_std': np.nanstd(perfs)
    }


def main():
    parser = argparse.ArgumentParser(description='Fetch peak powers from Intervals.icu')
    parser.add_argument('--api-key', default=os.environ.get('INTERVALS_API_KEY'),
                        help='Intervals.icu API key')
    parser.add_argument('--athlete', default='0', help='Athlete ID')
    parser.add_argument('--days', type=int, default=365*3,
                        help='Days of history to fetch (default: 3 years)')
    parser.add_argument('--output-dir', default='/Users/mattirowe/athlete-coaching-system/data/matti-rowe',
                        help='Output directory')

    args = parser.parse_args()

    if not args.api_key:
        print("Error: No API key.")
        print("\nGet your key from: intervals.icu → Settings → Developer")
        print("\nThen run:")
        print("  export INTERVALS_API_KEY='your_key'")
        print("  python scripts/fetch_peak_powers.py")
        sys.exit(1)

    print("=" * 60)
    print("PEAK POWER EXTRACTION FOR BANISTER MODEL")
    print("=" * 60)

    # Connect
    client = IntervalsPeakPowers(args.api_key, args.athlete)
    athlete = client.test_connection()
    if not athlete:
        sys.exit(1)

    # Fetch peak powers
    newest = datetime.now().strftime("%Y-%m-%d")
    oldest = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    peak_df = client.fetch_all_peak_powers(oldest, newest, durations=[180, 300, 1200])

    if peak_df.empty:
        print("No activities with power data found")
        sys.exit(1)

    # Save raw peak powers
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    peak_df.to_csv(output_dir / 'peak_powers.csv', index=False)
    print(f"\nSaved: {output_dir}/peak_powers.csv")

    # Create daily TSS from peak data
    daily_tss = peak_df.groupby('date')['tss'].sum().reset_index()
    daily_tss.columns = ['date', 'Load']

    # Run Banister on each peak duration
    print("\n" + "=" * 60)
    print("BANISTER MODEL BY PEAK POWER DURATION")
    print("=" * 60)

    results = []
    for col in ['peak_3min', 'peak_5min', 'peak_20min']:
        if col in peak_df.columns:
            r = run_banister_with_peaks(daily_tss.copy(), peak_df.copy(), col)
            if r:
                results.append(r)
                print(f"\n{col}:")
                print(f"  n={r['n']} samples, mean={r['perf_mean']:.0f}W ±{r['perf_std']:.0f}")
                print(f"  Tau1={r['tau1']:.1f}d, Tau2={r['tau2']:.1f}d")
                print(f"  k1={r['k1']:.3f}, k2={r['k2']:.3f}")
                print(f"  → {r['responder']}")

    # Summary comparison
    if results:
        print("\n" + "=" * 60)
        print("COMPARISON SUMMARY")
        print("=" * 60)
        print(f"{'Metric':<15} {'n':>5} {'Tau1':>6} {'Tau2':>6} {'k1':>6} {'Responder':<20}")
        print("-" * 60)
        for r in results:
            print(f"{r['metric']:<15} {r['n']:>5} {r['tau1']:>6.1f} {r['tau2']:>6.1f} {r['k1']:>6.2f} {r['responder']:<20}")

        # Save results
        with open(output_dir / 'peak_power_banister.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved: {output_dir}/peak_power_banister.json")


if __name__ == '__main__':
    main()
