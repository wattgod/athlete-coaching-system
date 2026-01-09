# Athlete OS

Agent-native coaching system for endurance athletes.

## What Is This?

Athlete OS is a framework for AI-assisted endurance coaching. It combines:

- **Training science** - Readiness models, health gates, periodization frameworks
- **Real-time state** - Live athlete data from WHOOP, Intervals.icu, Garmin
- **AI coaching** - LLM-powered recommendations using structured context

Built by [Gravel God Coaching](https://gravelgod.com) for scaling personalized coaching.

## Quick Start

```bash
# Clone with submodules
git clone --recursive https://github.com/wattgod/athlete-coaching-system.git
cd athlete-coaching-system

# Set up environment
cp .env.example .env
# Add your INTERVALS_API_KEY to .env

# Sync athlete data
python scripts/intervals_sync.py --days 30

# View athlete state
cat athletes/matti-rowe/athlete_state.json | jq '.readiness'
```

## Project Structure

```
athlete-coaching-system/
├── athletes/                    # Athlete data
│   ├── _template/               # New athlete template
│   └── matti-rowe/              # Example athlete
│       ├── profile.yaml         # Static profile (goals, zones, history)
│       └── athlete_state.json   # Live state (readiness, fatigue, PMC)
├── knowledge/                   # Training knowledge base
│   ├── coaching/                # Nate Wilson methodology
│   ├── frameworks/              # Readiness, planning, health engines
│   ├── archetypes/              # Workout library (submodule)
│   └── philosophies/            # Training models (submodule)
├── prompts/                     # AI system prompts
│   └── system_prompt.md         # Coaching AI behavior
├── scripts/                     # Automation tools
│   ├── intervals_sync.py        # Data sync
│   └── profile_manager.py       # CRUD operations
├── CLAUDE.md                    # AI context file
├── TOOLS.md                     # Available operations
└── ROADMAP.md                   # Development priorities
```

## Core Concepts

### Readiness-Gated Training

Training decisions are gated by readiness score (0-100):

| Score | Status | Allowed Sessions |
|-------|--------|------------------|
| 65+ | Green | Key sessions (threshold, VO2max) |
| 40-65 | Yellow | Support sessions (endurance, technique) |
| < 40 | Red | Recovery only |

### Health Gates

Before any intensity, check 5 health gates:
- **Sleep** - 7+ hours, no debt
- **Energy** - Stable weight, normal appetite
- **Autonomic** - HRV near baseline
- **Musculoskeletal** - No injury signals
- **Stress** - Life stress tolerable

If ANY gate fails → intensity blocked.

### Zone Distribution (Nate Wilson)

Target distribution for gravel/ultra athletes:
- **84% Zone 1-2** - Aerobic foundation
- **6% G-Spot (Z3)** - Sweet spot work
- **10% Zone 4+** - High intensity

## Documentation

- [CLAUDE.md](CLAUDE.md) - AI assistant context
- [TOOLS.md](TOOLS.md) - Available scripts and operations
- [ROADMAP.md](ROADMAP.md) - Development priorities
- [prompts/system_prompt.md](prompts/system_prompt.md) - Coaching AI behavior

## Knowledge Base

| Document | Purpose |
|----------|---------|
| `knowledge/coaching/NATE_WILSON_COACHING_v3.md` | Core methodology, Four Pillars |
| `knowledge/frameworks/READINESS_ENGINE.md` | Readiness prediction model |
| `knowledge/frameworks/WEEKLY_PLANNING_ENGINE.md` | Session gating logic |
| `knowledge/frameworks/HEALTH_RECOVERY_ENGINE.md` | Health gates, recovery |
| `knowledge/frameworks/ATHLETE_GOAL_FRAMEWORK.md` | Goal setting framework |

## Data Sources

| Source | Data | Sync Method |
|--------|------|-------------|
| Intervals.icu | Activities, PMC, zones | `intervals_sync.py` |
| WHOOP | HRV, sleep, recovery | Manual (API planned) |
| Garmin | Activities | Via Intervals.icu |

## License

Private repository. All rights reserved.
