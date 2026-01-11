#!/usr/bin/env python3
"""
State Validator - Validate athlete_state.json against JSON Schema

Ensures the athlete state file conforms to the expected structure,
catching errors before they cause issues in downstream scripts.

Usage:
    python scripts/validate_state.py matti-rowe
    python scripts/validate_state.py matti-rowe --verbose
    python scripts/validate_state.py --all
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from jsonschema import Draft202012Validator, ValidationError, validate
    from jsonschema.exceptions import SchemaError
except ImportError:
    print("Error: jsonschema required. Install with: pip install jsonschema")
    sys.exit(1)


# =============================================================================
# VALIDATION
# =============================================================================

def load_schema(schema_path: Path) -> Dict[str, Any]:
    """Load the JSON Schema."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    with open(schema_path) as f:
        return json.load(f)


def load_state(state_path: Path) -> Dict[str, Any]:
    """Load the athlete state."""
    if not state_path.exists():
        raise FileNotFoundError(f"State not found: {state_path}")

    with open(state_path) as f:
        return json.load(f)


def validate_state(
    state: Dict[str, Any],
    schema: Dict[str, Any],
    verbose: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate state against schema.

    Returns (is_valid, list_of_errors)
    """
    errors = []

    # Create validator
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as e:
        return False, [f"Invalid schema: {e.message}"]

    # Collect all errors
    for error in sorted(validator.iter_errors(state), key=lambda e: e.path):
        path = ".".join(str(p) for p in error.path) or "(root)"
        errors.append(f"{path}: {error.message}")

        if verbose:
            print(f"  ❌ {path}")
            print(f"     {error.message}")

    is_valid = len(errors) == 0

    if verbose and is_valid:
        print("  ✅ All validations passed")

    return is_valid, errors


def validate_business_rules(
    state: Dict[str, Any],
    verbose: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate business rules not expressible in JSON Schema.

    Returns (is_valid, list_of_warnings)
    """
    warnings = []

    # Check readiness score matches calculated
    readiness = state.get("readiness", {})
    breakdown = readiness.get("score_breakdown", {})

    if breakdown:
        final = breakdown.get("final_score")
        score = readiness.get("score")
        if final is not None and score is not None and final != score:
            warnings.append(f"Readiness score mismatch: score={score}, final_score={final}")

    # Check health gates consistency
    health_gates = state.get("health_gates", {})
    overall = health_gates.get("overall", {})
    all_pass = overall.get("all_gates_pass")

    if all_pass is not None:
        gates = ["sleep", "energy", "autonomic", "musculoskeletal", "stress"]
        actual_all_pass = all(
            health_gates.get(g, {}).get("gate_pass", True)
            for g in gates
        )
        if all_pass != actual_all_pass:
            warnings.append(f"Health gates inconsistency: all_gates_pass={all_pass}, actual={actual_all_pass}")

    # Check TSB calculation
    pmc = state.get("performance_management", {})
    ctl = pmc.get("ctl")
    atl = pmc.get("atl")
    tsb = pmc.get("tsb")

    if ctl is not None and atl is not None and tsb is not None:
        expected_tsb = ctl - atl
        if abs(tsb - expected_tsb) > 0.5:
            warnings.append(f"TSB calculation: expected {expected_tsb:.1f} (CTL-ATL), got {tsb}")

    # Check key session eligibility
    score = readiness.get("score", 0)
    threshold = readiness.get("threshold_key_session", 70)
    eligible = readiness.get("key_session_eligible")
    intensity_allowed = overall.get("intensity_allowed", True)

    if eligible is not None:
        expected_eligible = score >= threshold and intensity_allowed
        if eligible != expected_eligible:
            warnings.append(
                f"Key session eligibility: expected {expected_eligible} "
                f"(score={score}, threshold={threshold}, gates_pass={intensity_allowed}), got {eligible}"
            )

    if verbose:
        if warnings:
            print("\n  ⚠️  Business rule warnings:")
            for w in warnings:
                print(f"     {w}")
        else:
            print("  ✅ Business rules OK")

    return len(warnings) == 0, warnings


# =============================================================================
# MAIN
# =============================================================================

def validate_athlete(
    athlete_dir: Path,
    schema: Dict[str, Any],
    verbose: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """Validate a single athlete's state file."""
    state_path = athlete_dir / "athlete_state.json"

    result = {
        "athlete": athlete_dir.name,
        "state_file": str(state_path),
        "schema_valid": False,
        "schema_errors": [],
        "business_rules_valid": False,
        "business_warnings": [],
    }

    if verbose:
        print(f"\n[Validating {athlete_dir.name}]")

    try:
        state = load_state(state_path)
    except FileNotFoundError:
        result["schema_errors"] = ["State file not found"]
        return False, result
    except json.JSONDecodeError as e:
        result["schema_errors"] = [f"Invalid JSON: {e}"]
        return False, result

    # Schema validation
    if verbose:
        print("  Checking schema...")
    schema_valid, schema_errors = validate_state(state, schema, verbose)
    result["schema_valid"] = schema_valid
    result["schema_errors"] = schema_errors

    # Business rules validation
    if verbose:
        print("  Checking business rules...")
    rules_valid, rules_warnings = validate_business_rules(state, verbose)
    result["business_rules_valid"] = rules_valid
    result["business_warnings"] = rules_warnings

    is_valid = schema_valid and rules_valid
    return is_valid, result


def main():
    parser = argparse.ArgumentParser(
        description="Validate athlete state against JSON Schema"
    )
    parser.add_argument(
        "athlete_name",
        nargs="?",
        help="Athlete folder name (e.g., matti-rowe)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all athletes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed validation results"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    if not args.athlete_name and not args.all:
        parser.error("Either athlete_name or --all is required")

    # Find paths
    base_dir = Path(__file__).parent.parent
    schema_path = base_dir / "schemas" / "athlete_state.schema.json"
    athletes_dir = base_dir / "athletes"

    # Load schema
    try:
        schema = load_schema(schema_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Determine which athletes to validate
    if args.all:
        athlete_dirs = [d for d in athletes_dir.iterdir() if d.is_dir()]
    else:
        athlete_dir = athletes_dir / args.athlete_name
        if not athlete_dir.exists():
            print(f"Error: Athlete directory not found: {athlete_dir}")
            sys.exit(1)
        athlete_dirs = [athlete_dir]

    # Validate each athlete
    results = []
    all_valid = True

    for athlete_dir in athlete_dirs:
        is_valid, result = validate_athlete(athlete_dir, schema, args.verbose)
        results.append(result)
        if not is_valid:
            all_valid = False

    # Output
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 50)
        print("VALIDATION RESULTS")
        print("=" * 50)

        for result in results:
            athlete = result["athlete"]
            schema_ok = "✅" if result["schema_valid"] else "❌"
            rules_ok = "✅" if result["business_rules_valid"] else "⚠️"

            print(f"\n{athlete}:")
            print(f"  Schema: {schema_ok}")
            print(f"  Business Rules: {rules_ok}")

            if result["schema_errors"]:
                print(f"  Errors ({len(result['schema_errors'])}):")
                for err in result["schema_errors"][:5]:
                    print(f"    - {err}")
                if len(result["schema_errors"]) > 5:
                    print(f"    ... and {len(result['schema_errors']) - 5} more")

            if result["business_warnings"]:
                print(f"  Warnings ({len(result['business_warnings'])}):")
                for warn in result["business_warnings"]:
                    print(f"    - {warn}")

        print("\n" + "-" * 50)
        if all_valid:
            print("✅ All validations passed")
        else:
            print("❌ Validation failed")

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
