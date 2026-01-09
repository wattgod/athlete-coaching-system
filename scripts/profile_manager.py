#!/usr/bin/env python3
"""
Athlete Profile Manager - CRUD operations for athlete data

Provides functions to create, read, update, and delete athlete profiles
and their associated state files.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

ATHLETES_DIR = Path(__file__).parent.parent / "athletes"
TEMPLATE_DIR = ATHLETES_DIR / "_template"


def get_athlete_path(athlete_name: str) -> Path:
    """Get the directory path for an athlete."""
    return ATHLETES_DIR / athlete_name


def list_athletes() -> List[str]:
    """List all athlete names (excluding template)."""
    athletes = []
    for path in ATHLETES_DIR.iterdir():
        if path.is_dir() and path.name != "_template" and not path.name.startswith("."):
            athletes.append(path.name)
    return sorted(athletes)


def read_profile(athlete_name: str) -> Optional[Dict]:
    """
    Read an athlete's profile.yaml

    Args:
        athlete_name: Name/slug of the athlete directory

    Returns:
        Profile dict or None if not found
    """
    profile_path = get_athlete_path(athlete_name) / "profile.yaml"
    if not profile_path.exists():
        return None

    with open(profile_path) as f:
        return yaml.safe_load(f)


def read_state(athlete_name: str) -> Optional[Dict]:
    """
    Read an athlete's live state (athlete_state.json)

    Args:
        athlete_name: Name/slug of the athlete directory

    Returns:
        State dict or None if not found
    """
    state_path = get_athlete_path(athlete_name) / "athlete_state.json"
    if not state_path.exists():
        return None

    with open(state_path) as f:
        return json.load(f)


def _set_nested_value(data: Dict, key_path: str, value: Any) -> None:
    """
    Set a value in a nested dict using dot notation.

    Args:
        data: The dict to modify
        key_path: Dot-separated path (e.g., "physiology.ftp")
        value: Value to set
    """
    keys = key_path.split(".")
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value


def _get_nested_value(data: Dict, key_path: str) -> Any:
    """
    Get a value from a nested dict using dot notation.

    Args:
        data: The dict to read from
        key_path: Dot-separated path (e.g., "physiology.ftp")

    Returns:
        The value or None if not found
    """
    keys = key_path.split(".")
    current = data

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]

    return current


def update_athlete(athlete_name: str, updates: Dict[str, Any]) -> bool:
    """
    Update an athlete's profile with new values.

    Args:
        athlete_name: Name/slug of the athlete directory
        updates: Dict of key_path -> value pairs
                 Key paths use dot notation: "physiology.ftp", "status.phase"

    Returns:
        True if successful, False otherwise

    Example:
        update_athlete("matti-rowe", {
            "physiology.ftp": 365,
            "status.phase": "build",
            "status.week_of_plan": 8
        })
    """
    profile = read_profile(athlete_name)
    if profile is None:
        print(f"Error: Athlete '{athlete_name}' not found")
        return False

    for key_path, value in updates.items():
        _set_nested_value(profile, key_path, value)

    profile_path = get_athlete_path(athlete_name) / "profile.yaml"
    with open(profile_path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Updated {athlete_name} profile: {list(updates.keys())}")
    return True


def update_state(athlete_name: str, updates: Dict[str, Any], updated_by: str = "manual") -> bool:
    """
    Update an athlete's live state with new values.

    Args:
        athlete_name: Name/slug of the athlete directory
        updates: Dict of key_path -> value pairs
                 Key paths use dot notation: "performance_management.ctl"
        updated_by: Source of the update (for audit trail)

    Returns:
        True if successful, False otherwise

    Example:
        update_state("matti-rowe", {
            "performance_management.ctl": 68,
            "performance_management.tsb": -5,
            "recent_training.last_workout.date": "2025-01-09"
        }, updated_by="intervals_sync")
    """
    state = read_state(athlete_name)
    if state is None:
        # Initialize from template if no state exists
        template_state = TEMPLATE_DIR / "athlete_state.json"
        if template_state.exists():
            with open(template_state) as f:
                state = json.load(f)
        else:
            state = {"_meta": {}}

    for key_path, value in updates.items():
        _set_nested_value(state, key_path, value)

    # Update metadata
    state["_meta"]["last_updated"] = datetime.utcnow().isoformat() + "Z"
    state["_meta"]["updated_by"] = updated_by

    state_path = get_athlete_path(athlete_name) / "athlete_state.json"
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Updated {athlete_name} state: {list(updates.keys())}")
    return True


def create_athlete(athlete_name: str, initial_data: Optional[Dict] = None) -> bool:
    """
    Create a new athlete from the template.

    Args:
        athlete_name: Name/slug for the new athlete (lowercase, hyphens)
        initial_data: Optional dict of initial profile values

    Returns:
        True if successful, False otherwise
    """
    athlete_path = get_athlete_path(athlete_name)

    if athlete_path.exists():
        print(f"Error: Athlete '{athlete_name}' already exists")
        return False

    # Copy template directory
    shutil.copytree(TEMPLATE_DIR, athlete_path)

    # Apply initial data if provided
    if initial_data:
        update_athlete(athlete_name, initial_data)

    print(f"Created athlete: {athlete_name}")
    return True


def delete_athlete(athlete_name: str, confirm: bool = False) -> bool:
    """
    Delete an athlete directory.

    Args:
        athlete_name: Name/slug of the athlete to delete
        confirm: Must be True to actually delete

    Returns:
        True if successful, False otherwise
    """
    if not confirm:
        print("Error: Must pass confirm=True to delete athlete")
        return False

    athlete_path = get_athlete_path(athlete_name)

    if not athlete_path.exists():
        print(f"Error: Athlete '{athlete_name}' not found")
        return False

    if athlete_name == "_template":
        print("Error: Cannot delete template")
        return False

    shutil.rmtree(athlete_path)
    print(f"Deleted athlete: {athlete_name}")
    return True


def get_athlete_context(athlete_name: str) -> Optional[Dict]:
    """
    Get full context for an athlete (profile + state) for prompt injection.

    Args:
        athlete_name: Name/slug of the athlete

    Returns:
        Dict with 'profile' and 'state' keys, or None if not found
    """
    profile = read_profile(athlete_name)
    state = read_state(athlete_name)

    if profile is None:
        return None

    return {
        "profile": profile,
        "state": state or {}
    }


def main():
    """CLI interface for profile manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Athlete Profile Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    subparsers.add_parser("list", help="List all athletes")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show athlete profile")
    show_parser.add_argument("athlete", help="Athlete name")
    show_parser.add_argument("--state", action="store_true", help="Show state instead of profile")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create new athlete")
    create_parser.add_argument("athlete", help="Athlete name (lowercase, hyphens)")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update athlete profile")
    update_parser.add_argument("athlete", help="Athlete name")
    update_parser.add_argument("--set", nargs=2, action="append", metavar=("KEY", "VALUE"),
                               help="Set key=value (use dot notation for nested)")
    update_parser.add_argument("--state", action="store_true", help="Update state instead of profile")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete athlete")
    delete_parser.add_argument("athlete", help="Athlete name")
    delete_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")

    args = parser.parse_args()

    if args.command == "list":
        athletes = list_athletes()
        print(f"Athletes ({len(athletes)}):")
        for name in athletes:
            print(f"  - {name}")

    elif args.command == "show":
        if args.state:
            data = read_state(args.athlete)
            if data:
                print(json.dumps(data, indent=2))
            else:
                print(f"No state found for {args.athlete}")
        else:
            data = read_profile(args.athlete)
            if data:
                print(yaml.dump(data, default_flow_style=False))
            else:
                print(f"Athlete not found: {args.athlete}")

    elif args.command == "create":
        create_athlete(args.athlete)

    elif args.command == "update":
        if not args.set:
            print("Error: No updates specified. Use --set KEY VALUE")
            sys.exit(1)

        updates = {}
        for key, value in args.set:
            # Try to parse as JSON for complex values
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # Try numeric
                try:
                    if "." in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass  # Keep as string
            updates[key] = value

        if args.state:
            update_state(args.athlete, updates)
        else:
            update_athlete(args.athlete, updates)

    elif args.command == "delete":
        delete_athlete(args.athlete, confirm=args.confirm)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
