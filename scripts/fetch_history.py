#!/usr/bin/env python3
"""
Fetch Historical Data for Dashboard Views

Fetches PMC history and activity list from Intervals.icu for Calendar and Trends views.

Usage:
    python scripts/fetch_history.py matti-rowe
    python scripts/fetch_history.py matti-rowe --days 90
    python scripts/fetch_history.py matti-rowe --output /path/to/output.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.intervals_sync import IntervalsSync


def load_profile(athlete_dir: Path) -> Dict[str, Any]:
    """Load athlete profile from YAML."""
    profile_file = athlete_dir / "profile.yaml"
    if not profile_file.exists():
        return {}
    with open(profile_file) as f:
        return yaml.safe_load(f)


def get_intervals_client(profile: Dict) -> Optional[IntervalsSync]:
    """Get Intervals.icu client from profile or env."""
    api_key = os.environ.get("INTERVALS_API_KEY")
    if not api_key:
        print("Warning: INTERVALS_API_KEY not set")
        return None

    # Get athlete ID from profile or default to "0" (self)
    athlete_id = profile.get("integrations", {}).get("intervals_icu", {}).get("athlete_id", "0")

    return IntervalsSync(api_key, athlete_id)


def fetch_pmc_history(client: IntervalsSync, days: int = 90) -> List[Dict]:
    """
    Fetch PMC (Performance Management Chart) history.

    Returns list of daily records with CTL, ATL, TSB, ramp rate.
    """
    newest = datetime.now().strftime("%Y-%m-%d")
    oldest = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"Fetching PMC history: {oldest} to {newest}")

    wellness = client.get_wellness(oldest=oldest, newest=newest)

    pmc_data = []
    for record in wellness:
        date = record.get("id")  # Date is stored as 'id'
        if not date:
            continue

        ctl = record.get("ctl")
        atl = record.get("atl")

        pmc_data.append({
            "date": date,
            "ctl": round(ctl, 1) if ctl else None,
            "atl": round(atl, 1) if atl else None,
            "tsb": round(ctl - atl, 1) if ctl and atl else None,
            "ramp_rate": round(record.get("rampRate", 0), 2) if record.get("rampRate") else None,
            "weight": record.get("weight"),
            "rhr": record.get("restingHR"),
            "hrv": record.get("hrv"),
            "sleep_hours": round(record.get("sleepTime", 0) / 3600, 1) if record.get("sleepTime") else None,
        })

    print(f"  Retrieved {len(pmc_data)} days of PMC data")
    return pmc_data


def fetch_activity_history(client: IntervalsSync, days: int = 90) -> List[Dict]:
    """
    Fetch activity list for date range.

    Returns list of activities with date, name, type, TSS, duration.
    """
    newest = datetime.now().strftime("%Y-%m-%d")
    oldest = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"Fetching activities: {oldest} to {newest}")

    activities = client.list_activities(oldest=oldest, newest=newest)

    activity_data = []
    for activity in activities:
        # Extract date from start_date_local
        start = activity.get("start_date_local", "")
        date = start[:10] if start else None
        if not date:
            continue

        # Get activity type - filter to cycling only
        activity_type = activity.get("type", "")
        if activity_type not in ["Ride", "VirtualRide", "Cycling", "IndoorCycling", "MountainBikeRide", "GravelRide"]:
            continue

        activity_data.append({
            "date": date,
            "id": activity.get("id"),
            "name": activity.get("name", "Workout"),
            "type": activity_type,
            "tss": round(activity.get("icu_training_load", 0)) if activity.get("icu_training_load") else None,
            "duration_minutes": round(activity.get("moving_time", 0) / 60) if activity.get("moving_time") else None,
            "distance_km": round(activity.get("distance", 0) / 1000, 1) if activity.get("distance") else None,
            "intensity": round(activity.get("icu_intensity", 0), 2) if activity.get("icu_intensity") else None,
            "avg_power": activity.get("icu_weighted_avg_watts"),
        })

    print(f"  Retrieved {len(activity_data)} cycling activities")
    return activity_data


def get_race_calendar(profile: Dict) -> List[Dict]:
    """Extract race calendar from profile."""
    events = profile.get("goals", {}).get("events", [])
    races = []

    for event in events:
        if event.get("date"):
            races.append({
                "date": event["date"],
                "name": event.get("name", "Race"),
                "priority": event.get("priority", "C"),
                "distance": event.get("distance"),
                "type": "race",
            })

    return races


def generate_history_data(
    athlete_name: str,
    days: int = 90,
    include_pmc: bool = True,
    include_activities: bool = True,
) -> Dict[str, Any]:
    """
    Generate complete history data for dashboard.

    Args:
        athlete_name: Athlete directory name
        days: Number of days of history to fetch
        include_pmc: Include PMC/wellness data
        include_activities: Include activity list

    Returns:
        Dict with pmc, activities, races, and metadata
    """
    base_dir = Path(__file__).parent.parent
    athlete_dir = base_dir / "athletes" / athlete_name

    if not athlete_dir.exists():
        raise FileNotFoundError(f"Athlete directory not found: {athlete_dir}")

    profile = load_profile(athlete_dir)
    client = get_intervals_client(profile)

    history = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "athlete": athlete_name,
            "days": days,
        },
        "pmc": [],
        "activities": [],
        "races": get_race_calendar(profile),
    }

    if client:
        if include_pmc:
            try:
                history["pmc"] = fetch_pmc_history(client, days)
            except Exception as e:
                print(f"Warning: Failed to fetch PMC: {e}")

        if include_activities:
            try:
                history["activities"] = fetch_activity_history(client, days)
            except Exception as e:
                print(f"Warning: Failed to fetch activities: {e}")
    else:
        print("Skipping Intervals.icu fetch - no API key")

    return history


def load_cache(athlete_dir: Path, max_age_hours: int = 4) -> Optional[Dict]:
    """Load cached history if still valid."""
    cache_file = athlete_dir / "history_cache.json"
    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            cache = json.load(f)

        # Check age
        generated = cache.get("_meta", {}).get("generated_at")
        if generated:
            gen_time = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - gen_time).total_seconds() / 3600
            if age_hours < max_age_hours:
                print(f"Using cached history ({age_hours:.1f}h old)")
                return cache

        print("Cache expired, fetching fresh data")
    except Exception as e:
        print(f"Cache read error: {e}")

    return None


def save_cache(athlete_dir: Path, data: Dict):
    """Save history data to cache."""
    cache_file = athlete_dir / "history_cache.json"
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Cached history to {cache_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch historical data for dashboard views"
    )
    parser.add_argument(
        "athlete_name",
        help="Athlete folder name (e.g., matti-rowe)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=90,
        help="Days of history to fetch (default: 90)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: athletes/{name}/history_cache.json)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache and fetch fresh data"
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Output to stdout instead of file"
    )

    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    athlete_dir = base_dir / "athletes" / args.athlete_name

    if not athlete_dir.exists():
        print(f"Error: Athlete directory not found: {athlete_dir}")
        sys.exit(1)

    # Try cache first
    if not args.no_cache and not args.stdout:
        cached = load_cache(athlete_dir)
        if cached:
            print("Using cached data")
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(cached, f, indent=2)
            return

    # Fetch fresh data
    history = generate_history_data(args.athlete_name, days=args.days)

    # Output
    if args.stdout:
        print(json.dumps(history, indent=2))
    else:
        output_path = args.output or (athlete_dir / "history_cache.json")
        output_path = Path(output_path)
        with open(output_path, "w") as f:
            json.dump(history, f, indent=2)
        print(f"History data written to: {output_path}")


if __name__ == "__main__":
    main()
