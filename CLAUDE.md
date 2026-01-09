# Athlete OS - Claude Code Context

Primary context file for AI assistants working on this project.

## Project Overview

**Athlete OS** is an agent-native coaching system for endurance athletes. It combines training science frameworks, real-time athlete state, and AI coaching to deliver personalized training recommendations.

**Owner:** Matti Rowe (Gravel God Coaching)
**Primary Use Case:** Self-coaching for Unbound 200 preparation

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ATHLETE OS                                │
├─────────────────────────────────────────────────────────────────┤
│  KNOWLEDGE LAYER                                                 │
│  ├── knowledge/coaching/     → Nate Wilson methodology          │
│  ├── knowledge/frameworks/   → Readiness, Planning, Health      │
│  ├── knowledge/archetypes/   → 31 workout types (submodule)     │
│  └── knowledge/philosophies/ → 13 training models (submodule)   │
├─────────────────────────────────────────────────────────────────┤
│  STATE LAYER                                                     │
│  ├── athletes/{name}/profile.yaml      → Static athlete config  │
│  └── athletes/{name}/athlete_state.json → Live state + readiness│
├─────────────────────────────────────────────────────────────────┤
│  PROMPT LAYER                                                    │
│  └── prompts/system_prompt.md → Coaching AI system prompt       │
├─────────────────────────────────────────────────────────────────┤
│  TOOLS LAYER                                                     │
│  ├── scripts/intervals_sync.py   → Data sync from Intervals.icu │
│  ├── scripts/profile_manager.py  → CRUD for athlete data        │
│  └── pwx_parser/                 → Activity analysis             │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files to Read First

1. **`prompts/system_prompt.md`** - How the coaching AI should behave
2. **`athletes/matti-rowe/athlete_state.json`** - Live state with readiness scoring
3. **`athletes/matti-rowe/profile.yaml`** - Athlete profile and goals
4. **`TOOLS.md`** - Available operations and scripts
5. **`ROADMAP.md`** - Current priorities and next steps

## Knowledge Documents

### Coaching Methodology
- `knowledge/coaching/NATE_WILSON_COACHING_v3.md` - **Core methodology**
  - Four Pillars: Patience, Changing Pace, Durability, Fueling
  - Zone distribution: 84% Z1-Z2, 6% G-Spot, 10% Z4+
  - 16 workout archetypes × 5 progression levels

### System Frameworks
- `knowledge/frameworks/READINESS_ENGINE.md` - Readiness prediction model
- `knowledge/frameworks/WEEKLY_PLANNING_ENGINE.md` - Readiness-gated planning
- `knowledge/frameworks/HEALTH_RECOVERY_ENGINE.md` - Health gates, k1 multiplier
- `knowledge/frameworks/ATHLETE_GOAL_FRAMEWORK.md` - Goal setting, habit formation

### Reference Libraries (Git Submodules)
- `knowledge/archetypes/` - Workout library with ZWO files
- `knowledge/philosophies/` - Training philosophy selection framework

## Readiness System

The athlete state includes a **readiness scoring system**:

```json
{
  "readiness": {
    "score": 58,
    "threshold_key_session": 65,
    "key_session_eligible": false,
    "recommendation": "yellow"
  },
  "health_gates": {
    "sleep": { "gate_pass": true },
    "energy": { "gate_pass": true },
    "autonomic": { "gate_pass": true },
    "musculoskeletal": { "gate_pass": true },
    "stress": { "gate_pass": true },
    "overall": { "intensity_allowed": true }
  }
}
```

**Decision Logic:**
- Score ≥ 70 → Key session eligible (threshold, VO2max, race-specific)
- Score 45-70 → Support sessions only (endurance, technique)
- Score < 45 → Recovery mandatory
- Any health gate fail → Intensity blocked

## Data Flow

```
WHOOP/Garmin → Intervals.icu → intervals_sync.py → athlete_state.json
                                                          ↓
                                              AI reads state + profile
                                                          ↓
                                              Coaching recommendation
```

## Voice & Tone

- Direct and honest, no fluff
- "Recovery makes you fast"
- "You don't get a medal for being tired"
- Occasional dry humor
- Focus on sustainable performance
- Never say "Crush it!" or "Beast mode!"

## Common Tasks

### Check Athlete Readiness
```bash
cat athletes/matti-rowe/athlete_state.json | jq '.readiness'
```

### Update Athlete State
```python
from scripts.profile_manager import update_state
update_state("matti-rowe", {"readiness.score": 72})
```

### Sync Latest Data
```bash
python scripts/intervals_sync.py --days 7
```

## Current Sprint Focus

See `ROADMAP.md` for current priorities. Key areas:
1. Intervals.icu sync automation
2. Readiness score calculation script
3. Weekly planning automation

## Git Workflow

- Main branch: `main`
- Submodules: `knowledge/archetypes/`, `knowledge/philosophies/`
- After pulling: `git submodule update --init --recursive`
