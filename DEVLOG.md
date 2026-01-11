# Athlete OS - Development Log

Daily development progress and decisions.

---

## 2026-01-11

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
