# Matti Rowe - Coaching Intelligence Dashboard
Generated: 2026-01-08 (Validated Analysis)

## Athlete Classification

**Primary Finding: Endurance Slow Responder**

| System | Evidence | Confidence |
|--------|----------|------------|
| Endurance (90min+) | CTL negatively correlates (r=-0.28) | **High** |
| VO2max/Threshold (3-20min) | No CTL signal after controlling for season | **Inconclusive** |
| Recovery | IF explains 96.6% of next-day feeling | **High** |

**Interpretation:** Accumulated training load (CTL) hurts your sustained endurance power. You need freshness to perform at 90min+ efforts. Peak power durations show no clear CTL relationship - they're dominated by seasonal variation and day-to-day noise.

---

## What's Actually Validated

### High Confidence Findings

1. **IF Dominates Recovery** (96.6% importance)
   - Higher intensity sessions significantly impact next-day feeling
   - This is the strongest signal in your data

2. **Endurance = Slow Responder**
   - 90min power: r = -0.28 with CTL (within-month)
   - High training load → lower sustained power
   - Need freshness for long efforts

3. **Seasonal Variation**
   - ~6% swing in peak powers (October best, November worst)
   - Month explains more variance than CTL for short durations

### Inconclusive (Needs Better Data)

1. **VO2max trainability** - Peak 3-5min doesn't correlate with CTL
2. **Threshold trainability** - Peak 20min doesn't correlate with CTL
3. **Sprint trainability** - Peak 5-30s doesn't correlate with CTL

---

## Power Duration Curve (Validated)

| Duration | Mean | Max | n |
|----------|------|-----|---|
| 5s | 411W | 834W | 157 |
| 30s | 378W | 585W | 157 |
| 1min | 360W | 544W | 157 |
| 3min | 336W | 486W | 157 |
| 5min | 326W | 475W | 157 |
| 10min | 309W | 413W | 157 |
| 20min | 294W | 407W | 156 |
| 60min | 265W | 322W | 150 |
| 90min | 260W | 303W | 129 |
| 180min | 254W | 293W | 16 |

---

## Coaching Playbook (Revised)

### What We Know Works

1. **Manage intensity carefully** - IF is the #1 driver of how you feel
2. **Taper for endurance events** - you need freshness for 90min+ efforts
3. **Seasonal periodization matters** - October is your peak, plan accordingly

### What We Can't Conclude

1. ~~"Quick Responder" for intensity~~ - No signal after controlling for season
2. ~~Optimal threshold block length~~ - Would need controlled tests
3. ~~VO2max trainability~~ - Noise too high in training data

### To Get Better Data

For valid trainability measurement:
- Monthly FTP tests (same protocol, same conditions)
- Indoor tests to remove weather/terrain variation
- Race results with known CTL/TSB at start

---

## Readiness Model (Unchanged - High Confidence)

| Factor | Importance | Effect |
|--------|------------|--------|
| **Intensity Factor (IF)** | 96.6% | -3.69 points per 0.1 IF |
| CTL | 1.7% | Slightly protective |
| TSB | 1.3% | Fresher = better |

---

## Data Quality Notes

- Peak powers from FIT files: 157 activities validated
- Removed: power spikes ≥1500W, outliers >3σ, unrealistic sustained values
- Seasonality controls applied to all correlation tests
- Within-month correlations used to separate training effect from season

## Key Limitation

Training ride peaks are noisy. The Banister model needs:
- Consistent test protocols
- Controlled conditions
- Regular measurement cadence

Using "every ride is a test" introduces too much variance to detect the training signal for short durations.
