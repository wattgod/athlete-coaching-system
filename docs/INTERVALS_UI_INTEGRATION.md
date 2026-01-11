# Intervals.icu UI Integration

Documentation for dashboard UI patterns inspired by [Intervals.icu](https://intervals.icu).

## Color Scheme

### PMC Chart Colors (Intervals.icu Standard)
| Metric | Color | Hex | CSS Variable |
|--------|-------|-----|--------------|
| CTL (Fitness) | Blue | #2196F3 | `--ctl-blue` |
| ATL (Fatigue) | Pink | #E91E63 | `--atl-pink` |
| TSB (Form) | Yellow | #FFC107 | `--tsb-yellow` |
| Daily Load | Purple | #9C27B0 | `--load-purple` |

### TSB Zone Backgrounds
| Zone | TSB Range | Color | Meaning |
|------|-----------|-------|---------|
| Fresh | > 25 | Light green | Well rested, possibly detrained |
| Optimal | 5-15 | Green | Peak performance zone |
| Gray | -5 to 5 | Gray | Transition zone |
| Risk | < -20 | Red | Overtraining risk |

### Training Zone Colors (Zwift/Garmin Standard)
| Zone | Name | Color | Hex | CSS Variable |
|------|------|-------|-----|--------------|
| Z1 | Recovery | Gray | #9E9E9E | `--zone1` |
| Z2 | Endurance | Blue | #2196F3 | `--zone2` |
| Z3 | Tempo | Green | #4CAF50 | `--zone3` |
| Z4 | Threshold | Yellow | #FFC107 | `--zone4` |
| Z5 | VO2max | Red | #F44336 | `--zone5` |
| Z6 | Anaerobic | Purple | #9C27B0 | `--zone6` |

## Features Implemented

### 1. PMC Chart Enhancements
- **TSB Zone Backgrounds**: Colored regions showing form zones (fresh/optimal/gray/risk)
- **Daily Load Bars**: Purple histogram at top showing daily TSS
- **Intervals.icu Colors**: CTL (blue), ATL (pink dashed), TSB (yellow)
- **Zone Labels**: FRESH, OPTIMAL, RISK labels on right side

### 2. Calendar Improvements
- **Weekly Progress Bar**: Shows TSS progress vs weekly target
  - Blue: Under 70% of target
  - Green: 70-110% of target (on track)
  - Yellow: Over 110% of target
- **Intensity Skyline Bars**: Mini bar charts on each activity showing zone distribution
  - Inspired by Intervals.icu "skyline chart" feature
  - Color-coded by training zone

### 3. Activity Visualization
- **Intensity-Based Coloring**: Activities colored by intensity level
- **Zone Distribution**: Mini horizontal bars showing time in each zone

## Usage

### Generate Dashboard with History
```bash
# With Intervals.icu API
export INTERVALS_API_KEY=your_key
python scripts/generate_dashboard.py matti-rowe --include-history

# View dashboard
open docs/dashboard.html
```

### CSS Variables
All colors are defined as CSS custom properties in `:root` for easy theming:

```css
:root {
    /* PMC colors */
    --ctl-blue: #2196F3;
    --atl-pink: #E91E63;
    --tsb-yellow: #FFC107;
    --load-purple: #9C27B0;

    /* Zone colors */
    --zone1: #9E9E9E;
    --zone2: #2196F3;
    --zone3: #4CAF50;
    --zone4: #FFC107;
    --zone5: #F44336;
    --zone6: #9C27B0;
}
```

## Sources

UI patterns researched from:
- [Intervals.icu Forum - Calendar Update](https://forum.intervals.icu/t/calendar-and-week-info-update/109142)
- [Intervals.icu Forum - Skyline Chart](https://forum.intervals.icu/t/activity-skyline-chart-on-the-calendar/59341)
- [Intervals.icu Forum - Fitness Graph Colors](https://forum.intervals.icu/t/fitness-graph-colors/8619)
- [Intervals.icu Forum - Workout Colors](https://forum.intervals.icu/t/workouts-colors/54026)

## Design Philosophy

The integration maintains the Neo-Brutalist aesthetic of the Situation Station dashboard while adopting Intervals.icu's effective data visualization patterns:

1. **Color Semantics**: Colors have consistent meaning (blue=fitness, pink=fatigue, green=good, red=risk)
2. **Information Density**: More data visible at a glance without clutter
3. **Progressive Disclosure**: Summary views (weekly progress) with detail on hover/click
4. **Standard Palette**: Zone colors match industry standards (Zwift, Garmin, TrainingPeaks)
