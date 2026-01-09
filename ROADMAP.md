# Athlete OS Roadmap

Development priorities and next steps.

---

## Current State (January 2026)

### Completed
- [x] Athlete profile schema (`profile.yaml`)
- [x] Live state schema (`athlete_state.json`)
- [x] Readiness scoring system with factor weights
- [x] Health gates implementation (5 domains)
- [x] Knowledge base integration (Nate Wilson, frameworks)
- [x] System prompt v1.1 with readiness logic
- [x] Git submodules for archetypes and philosophies
- [x] Basic profile manager CRUD operations
- [x] CLAUDE.md context file for AI handoffs

### In Progress
- [ ] Intervals.icu sync automation
- [ ] WHOOP API integration

---

## Next Steps (Priority Order)

### P0: Data Pipeline

**1. Readiness Score Calculator**
Create `scripts/calculate_readiness.py` that:
- Reads current `athlete_state.json`
- Pulls latest WHOOP/HRV data
- Computes readiness score using factor weights
- Updates `readiness` and `health_gates` sections
- Runs daily via cron or on-demand

**2. Intervals.icu Sync Enhancement**
Update `scripts/intervals_sync.py` to:
- Pull PMC data (CTL, ATL, TSB)
- Pull zone distribution for rolling 7d
- Update `performance_management` section
- Calculate intensity distribution drift from 84/6/10 target

**3. WHOOP Integration**
Create `scripts/whoop_sync.py` that:
- Authenticates with WHOOP API
- Pulls daily recovery, HRV, sleep
- Updates `whoop_daily` and `fatigue_indicators`
- Triggers readiness recalculation

### P1: Weekly Planning Engine

**4. Weekly Intent Generator**
Create `scripts/generate_weekly_intent.py` that:
- Reads athlete profile (availability, goals)
- Reads current state (readiness, TSB, phase)
- Outputs weekly intent JSON:
  ```json
  {
    "key_sessions_target": 2,
    "aerobic_volume_hours": [8, 10],
    "priority": "respond > complete"
  }
  ```

**5. Daily Session Recommender**
Create `scripts/recommend_session.py` that:
- Checks health gates
- Checks readiness score
- Recommends session type (key/support/recovery)
- Suggests specific archetype from library

### P2: Automation & Alerts

**6. Alert Engine**
Create `scripts/check_alerts.py` that:
- Monitors TSB drift (< -20 warning)
- Monitors ramp rate (> 5 TSS/week warning)
- Monitors compliance (< 70% warning)
- Monitors zone distribution drift
- Updates `alerts.active` in state

**7. Daily Briefing Generator**
Create `scripts/daily_briefing.py` that:
- Generates morning coaching message
- Includes: readiness, recommended session, alerts
- Outputs markdown for review

### P3: Content & Reporting

**8. Weekly Review Generator**
Create `scripts/weekly_review.py` that:
- Summarizes week (TSS, hours, compliance)
- Analyzes zone distribution vs targets
- Identifies wins and flags
- Suggests next week adjustments

**9. Race Countdown Dashboard**
Create `scripts/race_countdown.py` that:
- Shows days to A-race
- CTL trajectory to target
- Key milestones remaining
- Risk factors

---

## Technical Debt

- [ ] Update `.cursor/rules.md` to match current architecture
- [ ] Add JSON schema validation for `athlete_state.json`
- [ ] Add unit tests for profile_manager.py
- [ ] Document Intervals.icu API setup in SETUP_GUIDE.md
- [ ] Create `.env.example` with required variables

---

## Future Considerations

### Phase 2: Multi-Athlete Support
- Roster management
- Cross-athlete insights
- Coach dashboard

### Phase 3: Workout Generation
- Auto-generate ZWO files from archetypes
- Push workouts to Intervals.icu calendar
- Adaptive plan modifications

### Phase 4: Performance Modeling
- Power-duration curve fitting
- Race performance prediction
- Optimal taper calculator

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-09 | Use Intervals.icu over TrainingPeaks | TP API not available |
| 2026-01-09 | Readiness threshold = 65 | Based on READINESS_ENGINE.md |
| 2026-01-09 | 5 health gates | Based on HEALTH_RECOVERY_ENGINE.md |
| 2026-01-09 | Factor weights: HRV 25%, Sleep 20%, Recovery 20%, TSB 20%, RHR 15% | Balanced approach, adjustable per athlete |

---

## Contact

Questions or contributions: Matti Rowe (Gravel God Coaching)
