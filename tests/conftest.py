"""
Pytest configuration and shared fixtures for athlete-coaching-system tests.
"""

import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def root_dir() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def archetypes_path(root_dir: Path) -> Path:
    """Get the archetypes submodule path."""
    return root_dir / "knowledge" / "archetypes"


@pytest.fixture(scope="session")
def knowledge_path(root_dir: Path) -> Path:
    """Get the knowledge directory path."""
    return root_dir / "knowledge"
