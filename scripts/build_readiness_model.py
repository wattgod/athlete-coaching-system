#!/usr/bin/env python3
"""
Readiness Model Builder
Based on Nate Wilson's Chapter 13 methodology

Builds athlete-specific decision trees to predict session feeling
from morning metrics and planned training load.

Usage:
    python build_readiness_model.py --metrics-dir /path/to/metrics --workouts-dir /path/to/workouts
"""

import os
import sys
import math
import glob
import zipfile
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error
from sklearn.linear_model import LinearRegression


def extract_and_combine_csvs(zip_pattern: str, csv_name: str) -> pd.DataFrame:
    """Extract CSV files from multiple zips and combine into single DataFrame."""
    all_data = []
    zip_files = sorted(glob.glob(zip_pattern))

    for zip_path in zip_files:
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                if csv_name in z.namelist():
                    with z.open(csv_name) as f:
                        df = pd.read_csv(f)
                        all_data.append(df)
                        print(f"  Loaded {len(df)} rows from {os.path.basename(zip_path)}")
        except Exception as e:
            print(f"  Warning: Could not process {zip_path}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)
    return combined.drop_duplicates()


def process_metrics(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Process raw metrics export into pivoted format with one row per date.

    Input format: Timestamp, Type, Value
    Output format: date, HRV, Pulse, Sleep Hours, etc.
    """
    if metrics_df.empty:
        return pd.DataFrame()

    # Parse timestamp and extract date
    metrics_df['Timestamp'] = pd.to_datetime(metrics_df['Timestamp'])
    metrics_df['date'] = metrics_df['Timestamp'].dt.date

    # Pivot to get one row per date with columns for each metric type
    pivoted = metrics_df.pivot_table(
        index='date',
        columns='Type',
        values='Value',
        aggfunc='first'
    ).reset_index()

    # Clean column names
    pivoted.columns.name = None

    return pivoted


def process_workouts(workouts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Process raw workouts export.

    Key columns: WorkoutDay, TSS, IF, Feeling, PowerAverage, TimeTotalInHours
    """
    if workouts_df.empty:
        return pd.DataFrame()

    # Parse date
    workouts_df['date'] = pd.to_datetime(workouts_df['WorkoutDay']).dt.date

    # Convert numeric columns
    numeric_cols = ['TSS', 'IF', 'Feeling', 'PowerAverage', 'TimeTotalInHours',
                    'HeartRateAverage', 'CadenceAverage']
    for col in numeric_cols:
        if col in workouts_df.columns:
            workouts_df[col] = pd.to_numeric(workouts_df[col], errors='coerce')

    # Aggregate by date (sum TSS, mean IF, mean Feeling for multi-workout days)
    agg_dict = {}
    if 'TSS' in workouts_df.columns:
        agg_dict['TSS'] = 'sum'
    if 'IF' in workouts_df.columns:
        agg_dict['IF'] = 'mean'
    if 'Feeling' in workouts_df.columns:
        agg_dict['Feeling'] = 'mean'
    if 'TimeTotalInHours' in workouts_df.columns:
        agg_dict['TimeTotalInHours'] = 'sum'
    if 'PowerAverage' in workouts_df.columns:
        agg_dict['PowerAverage'] = 'mean'

    if not agg_dict:
        return pd.DataFrame()

    daily = workouts_df.groupby('date').agg(agg_dict).reset_index()

    return daily


def calculate_ctl(tss_series: pd.Series, start_value: float = 50.0) -> pd.Series:
    """Calculate Chronic Training Load (42-day exponential moving average)."""
    ctl = [start_value]
    decay = math.exp(-1/42)

    for i in range(1, len(tss_series)):
        tss = tss_series.iloc[i] if not pd.isna(tss_series.iloc[i]) else 0
        new_ctl = tss * (1 - decay) + ctl[-1] * decay
        ctl.append(new_ctl)

    return pd.Series(ctl, index=tss_series.index)


def calculate_atl(tss_series: pd.Series, start_value: float = 50.0) -> pd.Series:
    """Calculate Acute Training Load (7-day exponential moving average)."""
    atl = [start_value]
    decay = math.exp(-1/7)

    for i in range(1, len(tss_series)):
        tss = tss_series.iloc[i] if not pd.isna(tss_series.iloc[i]) else 0
        new_atl = tss * (1 - decay) + atl[-1] * decay
        atl.append(new_atl)

    return pd.Series(atl, index=tss_series.index)


def engineer_features(data: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features for the readiness model.

    Creates 7-day rolling averages for all wellness metrics.
    """
    df = data.copy()

    # Sort by date
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Fill missing TSS with 0 (rest days)
    if 'TSS' in df.columns:
        df['TSS'] = df['TSS'].fillna(0)

    # Calculate CTL, ATL, TSB
    if 'TSS' in df.columns:
        df['CTL'] = calculate_ctl(df['TSS'])
        df['ATL'] = calculate_atl(df['TSS'])
        df['TSB'] = df['CTL'] - df['ATL']

    # 7-day rolling averages for wellness metrics
    rolling_cols = ['HRV', 'Pulse', 'Sleep Hours']
    for col in rolling_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df[f'{col}_7'] = df[col].rolling(window=7, min_periods=1).mean()

    # Invert Feeling if needed (TrainingPeaks exports it backward)
    # 1 = sad, 5 = happy in TP → we want 1 = sad (bad), 5 = happy (good)
    # Actually, let's check the data first and not assume

    return df


def train_readiness_model(data: pd.DataFrame, max_depth: int = 4) -> dict:
    """
    Train a decision tree to predict session Feeling.

    Returns dict with model, feature importances, and metrics.
    """
    if 'Feeling' not in data.columns:
        raise ValueError("No 'Feeling' column in data")

    # Start with core training load features (always available from workout data)
    core_features = ['TSS', 'IF', 'CTL', 'TSB', 'ATL']

    # Optional wellness features (may have limited data)
    wellness_features = ['HRV_7', 'Pulse_7', 'Sleep Hours_7']

    # Filter to rows with valid Feeling
    feeling_data = data[data['Feeling'].notna()].copy()
    print(f"Sessions with Feeling data: {len(feeling_data)}")

    # Check which wellness features have enough data (>50% coverage)
    available_wellness = []
    for f in wellness_features:
        if f in feeling_data.columns:
            coverage = feeling_data[f].notna().sum() / len(feeling_data)
            print(f"  {f}: {coverage*100:.0f}% coverage")
            if coverage > 0.5:
                available_wellness.append(f)

    # Use core features + any well-covered wellness features
    features = [f for f in core_features if f in feeling_data.columns]
    features.extend(available_wellness)

    print(f"Using features: {features}")

    # Filter to rows with valid features
    model_data = feeling_data[features + ['Feeling']].dropna()

    if len(model_data) < 20:
        raise ValueError(f"Not enough data points with valid Feeling: {len(model_data)}")

    print(f"\nTraining on {len(model_data)} sessions with valid Feeling scores")
    print(f"Features: {features}")

    X = model_data[features]
    y = model_data['Feeling']

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train decision tree
    tree_model = DecisionTreeRegressor(random_state=42, max_depth=max_depth)
    tree_model.fit(X_train, y_train)

    # Compare to linear baseline
    linear_model = LinearRegression()
    linear_model.fit(X_train, y_train)

    # Evaluate both
    tree_pred = tree_model.predict(X_test)
    linear_pred = linear_model.predict(X_test)

    tree_rmse = np.sqrt(mean_squared_error(y_test, tree_pred))
    linear_rmse = np.sqrt(mean_squared_error(y_test, linear_pred))

    # Use whichever model performs better
    if linear_rmse < tree_rmse:
        print(f"\n  Linear model wins (RMSE: {linear_rmse:.3f} vs Tree: {tree_rmse:.3f})")
        best_model = linear_model
        model_type = 'linear'
        # For linear model, use absolute coefficient values as importances
        coef_importances = list(zip(features, np.abs(linear_model.coef_)))
        total = sum(abs(c) for _, c in coef_importances)
        importances = [(f, abs(c)/total) for f, c in coef_importances]
        importances = sorted(importances, key=lambda x: x[1], reverse=True)
        # Also store coefficients for interpretation
        coefficients = dict(zip(features, linear_model.coef_))
    else:
        print(f"\n  Decision Tree wins (RMSE: {tree_rmse:.3f} vs Linear: {linear_rmse:.3f})")
        best_model = tree_model
        model_type = 'tree'
        importances = list(zip(features, tree_model.feature_importances_))
        importances = sorted(importances, key=lambda x: x[1], reverse=True)
        coefficients = None

    test_rmse = min(tree_rmse, linear_rmse)

    return {
        'model': best_model,
        'model_type': model_type,
        'features': features,
        'feature_importances': importances,
        'coefficients': coefficients,
        'tree_rmse': tree_rmse,
        'linear_rmse': linear_rmse,
        'test_rmse': test_rmse,
        'n_train': len(X_train),
        'n_test': len(X_test),
        'feeling_stats': {
            'mean': float(y.mean()),
            'std': float(y.std()),
            'min': float(y.min()),
            'max': float(y.max())
        }
    }


def predict_readiness(model, features: list, metrics: dict, feeling_stats: dict = None) -> dict:
    """
    Predict readiness for a given day.

    Args:
        model: Trained model (DecisionTreeRegressor or LinearRegression)
        features: List of feature names the model expects
        metrics: Dict with feature values for today
        feeling_stats: Dict with mean, std, min, max of training Feeling data

    Returns:
        Dict with predicted feeling, readiness score, and recommendation
    """
    # Build feature vector
    X = pd.DataFrame([{f: metrics.get(f, 0) for f in features}])

    predicted_feel = model.predict(X)[0]

    # Scale to 0-100 based on observed range
    if feeling_stats:
        feel_min = feeling_stats['min']
        feel_max = feeling_stats['max']
        feel_mean = feeling_stats['mean']
        readiness_score = ((predicted_feel - feel_min) / (feel_max - feel_min)) * 100
        # Threshold: above mean = Load, below = Recovery
        ready_to_load = predicted_feel >= feel_mean
    else:
        readiness_score = predicted_feel * 10  # Default scaling
        ready_to_load = predicted_feel >= 4.0

    return {
        'predicted_feel': round(predicted_feel, 2),
        'readiness_score': round(max(0, min(100, readiness_score)), 1),
        'ready_to_load': ready_to_load,
        'recommendation': 'Load' if ready_to_load else 'Recovery'
    }


def main():
    parser = argparse.ArgumentParser(description='Build athlete readiness model')
    parser.add_argument('--data-dir', type=str,
                        default='/Users/mattirowe/Desktop/Athlete OS Docs/Matti',
                        help='Directory containing TrainingPeaks zip exports')
    parser.add_argument('--output-dir', type=str,
                        default='/Users/mattirowe/athlete-coaching-system/data/matti-rowe',
                        help='Output directory for processed data and model')
    parser.add_argument('--max-depth', type=int, default=6,
                        help='Maximum depth of decision tree')

    args = parser.parse_args()

    print("=" * 60)
    print("READINESS MODEL BUILDER")
    print("=" * 60)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Step 1: Extract and combine metrics
    print("\n[1/5] Loading metrics data...")
    metrics_pattern = os.path.join(args.data_dir, 'MetricsExport*.zip')
    metrics_df = extract_and_combine_csvs(metrics_pattern, 'metrics.csv')
    print(f"  Total metrics rows: {len(metrics_df)}")

    # Step 2: Extract and combine workouts
    print("\n[2/5] Loading workouts data...")
    workouts_pattern = os.path.join(args.data_dir, 'WorkoutExport-Skaddla*.zip')
    workouts_df = extract_and_combine_csvs(workouts_pattern, 'workouts.csv')
    print(f"  Total workout rows: {len(workouts_df)}")

    if metrics_df.empty or workouts_df.empty:
        print("ERROR: Could not load data")
        return

    # Step 3: Process data
    print("\n[3/5] Processing data...")
    metrics_processed = process_metrics(metrics_df)
    workouts_processed = process_workouts(workouts_df)

    print(f"  Metrics: {len(metrics_processed)} days")
    print(f"  Workouts: {len(workouts_processed)} days")

    # Merge on date
    data = pd.merge(metrics_processed, workouts_processed, on='date', how='outer')
    data = data.sort_values('date').reset_index(drop=True)
    print(f"  Merged: {len(data)} days")

    # Step 4: Engineer features
    print("\n[4/5] Engineering features...")
    data = engineer_features(data)

    # Check Feeling data
    feeling_count = data['Feeling'].notna().sum() if 'Feeling' in data.columns else 0
    print(f"  Days with Feeling data: {feeling_count}")

    if feeling_count < 20:
        print("\nWARNING: Not enough Feeling data to train model")
        print("Saving processed data for inspection...")
        data.to_csv(os.path.join(args.output_dir, 'processed_data.csv'), index=False)
        print(f"  Saved to {args.output_dir}/processed_data.csv")
        return

    # Step 5: Train model
    print("\n[5/5] Training readiness model...")
    try:
        results = train_readiness_model(data, max_depth=args.max_depth)
    except ValueError as e:
        print(f"ERROR: {e}")
        data.to_csv(os.path.join(args.output_dir, 'processed_data.csv'), index=False)
        return

    # Print results
    print("\n" + "=" * 60)
    print("MODEL RESULTS")
    print("=" * 60)

    print(f"\nData: {results['n_train']} train / {results['n_test']} test sessions")
    print(f"Feeling range: {results['feeling_stats']['min']:.1f} - {results['feeling_stats']['max']:.1f}")
    print(f"Feeling mean: {results['feeling_stats']['mean']:.2f} ± {results['feeling_stats']['std']:.2f}")

    print(f"\nModel Performance:")
    print(f"  Selected Model: {results['model_type'].upper()}")
    print(f"  Tree RMSE: {results['tree_rmse']:.3f}")
    print(f"  Linear RMSE: {results['linear_rmse']:.3f}")
    print(f"  Best RMSE: {results['test_rmse']:.3f}")

    print(f"\nFeature Importances (what matters for YOU):")
    for feature, importance in results['feature_importances']:
        bar = '█' * int(importance * 40)
        print(f"  {feature:20} {importance:.2f} {bar}")

    # If linear model, show interpretation
    if results.get('coefficients'):
        print(f"\nLinear Model Interpretation:")
        for feat, coef in results['coefficients'].items():
            direction = '↑' if coef > 0 else '↓'
            impact = 'better' if coef > 0 else 'worse'
            print(f"  {feat}: {coef:+.4f} (higher {feat} → {direction} feeling {impact})")

    # Save results
    output = {
        'athlete_id': 'matti-rowe',
        'model_date': datetime.now().isoformat(),
        'model_type': results['model_type'],
        'features': results['features'],
        'feature_importances': results['feature_importances'],
        'coefficients': results.get('coefficients'),
        'test_rmse': results['test_rmse'],
        'tree_rmse': results['tree_rmse'],
        'linear_rmse': results['linear_rmse'],
        'feeling_stats': results['feeling_stats'],
        'n_train': results['n_train'],
        'n_test': results['n_test'],
        'max_depth': args.max_depth
    }

    with open(os.path.join(args.output_dir, 'readiness_model_results.json'), 'w') as f:
        json.dump(output, f, indent=2)

    data.to_csv(os.path.join(args.output_dir, 'processed_data.csv'), index=False)

    # Save model
    import pickle
    with open(os.path.join(args.output_dir, 'readiness_model.pkl'), 'wb') as f:
        pickle.dump(results['model'], f)

    print(f"\nSaved to {args.output_dir}:")
    print(f"  - processed_data.csv")
    print(f"  - readiness_model_results.json")
    print(f"  - readiness_model.pkl")

    # Demo prediction - use realistic values from YOUR training data
    print("\n" + "=" * 60)
    print("DEMO PREDICTIONS (using YOUR data ranges)")
    print("=" * 60)
    print(f"(Threshold for 'Load': Feeling >= {results['feeling_stats']['mean']:.2f})")

    # Fresh day scenario - matches "good feeling" pattern from YOUR data
    # High feeling days: mean IF=0.7, mean TSS=104, TSB around 0, CTL~100
    fresh_day = {
        'HRV_7': 55, 'Pulse_7': 52, 'Sleep Hours_7': 7.5,
        'TSS': 65, 'IF': 0.65, 'CTL': 100, 'TSB': 5, 'ATL': 95
    }
    fresh_result = predict_readiness(results['model'], results['features'], fresh_day, results['feeling_stats'])
    features_used = ', '.join([f"{f}={fresh_day.get(f)}" for f in results['features'][:4]])
    print(f"\nFresh day: {features_used}")
    print(f"  Predicted Feel: {fresh_result['predicted_feel']:.1f}")
    print(f"  Readiness: {fresh_result['readiness_score']:.0f}/100")
    print(f"  → {fresh_result['recommendation']}")

    # Moderate day - typical training
    moderate_day = {
        'HRV_7': 45, 'Pulse_7': 55, 'Sleep Hours_7': 7.0,
        'TSS': 100, 'IF': 0.75, 'CTL': 100, 'TSB': -5, 'ATL': 105
    }
    moderate_result = predict_readiness(results['model'], results['features'], moderate_day, results['feeling_stats'])
    features_used = ', '.join([f"{f}={moderate_day.get(f)}" for f in results['features'][:4]])
    print(f"\nModerate day: {features_used}")
    print(f"  Predicted Feel: {moderate_result['predicted_feel']:.1f}")
    print(f"  Readiness: {moderate_result['readiness_score']:.0f}/100")
    print(f"  → {moderate_result['recommendation']}")

    # Hard day scenario - matches "bad feeling" pattern from YOUR data
    # Low feeling days: mean IF=0.8, mean TSS=148, TSB around -4, CTL~100
    hard_day = {
        'HRV_7': 35, 'Pulse_7': 62, 'Sleep Hours_7': 5.5,
        'TSS': 150, 'IF': 0.85, 'CTL': 100, 'TSB': -15, 'ATL': 115
    }
    hard_result = predict_readiness(results['model'], results['features'], hard_day, results['feeling_stats'])
    features_used = ', '.join([f"{f}={hard_day.get(f)}" for f in results['features'][:4]])
    print(f"\nHard day: {features_used}")
    print(f"  Predicted Feel: {hard_result['predicted_feel']:.1f}")
    print(f"  Readiness: {hard_result['readiness_score']:.0f}/100")
    print(f"  → {hard_result['recommendation']}")


if __name__ == '__main__':
    main()
