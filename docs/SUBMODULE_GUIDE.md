# Archetype Submodule Guide

This document explains how the `nate-workout-archetypes` repository is integrated into `athlete-coaching-system` as a Git submodule.

## Overview

The workout archetypes library is maintained separately in the `nate-workout-archetypes` repository and pulled into this project as a Git submodule at `knowledge/archetypes/`.

**Benefits:**
- Single source of truth for archetype definitions
- Version-controlled updates with explicit commits
- CI validation on every change
- No file duplication or drift

## Directory Structure

```
athlete-coaching-system/
├── knowledge/
│   ├── archetypes/                    <- Submodule: nate-workout-archetypes
│   │   ├── WORKOUT_ARCHETYPES_WHITE_PAPER.md
│   │   ├── ARCHITECTURE.md
│   │   ├── CATEGORIZATION_RULES.md
│   │   ├── zwo_output/
│   │   └── zwo_output_cleaned/
│   ├── philosophies/
│   ├── coaching_heuristics/
│   └── workout_templates/             <- Legacy (may be removed)
├── tests/
│   ├── validate_archetypes.py
│   └── test_regression.py
└── .github/workflows/
    └── validate-archetypes.yml
```

## Initial Setup (New Clone)

When cloning this repository for the first time:

```bash
# Clone with submodules
git clone --recursive https://github.com/wattgod/athlete-coaching-system.git

# Or if already cloned without submodules:
git submodule update --init --recursive
```

## Updating the Submodule

When `nate-workout-archetypes` has new commits you want to pull in:

```bash
# Navigate to submodule
cd knowledge/archetypes

# Fetch and checkout latest
git fetch origin main
git checkout origin/main

# Go back to main repo
cd ../..

# Stage the submodule update
git add knowledge/archetypes

# Run validation before committing
python tests/validate_archetypes.py
pytest tests/test_regression.py -v

# If validation passes, commit the update
git commit -m "Update archetypes submodule to latest"
git push
```

### Quick Update Script

```bash
#!/bin/bash
# update-archetypes.sh

cd knowledge/archetypes
git fetch origin main
git checkout origin/main
cd ../..

echo "Running validation..."
python tests/validate_archetypes.py
pytest tests/test_regression.py -v

if [ $? -eq 0 ]; then
    git add knowledge/archetypes
    git commit -m "Update archetypes submodule"
    echo "Submodule updated successfully!"
else
    echo "Validation failed - not committing"
    exit 1
fi
```

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/validate-archetypes.yml`) runs:

1. **On every push/PR** that touches:
   - `knowledge/archetypes/**`
   - `tests/**`

2. **Daily scheduled check** at 6 AM UTC:
   - Checks if submodule is behind origin
   - Creates GitHub issue if updates available

3. **Validation steps:**
   - Required file existence
   - White paper archetype count (min 22)
   - ZWO file XML validity
   - Power range validation
   - Regression test suite

## Validation Scripts

### `tests/validate_archetypes.py`

Standalone validation script. Run manually:

```bash
python tests/validate_archetypes.py
```

Checks:
- Required files exist
- White paper has minimum archetype count
- ZWO files are valid XML
- Power values in valid range (0.0-2.5 FTP)

### `tests/test_regression.py`

Pytest-based regression suite:

```bash
pytest tests/test_regression.py -v
```

Tests:
- Submodule existence and structure
- Critical archetypes documented
- 6-level progression system
- ZWO file validity and structure
- Category consistency
- Baseline counts (archetype, ZWO file minimums)

## Pinning to Specific Version

To pin the submodule to a specific commit:

```bash
cd knowledge/archetypes
git checkout <commit-hash>
cd ../..
git add knowledge/archetypes
git commit -m "Pin archetypes to <version>"
```

## Troubleshooting

### Submodule shows as modified but no changes

```bash
git submodule update --init --recursive
```

### Submodule is empty

```bash
git submodule update --init
```

### Detached HEAD in submodule

This is normal. Submodules are checked out at specific commits, not branches.

### CI fails on submodule checkout

Ensure the workflow uses:
```yaml
- uses: actions/checkout@v4
  with:
    submodules: recursive
```

## Migration from Duplicated Files

If you previously had archetype files duplicated in `knowledge/workout_templates/`:

1. The submodule now contains the canonical versions
2. Old files in `workout_templates/` can be removed or kept for reference
3. Update any imports/references to use `knowledge/archetypes/` paths

## Contact

For issues with the archetype library itself, see:
https://github.com/wattgod/nate-workout-archetypes
