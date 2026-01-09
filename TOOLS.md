# Athlete OS - Tools Manifest

Available operations for AI agents and automation.

## Data Sync

### `intervals_sync.py`
**Location:** `scripts/intervals_sync.py`
**Purpose:** Sync activities from Intervals.icu and run coaching analysis

```bash
# Sync last 90 days (default)
python scripts/intervals_sync.py

# Sync specific time range
python scripts/intervals_sync.py --days 30

# Sync all history
python scripts/intervals_sync.py --all

# Sync specific athlete (coaches)
python scripts/intervals_sync.py --athlete i12345
```

**Inputs:**
- `INTERVALS_API_KEY` - environment variable or `--api-key`
- `--athlete` - athlete ID (default: "0" = yourself)
- `--days` - number of days to sync
- `--config` - athlete config file path

**Outputs:**
- `./fit_files/*.fit` - raw activity files
- `./output/intervals_analysis.csv` - parsed metrics
- `./output/coaching_report.md` - recommendations
- `./output/alerts.json` - active alerts

---

## Analysis Tools

### `fetch_peak_powers.py`
**Location:** `scripts/fetch_peak_powers.py`
**Purpose:** Extract peak power values across durations

**Outputs:** Peak power curve data (1s, 5s, 30s, 1min, 5min, 20min, 60min)

### `build_readiness_model.py`
**Location:** `scripts/build_readiness_model.py`
**Purpose:** Build training readiness model from historical data

### `build_trainability_model.py`
**Location:** `scripts/build_trainability_model.py`
**Purpose:** Build athlete trainability model for optimization

---

## PWX Parser

### `PWXParser`
**Location:** `pwx_parser/parser.py`
**Purpose:** Parse PWX/TCX power files

```python
from pwx_parser.parser import PWXParser

parser = PWXParser(ftp=250, lthr=170)
data = parser.parse("activity.pwx")
```

**Returns:** Dict with power, HR, cadence arrays and metadata

### `GravelGodAnalyzer`
**Location:** `pwx_parser/gravel_god.py`
**Purpose:** Run coaching analysis on parsed activities

```python
from pwx_parser.gravel_god import GravelGodAnalyzer

analyzer = GravelGodAnalyzer(config, activities)
analyzer.generate_reports(output_path)
```

**Generates:**
- Coaching report with recommendations
- Alert detection (TSB, compliance, ramp rate)
- Zone distribution analysis

---

## Athlete Management

### Read Profile
```python
import yaml
from pathlib import Path

profile_path = Path("athletes/matti-rowe/profile.yaml")
with open(profile_path) as f:
    profile = yaml.safe_load(f)
```

### Read Live State
```python
import json
from pathlib import Path

state_path = Path("athletes/matti-rowe/athlete_state.json")
with open(state_path) as f:
    state = json.load(f)
```

### Update Athlete Profile
```python
from scripts.profile_manager import update_athlete

update_athlete("matti-rowe", {
    "physiology.ftp": 365,
    "status.phase": "build"
})
```

### Update Live State
```python
from scripts.profile_manager import update_state

update_state("matti-rowe", {
    "performance_management.ctl": 68,
    "performance_management.tsb": -5
})
```

---

## Workout Generation

### Knowledge Submodules

| Submodule | Path | Contents |
|-----------|------|----------|
| Archetypes | `knowledge/archetypes/` | 31 workout archetypes × 6 levels |
| Philosophies | `knowledge/philosophies/` | 13 training methodologies |

### ZWO Files
**Location:** `knowledge/archetypes/zwo_output_cleaned/`
**Format:** Zwift workout XML files

```xml
<workout_file>
  <name>G-Spot Intervals L3</name>
  <workout>
    <SteadyState Duration="600" Power="0.55"/>
    <IntervalsT Repeat="4" OnDuration="480" OnPower="0.90" OffDuration="240" OffPower="0.55"/>
    <SteadyState Duration="300" Power="0.50"/>
  </workout>
</workout_file>
```

---

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `INTERVALS_API_KEY` | Intervals.icu API access | Yes (for sync) |
| `STRAVA_CLIENT_ID` | Strava OAuth | No |
| `STRAVA_CLIENT_SECRET` | Strava OAuth | No |

---

## File Paths

```
athlete-coaching-system/
├── athletes/
│   ├── _template/
│   │   ├── profile.yaml          # Profile template
│   │   └── athlete_state.json    # State template
│   └── {athlete-name}/
│       ├── profile.yaml          # Athlete profile
│       └── athlete_state.json    # Live state
├── scripts/
│   ├── intervals_sync.py         # Main sync tool
│   ├── profile_manager.py        # CRUD operations
│   ├── fetch_peak_powers.py      # Peak power analysis
│   ├── build_readiness_model.py  # Readiness model
│   └── build_trainability_model.py
├── knowledge/
│   ├── archetypes/               # Workout archetypes (submodule)
│   └── philosophies/             # Training philosophies (submodule)
├── pwx_parser/
│   ├── parser.py                 # PWX/TCX parser
│   └── gravel_god.py             # Coaching analyzer
└── output/                       # Analysis results
```

---

## Agent Context Files

When building prompts, inject these files for full context:

1. **Static profile:** `athletes/{name}/profile.yaml`
2. **Live state:** `athletes/{name}/athlete_state.json`
3. **Philosophy docs:** `knowledge/philosophies/ENDURANCE_TRAINING_MODELS.md`
4. **Archetype library:** `knowledge/archetypes/WORKOUT_ARCHETYPES_WHITE_PAPER.md`

---

## Planned Tools (Not Yet Implemented)

- [ ] `strava_sync.py` - Strava activity sync
- [ ] `plan_builder.py` - Consolidated plan generation
- [ ] `workout_scheduler.py` - Auto-schedule workouts
- [ ] `race_predictor.py` - Performance prediction
