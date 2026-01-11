# Athlete Questionnaire Analysis & Recommendations

Adapting the training plan questionnaire for ongoing coaching with Athlete OS.

---

## Current Form Analysis

**Source:** `training-plan-questionnaire.html` (7 sections, ~25 questions)

### Strengths
- Clean Neo-Brutalist design (Sometype Mono, cream/charcoal)
- Smart inference: calculates W/kg, detects "blindspots"
- Practical scheduling questions (long ride days, interval days, off days)
- Real-time validation (weeks until race, past date detection)
- Mobile responsive

### Designed For: Training Plans (One-Time)
- Race-focused (single target event)
- Fixed timeline
- No ongoing relationship
- No monitoring/check-in infrastructure

---

## Coaching vs Training Plans: Key Differences

| Aspect | Training Plan | Coaching |
|--------|---------------|----------|
| Relationship | One-time | Ongoing |
| Goals | Single race | Evolving targets |
| Monitoring | None | Daily/weekly check-ins |
| Adjustment | Fixed plan | Adaptive, readiness-gated |
| Data sources | Self-reported | WHOOP, Intervals.icu, check-ins |
| Communication | Delivery only | Regular touchpoints |

---

## What Athlete OS Needs (Gap Analysis)

### Currently Captured in Form
- [x] Name, email, contact
- [x] Age, weight, sex
- [x] FTP, HR zones
- [x] Weekly hours available
- [x] Sleep quality (high-level)
- [x] Stress level
- [x] Schedule constraints (long ride days, interval days, off days)
- [x] Strength training status
- [x] Injuries/limitations
- [x] Race goal and date

### Missing for Athlete OS

#### 1. Wearable/Integration Setup (Critical)
```
- Do you use WHOOP? (yes/no → WHOOP sync setup)
- Do you use a Garmin device? (model → HRV data availability)
- What platform do you track training? (Intervals.icu, TrainingPeaks, Strava)
- Intervals.icu athlete ID (for PMC sync)
```
**Why:** Athlete OS pulls real data from these sources. Without them, we rely on manual input.

#### 2. Baseline Physiology (Health Gates)
```
- Resting heart rate (baseline for autonomic gate)
- Average sleep hours per night (baseline for sleep gate)
- HRV if known (WHOOP users have this)
- Any chronic conditions affecting recovery? (for energy gate)
```
**Why:** Readiness scoring compares daily values to personal baselines.

#### 3. Recovery Profile
```
- How quickly do you bounce back from hard efforts? (fast/normal/slow)
- Age-adjusted recovery expectations
- History of overtraining/burnout?
```
**Why:** Affects k1 multiplier and recovery day recommendations.

#### 4. Communication & Accountability
```
- How often do you want check-ins? (daily/few times week/weekly)
- Preferred communication method (email/text/app)
- How much detail do you want in feedback? (minimal/moderate/comprehensive)
- How much autonomy do you prefer? (tell me exactly/general guidance/high autonomy)
```
**Why:** Personalizes AI coaching style and frequency.

#### 5. Psychographics (Inferred Questions)
```
- When you miss a workout, how do you typically respond?
  → Infers: perfectionism, flexibility, self-compassion
- What's your biggest fear about this training block?
  → Infers: anxiety triggers, mental game needs
- Describe your best training period ever. What made it work?
  → Infers: what conditions lead to success
```
**Why:** Reveals mental patterns without direct "rate your anxiety" questions.

#### 6. Life Context (Time Management)
```
- Do you work? Hours per week? Job stress level?
- Family situation (partner, kids, ages)
- Regular time commitments besides training
- Travel frequency
```
**Why:** Affects realistic training volume and schedule flexibility.

---

## Explicit vs Inferred Questions

### Explicit Questions (Direct Data)
Ask directly when you need specific values:
- FTP, HR zones, weight → Zone calculations
- Weekly hours available → Volume planning
- Race date → Timeline calculations
- Injury details → Movement restrictions

### Inferred Questions (Psychological Insight)
Ask indirectly to reveal patterns:

| Question | What It Reveals |
|----------|-----------------|
| "When you miss a planned workout, what do you usually do?" | Perfectionism, flexibility, self-compassion |
| "Describe your best training period ever." | Success conditions, motivation drivers |
| "What's the longest you've stuck with a training plan?" | Consistency patterns, dropout triggers |
| "How do you feel about indoor training?" | Compliance likelihood in bad weather |
| "What would make you quit?" | Risk factors, non-negotiables |
| "Who knows about your race goal?" | Accountability style (public vs private) |

### Hidden Inference from Existing Questions
The current form already infers some things:

```javascript
// Current blindspot inference in form:
- Poor sleep quality → "Recovery Deficit"
- High stress → "Life Stress Overload"
- No strength training → "Movement Quality Gap"
- Any injuries listed → "Injury Management Required"
- Low weekly hours → "Time-Crunched Reality"
- Age >= 45 → "Masters Recovery Window"
```

This is good! Expand this pattern.

---

## Recommended Sections for Coaching Questionnaire

### Section 1: Contact (Keep As-Is)
- Name, email

### Section 2: About You (Expand)
- Age, sex, weight, height
- **ADD:** Resting HR, typical sleep hours
- **ADD:** Recovery speed self-assessment
- Years cycling, sleep quality, stress level

### Section 3: Goals (Expand)
- Primary goal type (race, fitness, base building, return from injury)
- **ADD:** If racing, list all events with dates and priority (A/B/C)
- **ADD:** What does success look like? (open text)
- **ADD:** What's holding you back? (open text → reveals blindspots)

### Section 4: Current Fitness (Keep, Add)
- Longest recent ride, FTP, HR zones
- **ADD:** Current weekly volume (actual, not aspirational)
- **ADD:** Current training phase (off-season, base, build, race)
- **ADD:** Coming off injury/illness? (triggers return-to-sport protocol)

### Section 5: Schedule (Keep As-Is)
- Weekly hours, trainer access
- Long ride days, interval days, off days

### Section 6: Equipment & Integrations (NEW - Critical)
```
Do you use any of these?
- [ ] WHOOP (enables HRV/recovery sync)
- [ ] Garmin (specify model)
- [ ] Wahoo
- [ ] Smart trainer (Zwift, etc.)
- [ ] Power meter on bike

Training platform:
- [ ] Intervals.icu (recommended - free)
- [ ] TrainingPeaks
- [ ] Strava only
- [ ] Other

If Intervals.icu, what's your athlete ID? [_____]
```

### Section 7: Health & Recovery (Expand)
- Injuries/limitations (keep)
- **ADD:** Chronic conditions (affects health gates)
- **ADD:** Medications that affect HR or recovery
- **ADD:** History of overtraining/burnout (yes/no + describe)

### Section 8: Strength (Keep As-Is)
- Current strength training, equipment

### Section 9: Work & Life (NEW)
```
- Do you work? Hours/week? Stress level?
- Family situation
- Other regular commitments
- Is time management a challenge?
```

### Section 10: Coaching Preferences (NEW)
```
- Check-in frequency: daily / few times week / weekly
- Feedback detail: minimal / moderate / comprehensive
- Autonomy: tell me exactly / general guidance / high autonomy
- Communication style: direct / encouraging / data-driven
```

### Section 11: Mental Game (NEW - Inferred)
```
Open questions that reveal psychology:

1. "When you miss a planned workout, what do you usually do?"
   Options:
   - Make it up ASAP, even if it means back-to-back hard days
   - Move on, trust the process
   - Feel guilty but let it go
   - Spiral and question everything

2. "How do you handle races that don't go to plan?"
   (Open text → reveals resilience, self-talk patterns)

3. "Describe your best training block ever. What made it work?"
   (Open text → reveals success conditions)

4. "What would make you quit this training block?"
   (Open text → reveals risk factors)
```

### Section 12: Anything Else (Keep)
- Open notes field

---

## Data Flow: Questionnaire → Profile.yaml → Athlete_State.json

```
Questionnaire Response
        ↓
create_profile_from_form.py
        ↓
athletes/{name}/profile.yaml (static data)
        ↓
scripts/intervals_sync.py, whoop_sync.py
        ↓
athletes/{name}/athlete_state.json (live data)
        ↓
calculate_readiness.py
        ↓
Daily coaching recommendations
```

Key mappings needed:
- WHOOP checkbox → enables whoop_sync.py setup
- Intervals.icu ID → enables intervals_sync.py
- Resting HR → baseline for autonomic health gate
- Sleep hours → baseline for sleep health gate
- Recovery speed → affects k1 multiplier in readiness calc
- Coaching preferences → system prompt personalization

---

## Implementation Priority

### Phase 1: Critical (Do Now)
1. Add wearable/integration questions (WHOOP, Intervals.icu ID)
2. Add baseline physiology (RHR, sleep hours)
3. Add coaching preferences (frequency, style)
4. Rename from "Training Plan" to "Coaching Intake"

### Phase 2: Enhanced (Next)
5. Add work/life section
6. Add mental game inferred questions
7. Build `create_profile_from_form.py` script
8. Add progress save/resume functionality

### Phase 3: Polish
9. Multi-step wizard format
10. Conditional field logic
11. Pre-population from Intervals.icu/WHOOP if authorized
12. Webhook integration for automated profile creation

---

## Questions to Consider

1. **Length vs Completion Rate:** Full questionnaire is ~60 questions. Training plan form is ~25. What's acceptable for coaching intake?

2. **Required vs Optional:** Which fields are truly required for Athlete OS to function? Which are nice-to-have?

3. **Pre-coaching vs Ongoing:** Some data (like HRV baseline) is better gathered over time than asked upfront. What's the minimal viable intake?

4. **Privacy Sensitivity:** Health conditions, medications, mental health questions - how to handle sensitively?

---

## Next Steps

1. [x] Review this analysis and decide on scope
2. [x] Modify `docs/athlete-questionnaire.html` with additions
3. [x] Create `scripts/create_profile_from_questionnaire.py`
4. [ ] Test with your own profile data
5. [ ] Deploy via GitHub Pages
