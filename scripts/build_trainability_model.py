#!/usr/bin/env python3
"""
Trainability Model Builder
Based on Nate Wilson's Chapter 9 - "Are You Responding to Your Training?"

Implements the Banister Impulse-Response model to quantify:
- k1: Trainability (how much performance you gain per unit load)
- k2: Fatigue sensitivity
- Tau1: Fitness decay rate
- Tau2: Fatigue decay rate
- P0: Baseline performance

Performance metric: Efficiency Factor (Power/HR) from comparable rides.

Usage:
    python build_trainability_model.py --data-dir /path/to/exports
"""

import os
import sys
import glob
import zipfile
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from scipy.optimize import minimize


def extract_and_combine_workouts(zip_pattern: str) -> pd.DataFrame:
    """Extract workout CSVs from multiple zips and combine."""
    all_data = []
    zip_files = sorted(glob.glob(zip_pattern))

    for zip_path in zip_files:
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'workouts.csv' in z.namelist():
                    with z.open('workouts.csv') as f:
                        df = pd.read_csv(f)
                        all_data.append(df)
                        print(f"  Loaded {len(df)} rows from {os.path.basename(zip_path)}")
        except Exception as e:
            print(f"  Warning: Could not process {zip_path}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)
    return combined.drop_duplicates()


def calculate_efficiency_factor(power: float, hr: float) -> float:
    """
    Calculate Efficiency Factor (EF) = Normalized Power / Avg HR

    Higher EF = more aerobically efficient.
    This is the performance anchor for the Banister model.
    """
    if pd.isna(power) or pd.isna(hr) or hr == 0:
        return np.nan
    return power / hr


def filter_comparable_rides(df: pd.DataFrame,
                           min_duration_hours: float = 1.0,
                           max_if: float = 0.80,
                           min_hr: float = 100) -> pd.DataFrame:
    """
    Filter to comparable aerobic rides for EF calculation.

    We want steady-state, sub-threshold rides where EF is meaningful:
    - Duration >= 1 hour
    - IF <= 0.80 (aerobic, not threshold/VO2max efforts)
    - Avg HR >= 100 (actually riding, not just rolling)
    """
    mask = (
        (df['TimeTotalInHours'] >= min_duration_hours) &
        (df['IF'] <= max_if) &
        (df['IF'] > 0) &
        (df['HeartRateAverage'] >= min_hr) &
        (df['PowerAverage'] > 0)
    )
    return df[mask].copy()


def process_workouts_for_banister(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process workout data for Banister model.

    Returns daily dataframe with:
    - date
    - Load (TSS)
    - Performance (Efficiency Factor, when available)
    """
    # Work on a copy to avoid SettingWithCopyWarning
    df = df.copy()

    # Parse dates
    df['date'] = pd.to_datetime(df['WorkoutDay']).dt.date

    # Convert columns
    numeric_cols = ['TSS', 'IF', 'PowerAverage', 'HeartRateAverage', 'TimeTotalInHours']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Calculate EF for each workout
    df['EF'] = df.apply(
        lambda row: calculate_efficiency_factor(row['PowerAverage'], row['HeartRateAverage']),
        axis=1
    )

    # Aggregate by date
    # Load = sum of TSS
    # Performance = mean EF (only from comparable rides)
    daily_tss = df.groupby('date')['TSS'].sum().reset_index()
    daily_tss.columns = ['date', 'Load']

    # For performance, only use comparable rides
    comparable = filter_comparable_rides(df)
    daily_ef = comparable.groupby('date')['EF'].mean().reset_index()
    daily_ef.columns = ['date', 'Performance']

    # Merge
    result = pd.merge(daily_tss, daily_ef, on='date', how='left')
    result = result.sort_values('date').reset_index(drop=True)

    return result


def update_load(prev_value: float, load: float, tau: float) -> float:
    """Exponential decay update for fitness/fatigue."""
    decay = np.exp(-1 / tau)
    return load * (1 - decay) + prev_value * decay


def optimize_banister(params, data):
    """
    Banister model loss function (RMSE).

    Performance = k1 * CTL - k2 * ATL + P0
    """
    tau1, tau2, k1, k2, p0 = params

    loads = data['Load'].values
    perf_actual = data['Performance'].values

    # Initialize at reasonable training load
    ctl = 50.0
    atl = 50.0

    errors = []

    for i in range(len(loads)):
        load = loads[i] if not np.isnan(loads[i]) else 0
        ctl = update_load(ctl, load, tau1)
        atl = update_load(atl, load, tau2)

        if not np.isnan(perf_actual[i]):
            perf_pred = k1 * ctl - k2 * atl + p0
            errors.append((perf_pred - perf_actual[i]) ** 2)

    if not errors:
        return 1e6

    return np.sqrt(np.mean(errors))


def optimize_banister_tsb(params, data):
    """
    Simplified Banister using TSB instead of separate ATL penalty.

    Performance = k1 * CTL + TSB + P0

    This makes k1 directly comparable across athletes.
    """
    tau1, tau2, k1, p0 = params

    loads = data['Load'].values
    perf_actual = data['Performance'].values

    ctl = 50.0
    atl = 50.0

    errors = []

    for i in range(len(loads)):
        load = loads[i] if not np.isnan(loads[i]) else 0
        ctl = update_load(ctl, load, tau1)
        atl = update_load(atl, load, tau2)
        tsb = ctl - atl

        if not np.isnan(perf_actual[i]):
            perf_pred = k1 * ctl + tsb + p0
            errors.append((perf_pred - perf_actual[i]) ** 2)

    if not errors:
        return 1e6

    return np.sqrt(np.mean(errors))


def classify_responder(k1: float) -> dict:
    """
    Classify athlete response type based on k1.

    From Chapter 9:
    - Quick Responders (~15%): k1 > 0.3
    - Medium Responders (~70%): k1 = 0.1-0.3
    - Slow Responders (~15%): k1 < 0.1
    """
    if k1 > 0.3:
        return {
            'type': 'Quick Responder',
            'percentage': '~15% of athletes',
            'characteristics': [
                'Improve fast, respond strongly to small doses',
                'Naturally strong, high lactate producers',
                'Fragile if overcooked - excess intensity breaks them',
                'Need restraint, patience, and recovery discipline'
            ],
            'coaching_implications': [
                'Less volume needed for adaptation',
                'Focus on quality over quantity',
                'Longer recovery between hard sessions',
                'Aggressive tapers work well'
            ]
        }
    elif k1 >= 0.1:
        return {
            'type': 'Medium Responder',
            'percentage': '~70% of athletes',
            'characteristics': [
                'Normal adaptation speed',
                'Balanced physiology',
                'Respond best to consistent, mixed-intensity training',
                'Progress comes from long, boring blocks done well'
            ],
            'coaching_implications': [
                'Standard periodization works',
                'Consistency is key',
                'Can handle moderate intensity distribution',
                'Standard 7-14 day tapers'
            ]
        }
    else:
        return {
            'type': 'Slow Responder',
            'percentage': '~15% of athletes',
            'characteristics': [
                'Often smaller, lower muscle mass',
                'High untrained VO2max - less upside',
                'Poor lactate production, strong recovery',
                'Require high volume + intensity over multiple seasons'
            ],
            'coaching_implications': [
                'Need more training stimulus than average',
                'Win by durability, not speed of adaptation',
                'Longer build phases required',
                'Extended tapers may not help - stay sharp'
            ]
        }


def run_banister_model(data: pd.DataFrame, use_tsb_model: bool = True) -> dict:
    """
    Run the Banister optimizer and return results.
    """
    perf_count = data['Performance'].notna().sum()
    print(f"\nPerformance data points: {perf_count}")

    if perf_count < 10:
        raise ValueError(f"Not enough performance data points: {perf_count}. Need at least 10.")

    if use_tsb_model:
        # TSB-based model (4 parameters)
        initial_guess = [42, 7, 0.02, 1.5]  # tau1, tau2, k1, p0
        bounds = [
            (10, 100),  # Tau1 (wider range)
            (3, 30),    # Tau2 (wider range - was hitting 20 ceiling)
            (0.0001, 1.0),  # k1 (scaled for EF units)
            (0, 5)      # P0
        ]

        result = minimize(
            optimize_banister_tsb,
            initial_guess,
            args=(data,),
            bounds=bounds,
            method='L-BFGS-B'
        )

        tau1, tau2, k1, p0 = result.x
        k2 = None

    else:
        # Full 5-parameter model
        initial_guess = [45, 7, 0.02, 0.02, 1.0]
        bounds = [
            (10, 80),   # Tau1
            (3, 20),    # Tau2
            (0.001, 0.5),  # k1
            (0.001, 0.5),  # k2
            (0, 5)      # P0
        ]

        result = minimize(
            optimize_banister,
            initial_guess,
            args=(data,),
            bounds=bounds,
            method='L-BFGS-B'
        )

        tau1, tau2, k1, k2, p0 = result.x

    # Classify responder type
    # Note: k1 scale depends on performance metric (EF ~1.0-2.0 range)
    # We need to normalize k1 to standard scale
    # If EF mean is ~1.5, and CTL mean is ~80, then k1 of 0.01 means
    # 80 CTL * 0.01 = 0.8 EF contribution
    # To convert to standard k1 scale, multiply by performance scale
    perf_mean = data['Performance'].mean()
    k1_normalized = k1 * 100  # Scale for interpretation

    responder_info = classify_responder(k1_normalized)

    return {
        'tau1': tau1,
        'tau2': tau2,
        'k1': k1,
        'k1_normalized': k1_normalized,
        'k2': k2,
        'p0': p0,
        'rmse': result.fun,
        'responder': responder_info,
        'n_performance': perf_count,
        'perf_mean': perf_mean,
        'model_type': 'tsb' if use_tsb_model else 'full'
    }


def main():
    parser = argparse.ArgumentParser(description='Build athlete trainability model')
    parser.add_argument('--data-dir', type=str,
                        default='/Users/mattirowe/Desktop/Athlete OS Docs/Matti',
                        help='Directory containing TrainingPeaks zip exports')
    parser.add_argument('--output-dir', type=str,
                        default='/Users/mattirowe/athlete-coaching-system/data/matti-rowe',
                        help='Output directory for model results')
    parser.add_argument('--min-duration', type=float, default=1.0,
                        help='Minimum ride duration (hours) for EF calculation')
    parser.add_argument('--max-if', type=float, default=0.80,
                        help='Maximum IF for EF rides (aerobic only)')

    args = parser.parse_args()

    print("=" * 60)
    print("TRAINABILITY MODEL BUILDER")
    print("Based on Chapter 9: Are You Responding to Your Training?")
    print("=" * 60)

    os.makedirs(args.output_dir, exist_ok=True)

    # Load workout data
    print("\n[1/4] Loading workout data...")
    workout_pattern = os.path.join(args.data_dir, 'WorkoutExport*.zip')
    workouts_df = extract_and_combine_workouts(workout_pattern)
    print(f"  Total workout rows: {len(workouts_df)}")

    if workouts_df.empty:
        print("ERROR: No workout data found")
        return

    # Check available columns
    print("\n[2/4] Processing for Banister model...")
    required_cols = ['WorkoutDay', 'TSS', 'IF', 'PowerAverage', 'HeartRateAverage', 'TimeTotalInHours']
    missing = [c for c in required_cols if c not in workouts_df.columns]
    if missing:
        print(f"ERROR: Missing columns: {missing}")
        return

    # Filter to rides with power and HR data
    valid_rides = workouts_df[
        (workouts_df['PowerAverage'].notna()) &
        (workouts_df['HeartRateAverage'].notna()) &
        (workouts_df['TSS'].notna())
    ].copy()
    print(f"  Rides with power + HR + TSS: {len(valid_rides)}")

    # Convert numeric columns early
    for col in ['TSS', 'IF', 'PowerAverage', 'HeartRateAverage', 'TimeTotalInHours']:
        if col in valid_rides.columns:
            valid_rides[col] = pd.to_numeric(valid_rides[col], errors='coerce')

    # Calculate EF for all valid rides
    valid_rides['EF'] = valid_rides['PowerAverage'] / valid_rides['HeartRateAverage']

    # Process for Banister
    banister_data = process_workouts_for_banister(valid_rides)
    print(f"  Days with Load: {banister_data['Load'].notna().sum()}")
    print(f"  Days with Performance (EF): {banister_data['Performance'].notna().sum()}")

    # Filter comparable rides stats
    comparable = filter_comparable_rides(valid_rides, args.min_duration, args.max_if)
    print(f"\n  Comparable rides (>{args.min_duration}h, IF<{args.max_if}):")
    print(f"    Count: {len(comparable)}")
    if len(comparable) > 0:
        print(f"    EF range: {comparable['EF'].min():.3f} - {comparable['EF'].max():.3f}")
        print(f"    EF mean: {comparable['EF'].mean():.3f}")

    # Run optimizer
    print("\n[3/4] Running Banister optimizer...")
    try:
        results = run_banister_model(banister_data)
    except ValueError as e:
        print(f"ERROR: {e}")
        print("\nSaving raw data for inspection...")
        banister_data.to_csv(os.path.join(args.output_dir, 'banister_data.csv'), index=False)
        return

    # Print results
    print("\n" + "=" * 60)
    print("MODEL RESULTS")
    print("=" * 60)

    print(f"\nBanister Parameters (YOUR physiology):")
    print(f"  Tau1 (Fitness decay): {results['tau1']:.1f} days")
    print(f"  Tau2 (Fatigue decay): {results['tau2']:.1f} days")
    print(f"  k1 (Trainability): {results['k1']:.4f} (raw)")
    print(f"  k1 (Normalized): {results['k1_normalized']:.3f}")
    if results['k2']:
        print(f"  k2 (Fatigue cost): {results['k2']:.4f}")
    print(f"  P0 (Baseline EF): {results['p0']:.3f}")
    print(f"  Model RMSE: {results['rmse']:.4f}")

    print(f"\n" + "-" * 60)
    print(f"RESPONDER CLASSIFICATION: {results['responder']['type'].upper()}")
    print(f"({results['responder']['percentage']})")
    print("-" * 60)

    print("\nCharacteristics:")
    for char in results['responder']['characteristics']:
        print(f"  • {char}")

    print("\nCoaching Implications:")
    for imp in results['responder']['coaching_implications']:
        print(f"  → {imp}")

    # Taper recommendation based on Tau2
    print(f"\nTaper Strategy (based on Tau2={results['tau2']:.1f}):")
    if results['tau2'] < 7:
        print("  → Short, aggressive taper (5-7 days)")
        print("  → You shed fatigue quickly")
    elif results['tau2'] < 12:
        print("  → Standard taper (10-14 days)")
        print("  → Typical fatigue dynamics")
    else:
        print("  → Extended taper (14-21 days)")
        print("  → Fatigue lingers - start early")

    # Save results
    print("\n[4/4] Saving results...")

    output = {
        'athlete_id': 'matti-rowe',
        'model_date': datetime.now().isoformat(),
        'model_type': results['model_type'],
        'parameters': {
            'tau1': float(results['tau1']),
            'tau2': float(results['tau2']),
            'k1': float(results['k1']),
            'k1_normalized': float(results['k1_normalized']),
            'k2': float(results['k2']) if results['k2'] else None,
            'p0': float(results['p0'])
        },
        'performance_metric': 'Efficiency Factor (Power/HR)',
        'rmse': float(results['rmse']),
        'n_performance': int(results['n_performance']),
        'responder_type': results['responder']['type'],
        'responder_details': results['responder']
    }

    with open(os.path.join(args.output_dir, 'trainability_model_results.json'), 'w') as f:
        json.dump(output, f, indent=2)

    banister_data.to_csv(os.path.join(args.output_dir, 'banister_data.csv'), index=False)

    print(f"\nSaved to {args.output_dir}:")
    print(f"  - trainability_model_results.json")
    print(f"  - banister_data.csv")

    # Key insight
    print("\n" + "=" * 60)
    print("KEY INSIGHT")
    print("=" * 60)
    print(f"""
Your k1 (trainability) tells you how much performance you gain
per unit of training load.

k1 = {results['k1_normalized']:.3f} means:
  • Every 10 CTL increase → ~{results['k1'] * 10:.3f} EF improvement
  • Your rate of adaptation is {"above" if results['k1_normalized'] > 0.2 else "around" if results['k1_normalized'] > 0.1 else "below"} average

This is the return on your training investment.
PMC tracks the cost (load). This model tracks the return (adaptation).
""")


if __name__ == '__main__':
    main()
