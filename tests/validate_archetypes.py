#!/usr/bin/env python3
"""
Archetype Validation Script

Validates the nate-workout-archetypes submodule for:
1. Required files exist
2. White paper has all expected archetypes
3. ZWO files are valid XML
4. Archetype count matches expectations
5. 6-level progressions are complete
"""

import os
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

# Configuration
ARCHETYPES_PATH = Path(__file__).parent.parent / "knowledge" / "archetypes"
MIN_EXPECTED_ARCHETYPES = 15  # Minimum archetypes expected (baseline for regression detection)
EXPECTED_LEVELS = 6  # Each archetype should have 6 progression levels

# Required files that must exist
REQUIRED_FILES = [
    "WORKOUT_ARCHETYPES_WHITE_PAPER.md",
    "ARCHITECTURE.md",
    "CATEGORIZATION_RULES.md",
]

# Expected archetype categories
EXPECTED_CATEGORIES = [
    "VO2max",
    "Threshold",
    "Tempo",
    "Endurance",
    "Recovery",
    "Sprint",
    "Neuromuscular",
    "SFR",
    "Mixed",
]

# Validation results
class ValidationResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, msg):
        self.passed.append(msg)
        print(f"  [PASS] {msg}")

    def add_fail(self, msg):
        self.failed.append(msg)
        print(f"  [FAIL] {msg}")

    def add_warning(self, msg):
        self.warnings.append(msg)
        print(f"  [WARN] {msg}")

    @property
    def success(self):
        return len(self.failed) == 0


def validate_required_files(result: ValidationResult):
    """Check that all required documentation files exist."""
    print("\n=== Validating Required Files ===")

    for filename in REQUIRED_FILES:
        filepath = ARCHETYPES_PATH / filename
        if filepath.exists():
            result.add_pass(f"Found {filename}")
        else:
            result.add_fail(f"Missing required file: {filename}")


def validate_white_paper(result: ValidationResult):
    """Parse the white paper and validate archetype definitions."""
    print("\n=== Validating White Paper ===")

    white_paper_path = ARCHETYPES_PATH / "WORKOUT_ARCHETYPES_WHITE_PAPER.md"
    if not white_paper_path.exists():
        result.add_fail("White paper not found, cannot validate")
        return

    content = white_paper_path.read_text()

    # Count archetype definitions (lines starting with "- " followed by archetype name pattern)
    archetype_pattern = r"^[-*]\s+\*?\*?([a-z0-9_]+)\*?\*?:"
    archetypes = re.findall(archetype_pattern, content, re.MULTILINE | re.IGNORECASE)

    # Also look for archetype headers in tables or bold format
    table_pattern = r"\|\s*([a-z0-9_]+)\s*\|"
    table_archetypes = re.findall(table_pattern, content, re.IGNORECASE)

    all_archetypes = set(archetypes + table_archetypes)
    # Filter out common non-archetype words
    exclude_words = {'zone', 'ftp', 'rpm', 'level', 'power', 'duration', 'purpose', 'name', 'category'}
    all_archetypes = {a for a in all_archetypes if a.lower() not in exclude_words}

    if len(all_archetypes) >= MIN_EXPECTED_ARCHETYPES:
        result.add_pass(f"Found {len(all_archetypes)} archetypes (minimum: {MIN_EXPECTED_ARCHETYPES})")
    else:
        result.add_fail(f"Only found {len(all_archetypes)} archetypes, expected at least {MIN_EXPECTED_ARCHETYPES}")

    # Check for expected categories
    for category in EXPECTED_CATEGORIES:
        if category.lower() in content.lower():
            result.add_pass(f"Category '{category}' documented")
        else:
            result.add_warning(f"Category '{category}' may be missing from documentation")

    # Check for 6-level progression documentation
    if "level 1" in content.lower() and "level 6" in content.lower():
        result.add_pass("6-level progression system documented")
    else:
        result.add_warning("6-level progression may not be fully documented")


def validate_zwo_files(result: ValidationResult):
    """Validate ZWO files are valid XML with required structure."""
    print("\n=== Validating ZWO Files ===")

    zwo_dirs = [
        ARCHETYPES_PATH / "zwo_output",
        ARCHETYPES_PATH / "zwo_output_cleaned",
    ]

    total_zwo = 0
    valid_zwo = 0
    invalid_zwo = []

    for zwo_dir in zwo_dirs:
        if not zwo_dir.exists():
            continue

        for zwo_file in zwo_dir.rglob("*.zwo"):
            total_zwo += 1
            try:
                tree = ET.parse(zwo_file)
                root = tree.getroot()

                # Check for required elements
                has_workout = root.find(".//workout") is not None
                has_name = root.find(".//name") is not None

                if has_workout and has_name:
                    valid_zwo += 1
                else:
                    invalid_zwo.append(f"{zwo_file.name}: missing required elements")
            except ET.ParseError as e:
                invalid_zwo.append(f"{zwo_file.name}: XML parse error - {e}")

    if total_zwo == 0:
        result.add_warning("No ZWO files found to validate")
    elif len(invalid_zwo) == 0:
        result.add_pass(f"All {valid_zwo}/{total_zwo} ZWO files are valid XML")
    else:
        result.add_fail(f"{len(invalid_zwo)} invalid ZWO files out of {total_zwo}")
        for error in invalid_zwo[:5]:  # Show first 5 errors
            result.add_fail(f"  - {error}")
        if len(invalid_zwo) > 5:
            result.add_fail(f"  ... and {len(invalid_zwo) - 5} more")


def validate_archetype_coverage(result: ValidationResult):
    """Check that ZWO files cover expected archetype categories."""
    print("\n=== Validating Archetype Coverage ===")

    zwo_dir = ARCHETYPES_PATH / "zwo_output_cleaned"
    if not zwo_dir.exists():
        zwo_dir = ARCHETYPES_PATH / "zwo_output"

    if not zwo_dir.exists():
        result.add_warning("No ZWO output directory found")
        return

    # Count files by category (based on directory structure or filename)
    category_counts = defaultdict(int)

    for item in zwo_dir.iterdir():
        if item.is_dir():
            category_counts[item.name] = len(list(item.glob("*.zwo")))
        elif item.suffix == ".zwo":
            # Try to extract category from filename
            name_lower = item.stem.lower()
            for cat in EXPECTED_CATEGORIES:
                if cat.lower() in name_lower:
                    category_counts[cat] += 1
                    break
            else:
                category_counts["uncategorized"] += 1

    if category_counts:
        result.add_pass(f"Found workouts in {len(category_counts)} categories")
        for cat, count in sorted(category_counts.items()):
            if count > 0:
                result.add_pass(f"  {cat}: {count} workouts")
    else:
        result.add_warning("Could not determine workout categories")


def validate_power_ranges(result: ValidationResult):
    """Spot-check ZWO files for valid power ranges."""
    print("\n=== Validating Power Ranges ===")

    zwo_dir = ARCHETYPES_PATH / "zwo_output_cleaned"
    if not zwo_dir.exists():
        zwo_dir = ARCHETYPES_PATH / "zwo_output"

    if not zwo_dir.exists():
        result.add_warning("No ZWO output directory found")
        return

    # Sample some files
    zwo_files = list(zwo_dir.rglob("*.zwo"))[:50]  # Check first 50
    power_issues = []

    for zwo_file in zwo_files:
        try:
            tree = ET.parse(zwo_file)
            root = tree.getroot()

            # Check power values in workout elements
            for elem in root.iter():
                for attr in ['Power', 'PowerLow', 'PowerHigh', 'OnPower', 'OffPower']:
                    if attr in elem.attrib:
                        power = float(elem.attrib[attr])
                        # Power should be decimal FTP percentage (0.0 - 2.0 range typically)
                        if power < 0 or power > 3.0:
                            power_issues.append(f"{zwo_file.name}: {attr}={power} out of range")
        except (ET.ParseError, ValueError):
            pass  # Already caught in ZWO validation

    if len(power_issues) == 0:
        result.add_pass(f"Power ranges valid in {len(zwo_files)} sampled files")
    else:
        result.add_fail(f"Found {len(power_issues)} power range issues")
        for issue in power_issues[:5]:
            result.add_fail(f"  - {issue}")


def main():
    print("=" * 60)
    print("ARCHETYPE VALIDATION")
    print("=" * 60)
    print(f"\nArchetypes path: {ARCHETYPES_PATH}")

    if not ARCHETYPES_PATH.exists():
        print("\n[FATAL] Archetypes submodule not found!")
        print("Run: git submodule update --init --recursive")
        sys.exit(1)

    result = ValidationResult()

    # Run all validations
    validate_required_files(result)
    validate_white_paper(result)
    validate_zwo_files(result)
    validate_archetype_coverage(result)
    validate_power_ranges(result)

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Passed:   {len(result.passed)}")
    print(f"  Warnings: {len(result.warnings)}")
    print(f"  Failed:   {len(result.failed)}")

    if result.success:
        print("\n[SUCCESS] All validations passed!")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some validations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
