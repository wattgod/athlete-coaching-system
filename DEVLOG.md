# Athlete OS - Development Log

Daily development progress and decisions.

---

## 2026-01-11

### Coaching Intake Questionnaire
Adapted training plan questionnaire for ongoing coaching intake.

**New Files:**
- `docs/athlete-questionnaire.html` - 12-section coaching intake form (1489 lines)
- `docs/QUESTIONNAIRE_ANALYSIS.md` - Gap analysis and implementation plan
- `scripts/create_profile_from_questionnaire.py` - Parses form output to profile.yaml + athlete_state.json

**Form Features:**
- Progress bar with section completion tracking
- Save/restore progress via localStorage
- Conditional fields (race details, Intervals.icu ID)
- Equipment & Integrations section (WHOOP, Garmin, Intervals.icu)
- Baseline physiology (RHR, sleep hours, HRV)
- Coaching Preferences (frequency, detail, autonomy, style)
- Mental Game section with inferred questions
- Work & Life context section
- Blindspot and trait inference on submission

**Profile Creation Script:**
- Parses markdown questionnaire output
- Calculates power zones from FTP
- Infers schedule from day selections
- Maps coaching preferences to system settings
- Creates both profile.yaml and athlete_state.json
- Run: `python scripts/create_profile_from_questionnaire.py response.md`

**GitHub Issue Flow:**
- Form submits directly to GitHub Issues with title "Athlete Intake: {name}"
- `.github/workflows/athlete-intake.yml` auto-processes submissions
- Creates profile.yaml and athlete_state.json automatically
- Closes issue with profile summary on success
- Live at: https://wattgod.github.io/athlete-coaching-system/athlete-questionnaire.html

**Enhanced Blindspot Inference:**
- Alcohol patterns → "Alcohol Recovery Impact"
- Dieting/weight patterns → "Weight Management Stress"
- Caffeine patterns → "Caffeine Dependency"
- Sleep issues → "Sleep Disorder"

### Metrics Export Import
Script to import Intervals.icu CSV exports (WHOOP data) into athlete state.

**New File:**
- `scripts/import_metrics_export.py` - Parses metrics CSV, updates athlete_state.json

**Features:**
- Reads Intervals.icu metrics export (WHOOP HRV, RHR, Sleep, Recovery)
- Calculates 7-day rolling averages for baselines
- Determines HRV/RHR trends (stable, elevated, suppressed)
- Calculates sleep quality from deep + REM ratio
- Updates both fatigue_indicators and health_gates

**Usage:**
```bash
python scripts/import_metrics_export.py /path/to/metrics.csv athletes/matti-rowe
```

### Intervals.icu UI Integration
Integrated Intervals.icu-inspired UI patterns into the dashboard.

**New Documentation:**
- `docs/INTERVALS_UI_INTEGRATION.md` - Full color scheme and feature documentation

**PMC Chart Enhancements:**
- CTL (blue #2196F3), ATL (pink #E91E63), TSB (yellow #FFC107) - Intervals.icu colors
- TSB zone backgrounds: Fresh (green), Optimal (darker green), Gray (transition), Risk (red)
- Daily load bars (purple histogram) at top of chart
- Zone labels: FRESH, OPTIMAL, RISK

**Calendar Improvements:**
- Weekly TSS progress bar with color coding (blue: under, green: on-target, yellow: over)
- Intensity skyline bars on each activity showing zone distribution
- Zwift/Garmin standard zone colors (Z1: gray, Z2: blue, Z3: green, Z4: yellow, Z5: red)

**CSS Variables Added:**
```css
--ctl-blue: #2196F3;
--atl-pink: #E91E63;
--tsb-yellow: #FFC107;
--zone1 through --zone6
```

**Sources:**
- [Intervals.icu Forum - Calendar Update](https://forum.intervals.icu/t/calendar-and-week-info-update/109142)
- [Intervals.icu Forum - Skyline Chart](https://forum.intervals.icu/t/activity-skyline-chart-on-the-calendar/59341)
- [Intervals.icu Forum - Fitness Graph Colors](https://forum.intervals.icu/t/fitness-graph-colors/8619)

### Athlete Dashboard ("Situation Station")
Neo-Brutalist web dashboard for athletes to view their complete coaching status.

**New Files:**
- `docs/dashboard.html` - Full athlete dashboard (GitHub Pages)
- `scripts/generate_dashboard.py` - Aggregates data for dashboard display
- `scripts/fetch_history.py` - Fetches PMC and activity history from Intervals.icu
- `athletes/matti-rowe/dashboard_data.json` - Pre-computed dashboard data

**Dashboard Views (Tabbed):**
1. **Today** - Current readiness and daily recommendation (original view)
2. **Calendar** - Month grid with completed workouts and race dates
3. **Trends** - PMC chart (CTL/ATL/TSB), weekly volume bar chart, period stats

**Today View Sections:**
1. **Readiness Hero** - Large score (0-100) with color coding, ANS quadrant badge
2. **Health Gates** - 5 gates with pass/fail indicators
3. **Today's Session** - Workout recommendation with rationale
4. **Training Load (PMC)** - CTL/ATL/TSB metrics
5. **Recent Training** - 7-day summary with zone distribution bars
6. **Blindspots** - Active blindspots, adjusted thresholds, daily reminders
7. **Weekly Intent** - Key sessions remaining, volume targets
8. **Race Countdown** - Days to A-race, CTL trajectory
9. **Alerts** - Active and recently resolved

**Calendar View Features:**
- Month navigation (prev/next)
- Completed workouts with TSS
- Race dates highlighted with priority (A/B/C)
- Today highlight
- Legend for activity types

**Trends View Features:**
- SVG line chart for CTL, ATL, TSB (90 days)
- Weekly TSS bar chart
- Period stats: Total TSS, Avg/Week, Activities, Hours
- Custom SVG charts (no external libraries)

**Accessibility Features:**
- Data freshness banner with color-coded status
- Skip link for keyboard navigation
- ARIA labels throughout
- Text labels alongside colors (READY/CAUTION/RECOVER)
- PASS/FAIL text on health gates

**Design System:**
- Sometype Mono font (monospace)
- 3px solid black borders
- Uppercase headings with letter-spacing
- Color-coded readiness (green/yellow/red)
- Responsive mobile layout

**Usage:**
```bash
python scripts/generate_dashboard.py matti-rowe --include-history
# Then open docs/dashboard.html in browser
```

**Live URL:** https://wattgod.github.io/athlete-coaching-system/dashboard.html

### Blindspot Rules Engine
Centralized system for coaching adjustments based on athlete blindspots.

**New Files:**
- `scripts/blindspot_rules.py` - Core rules engine with threshold adjustments
- `knowledge/frameworks/BLINDSPOT_RULES.md` - Full documentation

**Features:**
- 12 blindspot types with specific adjustments
- Threshold stacking (most conservative wins)
- Gate weight multipliers (sleep, MSK, stress)
- Context-aware prompts (daily, pre-ride, recovery)
- Blindspot-specific alert conditions

**Integrated Into:**
- `calculate_readiness.py` - Adjusted thresholds, gate weights, blindspot info in output
- `daily_briefing.py` - "Today's Reminders" section, adjusted thresholds banner
- `check_alerts.py` - Blindspot-specific alerts, adjusted ramp rate checks

**Example Adjustments (Matti's Profile):**
- Key session threshold: 70 (normally 65)
- Max ramp rate: 5.0 TSS/day (normally 7)
- TSB floor: -20 (normally -30)
- Min rest days: 2/week
- RHR offset: +4 bpm (caffeine adjustment)
- MSK gate: 1.8x sensitivity (injury + movement gap)

### Ralph Autonomous Agent - ALL 8 STORIES COMPLETE
Set up and executed Ralph loop for autonomous task completion.

**New Scripts Created:**
- `scripts/generate_weekly_intent.py` - Weekly intent based on TSB/readiness/phase
- `scripts/recommend_session.py` - Daily session recommendation with archetype selection
- `scripts/check_alerts.py` - Alert engine monitoring TSB, ramp rate, compliance, zones
- `scripts/weekly_review.py` - Weekly summary with wins/flags/suggestions
- `scripts/race_countdown.py` - Race countdown dashboard with CTL trajectory
- `scripts/validate_state.py` - JSON Schema validation for athlete_state.json
- `tests/test_profile_manager.py` - 29 unit tests for profile manager
- `schemas/athlete_state.schema.json` - JSON Schema for state validation
- `docs/SETUP_INTERVALS.md` - Intervals.icu setup documentation

**Ralph Infrastructure:**
- `scripts/ralph/ralph.sh` - Bash loop for autonomous execution
- `scripts/ralph/prompt.md` - Agent instructions per iteration
- `scripts/ralph/prd.json` - Story tracking (8/8 complete)
- `scripts/ralph/progress.txt` - Accumulated learnings

### Development Practices
- Created `.env.example` with documentation for all required environment variables
- Variables: INTERVALS_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, WHOOP credentials
- Confirmed `.env` is in .gitignore

---

## 2026-01-09

### Daily Workflow System
Built complete daily check-in and briefing workflow:
- `scripts/morning_check_in.py` - Subjective data collection (sleep, fatigue, stress, soreness, motivation)
- `scripts/morning_survey_email.py` - Morning brief email with check-in link
- `scripts/daily_briefing.py` - Neo-Brutalist HTML briefing with readiness score
- `scripts/daily_workflow.py` - Orchestrates full workflow

### GitHub Check-In Flow
- `docs/checkin.html` - Neo-Brutalist web form for check-in (GitHub Pages)
- `.github/workflows/daily-checkin.yml` - Action triggers on issue, runs scripts, sends briefing

### ANS Quadrant Framework
Implemented advanced HRV analysis based on Alan Couzens research:
- `knowledge/frameworks/HRV_ANS_QUADRANTS.md` - Full documentation
- Four quadrants: Q1 (Deep Recovery), Q2 (Ready), Q3 (Overreach), Q4 (Overtrained)
- Q2 gives +10 readiness bonus, Q3/Q4 block intensity
- Orthostatic HR test integration for sympathetic detection

### Readiness Calculation Updates
- Added ANS quadrant detection to `calculate_readiness.py`
- Health gates now pull from check-in data (soreness → musculoskeletal, stress → stress gate)
- Orthostatic data stored in `fatigue_indicators.orthostatic`

### Data Sync
- Tested Intervals.icu sync - real PMC data: CTL 10.2, ATL 21.9, TSB -11.6
- WHOOP sync available but requires developer credentials

### Design System
Neo-Brutalist email design:
- Sometype Mono font
- 3px solid black borders
- Color-coded readiness score (green/yellow/red)
- Uppercase headings, wide letter-spacing
- Table-style metrics

---

## Earlier Work (Pre-Log)

See `ROADMAP.md` for completed items:
- Athlete profile schema
- Live state schema
- Readiness scoring system
- Health gates (5 domains)
- WHOOP API integration
- Intervals.icu sync
- Knowledge base structure
