#!/usr/bin/env python3
"""
Morning Check-In Script

Collects subjective readiness data from the athlete and updates athlete_state.json.
Can be run interactively or with command-line arguments.

Includes optional orthostatic HR test for ANS quadrant detection.

Usage:
    # Interactive mode
    python3 scripts/morning_check_in.py matti-rowe

    # Command-line mode
    python3 scripts/morning_check_in.py matti-rowe --sleep-quality 8 --fatigue 3 --stress 4 --soreness 2 --motivation 8

    # With orthostatic test (lying HR, standing HR after 60s)
    python3 scripts/morning_check_in.py matti-rowe --sleep-quality 8 --fatigue 3 --stress 4 --soreness 2 --motivation 8 --hr-lying 52 --hr-standing 68

    # With notes
    python3 scripts/morning_check_in.py matti-rowe --sleep-quality 7 --fatigue 4 --stress 3 --soreness 2 --motivation 7 --notes "Felt a bit tired waking up"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_athlete_state_path(athlete_name: str) -> Path:
    """Get path to athlete's state file."""
    base_path = Path(__file__).parent.parent / "athletes" / athlete_name
    return base_path / "athlete_state.json"


def load_state(path: Path) -> dict:
    """Load athlete state from JSON file."""
    with open(path) as f:
        return json.load(f)


def save_state(path: Path, state: dict) -> None:
    """Save athlete state to JSON file."""
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def validate_rating(value: int, field_name: str) -> int:
    """Validate that a rating is between 1 and 10."""
    if not 1 <= value <= 10:
        raise ValueError(f"{field_name} must be between 1 and 10, got {value}")
    return value


def validate_hr(value: int, field_name: str) -> int:
    """Validate that a heart rate is within reasonable bounds."""
    if not 30 <= value <= 220:
        raise ValueError(f"{field_name} must be between 30 and 220 bpm, got {value}")
    return value


def prompt_rating(prompt: str, description: str = "") -> int:
    """Prompt user for a rating between 1 and 10."""
    while True:
        try:
            if description:
                print(f"\n{description}")
            value = int(input(f"{prompt} (1-10): "))
            return validate_rating(value, prompt)
        except ValueError as e:
            print(f"Invalid input: {e}. Please enter a number between 1 and 10.")


def prompt_hr(prompt: str, description: str = "") -> int:
    """Prompt user for a heart rate value."""
    while True:
        try:
            if description:
                print(f"\n{description}")
            value = int(input(f"{prompt} (bpm): "))
            return validate_hr(value, prompt)
        except ValueError as e:
            print(f"Invalid input: {e}. Please enter a number between 30 and 220.")


def interactive_check_in() -> dict:
    """Run interactive check-in session."""
    print("\n" + "=" * 50)
    print("  MORNING CHECK-IN")
    print("=" * 50)
    print("\nRate the following on a scale of 1-10:")
    print("(1 = worst/lowest, 10 = best/highest)\n")

    data = {}

    # Sleep quality
    data["sleep_quality"] = prompt_rating(
        "Sleep quality",
        "How well did you sleep? (1=terrible, 10=amazing)"
    )

    # Fatigue level (inverted - low number = good)
    data["fatigue_level"] = prompt_rating(
        "Fatigue level",
        "How fatigued do you feel? (1=fresh, 10=exhausted)"
    )

    # Stress level (inverted - low number = good)
    data["stress_level"] = prompt_rating(
        "Life stress",
        "Current life stress? (1=calm, 10=overwhelmed)"
    )

    # Soreness level (inverted - low number = good)
    data["soreness_level"] = prompt_rating(
        "Muscle soreness",
        "How sore are your legs/body? (1=fresh, 10=very sore)"
    )

    # Motivation
    data["motivation"] = prompt_rating(
        "Motivation to train",
        "How motivated are you to train today? (1=not at all, 10=fired up)"
    )

    # Optional orthostatic HR test
    print("\n" + "-" * 40)
    print("OPTIONAL: Orthostatic HR Test")
    print("(For ANS quadrant detection - improves readiness accuracy)")
    print("-" * 40)
    print("\nDo you want to record orthostatic HR? (y/n)")
    do_orthostatic = input("> ").strip().lower()

    if do_orthostatic in ("y", "yes"):
        print("\nProtocol:")
        print("1. Lie down for 2-5 minutes, record your resting HR")
        print("2. Stand up smoothly, wait 60 seconds, record HR again")
        print()

        data["hr_lying"] = prompt_hr(
            "Lying HR",
            "Heart rate after lying still for 2-5 minutes"
        )
        data["hr_standing"] = prompt_hr(
            "Standing HR",
            "Heart rate 60 seconds after standing up"
        )
        data["orthostatic_delta"] = data["hr_standing"] - data["hr_lying"]
        print(f"\nOrthostatic delta: {data['orthostatic_delta']} bpm")

    # Optional notes
    print("\nAny notes for today? (press Enter to skip)")
    notes = input("> ").strip()
    if notes:
        data["notes"] = notes

    return data


def update_athlete_state(state: dict, check_in_data: dict) -> dict:
    """Update athlete state with check-in data."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Ensure subjective_data section exists
    if "subjective_data" not in state:
        state["subjective_data"] = {}

    # Update subjective data
    state["subjective_data"].update({
        "date": now[:10],  # YYYY-MM-DD
        "timestamp": now,
        "sleep_quality": check_in_data["sleep_quality"],
        "fatigue_level": check_in_data["fatigue_level"],
        "stress_level": check_in_data["stress_level"],
        "soreness_level": check_in_data["soreness_level"],
        "motivation": check_in_data["motivation"],
    })

    if "notes" in check_in_data:
        state["subjective_data"]["notes"] = check_in_data["notes"]

    # Store orthostatic data if provided
    if "orthostatic_delta" in check_in_data:
        state["subjective_data"]["hr_lying"] = check_in_data.get("hr_lying")
        state["subjective_data"]["hr_standing"] = check_in_data.get("hr_standing")
        state["subjective_data"]["orthostatic_delta"] = check_in_data["orthostatic_delta"]

    # Also update fatigue_indicators if they exist
    if "fatigue_indicators" not in state:
        state["fatigue_indicators"] = {}

    # Map subjective data to fatigue indicators
    state["fatigue_indicators"]["subjective"] = {
        "fatigue_rating": check_in_data["fatigue_level"],
        "motivation_rating": check_in_data["motivation"],
        "soreness_rating": check_in_data["soreness_level"],
        "updated": now,
    }

    # Update stress in fatigue indicators
    state["fatigue_indicators"]["stress"] = {
        "life_stress": check_in_data["stress_level"],
        "updated": now,
    }

    # Update sleep quality in fatigue indicators
    if "sleep" not in state["fatigue_indicators"]:
        state["fatigue_indicators"]["sleep"] = {}
    state["fatigue_indicators"]["sleep"]["quality_rating"] = check_in_data["sleep_quality"]
    state["fatigue_indicators"]["sleep"]["updated"] = now

    # Update orthostatic data in fatigue indicators (for ANS quadrant detection)
    if "orthostatic_delta" in check_in_data:
        if "orthostatic" not in state["fatigue_indicators"]:
            state["fatigue_indicators"]["orthostatic"] = {}

        # Get existing baseline or calculate rolling average
        existing_baseline = state["fatigue_indicators"]["orthostatic"].get("baseline")
        current_delta = check_in_data["orthostatic_delta"]

        # Simple baseline: use existing or set current as initial baseline
        if existing_baseline is None:
            # First measurement - use as initial baseline
            new_baseline = current_delta
        else:
            # Exponential moving average for baseline (alpha = 0.1)
            new_baseline = round(0.1 * current_delta + 0.9 * existing_baseline, 1)

        state["fatigue_indicators"]["orthostatic"] = {
            "delta": current_delta,
            "baseline": new_baseline,
            "hr_lying": check_in_data.get("hr_lying"),
            "hr_standing": check_in_data.get("hr_standing"),
            "updated": now,
        }

    # Update metadata
    if "metadata" not in state:
        state["metadata"] = {}
    state["metadata"]["last_check_in"] = now

    return state


def calculate_subjective_score(check_in_data: dict) -> float:
    """
    Calculate a subjective readiness score from check-in data.

    Positive factors: sleep_quality, motivation (higher = better)
    Negative factors: fatigue, stress, soreness (lower = better, inverted)

    Returns score 0-100.
    """
    # Positive factors (1-10 scale, higher is better)
    positive_sum = check_in_data["sleep_quality"] + check_in_data["motivation"]
    positive_max = 20  # 2 factors * 10 max

    # Negative factors (1-10 scale, but we invert: 1=good becomes 10, 10=bad becomes 1)
    fatigue_inverted = 11 - check_in_data["fatigue_level"]
    stress_inverted = 11 - check_in_data["stress_level"]
    soreness_inverted = 11 - check_in_data["soreness_level"]
    negative_sum = fatigue_inverted + stress_inverted + soreness_inverted
    negative_max = 30  # 3 factors * 10 max

    # Combined score (0-100)
    total = positive_sum + negative_sum
    total_max = positive_max + negative_max
    score = (total / total_max) * 100

    return round(score, 1)


def main():
    parser = argparse.ArgumentParser(
        description="Morning check-in for subjective readiness data"
    )
    parser.add_argument(
        "athlete_name",
        help="Athlete folder name (e.g., 'matti-rowe')"
    )
    parser.add_argument(
        "--sleep-quality", type=int,
        help="Sleep quality rating (1-10, 10=best)"
    )
    parser.add_argument(
        "--fatigue", type=int,
        help="Fatigue level (1-10, 1=fresh, 10=exhausted)"
    )
    parser.add_argument(
        "--stress", type=int,
        help="Life stress level (1-10, 1=calm, 10=overwhelmed)"
    )
    parser.add_argument(
        "--soreness", type=int,
        help="Muscle soreness (1-10, 1=fresh, 10=very sore)"
    )
    parser.add_argument(
        "--motivation", type=int,
        help="Motivation to train (1-10, 10=highly motivated)"
    )
    parser.add_argument(
        "--notes", type=str,
        help="Optional notes for the day"
    )
    parser.add_argument(
        "--hr-lying", type=int,
        help="Lying heart rate (bpm) for orthostatic test"
    )
    parser.add_argument(
        "--hr-standing", type=int,
        help="Standing heart rate (bpm) for orthostatic test - measured 60s after standing"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output result as JSON"
    )

    args = parser.parse_args()

    # Check if athlete exists
    state_path = get_athlete_state_path(args.athlete_name)
    if not state_path.exists():
        print(f"Error: Athlete '{args.athlete_name}' not found at {state_path}")
        sys.exit(1)

    # Determine if we're in interactive or CLI mode
    cli_args = [args.sleep_quality, args.fatigue, args.stress, args.soreness, args.motivation]

    if all(arg is not None for arg in cli_args):
        # CLI mode - all required args provided
        check_in_data = {
            "sleep_quality": validate_rating(args.sleep_quality, "sleep-quality"),
            "fatigue_level": validate_rating(args.fatigue, "fatigue"),
            "stress_level": validate_rating(args.stress, "stress"),
            "soreness_level": validate_rating(args.soreness, "soreness"),
            "motivation": validate_rating(args.motivation, "motivation"),
        }
        if args.notes:
            check_in_data["notes"] = args.notes

        # Handle orthostatic HR (both must be provided together)
        if args.hr_lying is not None and args.hr_standing is not None:
            check_in_data["hr_lying"] = validate_hr(args.hr_lying, "hr-lying")
            check_in_data["hr_standing"] = validate_hr(args.hr_standing, "hr-standing")
            check_in_data["orthostatic_delta"] = args.hr_standing - args.hr_lying
        elif args.hr_lying is not None or args.hr_standing is not None:
            print("Warning: Both --hr-lying and --hr-standing must be provided for orthostatic test")
            print("Skipping orthostatic data...")
    elif any(arg is not None for arg in cli_args):
        # Partial CLI args - error
        print("Error: If using CLI mode, all ratings must be provided:")
        print("  --sleep-quality, --fatigue, --stress, --soreness, --motivation")
        sys.exit(1)
    else:
        # Interactive mode
        check_in_data = interactive_check_in()

    # Calculate subjective score
    subjective_score = calculate_subjective_score(check_in_data)
    check_in_data["subjective_score"] = subjective_score

    # Load and update state
    state = load_state(state_path)
    state = update_athlete_state(state, check_in_data)

    # Also store the subjective score
    state["subjective_data"]["subjective_score"] = subjective_score

    # Save updated state
    save_state(state_path, state)

    # Output
    if args.json:
        print(json.dumps({
            "status": "success",
            "athlete": args.athlete_name,
            "check_in": check_in_data,
            "subjective_score": subjective_score,
        }, indent=2))
    else:
        print("\n" + "=" * 50)
        print("  CHECK-IN COMPLETE")
        print("=" * 50)
        print(f"\nAthlete: {args.athlete_name}")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"\nRatings:")
        print(f"  Sleep Quality:  {check_in_data['sleep_quality']}/10")
        print(f"  Fatigue Level:  {check_in_data['fatigue_level']}/10 (lower=better)")
        print(f"  Life Stress:    {check_in_data['stress_level']}/10 (lower=better)")
        print(f"  Soreness:       {check_in_data['soreness_level']}/10 (lower=better)")
        print(f"  Motivation:     {check_in_data['motivation']}/10")
        print(f"\nSubjective Score: {subjective_score}/100")

        # Quick interpretation
        if subjective_score >= 70:
            print("Interpretation: Feeling good - green light for key session")
        elif subjective_score >= 50:
            print("Interpretation: Moderate - support session recommended")
        else:
            print("Interpretation: Low readiness - consider recovery day")

        # Display orthostatic data if recorded
        if "orthostatic_delta" in check_in_data:
            print(f"\nOrthostatic Test:")
            print(f"  Lying HR:     {check_in_data['hr_lying']} bpm")
            print(f"  Standing HR:  {check_in_data['hr_standing']} bpm")
            print(f"  Delta:        {check_in_data['orthostatic_delta']} bpm")
            delta = check_in_data['orthostatic_delta']
            if delta < 10:
                print("  Status: Blunted response (possible deep recovery or fatigue)")
            elif delta <= 20:
                print("  Status: Normal range")
            else:
                print("  Status: Elevated (increased sympathetic activation)")

        if "notes" in check_in_data:
            print(f"\nNotes: {check_in_data['notes']}")

        print(f"\nState updated: {state_path}")
        print("\nNext: Run calculate_readiness.py to get full readiness score")


if __name__ == "__main__":
    main()
