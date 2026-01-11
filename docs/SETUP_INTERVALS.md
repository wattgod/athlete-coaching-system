# Intervals.icu Setup Guide

Complete guide to connecting Athlete OS with Intervals.icu for training data sync.

---

## What is Intervals.icu?

[Intervals.icu](https://intervals.icu) is a free training analysis platform that syncs with Garmin, Wahoo, Strava, and other fitness platforms. It provides:

- **PMC (Performance Management Chart)**: CTL, ATL, TSB tracking
- **Power analysis**: Zones, peaks, trends
- **Activity history**: Searchable workout database
- **API access**: Free developer API

Athlete OS uses the Intervals.icu API to pull:
- Daily wellness/PMC data (CTL, ATL, TSB, ramp rate)
- Activity details and power data
- Zone distribution analysis

---

## Step 1: Create an Intervals.icu Account

1. Go to [intervals.icu](https://intervals.icu)
2. Sign up with email or connect via Strava/Garmin
3. Connect your data sources (Garmin Connect, Wahoo, Strava, etc.)
4. Wait for initial data sync (may take a few minutes)

---

## Step 2: Get Your API Key

1. Log in to Intervals.icu
2. Click your **profile icon** (top right)
3. Select **Settings**
4. Scroll down to **Developer Settings**
5. Click **Show API Key** or **Generate API Key**
6. Copy the API key (looks like: `abc123def456...`)

**Important:** Keep your API key secret. Anyone with this key can access your data.

---

## Step 3: Find Your Athlete ID

Your athlete ID is shown in the URL when viewing your profile:

```
https://intervals.icu/athlete/i12345/...
                          ^^^^^^^
                          This is your athlete ID
```

Or find it in Settings → Developer Settings.

For most users, you can use `i0` which means "myself" (the authenticated user).

---

## Step 4: Configure Environment Variables

Create or edit `.env` in the project root:

```bash
# Intervals.icu API Configuration
INTERVALS_API_KEY=your_api_key_here
```

Or set as environment variable:

```bash
export INTERVALS_API_KEY=your_api_key_here
```

---

## Step 5: Update Athlete Profile

Edit your athlete's `profile.yaml` to include the Intervals.icu athlete ID:

```yaml
integrations:
  intervals_icu:
    athlete_id: "i12345"  # Your athlete ID from Step 3
```

---

## Step 6: Test the Connection

Run a basic sync to verify everything works:

```bash
# Sync PMC data to athlete state
python3 scripts/intervals_sync.py --sync-state --athlete-name matti-rowe

# Expected output:
# Fetching wellness data from Intervals.icu...
# Current PMC: CTL=65.2, ATL=72.1, TSB=-6.9
# Updated athlete state with PMC data
```

---

## Common Commands

### Sync PMC Data to Athlete State

```bash
python3 scripts/intervals_sync.py --sync-state --athlete-name matti-rowe
```

This updates `athlete_state.json` with:
- `performance_management.ctl`
- `performance_management.atl`
- `performance_management.tsb`
- `performance_management.ramp_rate`

### Download Recent Activities

```bash
# Last 30 days
python3 scripts/intervals_sync.py --days 30

# Last 90 days (default)
python3 scripts/intervals_sync.py

# All history
python3 scripts/intervals_sync.py --all
```

### Specify Athlete ID

```bash
python3 scripts/intervals_sync.py --athlete i12345 --days 30
```

---

## Troubleshooting

### "401 Unauthorized" Error

**Cause:** Invalid or expired API key.

**Fix:**
1. Go to Intervals.icu → Settings → Developer Settings
2. Regenerate your API key
3. Update `.env` with the new key

### "404 Not Found" Error

**Cause:** Invalid athlete ID.

**Fix:**
1. Check your athlete ID in the Intervals.icu URL
2. Try using `i0` (means "myself")
3. Update `profile.yaml` with correct ID

### "No wellness data found"

**Cause:** No activities synced or date range issue.

**Fix:**
1. Verify activities are synced in Intervals.icu web interface
2. Try a longer date range: `--days 90`
3. Check that your data source (Garmin, etc.) is connected

### Empty CTL/ATL Values

**Cause:** Not enough training history.

**Fix:**
- CTL needs ~42 days of data to calculate properly
- ATL needs ~7 days
- Ensure activities are syncing from your device

### Rate Limiting

**Cause:** Too many API requests.

**Fix:**
- Intervals.icu has generous rate limits
- If you hit them, wait a few minutes and retry
- Avoid running sync in tight loops

---

## API Reference

The sync script uses these Intervals.icu API endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/athlete/{id}` | Athlete profile (FTP, weight) |
| `GET /api/v1/athlete/{id}/wellness` | PMC data (CTL, ATL, TSB) |
| `GET /api/v1/athlete/{id}/activities` | Activity list |
| `GET /api/v1/activity/{id}` | Activity details |
| `GET /api/v1/activity/{id}/streams` | Power/HR streams |

Full API documentation: [intervals.icu/api/docs](https://intervals.icu/api/docs)

---

## Data Flow

```
Garmin/Wahoo/Strava
        ↓
   Intervals.icu (auto-sync)
        ↓
   intervals_sync.py (API call)
        ↓
   athlete_state.json
        ↓
   Readiness calculation, alerts, dashboards
```

---

## Security Notes

1. **Never commit `.env`** - It's in `.gitignore` for a reason
2. **Rotate keys regularly** - Regenerate if exposed
3. **Use environment variables** - Don't hardcode keys in scripts
4. **Limit access** - API key has read-only access to your data

---

## Support

- **Intervals.icu Discord**: [discord.gg/intervals](https://discord.gg/intervals)
- **API Issues**: Check [intervals.icu/api/docs](https://intervals.icu/api/docs)
- **Athlete OS Issues**: [github.com/wattgod/athlete-coaching-system/issues](https://github.com/wattgod/athlete-coaching-system/issues)
