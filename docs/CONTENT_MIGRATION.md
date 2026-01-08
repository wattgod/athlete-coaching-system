# Content Migration Guide

## The Goal

Transform your existing training guides from monolithic documents into atomic, queryable, composable pieces that Cursor can assemble on demand.

**Before:** One 50-page training guide PDF
**After:** 100+ atomic content blocks with metadata

---

## The Process

### Step 1: Identify Natural Breakpoints

Read through your existing content and mark where topics shift:

- Philosophy statements
- Zone explanations
- Workout type descriptions
- Recovery protocols
- Nutrition guidelines
- Race-week strategies
- Equipment recommendations

Each of these becomes a separate file.

### Step 2: Extract Atomic Pieces

**Rule of thumb:** If you'd ever want to use this piece in a different context, it's atomic.

**Example:** Your training guide has a section on "The Importance of Recovery"

This becomes: `content/reusable_blocks/recovery-philosophy.md`

You can now use it in:
- Training guide (original location)
- Onboarding documents
- Weekly review emails
- Standalone article

### Step 3: Add YAML Frontmatter

Every content file needs metadata:

```yaml
---
id: recovery-philosophy
title: "Why Recovery Makes You Fast"
category: recovery
tags: [recovery, adaptation, rest, training-stress]
used_in: [onboarding, weekly_reviews, training_guides]
placeholders: [ATHLETE_NAME]
word_count: 250
last_updated: 2025-01-07
---

Your actual content here...

Recovery isn't the absence of training—it's where adaptation happens. {ATHLETE_NAME}, when you're resting, your body is rebuilding stronger than before.

The three pillars of recovery:
1. Sleep (7-9 hours, non-negotiable)
2. Nutrition (protein within 30 min post-ride)
3. Stress management (training stress + life stress = total stress)

You don't get a medal for being tired.
```

---

## Frontmatter Reference

| Field | Required | Purpose |
|-------|----------|---------|
| `id` | Yes | Unique identifier for querying |
| `title` | Yes | Human-readable title |
| `category` | Yes | Primary category (recovery, zones, nutrition, etc.) |
| `tags` | Yes | Array of searchable tags |
| `used_in` | Yes | Where this content appears |
| `placeholders` | No | Variables that need replacement |
| `word_count` | No | Approximate length |
| `last_updated` | No | Date of last revision |
| `requires` | No | Other content IDs this depends on |
| `supersedes` | No | Old content this replaces |

---

## Category Taxonomy

```
recovery/
├── recovery-philosophy.md
├── sleep-guidelines.md
├── active-recovery.md
└── recovery-week-protocol.md

zones/
├── zone-overview.md
├── zone-1-explanation.md
├── zone-2-execution.md
├── sweet-spot-definition.md
├── threshold-execution.md
└── vo2max-intervals.md

nutrition/
├── nutrition-philosophy.md
├── pre-ride-fueling.md
├── during-ride-fueling.md
├── post-ride-recovery.md
└── race-day-nutrition.md

periodization/
├── base-phase-overview.md
├── build-phase-overview.md
├── peak-phase-overview.md
├── race-week-protocol.md
└── off-season-approach.md

workouts/
├── endurance-ride-guide.md
├── tempo-progression.md
├── sweet-spot-workouts.md
├── threshold-workouts.md
├── vo2max-workouts.md
└── race-simulation.md

mindset/
├── process-over-outcome.md
├── consistency-philosophy.md
├── handling-setbacks.md
└── race-day-mindset.md
```

---

## Placeholder Convention

Use curly braces for variables that get replaced during assembly:

| Placeholder | Description | Source |
|-------------|-------------|--------|
| `{ATHLETE_NAME}` | First name | profile.yaml |
| `{FTP}` | Current FTP in watts | profile.yaml |
| `{LTHR}` | Lactate threshold HR | profile.yaml |
| `{GOAL_EVENT}` | Primary goal race | profile.yaml |
| `{EVENT_DATE}` | Race date | profile.yaml |
| `{WEEKS_OUT}` | Weeks until event | calculated |
| `{HOURS_PER_WEEK}` | Training availability | profile.yaml |
| `{Z2_POWER}` | Zone 2 power range | calculated from FTP |
| `{SS_POWER}` | Sweet spot power range | calculated from FTP |
| `{THRESHOLD_POWER}` | Threshold power range | calculated from FTP |

---

## Example Migration

### Original (from training guide):

> Zone 2 is the foundation of endurance performance. Ride at 55-75% of FTP, which for most athletes means you can hold a conversation. Heart rate should be 60-70% of max. This zone builds your aerobic engine, increases mitochondrial density, and improves fat oxidation. Most of your training time should be here.

### Migrated:

**File:** `content/training_guides/zones/zone-2-execution.md`

```yaml
---
id: zone-2-execution
title: "Zone 2: The Aerobic Foundation"
category: zones
tags: [zone-2, endurance, aerobic, base-building]
used_in: [training_guides, onboarding, weekly_reviews]
placeholders: [ATHLETE_NAME, FTP, Z2_POWER]
word_count: 120
---

Zone 2 is the foundation of your endurance performance, {ATHLETE_NAME}.

**Your Z2 Range:** {Z2_POWER} watts (55-75% of {FTP}W FTP)

**Execution cues:**
- Conversational pace (can speak in full sentences)
- Heart rate 60-70% of max
- Feels almost too easy (that's correct)

**What it builds:**
- Aerobic engine capacity
- Mitochondrial density
- Fat oxidation efficiency

Most of your training time belongs here. Easy isn't lazy—it's strategic.
```

---

## Migration Workflow

1. **Export** existing guide to plain text
2. **Mark** section boundaries
3. **Create** file for each section
4. **Add** frontmatter
5. **Insert** placeholders where personalization makes sense
6. **Tag** appropriately
7. **Test** by asking Cursor to find content

### Testing Query Examples

```
"Show me all content about recovery"
"Find zone 2 execution guidelines"
"What content is used in onboarding?"
"List all content with ATHLETE_NAME placeholder"
```

---

## Assembly Example

**Request:** "Generate zone explanation section for Sarah's onboarding"

**Cursor finds:**
- zone-overview.md
- zone-2-execution.md
- sweet-spot-definition.md
- threshold-execution.md

**Cursor assembles with replacements:**
- {ATHLETE_NAME} → "Sarah"
- {FTP} → "245"
- {Z2_POWER} → "135-184"
- {SS_POWER} → "206-238"

**Output:** Personalized zone guide ready for Sarah's onboarding doc.

---

## Quality Checklist

For each migrated piece:

- [ ] Has unique `id`
- [ ] Category matches taxonomy
- [ ] Tags are specific and useful
- [ ] `used_in` is accurate
- [ ] Placeholders are marked
- [ ] Content is self-contained (doesn't depend on surrounding context)
- [ ] Gravel God voice is present
- [ ] No orphan references (e.g., "as mentioned above")
