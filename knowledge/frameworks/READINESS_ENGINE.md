# Athlete OS - Readiness Engine (Chapter 13)

Design input for Athlete OS readiness system. Contains decision logic, data flow, modeling choices, and implementation rules.

---

## Core Principle

**Do not plan recovery in advance.**
Plan *loading* only when the athlete is in a position to benefit.
Recovery is taken *on demand*, based on readiness.

**Readiness** = probability the athlete will *respond positively* to training **today**.

---

## What "Readiness" Actually Means

An athlete is ready when:
1. They can tolerate **intensity** today
2. They can **respond** to that load with adaptation, not breakdown

Readiness is **individual**, not population-based.

---

## Required Inputs (Daily)

### Morning Metrics (Subjective + Objective)

Collected pre-training:
- HRV
- Resting HR (Pulse)
- Fatigue (self-report)
- Soreness (self-report)
- Stress (self-report)
- Mood (optional)

### Training Load (Daily Aggregated)

- TSS (sum)
- IF (mean)
- Session Feel (post-session, inverted)

### Ground Truth Label

- **Session "Feel" score (1-9)**
  Used as the target variable for readiness prediction

---

## Data Engineering Pipeline

### 1. Flatten Morning Metrics

Each date → one row with all metrics

```python
metrics_data = metrics_data.pivot_table(
    index='date',
    columns='Type',
    values='Value',
    aggfunc='first'
).reset_index()

metrics_data = metrics_data[['date','Fatigue','HRV','Mood','Pulse','Soreness','Stress']]
```

### 2. Prepare Training Data

Invert TP "Feeling" scale (higher = worse → lower = worse)

```python
workouts_data = workouts_data[['WorkoutDay','TSS','IF','Feeling']]
workouts_data['Feeling'] = 10 - workouts_data['Feeling']
workouts_data['date'] = pd.to_datetime(workouts_data['WorkoutDay']).dt.date

workouts_data = workouts_data.groupby('date').agg({
    'TSS':'sum',
    'IF':'mean',
    'Feeling':'mean'
}).reset_index()
```

### 3. Merge to Single Readiness Table

```python
data = pd.merge(metrics_data, workouts_data, on='date', how='left')
```

---

## Signal Processing Rules

- Use **rolling averages**, not daily noise
- Default:
  - Acute = 7-day rolling
  - Baseline = 60-day rolling

This applies to:
- Pulse
- HRV
- Subjective metrics

---

## Modeling Approach

### Target

Predict **session feel** before training occurs.

### Baseline Model (for comparison)

Linear regression → insufficient due to non-linear interactions

### Preferred Model

**Decision Tree Regressor**
- Interpretable
- Handles non-linearity
- Individual-specific thresholds

```python
from sklearn.tree import DecisionTreeRegressor

model = DecisionTreeRegressor(
    random_state=1,
    max_depth=8
)
model.fit(train_X, train_y)
```

### Performance Benchmark

- Linear model RMSE ≈ 0.82
- Tree (depth 8) RMSE ≈ **0.42**

---

## Feature Importance (Individual Example)

Typical hierarchy (varies by athlete):

1. **IF (Intensity Factor)** - dominant driver
2. Stress (7-day)
3. Soreness (7-day)
4. TSB
5. Resting HR (7-day)

Often **NOT** important:
- HRV (for some athletes)
- Mood
- Fatigue
- CTL
- Raw TSS

**Warning:** HRV usefulness is athlete-specific. Do not assume universality.

---

## Decision Logic (Operational Use)

Model outputs predicted session feel → map to readiness score:

```
Readiness Score = Prediction × 10
```

### Planning Rules

- Readiness ≤ ~30 → **Recovery day**
- Readiness high → **Green light for load**
- Load always stays "under the readiness umbrella"

This replaces fixed microcycles.

---

## Visualization (Optional but Useful)

### Feature Importance

```python
importances = model.feature_importances_
features = train_X.columns

sorted_importance = sorted(
    zip(features, importances),
    key=lambda x: x[1],
    reverse=True
)
```

### Decision Tree Visualization

```python
from sklearn.tree import export_graphviz
from subprocess import call

export_graphviz(model, out_file='readiness_tree.dot', feature_names=features)
call(['dot','-Tpng','readiness_tree.dot','-o','readiness_tree.png','-Gdpi=600'])
```

---

## Athlete OS Implications

### This Enables:
- Dynamic load selection
- Fewer plateaus
- Reduced injury/illness
- Higher response to intensity blocks

### This Replaces:
- Fixed 3:1 or 2:1 cycles
- Blind CTL chasing
- Over-reliance on single metrics (HRV, TSB alone)

---

## Key Design Rule for Athlete OS

**Collapse many signals into ONE decision-grade number.**

Dashboards don't coach.
Decisions do.

End goal:
> "Should this athlete load today, and how hard?"

This system answers that.

---

## Implementation Schema

```json
{
  "readiness": {
    "score": 65,
    "threshold_for_key_session": 65,
    "recommendation": "green",
    "factors": {
      "IF_impact": "high",
      "stress_7d": "moderate",
      "soreness_7d": "low",
      "tsb": "neutral"
    }
  }
}
```
