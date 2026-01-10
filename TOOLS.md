# Athlete OS - Tools Manifest

Available operations for AI agents and automation.

## Data Sync

### `intervals_sync.py`
**Location:** `scripts/intervals_sync.py`
**Purpose:** Sync activities and PMC data from Intervals.icu

```bash
# Sync athlete state (RECOMMENDED) - updates athlete_state.json
python3 scripts/intervals_sync.py --sync-state --athlete-name matti-rowe

# Full sync with analysis (downloads FIT files)
python3 scripts/intervals_sync.py --days 30

# Sync all history
python3 scripts/intervals_sync.py --all
```

**State Sync Mode (`--sync-state`):**
Updates `athlete_state.json` with:
- PMC data (CTL, ATL, TSB, ramp rate)
- Rolling 7-day zone distribution
- Zone drift warnings vs 84/6/10 target
- Last workout info

```bash
# Quick daily sync
python3 scripts/intervals_sync.py --sync-state --athlete-name matti-rowe

# Output:
#   CTL: 65.2
#   ATL: 72.1
#   TSB: -6.9
#   Zone distribution (7d): Z1-Z2 78% | Z3 12% | Z4+ 10%
#   ⚠️  Too little Z1-Z2 (-6.0% from target)
```

**Full Sync Mode (default):**
Downloads FIT files and runs coaching analysis.

**Inputs:**
- `INTERVALS_API_KEY` - environment variable or `--api-key`
- `--athlete` - Intervals.icu athlete ID (default: "0" = yourself)
- `--athlete-name` - Local athlete folder name (e.g., "matti-rowe")
- `--days` - number of days to sync
- `--sync-state` - sync PMC/zones to athlete_state.json

**Outputs:**
- State sync: Updates `athletes/{name}/athlete_state.json`
- Full sync: `./fit_files/*.fit`, `./output/intervals_analysis.csv`

---

### `whoop_sync.py`
**Location:** `scripts/whoop_sync.py`
**Purpose:** Sync recovery, sleep, and HRV data from WHOOP API

**Setup (one time):**
1. Create app at https://developer.whoop.com/dashboard
2. Set redirect URI to: `http://localhost:8080/callback`
3. Export credentials:
   ```bash
   export WHOOP_CLIENT_ID="your_client_id"
   export WHOOP_CLIENT_SECRET="your_client_secret"
   ```
4. Authenticate: `python3 scripts/whoop_sync.py --auth`

**Usage:**
```bash
# First time: authenticate
python3 scripts/whoop_sync.py --auth

# Sync data to athlete state
python3 scripts/whoop_sync.py --athlete-name matti-rowe

# Sync more history
python3 scripts/whoop_sync.py --athlete-name matti-rowe --days 14
```

**Data synced:**
- Recovery score (current + 7-day avg)
- HRV RMSSD (current + 7-day avg)
- Resting heart rate (current + 7-day avg)
- Sleep hours and stages
- SpO2, skin temperature

**Output:** Updates `athletes/{name}/athlete_state.json`:
- `whoop_daily` - latest day's metrics
- `fatigue_indicators.hrv` - HRV data
- `fatigue_indicators.whoop_recovery` - recovery scores
- `fatigue_indicators.sleep` - sleep data

---

## Readiness Engine

### `calculate_readiness.py`
**Location:** `scripts/calculate_readiness.py`
**Purpose:** Calculate readiness score and health gates from athlete state

```bash
# Calculate and update readiness for an athlete
python3 scripts/calculate_readiness.py matti-rowe

# Verbose output with factor breakdown
python3 scripts/calculate_readiness.py matti-rowe --verbose

# Dry run (don't save changes)
python3 scripts/calculate_readiness.py matti-rowe --dry-run

# Output raw JSON
python3 scripts/calculate_readiness.py matti-rowe --json
```

**Factors (weighted):**
- HRV status (25%) - % of baseline
- Sleep status (20%) - hours vs target, debt
- Recovery score (20%) - WHOOP recovery vs baseline
- TSB status (20%) - fatigue/freshness balance
- RHR status (15%) - elevation vs baseline

**Health Gates:**
- Sleep: minimum hours, debt accumulation
- Energy: weight trend, appetite
- Autonomic: HRV and RHR vs baseline, ANS quadrant detection
- Musculoskeletal: injury signals, soreness
- Stress: life stress, cognitive fatigue

**ANS Quadrant Detection:**
Uses orthostatic HR test data (if available) to determine autonomic nervous system state:
- Q1: Deep Recovery (High PNS, Low SNS) - support sessions only
- Q2: Ready to Train (High PNS, High SNS) - optimal for key sessions (+10 bonus)
- Q3: Sympathetic Overreach (Low PNS, High SNS) - recovery only (-15 penalty)
- Q4: Overtrained (Low PNS, Low SNS) - extended recovery (-25 penalty)

See `knowledge/frameworks/HRV_ANS_QUADRANTS.md` for full documentation.

**Output:** Updates `athlete_state.json` with `readiness` and `health_gates` sections

---

## Daily Workflow

### `morning_check_in.py`
**Location:** `scripts/morning_check_in.py`
**Purpose:** Collect subjective readiness data from the athlete

```bash
# Interactive mode
python3 scripts/morning_check_in.py matti-rowe

# Command-line mode
python3 scripts/morning_check_in.py matti-rowe \
    --sleep-quality 8 --fatigue 3 --stress 4 --soreness 2 --motivation 8

# With orthostatic HR test (improves ANS quadrant detection)
python3 scripts/morning_check_in.py matti-rowe \
    --sleep-quality 8 --fatigue 3 --stress 4 --soreness 2 --motivation 8 \
    --hr-lying 52 --hr-standing 68

# With notes
python3 scripts/morning_check_in.py matti-rowe \
    --sleep-quality 7 --fatigue 4 --stress 3 --soreness 2 --motivation 7 \
    --notes "Felt a bit tired waking up"
```

**Ratings (1-10):**
- Sleep quality (10 = best)
- Fatigue level (10 = worst)
- Life stress (10 = worst)
- Muscle soreness (10 = worst)
- Motivation (10 = best)

**Orthostatic HR Test (Optional):**
- `--hr-lying` - Heart rate after lying still for 2-5 minutes
- `--hr-standing` - Heart rate 60 seconds after standing
- Delta (standing - lying) is used for ANS quadrant detection:
  - Normal: 10-20 bpm
  - Blunted (<10): Deep recovery or fatigue
  - Elevated (>25): Sympathetic activation

**Output:** Updates `athlete_state.json` with `subjective_data` and `fatigue_indicators.orthostatic` sections

---

### `morning_survey_email.py`
**Location:** `scripts/morning_survey_email.py`
**Purpose:** Send morning check-in survey via email

```bash
# Print survey to console
python3 scripts/morning_survey_email.py matti-rowe --print

# Send via email
python3 scripts/morning_survey_email.py matti-rowe --email

# Send to specific address
python3 scripts/morning_survey_email.py matti-rowe --email --to gravelgodcoaching@gmail.com
```

---

### `daily_briefing.py`
**Location:** `scripts/daily_briefing.py`
**Purpose:** Generate and email daily coaching briefing

```bash
# Print briefing to console
python3 scripts/daily_briefing.py matti-rowe

# Send via email
python3 scripts/daily_briefing.py matti-rowe --email

# Full workflow: sync + calculate + email
python3 scripts/daily_briefing.py matti-rowe --sync --calculate --email
```

**Output:**
- Readiness score with color coding
- Health gates status
- Session recommendation (key/support/recovery)
- Training load (CTL, ATL, TSB)

---

### `daily_workflow.py`
**Location:** `scripts/daily_workflow.py`
**Purpose:** Orchestrate the complete daily workflow

```bash
# Morning: Send survey (for cron at 6am)
python3 scripts/daily_workflow.py matti-rowe --survey --email

# After check-in: Full briefing
python3 scripts/daily_workflow.py matti-rowe --briefing --sync --email

# All-in-one interactive
python3 scripts/daily_workflow.py matti-rowe --interactive --sync --email
```

**Cron Examples:**
```bash
# Send survey every morning at 6am
0 6 * * * cd /path/to/athlete-coaching-system && python3 scripts/daily_workflow.py matti-rowe --survey --email

# Or use launchd on macOS (see docs)
```

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
| `INTERVALS_API_KEY` | Intervals.icu API access | Yes (for intervals sync) |
| `WHOOP_CLIENT_ID` | WHOOP OAuth client ID | Yes (for WHOOP sync) |
| `WHOOP_CLIENT_SECRET` | WHOOP OAuth client secret | Yes (for WHOOP sync) |
| `GMAIL_ADDRESS` | Gmail address for sending emails | Yes (for daily briefing) |
| `GMAIL_APP_PASSWORD` | Gmail App Password (NOT regular password) | Yes (for daily briefing) |
| `STRAVA_CLIENT_ID` | Strava OAuth | No |
| `STRAVA_CLIENT_SECRET` | Strava OAuth | No |

**Gmail App Password Setup:**
1. Enable 2FA on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Create a new app password for "Mail"
4. Set `GMAIL_APP_PASSWORD` to the generated password

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
│   ├── intervals_sync.py         # Intervals.icu data sync
│   ├── whoop_sync.py             # WHOOP data sync
│   ├── calculate_readiness.py    # Readiness score calculator
│   ├── morning_check_in.py       # Subjective data collection
│   ├── morning_survey_email.py   # Send survey via email
│   ├── daily_briefing.py         # Generate/email briefing
│   ├── daily_workflow.py         # Full workflow orchestrator
│   ├── profile_manager.py        # CRUD operations
│   ├── fetch_peak_powers.py      # Peak power analysis
│   ├── build_readiness_model.py  # Readiness model training
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
