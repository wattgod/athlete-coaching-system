# Quickstart Checklist

## Day 1: Foundation

- [ ] Create GitHub repo (private): `athlete-coaching-system`
- [ ] Clone to local machine
- [ ] Open in Cursor
- [ ] Verify .cursorrules loads (ask Cursor "what's your role?")

**Validation:** Cursor responds with Gravel God voice and understands coaching context.

---

## Day 2: Philosophy Database

- [ ] Create `knowledge/philosophies/PHILOSOPHY_MATRIX.md`
- [ ] Add your 13 methodologies with selection criteria
- [ ] Create `knowledge/coaching_heuristics/PHILOSOPHY_SELECTION.md`

**Validation:** Ask Cursor "What philosophy for a 45yo with 8 hrs/week targeting Unbound?"

---

## Day 3-4: Content Migration

- [ ] Pick one training guide section to migrate
- [ ] Break into atomic pieces (see CONTENT_MIGRATION.md)
- [ ] Add YAML frontmatter to each piece
- [ ] Place in `content/training_guides/`

**Validation:** Ask Cursor "Show me all content tagged 'recovery'"

---

## Day 5: First Athlete Profile

- [ ] Create `athletes/test-athlete/profile.yaml` using template
- [ ] Fill with real or sample data
- [ ] Add a few processed files (mmp.json, signals.json)

**Validation:** Ask Cursor "Summarize test-athlete's profile and current status"

---

## Day 6: Onboarding Generator

- [ ] Create onboarding sections in `content/onboarding/sections/`
- [ ] Create `scripts/generate_onboarding.py`
- [ ] Test with test-athlete

**Validation:** Run script → produces complete onboarding doc with personalization.

---

## Day 7: Intervals.icu Integration

- [ ] Copy `intervals_sync.py` from gravel-god project
- [ ] Configure for your athlete ID
- [ ] Run sync to populate `workout_files/`
- [ ] Verify processed/ data generation

**Validation:** `athletes/{name}/processed/` contains fresh analysis.

---

## Week 2: Processing Pipeline

- [ ] `scripts/extract_mmp.py` - Build MMP from activities
- [ ] `scripts/fit_power_model.py` - Fit Peronnet-Thibault
- [ ] `scripts/calculate_pmc.py` - Build CTL/ATL/TSB
- [ ] `scripts/generate_signals.py` - Create coaching flags

**Validation:** All processed/ files generate correctly from raw data.

---

## Week 3: Review Generator

- [ ] Create weekly review template in `content/`
- [ ] Create `scripts/generate_review.py`
- [ ] Test batch generation for all athletes

**Validation:** "Generate all weekly reviews" produces 20 personalized docs in <1 minute.

---

## Week 4: Pattern Recognition

- [ ] Build queries for common patterns
- [ ] Create dashboard view script
- [ ] Test cross-roster analysis

**Validation:** Can answer "Who needs attention?" across entire roster instantly.

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| Time to onboard new athlete | 2 hours | 15 minutes |
| Weekly review time (all athletes) | 4 hours | 30 minutes |
| Pattern recognition | Manual | Instant |
| Scaling capacity | 20 athletes | 30+ athletes |
