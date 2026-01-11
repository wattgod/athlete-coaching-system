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
- [x] `calculate_readiness.py` - Automated readiness score calculation

### Recently Completed
- [x] WHOOP API integration - `whoop_sync.py` with OAuth2 flow
- [x] Intervals.icu sync enhancement - `--sync-state` mode for PMC + zones
- [x] Daily workflow with email - `morning_check_in.py`, `daily_briefing.py`, `daily_workflow.py`
- [x] GitHub check-in workflow - `docs/checkin.html` + GitHub Action
- [x] ANS Quadrant detection - HRV analysis with sympathetic/parasympathetic balance
- [x] Orthostatic HR test - Optional input for improved ANS quadrant detection

---

## Next Steps (Priority Order)

### P0: Data Pipeline

**1. Readiness Score Calculator** ✅ DONE
`scripts/calculate_readiness.py` implemented:
- Reads current `athlete_state.json`
- Computes readiness score using factor weights (HRV 25%, Sleep 20%, Recovery 20%, TSB 20%, RHR 15%)
- Checks all 5 health gates
- Updates `readiness` and `health_gates` sections
- Run with: `python3 scripts/calculate_readiness.py matti-rowe --verbose`

**2. Intervals.icu Sync Enhancement** ✅ DONE
`scripts/intervals_sync.py --sync-state` implemented:
- Pulls PMC data (CTL, ATL, TSB, ramp rate) from wellness API
- Calculates rolling 7-day zone distribution from activity streams
- Compares vs 84/6/10 target with drift warnings
- Updates `performance_management` and `recent_training` sections
- Run with: `python3 scripts/intervals_sync.py --sync-state --athlete-name matti-rowe`

**3. WHOOP Integration** ✅ DONE
`scripts/whoop_sync.py` implemented:
- OAuth2 authentication with local callback server
- Pulls recovery, HRV, sleep data from WHOOP API v1
- Updates `whoop_daily` and `fatigue_indicators` sections
- Stores refresh tokens for subsequent runs
- Run with: `python3 scripts/whoop_sync.py --auth` (first time)
- Then: `python3 scripts/whoop_sync.py --athlete-name matti-rowe`

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

**7. Daily Briefing Generator** ✅ DONE
`scripts/daily_briefing.py` and `scripts/daily_workflow.py` implemented:
- Morning survey email (`morning_survey_email.py`)
- Subjective check-in collection (`morning_check_in.py`)
- Daily briefing with readiness, health gates, session recommendations
- Email delivery via Gmail SMTP
- Orchestrated workflow for cron scheduling

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
- [x] Create `.env.example` with required variables

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
| 2026-01-09 | Gmail SMTP for email delivery | Simple, no external service needed |
| 2026-01-09 | CLI-based check-in (not email reply) | Simpler than IMAP polling, can add web form later |
| 2026-01-09 | ANS Quadrant framework | Based on Alan Couzens - RMSSD alone insufficient |
| 2026-01-09 | Orthostatic HR test as SNS proxy | Most wearables lack frequency domain HRV |
| 2026-01-09 | Q3 blocks intensity automatically | Sympathetic overreach = high injury/illness risk |

---

## Contact

Questions or contributions: Matti Rowe (Gravel God Coaching)
