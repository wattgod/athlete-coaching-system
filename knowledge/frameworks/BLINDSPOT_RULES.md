# Blindspot Rules Engine

Automated coaching adjustments based on inferred athlete blindspots.

---

## Overview

Blindspots are patterns inferred from the intake questionnaire that may affect training response, recovery, or adherence. The system automatically adjusts thresholds, generates prompts, and triggers alerts based on active blindspots.

## How Blindspots Are Detected

1. **Intake Questionnaire**: Form analyzes responses and flags patterns
2. **Explicit Questions**: Sleep quality, stress level, strength training status
3. **Inferred from Text**: Obstacles, past injuries, medical conditions, quit triggers

### Text Pattern Detection

The form scans free-text fields for keywords:

| Pattern | Blindspot |
|---------|-----------|
| alcohol, drinking, beer, wine | Alcohol Recovery Impact |
| diet, dieting, weight, too heavy | Weight Management Stress |
| caffeine, coffee | Caffeine Dependency |
| sleep medication, insomnia, sleep apnea | Sleep Disorder |

---

## Blindspot Definitions

### Movement Quality Gap
**Trigger:** No current strength training or only occasional
**Adjustments:**
- Musculoskeletal gate weight: 1.2x (20% more sensitive)
**Prompts:**
- Daily: "Include 10-15min mobility/strength work today"
- Weekly: "Schedule 2 dedicated strength sessions this week"
**Alerts:**
- Warn after 7+ days without strength work

---

### Injury Management
**Trigger:** Active injuries listed in questionnaire
**Adjustments:**
- Musculoskeletal gate weight: 1.5x (50% more sensitive)
- Max weekly hours: 14
**Prompts:**
- Pre-ride: "Hip flexor mobility check before riding"
- Post-ride: "Targeted hip/QL stretching protocol"
**Alerts:**
- Warn if weekly hours > 14

---

### Overtraining Risk
**Trigger:** History of multiple overtraining episodes
**Adjustments:**
- Key session threshold: 70 (up from 65)
- Max ramp rate: 5.0 TSS/day (down from 7)
- TSB floor: -20 (up from -30)
- Min rest days: 2 per week
**Prompts:**
- Daily: "Listen to fatigue signals. You have OT history."
- Recovery: "Full recovery is non-negotiable with your history"
**Alerts:**
- Warn if TSB < -20
- Warn if ramp rate > 5 TSS/day

---

### Alcohol Recovery Impact
**Trigger:** Mentions of alcohol, drinking, beer in obstacles or history
**Adjustments:**
- HRV discount after alcohol: 50%
- Sleep gate weight: 1.3x
**Prompts:**
- Check-in: "Any alcohol last night? (affects HRV interpretation)"
- Post-alcohol: "Z2 max today. Alcohol suppresses recovery."
- Weekly: "Each drink costs ~1hr of quality recovery"
**Rules:**
- After drinking: max intensity = Z2
- HRV readings discounted if alcohol reported
**Alerts:**
- Warn if >10 drinks in a week pattern detected

---

### Weight Management Stress
**Trigger:** Mentions of dieting, weight concerns, "too heavy", "too fat"
**Adjustments:**
- Max fasted ride duration: 60 minutes (down from 90)
- Stress gate weight: 1.2x
**Prompts:**
- Fueling: "Fuel the work. Performance > scale."
- Pre-ride: "Eat before rides >90min. No fasted long rides."
- Mental: "Fast comes from fitness, not starvation."
**Rules:**
- No fasted rides over 90 minutes
- Messaging focuses on performance, not weight
**Alerts:**
- Warn if power declining with high RPE (underfueling signal)

---

### Caffeine Dependency
**Trigger:** Mentions of caffeine, coffee in medical conditions or triggers
**Adjustments:**
- RHR baseline offset: +4 bpm (caffeine elevates RHR)
- Sleep gate weight: 1.2x
**Prompts:**
- Daily: "Caffeine cutoff: noon. Affects sleep quality."
- RHR note: "RHR baseline adjusted +4bpm for caffeine use"
**Rules:**
- RHR readings adjusted by +4bpm expected baseline
- Caffeine cutoff: noon
**Alerts:**
- Info if poor sleep + afternoon caffeine pattern

---

### Recovery Deficit
**Trigger:** Poor or fair sleep quality rating
**Adjustments:**
- Key session threshold: 70
- Sleep gate weight: 1.5x
**Prompts:**
- Daily: "Sleep is your #1 performance enhancer"
- Evening: "Screens off 1hr before bed"
**Alerts:**
- Warn if 7-day avg sleep < 6 hours

---

### Life Stress Overload
**Trigger:** High or very high life stress rating
**Adjustments:**
- Key session threshold: 70
- Stress gate weight: 1.5x
- Max ramp rate: 5.0 TSS/day
**Prompts:**
- Daily: "Training should be a stress outlet, not another source"
- High stress: "Consider Z2 only today. Life stress counts."
**Alerts:**
- Warn if stress score > 7

---

### Time-Crunched
**Trigger:** Weekly hours available 3-5 or 5-7
**Adjustments:**
- Max weekly hours: 8
**Prompts:**
- Daily: "Quality > quantity. Make every minute count."
- Planning: "2 key sessions + endurance. That's the formula."

---

### Masters Recovery (Age 45+)
**Trigger:** Age >= 45
**Adjustments:**
- Min rest days: 2 per week
- Key session threshold: 68
- Max ramp rate: 5.0 TSS/day
**Prompts:**
- Daily: "Recovery takes longer. Respect the process."
- Post-intensity: "48-72hrs before next intensity"

---

### Extended Recovery Needs (Age 55+)
**Trigger:** Age >= 55
**Adjustments:**
- Min rest days: 2 per week
- Key session threshold: 72
- Max ramp rate: 4.0 TSS/day
**Prompts:**
- Daily: "One hard day, two easy days. Non-negotiable."
- Weekly: "Max 2 intensity sessions per week"

---

### Sleep Disorder
**Trigger:** Sleep medication, insomnia, sleep apnea mentioned
**Adjustments:**
- Sleep gate weight: 2.0x (double)
- Key session threshold: 70
**Prompts:**
- Daily: "Sleep quality gates everything. Prioritize it."
- Check-in: "How was sleep? This is critical for you."

---

## Threshold Stacking

When multiple blindspots apply, thresholds stack conservatively:

- **Key session threshold**: Takes highest value
- **Max ramp rate**: Takes lowest value
- **TSB floor**: Takes highest (least negative) value
- **Min rest days**: Takes highest value
- **Gate weights**: Multiply together

### Example: Matti Rowe

Active blindspots:
- Movement Quality Gap
- Injury Management
- Overtraining Risk
- Alcohol Recovery Impact
- Weight Management Stress
- Caffeine Dependency

Combined adjustments:
- Key session threshold: 70 (from Overtraining Risk)
- Max ramp rate: 5.0 TSS/day (from Overtraining Risk)
- TSB floor: -20 (from Overtraining Risk)
- Min rest days: 2/week (from Overtraining Risk)
- RHR offset: +4 bpm (from Caffeine)
- MSK gate weight: 1.5x × 1.2x = 1.8x
- Sleep gate weight: 1.3x × 1.2x = 1.56x
- Stress gate weight: 1.2x

---

## Integration Points

### calculate_readiness.py
- Loads profile to get blindspots
- Applies adjusted thresholds
- Applies gate weight multipliers
- Includes blindspot info in readiness output

### daily_briefing.py
- Shows daily reminders based on active blindspots
- Shows context-specific prompts (pre-ride, recovery)
- Displays adjusted thresholds banner

### check_alerts.py
- Runs blindspot-specific alert checks
- Checks adjusted ramp rate threshold
- Includes blindspot source in alert messages

---

## Adding New Blindspots

To add a new blindspot:

1. Add pattern detection in `docs/athlete-questionnaire.html` → `inferTraits()`
2. Add rule definition in `scripts/blindspot_rules.py` → `BLINDSPOT_RULES`
3. Define:
   - `description`: What this blindspot means
   - `adjustments`: Threshold modifications
   - `alerts`: Conditions and messages
   - `prompts`: Context-specific reminders
   - `rules`: Any special behavior rules

---

## Philosophy

> "Know your blindspots. Work around them, not through them."

The blindspot system embodies the Nate Wilson coaching principle of **Patience**: Rather than pushing through limitations, we adjust expectations and create guardrails that prevent self-sabotage.

Athletes don't fail from lack of motivation. They fail from:
- Ignoring recovery signals (Overtraining Risk)
- Underfueling to lose weight (Weight Management Stress)
- Compounding stress (Life Stress + Training Stress)
- Skipping the boring stuff (Movement Quality Gap)

The blindspot system makes the right choice the default choice.
