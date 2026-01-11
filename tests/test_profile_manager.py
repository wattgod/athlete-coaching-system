#!/usr/bin/env python3
"""
Unit Tests for Profile Manager

Tests CRUD operations for athlete profiles and state files.

Run with: pytest tests/test_profile_manager.py -v
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from profile_manager import (
    get_athlete_path,
    list_athletes,
    read_profile,
    read_state,
    update_athlete,
    update_state,
    create_athlete,
    delete_athlete,
    get_athlete_context,
    _set_nested_value,
    _get_nested_value,
    ATHLETES_DIR,
    TEMPLATE_DIR,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_athletes_dir(tmp_path):
    """Create a temporary athletes directory with template."""
    athletes_dir = tmp_path / "athletes"
    athletes_dir.mkdir()

    # Create template
    template_dir = athletes_dir / "_template"
    template_dir.mkdir()

    # Create template profile.yaml
    template_profile = {
        "name": "Template Athlete",
        "physiology": {
            "ftp": 200,
            "lthr": 160,
        },
        "status": {
            "phase": "base",
        },
    }
    with open(template_dir / "profile.yaml", "w") as f:
        yaml.dump(template_profile, f)

    # Create template athlete_state.json
    template_state = {
        "_meta": {
            "description": "Template state",
            "last_updated": "2026-01-01T00:00:00Z",
            "updated_by": "template",
        },
        "readiness": {
            "score": 70,
            "threshold_key_session": 70,
            "threshold_support_session": 45,
            "recommendation": "yellow",
            "key_session_eligible": True,
        },
        "health_gates": {
            "sleep": {"gate_pass": True},
            "energy": {"gate_pass": True},
            "autonomic": {"gate_pass": True},
            "musculoskeletal": {"gate_pass": True},
            "stress": {"gate_pass": True},
            "overall": {"all_gates_pass": True, "intensity_allowed": True},
        },
        "performance_management": {
            "ctl": 50,
            "atl": 60,
            "tsb": -10,
        },
    }
    with open(template_dir / "athlete_state.json", "w") as f:
        json.dump(template_state, f, indent=2)

    # Create a test athlete
    test_athlete_dir = athletes_dir / "test-athlete"
    shutil.copytree(template_dir, test_athlete_dir)

    # Customize test athlete
    test_profile = {
        "name": "Test Athlete",
        "physiology": {
            "ftp": 300,
            "lthr": 165,
            "max_hr": 185,
        },
        "status": {
            "phase": "build",
            "week_of_plan": 5,
        },
        "goals": {
            "primary_event": {
                "name": "Test Race",
                "date": "2026-06-01",
            }
        },
    }
    with open(test_athlete_dir / "profile.yaml", "w") as f:
        yaml.dump(test_profile, f)

    return athletes_dir


@pytest.fixture
def patched_dirs(temp_athletes_dir):
    """Patch the module-level directory constants."""
    with patch("profile_manager.ATHLETES_DIR", temp_athletes_dir):
        with patch("profile_manager.TEMPLATE_DIR", temp_athletes_dir / "_template"):
            yield temp_athletes_dir


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestNestedValueHelpers:
    """Tests for _set_nested_value and _get_nested_value."""

    def test_set_nested_value_simple(self):
        """Test setting a simple nested value."""
        data = {}
        _set_nested_value(data, "a.b.c", 42)
        assert data == {"a": {"b": {"c": 42}}}

    def test_set_nested_value_existing(self):
        """Test setting a value in existing structure."""
        data = {"a": {"b": {"x": 1}}}
        _set_nested_value(data, "a.b.c", 42)
        assert data == {"a": {"b": {"x": 1, "c": 42}}}

    def test_set_nested_value_top_level(self):
        """Test setting a top-level value."""
        data = {}
        _set_nested_value(data, "foo", "bar")
        assert data == {"foo": "bar"}

    def test_get_nested_value_exists(self):
        """Test getting an existing nested value."""
        data = {"a": {"b": {"c": 42}}}
        assert _get_nested_value(data, "a.b.c") == 42

    def test_get_nested_value_missing(self):
        """Test getting a missing nested value."""
        data = {"a": {"b": {}}}
        assert _get_nested_value(data, "a.b.c") is None

    def test_get_nested_value_top_level(self):
        """Test getting a top-level value."""
        data = {"foo": "bar"}
        assert _get_nested_value(data, "foo") == "bar"


# =============================================================================
# LIST ATHLETES TESTS
# =============================================================================

class TestListAthletes:
    """Tests for list_athletes function."""

    def test_list_athletes_basic(self, patched_dirs):
        """Test listing athletes excludes template."""
        athletes = list_athletes()
        assert "test-athlete" in athletes
        assert "_template" not in athletes

    def test_list_athletes_sorted(self, patched_dirs):
        """Test that athlete list is sorted."""
        # Create additional athletes
        (patched_dirs / "zoe-athlete").mkdir()
        (patched_dirs / "alice-athlete").mkdir()

        athletes = list_athletes()
        assert athletes == sorted(athletes)

    def test_list_athletes_excludes_hidden(self, patched_dirs):
        """Test that hidden directories are excluded."""
        (patched_dirs / ".hidden").mkdir()
        athletes = list_athletes()
        assert ".hidden" not in athletes


# =============================================================================
# READ PROFILE TESTS
# =============================================================================

class TestReadProfile:
    """Tests for read_profile function."""

    def test_read_profile_exists(self, patched_dirs):
        """Test reading an existing profile."""
        profile = read_profile("test-athlete")
        assert profile is not None
        assert profile["name"] == "Test Athlete"
        assert profile["physiology"]["ftp"] == 300

    def test_read_profile_not_found(self, patched_dirs):
        """Test reading a non-existent profile."""
        profile = read_profile("nonexistent")
        assert profile is None


# =============================================================================
# READ STATE TESTS
# =============================================================================

class TestReadState:
    """Tests for read_state function."""

    def test_read_state_exists(self, patched_dirs):
        """Test reading an existing state."""
        state = read_state("test-athlete")
        assert state is not None
        assert "_meta" in state
        assert "readiness" in state

    def test_read_state_not_found(self, patched_dirs):
        """Test reading state for non-existent athlete."""
        state = read_state("nonexistent")
        assert state is None


# =============================================================================
# UPDATE ATHLETE TESTS
# =============================================================================

class TestUpdateAthlete:
    """Tests for update_athlete function."""

    def test_update_athlete_simple(self, patched_dirs):
        """Test updating a simple value."""
        result = update_athlete("test-athlete", {"name": "Updated Name"})
        assert result is True

        profile = read_profile("test-athlete")
        assert profile["name"] == "Updated Name"

    def test_update_athlete_nested(self, patched_dirs):
        """Test updating a nested value."""
        result = update_athlete("test-athlete", {"physiology.ftp": 350})
        assert result is True

        profile = read_profile("test-athlete")
        assert profile["physiology"]["ftp"] == 350

    def test_update_athlete_multiple(self, patched_dirs):
        """Test updating multiple values."""
        result = update_athlete("test-athlete", {
            "physiology.ftp": 360,
            "status.phase": "peak",
            "status.week_of_plan": 10,
        })
        assert result is True

        profile = read_profile("test-athlete")
        assert profile["physiology"]["ftp"] == 360
        assert profile["status"]["phase"] == "peak"
        assert profile["status"]["week_of_plan"] == 10

    def test_update_athlete_not_found(self, patched_dirs):
        """Test updating a non-existent athlete."""
        result = update_athlete("nonexistent", {"name": "Test"})
        assert result is False


# =============================================================================
# UPDATE STATE TESTS
# =============================================================================

class TestUpdateState:
    """Tests for update_state function."""

    def test_update_state_simple(self, patched_dirs):
        """Test updating a simple state value."""
        result = update_state("test-athlete", {"readiness.score": 85})
        assert result is True

        state = read_state("test-athlete")
        assert state["readiness"]["score"] == 85

    def test_update_state_nested(self, patched_dirs):
        """Test updating nested state values."""
        result = update_state("test-athlete", {
            "performance_management.ctl": 75,
            "performance_management.atl": 80,
        })
        assert result is True

        state = read_state("test-athlete")
        assert state["performance_management"]["ctl"] == 75
        assert state["performance_management"]["atl"] == 80

    def test_update_state_meta_updated(self, patched_dirs):
        """Test that _meta is updated on state change."""
        update_state("test-athlete", {"readiness.score": 90}, updated_by="test")

        state = read_state("test-athlete")
        assert state["_meta"]["updated_by"] == "test"
        assert "last_updated" in state["_meta"]


# =============================================================================
# CREATE ATHLETE TESTS
# =============================================================================

class TestCreateAthlete:
    """Tests for create_athlete function."""

    def test_create_athlete_basic(self, patched_dirs):
        """Test creating a new athlete."""
        result = create_athlete("new-athlete")
        assert result is True

        # Verify athlete exists
        assert (patched_dirs / "new-athlete").exists()

        # Verify has profile and state
        profile = read_profile("new-athlete")
        assert profile is not None

        state = read_state("new-athlete")
        assert state is not None

    def test_create_athlete_with_initial_data(self, patched_dirs):
        """Test creating athlete with initial data."""
        result = create_athlete("custom-athlete", {
            "name": "Custom Athlete",
            "physiology.ftp": 280,
        })
        assert result is True

        profile = read_profile("custom-athlete")
        assert profile["name"] == "Custom Athlete"
        assert profile["physiology"]["ftp"] == 280

    def test_create_athlete_already_exists(self, patched_dirs):
        """Test creating an athlete that already exists."""
        result = create_athlete("test-athlete")
        assert result is False


# =============================================================================
# DELETE ATHLETE TESTS
# =============================================================================

class TestDeleteAthlete:
    """Tests for delete_athlete function."""

    def test_delete_athlete_without_confirm(self, patched_dirs):
        """Test that delete requires confirmation."""
        result = delete_athlete("test-athlete")
        assert result is False

        # Athlete should still exist
        assert (patched_dirs / "test-athlete").exists()

    def test_delete_athlete_with_confirm(self, patched_dirs):
        """Test deleting an athlete with confirmation."""
        result = delete_athlete("test-athlete", confirm=True)
        assert result is True

        # Athlete should be gone
        assert not (patched_dirs / "test-athlete").exists()

    def test_delete_athlete_not_found(self, patched_dirs):
        """Test deleting a non-existent athlete."""
        result = delete_athlete("nonexistent", confirm=True)
        assert result is False

    def test_delete_template_blocked(self, patched_dirs):
        """Test that template cannot be deleted."""
        result = delete_athlete("_template", confirm=True)
        assert result is False

        # Template should still exist
        assert (patched_dirs / "_template").exists()


# =============================================================================
# GET ATHLETE CONTEXT TESTS
# =============================================================================

class TestGetAthleteContext:
    """Tests for get_athlete_context function."""

    def test_get_context_exists(self, patched_dirs):
        """Test getting context for existing athlete."""
        context = get_athlete_context("test-athlete")
        assert context is not None
        assert "profile" in context
        assert "state" in context
        assert context["profile"]["name"] == "Test Athlete"

    def test_get_context_not_found(self, patched_dirs):
        """Test getting context for non-existent athlete."""
        context = get_athlete_context("nonexistent")
        assert context is None


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
