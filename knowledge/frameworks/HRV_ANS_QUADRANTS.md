# HRV ANS Quadrants Framework

Advanced HRV interpretation using Autonomic Nervous System balance for training readiness decisions.

Based on: Alan Couzens, "Taking Your Understanding of HRV to the Next Level"

---

## Core Insight

**RMSSD alone is insufficient for readiness assessment.**

Traditional HRV monitoring uses only parasympathetic (vagal) indicators like RMSSD. This misses half the picture—the sympathetic nervous system state. Optimal training readiness requires balance between both branches of the ANS.

---

## The Two-Dimensional Model

### Dimension 1: Parasympathetic Activity (HF / RMSSD)
- High Frequency power (HF) reflects vagal/parasympathetic tone
- RMSSD correlates strongly with HF
- Higher = better recovery, more "rest and digest"
- **What most wearables measure**

### Dimension 2: Sympathetic Activity (LF / SDNN)
- Low Frequency power (LF) reflects sympathetic nervous system
- SDNN (total HRV power) includes both branches
- Moderate levels indicate readiness to perform
- **Often ignored in consumer devices**

### Key Ratios
- **LF/HF Ratio**: Higher = more sympathetic dominance
- **SDNN vs RMSSD**: If SDNN high but RMSSD low = sympathetic activation

---

## The Four Quadrants

```
                    PARASYMPATHETIC (HF/RMSSD)
                         HIGH
                           │
           Q1              │              Q2
     DEEP RECOVERY         │         READY TO TRAIN
   ─────────────────────────┼───────────────────────────
     High PNS, Low SNS     │      High PNS, High SNS
     Body prioritizing     │      Optimal autonomic
     restoration           │      balance for training
                           │
   LOW ────────────────────┼──────────────────────── HIGH
        SYMPATHETIC (LF)   │                    SYMPATHETIC
                           │
           Q4              │              Q3
        OVERTRAINED        │      SYMPATHETIC OVERREACH
   ─────────────────────────┼───────────────────────────
     Low PNS, Low SNS      │      Low PNS, High SNS
     Both systems          │      ** DANGER ZONE **
     depressed             │      Fight-or-flight stuck ON
                           │
                         LOW
```

---

## Quadrant Definitions

### Q1: Deep Recovery (High PNS, Low SNS)
- **State**: Body in restoration mode
- **Indicators**: High RMSSD, low LF/HF ratio
- **Action**: Support sessions or active recovery only
- **Rationale**: System is recovering—don't interrupt with intensity
- **Duration**: 24-48 hours post hard training

### Q2: Ready to Train (High PNS, High SNS)
- **State**: Optimal autonomic balance
- **Indicators**: High RMSSD AND elevated LF, balanced LF/HF
- **Action**: Key sessions appropriate
- **Rationale**: Recovered AND primed—best window for hard training
- **Duration**: Transient state, typically 1-2 days

### Q3: Sympathetic Overreach (Low PNS, High SNS) ⚠️
- **State**: Fight-or-flight stuck on, poor recovery
- **Indicators**: Low RMSSD, high LF, elevated LF/HF ratio
- **Action**: IMMEDIATE recovery intervention
- **Rationale**: Stress response activated without recovery—injury/illness risk HIGH
- **Duration**: Extended stay = functional overreaching → non-functional overtraining
- **Red Flags**:
  - Elevated resting HR
  - Poor sleep despite fatigue
  - Irritability, anxiety
  - Performance decline despite high effort

### Q4: Overtrained (Low PNS, Low SNS)
- **State**: Both ANS branches suppressed
- **Indicators**: Low RMSSD, low LF, low total HRV
- **Action**: Extended recovery, possibly medical evaluation
- **Rationale**: System exhausted—adaptation capacity minimal
- **Duration**: Recovery can take weeks to months
- **Warning Signs**:
  - Paradoxically "flat" HRV (no variability)
  - Emotional numbness
  - Persistent fatigue regardless of rest
  - Loss of training motivation

---

## Practical Detection

### With Full HRV Data (Frequency Domain)
If your device provides HF and LF power:

```python
def detect_ans_quadrant(hf, lf, hf_baseline, lf_baseline):
    """
    Detect ANS quadrant from frequency domain HRV.

    Returns: quadrant (1-4) and status message
    """
    hf_pct = (hf / hf_baseline) * 100
    lf_pct = (lf / lf_baseline) * 100

    high_threshold = 90  # % of baseline
    low_threshold = 70   # % of baseline

    if hf_pct >= high_threshold:
        if lf_pct >= high_threshold:
            return 2, "ready_to_train"  # Q2
        else:
            return 1, "deep_recovery"   # Q1
    else:
        if lf_pct >= high_threshold:
            return 3, "sympathetic_overreach"  # Q3 - DANGER
        else:
            return 4, "overtrained"     # Q4
```

### With RMSSD + Orthostatic Test (More Common)
Most wearables only provide RMSSD. Use orthostatic HR test for sympathetic proxy:

```python
def detect_ans_quadrant_orthostatic(rmssd, rmssd_baseline, hr_delta, hr_delta_baseline):
    """
    Detect ANS quadrant using RMSSD + orthostatic HR response.

    rmssd: Current RMSSD value
    hr_delta: HR increase from lying to standing

    Higher hr_delta = more sympathetic activation
    """
    rmssd_pct = (rmssd / rmssd_baseline) * 100
    delta_ratio = hr_delta / hr_delta_baseline

    pns_high = rmssd_pct >= 90
    sns_high = delta_ratio >= 0.9  # Normal or elevated response

    if pns_high:
        if sns_high:
            return 2, "ready_to_train"
        else:
            return 1, "deep_recovery"
    else:
        if sns_high:
            return 3, "sympathetic_overreach"
        else:
            return 4, "overtrained"
```

---

## Orthostatic Heart Rate Test Protocol

A simple, accessible proxy for sympathetic activation:

### Morning Protocol (Before Getting Up)
1. **Lying**: Record HR after 5 min lying still (use wearable or finger on pulse)
2. **Standing**: Stand up smoothly, wait 60 seconds, record HR
3. **Calculate**: Delta = Standing HR - Lying HR

### Interpretation
| Delta | Sympathetic Status | Implication |
|-------|-------------------|-------------|
| 10-15 bpm | Normal baseline | Establish personal norm |
| 15-25 bpm | Elevated | Sympathetic activation, may indicate readiness |
| 25+ bpm | High | Stress response elevated, monitor closely |
| < 10 bpm | Blunted | Possible parasympathetic dominance OR overtraining |

### Individual Baseline
- Track for 2 weeks during normal training
- Calculate personal average and standard deviation
- Flag deviations > 1 SD from personal norm

---

## Integration with Readiness Scoring

### Quadrant-Based Adjustments

| Quadrant | Readiness Modifier | Session Allowed |
|----------|-------------------|-----------------|
| Q2 | +10 bonus | Key sessions |
| Q1 | 0 (neutral) | Support sessions |
| Q3 | -15 penalty | Recovery ONLY |
| Q4 | -25 penalty | Rest, medical consult |

### Health Gate Enhancement
Add ANS balance to the autonomic health gate:

```json
{
  "health_gates": {
    "autonomic": {
      "hrv_vs_baseline_pct": 92,
      "rhr_vs_baseline_pct": 103,
      "ans_quadrant": 2,
      "ans_status": "ready_to_train",
      "orthostatic_delta": 18,
      "orthostatic_baseline": 15,
      "gate_pass": true
    }
  }
}
```

### Automatic Red Flags
- **Q3 for 2+ consecutive days**: Force recovery, alert coach
- **Q4 detection**: Block all intensity, recommend medical evaluation
- **LF/HF > 3.0 with declining RMSSD**: Sympathetic overreach warning

---

## Data Sources

### Consumer Devices with Full HRV
- **WHOOP**: Provides HRV (RMSSD), but not frequency domain
- **Garmin**: Some models provide HRV status (simplified)
- **Polar**: Advanced models provide HF/LF analysis
- **Oura**: RMSSD-based, no frequency domain

### Manual Collection
- **HRV4Training app**: Can calculate HF/LF from camera
- **Elite HRV**: Chest strap + frequency domain analysis
- **Kubios**: Gold standard research software

### Orthostatic Test
- Any HR monitor or manual pulse
- Apple Watch/Garmin can automate lying HR on wake
- Standing HR measured manually 60s after standing

---

## Key Principles

1. **RMSSD is necessary but not sufficient** - it only shows parasympathetic side
2. **Context matters** - high RMSSD during heavy training block may indicate Q1, not Q2
3. **Trends over absolutes** - track ratios against personal baseline
4. **Q3 is the danger zone** - sympathetic overreach precedes overtraining
5. **Orthostatic test is a cheap proxy** - use when frequency domain unavailable

---

## References

- Couzens, A. "Taking Your Understanding of HRV to the Next Level"
- Plews, D. et al. "Training Adaptation and Heart Rate Variability in Elite Endurance Athletes" (2013)
- Buchheit, M. "Monitoring training status with HR measures" (2014)
- Kiviniemi, A. et al. "Endurance training guided individually by daily heart rate variability measurements" (2007)

---

## Implementation Notes for Athlete OS

1. **Morning check-in enhancement**: Add optional orthostatic HR fields
2. **Readiness calculation**: Incorporate ANS quadrant detection
3. **Health gate update**: Add sympathetic/parasympathetic balance check
4. **Alert system**: Flag Q3/Q4 states for immediate intervention
5. **Trend tracking**: Store daily quadrant for pattern analysis
