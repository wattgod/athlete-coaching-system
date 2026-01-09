# Gravel God Coaching - Cursor Rules

Rules for AI assistants in Cursor IDE. For full context, see `CLAUDE.md` in project root.

## Voice & Tone

**Do:**
- Be direct and honest, no fluff
- Lead with "Recovery makes you fast"
- Use "You don't get a medal for being tired"
- Employ occasional dry humor
- Be confident but not arrogant
- Focus on sustainable performance

**Don't:**
- Say "Crush it!" or "Beast mode!"
- Use motivation-poster language
- Be corporate or generic
- Over-explain or hedge unnecessarily

## Repository Structure

```
athlete-coaching-system/
├── athletes/
│   ├── _template/
│   │   ├── profile.yaml          # Profile template
│   │   └── athlete_state.json    # State template
│   └── {athlete-name}/
│       ├── profile.yaml          # Static profile (goals, zones, history)
│       └── athlete_state.json    # Live state (readiness, fatigue, PMC)
├── knowledge/
│   ├── coaching/                 # Nate Wilson methodology
│   │   └── NATE_WILSON_COACHING_v3.md
│   ├── frameworks/               # System frameworks
│   │   ├── READINESS_ENGINE.md
│   │   ├── WEEKLY_PLANNING_ENGINE.md
│   │   ├── HEALTH_RECOVERY_ENGINE.md
│   │   └── ATHLETE_GOAL_FRAMEWORK.md
│   ├── archetypes/               # Workout library (git submodule)
│   └── philosophies/             # Training models (git submodule)
├── prompts/
│   └── system_prompt.md          # Coaching AI system prompt
├── scripts/
│   ├── intervals_sync.py         # Data sync from Intervals.icu
│   └── profile_manager.py        # CRUD for athlete data
├── CLAUDE.md                     # AI context file (read this!)
├── TOOLS.md                      # Available operations
└── ROADMAP.md                    # Development priorities
```

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Full AI context - read first |
| `prompts/system_prompt.md` | Coaching AI behavior |
| `TOOLS.md` | Available scripts and operations |
| `ROADMAP.md` | Current priorities and next steps |

## Readiness System

Athlete state includes readiness scoring:

```json
{
  "readiness": {
    "score": 58,
    "threshold_key_session": 65,
    "key_session_eligible": false,
    "recommendation": "yellow"
  }
}
```

**Decision Logic:**
- Score ≥ 70 → Key session eligible
- Score 45-70 → Support sessions only
- Score < 45 → Recovery mandatory

## Health Gates

Check before prescribing intensity:
- **Sleep**: 7+ hours, no debt
- **Energy**: Stable weight, normal appetite
- **Autonomic**: HRV near baseline
- **Musculoskeletal**: No injury signals
- **Stress**: Life stress tolerable

If ANY gate fails → intensity blocked.

## Key Metrics

| Metric | Yellow Flag | Red Flag |
|--------|-------------|----------|
| TSB | < -20 | < -30 |
| Compliance | < 70% | < 50% |
| Ramp Rate | > 5 TSS/wk | > 8 TSS/wk |
| Decoupling | > 5% | > 10% |

## Zone Distribution (Target)

Nate Wilson methodology:
- **84% Zone 1-2** - Aerobic foundation
- **6% G-Spot (Z3)** - Sweet spot work (88-94% FTP)
- **10% Zone 4+** - High intensity

## Power Zones (% FTP)

| Zone | Range | Name |
|------|-------|------|
| Z1 | < 55% | Active Recovery |
| Z2 | 55-75% | Endurance |
| Z3 | 76-90% | Tempo |
| Z4 | 91-105% | Threshold |
| Z5 | 106-120% | VO2max |
| Z6 | 121-150% | Anaerobic |
| Z7 | > 150% | Neuromuscular |
| G-Spot | 84-97% | Sweet Spot |

## Common Operations

```python
# Read athlete state
import json
with open("athletes/matti-rowe/athlete_state.json") as f:
    state = json.load(f)

# Update state
from scripts.profile_manager import update_state
update_state("matti-rowe", {"readiness.score": 72})

# Sync data
# python scripts/intervals_sync.py --days 7
```

## File Conventions

- Athlete folders: lowercase, hyphenated (`matti-rowe/`)
- YAML frontmatter on content files
- ISO 8601 dates (YYYY-MM-DD)
- Power in watts, duration in seconds
