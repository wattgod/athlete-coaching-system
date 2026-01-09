#!/usr/bin/env python3
"""
Regression Test Suite for Archetype Integration

Tests that changes to the archetypes submodule don't break existing functionality.
Run with: pytest tests/test_regression.py -v
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Set
import pytest

# Paths
ROOT_DIR = Path(__file__).parent.parent
ARCHETYPES_PATH = ROOT_DIR / "knowledge" / "archetypes"
KNOWLEDGE_PATH = ROOT_DIR / "knowledge"


class TestArchetypeSubmodule:
    """Tests for the archetypes submodule existence and basic structure."""

    def test_submodule_exists(self):
        """Archetypes submodule should be checked out."""
        assert ARCHETYPES_PATH.exists(), "Archetypes submodule not found"
        assert (ARCHETYPES_PATH / ".git").exists() or (ROOT_DIR / ".git" / "modules").exists(), \
            "Archetypes directory exists but is not a git submodule"

    def test_white_paper_exists(self):
        """White paper documentation should exist."""
        white_paper = ARCHETYPES_PATH / "WORKOUT_ARCHETYPES_WHITE_PAPER.md"
        assert white_paper.exists(), "White paper not found"
        content = white_paper.read_text()
        assert len(content) > 1000, "White paper appears to be empty or truncated"

    def test_architecture_docs_exist(self):
        """Architecture documentation should exist."""
        assert (ARCHETYPES_PATH / "ARCHITECTURE.md").exists()
        assert (ARCHETYPES_PATH / "CATEGORIZATION_RULES.md").exists()


class TestArchetypeDefinitions:
    """Tests for archetype definitions and structure."""

    # Critical archetypes that must always exist (regression protection)
    CRITICAL_ARCHETYPES = [
        "vo2",        # VO2max work
        "threshold",  # Threshold work
        "tempo",      # Tempo/G-Spot
        "endurance",  # Base endurance
        "sfr",        # Strength/force
        "sprint",     # Neuromuscular
    ]

    def test_critical_archetypes_documented(self):
        """Critical archetype types must be documented in white paper."""
        white_paper = ARCHETYPES_PATH / "WORKOUT_ARCHETYPES_WHITE_PAPER.md"
        content = white_paper.read_text().lower()

        missing = []
        for archetype in self.CRITICAL_ARCHETYPES:
            if archetype not in content:
                missing.append(archetype)

        assert len(missing) == 0, f"Critical archetypes missing from documentation: {missing}"

    def test_six_level_progression_system(self):
        """The 6-level progression system must be documented."""
        white_paper = ARCHETYPES_PATH / "WORKOUT_ARCHETYPES_WHITE_PAPER.md"
        content = white_paper.read_text().lower()

        # Check for level references
        assert "level 1" in content, "Level 1 not documented"
        assert "level 6" in content, "Level 6 not documented"
        assert "progression" in content, "Progression system not documented"

    def test_power_zones_documented(self):
        """Power zone definitions should be present."""
        white_paper = ARCHETYPES_PATH / "WORKOUT_ARCHETYPES_WHITE_PAPER.md"
        content = white_paper.read_text().lower()

        # Check for zone references
        assert "ftp" in content, "FTP reference missing"
        assert any(z in content for z in ["zone 1", "z1", "zone1"]), "Zone definitions missing"


class TestZWOFiles:
    """Tests for ZWO workout file validity."""

    @pytest.fixture
    def zwo_directory(self) -> Path:
        """Get the ZWO output directory."""
        zwo_cleaned = ARCHETYPES_PATH / "zwo_output_cleaned"
        zwo_standard = ARCHETYPES_PATH / "zwo_output"

        if zwo_cleaned.exists():
            return zwo_cleaned
        elif zwo_standard.exists():
            return zwo_standard
        else:
            pytest.skip("No ZWO output directory found")

    @pytest.fixture
    def sample_zwo_files(self, zwo_directory: Path) -> List[Path]:
        """Get a sample of ZWO files for testing."""
        all_files = list(zwo_directory.rglob("*.zwo"))
        # Sample up to 100 files for faster testing
        return all_files[:100]

    def test_zwo_files_exist(self, zwo_directory: Path):
        """There should be ZWO files in the output directory."""
        zwo_files = list(zwo_directory.rglob("*.zwo"))
        assert len(zwo_files) > 0, "No ZWO files found"
        # Expect substantial library
        assert len(zwo_files) >= 100, f"Expected at least 100 ZWO files, found {len(zwo_files)}"

    def test_zwo_files_valid_xml(self, sample_zwo_files: List[Path]):
        """All ZWO files should be valid XML."""
        invalid = []
        for zwo_file in sample_zwo_files:
            try:
                ET.parse(zwo_file)
            except ET.ParseError as e:
                invalid.append((zwo_file.name, str(e)))

        assert len(invalid) == 0, f"Invalid XML files: {invalid[:5]}"

    def test_zwo_files_have_required_elements(self, sample_zwo_files: List[Path]):
        """ZWO files should have required structure."""
        missing_elements = []

        for zwo_file in sample_zwo_files:
            try:
                tree = ET.parse(zwo_file)
                root = tree.getroot()

                # Check required elements
                if root.find(".//workout") is None:
                    missing_elements.append((zwo_file.name, "workout"))
                if root.find(".//name") is None:
                    missing_elements.append((zwo_file.name, "name"))
            except ET.ParseError:
                pass  # Caught in other test

        assert len(missing_elements) == 0, f"Missing elements: {missing_elements[:5]}"

    def test_zwo_power_values_in_range(self, sample_zwo_files: List[Path]):
        """Power values should be decimal FTP percentages (0.0 - 2.5 range)."""
        out_of_range = []

        for zwo_file in sample_zwo_files:
            try:
                tree = ET.parse(zwo_file)
                root = tree.getroot()

                for elem in root.iter():
                    for attr in ['Power', 'PowerLow', 'PowerHigh', 'OnPower', 'OffPower']:
                        if attr in elem.attrib:
                            try:
                                power = float(elem.attrib[attr])
                                if power < 0 or power > 2.5:
                                    out_of_range.append((zwo_file.name, attr, power))
                            except ValueError:
                                out_of_range.append((zwo_file.name, attr, "invalid"))
            except ET.ParseError:
                pass

        assert len(out_of_range) == 0, f"Power values out of range: {out_of_range[:5]}"


class TestCategoryConsistency:
    """Tests for workout category consistency."""

    EXPECTED_CATEGORIES = {
        "vo2max", "vo2",
        "threshold", "tt",
        "tempo", "g_spot", "g-spot", "sweet_spot",
        "endurance",
        "recovery",
        "sprint", "neuromuscular",
        "sfr", "force",
        "cadence",
    }

    def test_categorization_rules_exist(self):
        """Categorization rules should be documented."""
        rules_file = ARCHETYPES_PATH / "CATEGORIZATION_RULES.md"
        assert rules_file.exists(), "Categorization rules not found"

        content = rules_file.read_text().lower()
        # Check for key category mentions
        categories_found = sum(1 for cat in self.EXPECTED_CATEGORIES if cat in content)
        assert categories_found >= 5, f"Only {categories_found} categories documented in rules"


class TestIntegrationPoints:
    """Tests for integration between archetypes and coaching system."""

    def test_knowledge_directory_structure(self):
        """Knowledge directory should have expected structure."""
        assert (KNOWLEDGE_PATH / "philosophies").exists(), "Philosophies directory missing"
        assert (KNOWLEDGE_PATH / "coaching_heuristics").exists(), "Coaching heuristics missing"
        assert (KNOWLEDGE_PATH / "archetypes").exists(), "Archetypes submodule missing"

    def test_no_duplicate_archetype_files(self):
        """Old workout_templates should not duplicate submodule content."""
        old_templates = KNOWLEDGE_PATH / "workout_templates"

        if old_templates.exists():
            old_archetype_file = old_templates / "WORKOUT_ARCHETYPES.md"
            if old_archetype_file.exists():
                # Warn but don't fail - might be intentionally kept for reference
                old_content = old_archetype_file.read_text()
                new_content = (ARCHETYPES_PATH / "WORKOUT_ARCHETYPES_WHITE_PAPER.md").read_text()

                # Check if old file is significantly different (outdated)
                if len(old_content) < len(new_content) * 0.5:
                    pytest.warns(UserWarning,
                                 match="Old workout_templates may be outdated compared to submodule")


class TestRegressionBaseline:
    """Baseline tests to catch regressions in archetype count and structure."""

    # Baseline values - update these when intentionally changing archetype structure
    MIN_ARCHETYPE_COUNT = 15
    MIN_ZWO_FILE_COUNT = 500
    MIN_CATEGORIES = 8

    def test_minimum_archetype_count(self):
        """Should have at least the baseline number of archetypes."""
        white_paper = ARCHETYPES_PATH / "WORKOUT_ARCHETYPES_WHITE_PAPER.md"
        content = white_paper.read_text()

        # Count archetype definitions
        archetype_pattern = r"^[-*]\s+\*?\*?([a-z0-9_]+)\*?\*?:"
        archetypes = re.findall(archetype_pattern, content, re.MULTILINE | re.IGNORECASE)

        assert len(archetypes) >= self.MIN_ARCHETYPE_COUNT, \
            f"Archetype count ({len(archetypes)}) below baseline ({self.MIN_ARCHETYPE_COUNT})"

    def test_minimum_zwo_file_count(self):
        """Should have at least the baseline number of ZWO files."""
        zwo_cleaned = ARCHETYPES_PATH / "zwo_output_cleaned"
        zwo_standard = ARCHETYPES_PATH / "zwo_output"

        zwo_dir = zwo_cleaned if zwo_cleaned.exists() else zwo_standard
        if not zwo_dir.exists():
            pytest.skip("No ZWO directory found")

        zwo_count = len(list(zwo_dir.rglob("*.zwo")))
        assert zwo_count >= self.MIN_ZWO_FILE_COUNT, \
            f"ZWO file count ({zwo_count}) below baseline ({self.MIN_ZWO_FILE_COUNT})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
