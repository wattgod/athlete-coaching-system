# Setup Guide

## Prerequisites

- GitHub account (free)
- Git installed locally
- Cursor IDE (https://cursor.sh - free tier works)
- Python 3.8+ (for processing scripts)

---

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `athlete-coaching-system`
3. **Private** (contains athlete data)
4. Initialize with README: No
5. Click "Create repository"

---

## Step 2: Clone Locally

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/athlete-coaching-system.git
cd athlete-coaching-system
```

Or if starting from existing local folder:

```bash
cd ~/athlete-coaching-system
git init
git remote add origin https://github.com/YOUR_USERNAME/athlete-coaching-system.git
```

---

## Step 3: Create Directory Structure

```bash
mkdir -p knowledge/{philosophies,workout_templates,coaching_heuristics}
mkdir -p content/{training_guides,onboarding/{sections,business},reusable_blocks}
mkdir -p athletes/_template/{workout_files,processed}
mkdir -p scripts docs
```

---

## Step 4: Add .cursorrules

Copy the `.cursorrules` file to the repo root. This teaches Cursor how to be your coaching assistant.

```bash
# Verify it's in place
ls -la .cursorrules
```

---

## Step 5: Initial Commit

```bash
git add .
git commit -m "Initial structure"
git push -u origin main
```

---

## Step 6: Open in Cursor

1. Open Cursor IDE
2. File → Open Folder → select `athlete-coaching-system`
3. Wait for indexing to complete

---

## Step 7: Verify Cursor Integration

Open Cursor chat (Cmd+L) and ask:

```
What's your role in this repository?
```

Cursor should respond with Gravel God voice, mentioning coaching, athletes, and the repository structure.

---

## Step 8: Configure Intervals.icu Sync

Copy the sync script from gravel-god:

```bash
cp ~/gravel-god/scripts/intervals_sync.py scripts/
cp ~/gravel-god/pwx_parser scripts/ -r
```

Create `config.yaml` in repo root:

```yaml
intervals_icu:
  api_key: "YOUR_API_KEY"
  athlete_id: "i13791"  # Your ID

athletes:
  matti:
    intervals_id: "i13791"
    ftp: 360
    lthr: 166
```

---

## Step 9: First Sync Test

```bash
cd ~/athlete-coaching-system
python3 scripts/intervals_sync.py --config config.yaml --athlete matti --days 30
```

---

## Step 10: .gitignore Setup

Create `.gitignore`:

```
# Sensitive
config.yaml
*.api_key

# Large files
athletes/*/workout_files/*.fit
athletes/*/workout_files/*.fit.gz

# Python
__pycache__/
*.pyc
.venv/

# OS
.DS_Store

# IDE
.cursor/
```

---

## Workflow

### Daily

1. Open repo in Cursor
2. Ask: "Who needs attention today?"
3. Draft reviews: "Generate weekly review for [athlete]"

### Weekly

1. Sync new data: `python3 scripts/intervals_sync.py --all-athletes`
2. Regenerate signals: `python3 scripts/generate_signals.py`
3. Batch reviews: "Generate all weekly reviews"

### New Athlete

1. Create `athletes/{name}/profile.yaml` from template
2. Configure Intervals.icu sync
3. Run initial sync
4. Ask Cursor: "Generate onboarding for {name}"

---

## Troubleshooting

### Cursor doesn't understand context

- Verify `.cursorrules` is in repo root
- Try: "Read the .cursorrules file and confirm your role"

### Sync fails

- Check API key in config.yaml
- Verify athlete ID format (starts with 'i')
- Test with curl: `curl -u "API_KEY:your_key" "https://intervals.icu/api/v1/athlete/0"`

### Git push rejected

- Pull first: `git pull --rebase`
- Then push: `git push`
