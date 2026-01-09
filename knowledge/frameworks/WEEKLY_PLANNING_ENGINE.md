# Athlete OS - Weekly Planning Engine (Chapter 14)

Design input for Athlete OS weekly planning system. Contains logic, constraints, rules, and system behavior.

---

## Core Thesis

**Weekly planning exists to maximize training response, not to execute a preset plan.**

The unit of planning is:
> **The best possible session the athlete can absorb today, given yesterday and tomorrow.**

Weekly structure is *emergent*, not imposed.

---

## The Planning Problem (Formalized)

**Given:**
- Finite recovery capacity
- Individual trainability (k1)
- Individual fatigue decay (τ2)
- Fluctuating readiness

**We want to:**
- Place **high-value sessions** where they produce the *largest marginal adaptation*
- Avoid wasting intensity on low-readiness days
- Avoid banking fatigue without fitness return

---

## Core Constraints

### 1. Intensity Is the Scarce Resource

- Aerobic volume is cheap
- Intensity is expensive
- Misplaced intensity = negative ROI

Therefore:
> **Intensity must be protected by readiness.**

---

### 2. Fatigue Is Nonlinear

- Fatigue cost increases disproportionately as readiness falls
- Same session ≠ same cost on different days

**Implication:**
> Session value = f(load × readiness), not load alone

---

## Weekly Planning Philosophy

### Replace This:
- Fixed weekly templates
- Pre-booked hard days
- "Tuesday = intervals"

### With This:
- **Readiness-gated sessions**
- Weekly intent, daily execution
- Load follows response

---

## Weekly Planning Primitives

### Session Types (Abstract)

- **Key Session** (High Intensity / High Adaptation Potential)
- **Support Session** (Aerobic / Technique / Volume)
- **Recovery Session** (Low load / parasympathetic)

Do NOT pre-assign days.
Only define **counts and priorities**.

---

## Weekly Intent Layer (High Level)

At start of week:

```json
{
  "key_sessions_target": 2,
  "aerobic_volume_target": "range",
  "max_weekly_load": "X",
  "priority": "respond > complete"
}
```

No fixed dates.

---

## Daily Decision Layer (Operational)

Each morning:

**Inputs:**
- Readiness score (from Readiness Engine)
- Residual fatigue (ATL / TSB / modeled fatigue)
- Upcoming opportunity cost (what's still needed this week)

**Decision:**
```
If readiness ≥ threshold AND key_sessions_remaining > 0:
    execute key session
Else:
    execute support or recovery session
```

---

## Readiness Threshold Logic

### Key Session Eligibility

- Athlete must be in **top readiness band**
- Threshold is **individual**, not universal

Example:
```json
{
  "athlete_id": 123,
  "key_session_readiness_min": 65
}
```

---

## Weekly Load Distribution Rules

### Rule 1: Never Chase Weekly TSS

- Weekly TSS is an outcome, not a target
- High TSS with low response = failure

---

### Rule 2: Front-Load Only If Athlete Responds Fast

- High k1 + low τ2 athletes tolerate early-week load
- Slow responders need spacing

---

### Rule 3: Missed Intensity Is Not "Made Up"

- Skipped key session due to low readiness ≠ debt
- Forcing it later often compounds fatigue

---

## Session Spacing Logic

Key sessions must respect:
- Individual τ2 (fatigue decay)
- Individual history of tolerance

Example constraint:
```json
{
  "min_days_between_key_sessions": "f(τ2)"
}
```

Higher τ2 → more spacing required.

---

## Micro-Recovery Integration

Recovery is **not**:
- A rest week
- A fixed day

Recovery **is**:
> The minimum reduction in load required to restore readiness.

**Operationally:**
1. Reduce intensity first
2. Reduce volume second
3. Full rest last

---

## Weekly Review Loop (Critical)

At week end:

**Evaluate:**
- Did readiness rebound after key sessions?
- Did performance metrics improve?
- Did fatigue resolve predictably?

**Update:**
- Readiness thresholds
- Session spacing
- Weekly capacity estimate

---

## Athlete OS Control Loop

```
Weekly Intent →
Daily Readiness →
Session Selection →
Response →
Weekly Review →
Parameter Update →
Next Week Intent
```

No hard resets.
No calendar worship.

---

## Failure Modes This Prevents

- "I hit my numbers but didn't get faster"
- Chronic gray-zone training
- Forced intensity on bad days
- Artificial recovery weeks
- Athlete distrust ("the plan didn't listen")

---

## Athlete Classification Implications

### High Responders
- Fewer key sessions
- Shorter windows
- Higher injury risk from impatience

### Medium Responders
- Most benefit from this system
- Respond to consistency + gating

### Low Responders
- Require patience
- Can accumulate more total work
- Still need intensity protection

---

## Design Rule for Athlete OS

**Weekly plans should never be static objects.**

They should be:
- Intent containers
- Constraint sets
- Decision frameworks

---

## Final Operating Principle

> **Fitness comes from responding well to training, not from doing more of it.**

Weekly planning exists to protect response.

---

## Implementation Schema

```json
{
  "weekly_intent": {
    "key_sessions_target": 2,
    "key_sessions_completed": 1,
    "key_sessions_remaining": 1,
    "aerobic_volume_target_hours": [8, 10],
    "max_weekly_tss": 600,
    "priority": "respond > complete"
  },
  "daily_decision": {
    "readiness_score": 72,
    "readiness_threshold": 65,
    "recommendation": "key_session_eligible",
    "session_type": "key",
    "archetype_suggestion": "VO2_4x4"
  }
}
```
