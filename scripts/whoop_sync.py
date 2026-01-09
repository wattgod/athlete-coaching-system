#!/usr/bin/env python3
"""
WHOOP Sync - Pull recovery, sleep, and HRV data from WHOOP API

Setup:
    1. Create an app at https://developer.whoop.com/dashboard
    2. Set redirect URI to: http://localhost:8080/callback
    3. Set environment variables:
       - WHOOP_CLIENT_ID
       - WHOOP_CLIENT_SECRET
    4. Run: python3 scripts/whoop_sync.py --auth (first time)
    5. Run: python3 scripts/whoop_sync.py --athlete-name matti-rowe

Usage:
    python3 scripts/whoop_sync.py --auth                    # Authenticate (first time)
    python3 scripts/whoop_sync.py --athlete-name matti-rowe # Sync data
    python3 scripts/whoop_sync.py --athlete-name matti-rowe --days 7
"""

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlparse
import requests

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# =============================================================================
# CONFIGURATION
# =============================================================================

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_API_BASE = "https://api.prod.whoop.com/developer"

REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "read:recovery read:sleep read:cycles read:profile read:body_measurement"

TOKEN_FILE = Path(__file__).parent.parent / ".whoop_tokens.json"


# =============================================================================
# OAUTH HELPERS
# =============================================================================

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from WHOOP"""

    def do_GET(self):
        """Process callback with authorization code"""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)

            if "code" in params:
                self.server.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    </body></html>
                """)
            else:
                error = params.get("error", ["Unknown error"])[0]
                self.server.auth_code = None
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def get_authorization_code(client_id: str) -> str:
    """Open browser for user authorization, return code"""

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": "athlete_os_auth",
    }
    auth_url = f"{WHOOP_AUTH_URL}?{urlencode(params)}"

    print("\nOpening browser for WHOOP authorization...")
    print(f"If browser doesn't open, visit: {auth_url}\n")

    webbrowser.open(auth_url)

    # Start local server to receive callback
    server = HTTPServer(("localhost", 8080), OAuthCallbackHandler)
    server.auth_code = None

    print("Waiting for authorization callback...")
    while server.auth_code is None:
        server.handle_request()

    return server.auth_code


def exchange_code_for_tokens(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange authorization code for access/refresh tokens"""

    response = requests.post(
        WHOOP_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    response.raise_for_status()
    return response.json()


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Refresh expired access token"""

    response = requests.post(
        WHOOP_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    response.raise_for_status()
    return response.json()


def save_tokens(tokens: dict):
    """Save tokens to file"""
    tokens["saved_at"] = datetime.now(timezone.utc).isoformat()
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    # Secure the file
    TOKEN_FILE.chmod(0o600)
    print(f"  Tokens saved to {TOKEN_FILE}")


def load_tokens() -> dict:
    """Load tokens from file"""
    if not TOKEN_FILE.exists():
        return None
    with open(TOKEN_FILE) as f:
        return json.load(f)


def authenticate(client_id: str, client_secret: str) -> dict:
    """Full OAuth flow to get tokens"""

    print("=" * 60)
    print("  WHOOP Authentication")
    print("=" * 60)

    code = get_authorization_code(client_id)

    if not code:
        print("Error: No authorization code received")
        return None

    print("  Exchanging code for tokens...")
    tokens = exchange_code_for_tokens(client_id, client_secret, code)

    save_tokens(tokens)

    print("\n  Authentication successful!")
    return tokens


def get_valid_access_token(client_id: str, client_secret: str) -> str:
    """Get a valid access token, refreshing if needed"""

    tokens = load_tokens()

    if not tokens:
        print("Error: No saved tokens. Run with --auth first.")
        return None

    # Check if token is expired (WHOOP tokens typically last 1 hour)
    # Try the token, refresh if it fails
    try:
        response = requests.get(
            f"{WHOOP_API_BASE}/v1/user/profile/basic",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        if response.status_code == 401:
            raise requests.exceptions.HTTPError("Token expired")

        response.raise_for_status()
        return tokens["access_token"]

    except requests.exceptions.HTTPError:
        print("  Access token expired, refreshing...")

        try:
            new_tokens = refresh_access_token(
                client_id, client_secret, tokens["refresh_token"]
            )
            save_tokens(new_tokens)
            return new_tokens["access_token"]

        except Exception as e:
            print(f"Error refreshing token: {e}")
            print("Try running with --auth to re-authenticate")
            return None


# =============================================================================
# WHOOP API CLIENT
# =============================================================================

class WHOOPClient:
    """Client for WHOOP API v2"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to API"""
        response = self.session.get(
            f"{WHOOP_API_BASE}{endpoint}",
            params=params
        )
        response.raise_for_status()
        return response.json()

    def get_profile(self) -> dict:
        """Get user profile"""
        return self._get("/v1/user/profile/basic")

    def get_body_measurement(self) -> dict:
        """Get body measurements (height, weight, max HR)"""
        return self._get("/v1/user/measurement/body")

    def get_recovery(self, start: str = None, end: str = None, limit: int = 25) -> list:
        """
        Get recovery data

        Args:
            start: Start date (ISO format)
            end: End date (ISO format)
            limit: Max records (default 25)

        Returns:
            List of recovery records
        """
        params = {"limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        result = self._get("/v1/recovery", params)
        return result.get("records", [])

    def get_sleep(self, start: str = None, end: str = None, limit: int = 25) -> list:
        """Get sleep data"""
        params = {"limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        result = self._get("/v1/activity/sleep", params)
        return result.get("records", [])

    def get_cycles(self, start: str = None, end: str = None, limit: int = 25) -> list:
        """Get physiological cycles (strain data)"""
        params = {"limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        result = self._get("/v1/cycle", params)
        return result.get("records", [])


# =============================================================================
# SYNC LOGIC
# =============================================================================

def sync_whoop_data(
    client_id: str,
    client_secret: str,
    athlete_name: str,
    days: int = 7
) -> dict:
    """
    Sync WHOOP data to athlete_state.json

    Args:
        client_id: WHOOP OAuth client ID
        client_secret: WHOOP OAuth client secret
        athlete_name: Local athlete folder name
        days: Days of history to fetch

    Returns:
        Dict of synced data
    """
    print("=" * 60)
    print("  WHOOP Sync")
    print("=" * 60)

    # Get valid access token
    access_token = get_valid_access_token(client_id, client_secret)
    if not access_token:
        return None

    client = WHOOPClient(access_token)

    # Get profile
    print("\n  Fetching profile...")
    try:
        profile = client.get_profile()
        print(f"    User: {profile.get('first_name', '')} {profile.get('last_name', '')}")
    except Exception as e:
        print(f"    Warning: Could not fetch profile: {e}")
        profile = {}

    # Get body measurements
    print("  Fetching body measurements...")
    try:
        body = client.get_body_measurement()
        max_hr = body.get("max_heart_rate")
        print(f"    Max HR: {max_hr}")
    except Exception as e:
        print(f"    Warning: Could not fetch body measurements: {e}")
        body = {}

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")

    # Get recovery data
    print(f"  Fetching recovery data (last {days} days)...")
    try:
        recoveries = client.get_recovery(start=start_str, end=end_str, limit=days)
        print(f"    Found {len(recoveries)} recovery records")
    except Exception as e:
        print(f"    Warning: Could not fetch recovery: {e}")
        recoveries = []

    # Get sleep data
    print(f"  Fetching sleep data (last {days} days)...")
    try:
        sleeps = client.get_sleep(start=start_str, end=end_str, limit=days)
        print(f"    Found {len(sleeps)} sleep records")
    except Exception as e:
        print(f"    Warning: Could not fetch sleep: {e}")
        sleeps = []

    # Process most recent recovery
    latest_recovery = None
    if recoveries:
        latest = recoveries[0]  # Already sorted descending
        score = latest.get("score", {})
        latest_recovery = {
            "date": latest.get("created_at", "")[:10],
            "recovery_score": score.get("recovery_score"),
            "hrv_rmssd": score.get("hrv_rmssd_milli"),  # in milliseconds
            "resting_hr": score.get("resting_heart_rate"),
            "spo2": score.get("spo2_percentage"),
            "skin_temp": score.get("skin_temp_celsius"),
        }

    # Process most recent sleep
    latest_sleep = None
    if sleeps:
        latest = sleeps[0]
        score = latest.get("score", {})
        latest_sleep = {
            "date": latest.get("start", "")[:10],
            "total_hours": (latest.get("end_epoch_milli", 0) - latest.get("start_epoch_milli", 0)) / 1000 / 3600 if latest.get("end_epoch_milli") else None,
            "sleep_performance": score.get("sleep_performance_percentage"),
            "sleep_efficiency": score.get("sleep_efficiency_percentage"),
            "sleep_consistency": score.get("sleep_consistency_percentage"),
            "respiratory_rate": score.get("respiratory_rate"),
            "stage_summary": score.get("stage_summary", {}),
        }

    # Calculate 7-day averages
    avg_recovery = None
    avg_hrv = None
    avg_rhr = None
    if recoveries:
        scores = [r.get("score", {}).get("recovery_score") for r in recoveries if r.get("score", {}).get("recovery_score")]
        hrvs = [r.get("score", {}).get("hrv_rmssd_milli") for r in recoveries if r.get("score", {}).get("hrv_rmssd_milli")]
        rhrs = [r.get("score", {}).get("resting_heart_rate") for r in recoveries if r.get("score", {}).get("resting_heart_rate")]

        if scores:
            avg_recovery = round(sum(scores) / len(scores), 1)
        if hrvs:
            avg_hrv = round(sum(hrvs) / len(hrvs), 1)
        if rhrs:
            avg_rhr = round(sum(rhrs) / len(rhrs), 1)

    avg_sleep_hours = None
    if sleeps:
        hours = []
        for s in sleeps:
            if s.get("end_epoch_milli") and s.get("start_epoch_milli"):
                h = (s["end_epoch_milli"] - s["start_epoch_milli"]) / 1000 / 3600
                if h > 0:
                    hours.append(h)
        if hours:
            avg_sleep_hours = round(sum(hours) / len(hours), 2)

    # Build state update
    state_updates = {}

    if latest_recovery:
        # HRV is in milliseconds, convert to standard format
        hrv_value = latest_recovery.get("hrv_rmssd")
        if hrv_value:
            hrv_value = round(hrv_value, 1)

        state_updates["whoop_daily"] = {
            "date": latest_recovery.get("date"),
            "hrv": hrv_value,
            "resting_hr": latest_recovery.get("resting_hr"),
            "recovery_score": latest_recovery.get("recovery_score"),
            "spo2": latest_recovery.get("spo2"),
            "skin_temp": latest_recovery.get("skin_temp"),
        }

        state_updates["fatigue_indicators"] = {
            "hrv": {
                "current": hrv_value,
                "7d_avg": avg_hrv,
            },
            "resting_hr": {
                "current": latest_recovery.get("resting_hr"),
                "7d_avg": avg_rhr,
            },
            "whoop_recovery": {
                "current": latest_recovery.get("recovery_score"),
                "7d_avg": avg_recovery,
            },
        }

    if latest_sleep:
        sleep_hours = latest_sleep.get("total_hours")
        if sleep_hours:
            sleep_hours = round(sleep_hours, 2)

        if "whoop_daily" not in state_updates:
            state_updates["whoop_daily"] = {}

        state_updates["whoop_daily"].update({
            "sleep_hours": sleep_hours,
        })

        # Add sleep stage breakdown if available
        stages = latest_sleep.get("stage_summary", {})
        if stages:
            state_updates["whoop_daily"]["deep_sleep_hours"] = round(stages.get("total_slow_wave_sleep_time_milli", 0) / 1000 / 3600, 2) if stages.get("total_slow_wave_sleep_time_milli") else None
            state_updates["whoop_daily"]["rem_sleep_hours"] = round(stages.get("total_rem_sleep_time_milli", 0) / 1000 / 3600, 2) if stages.get("total_rem_sleep_time_milli") else None
            state_updates["whoop_daily"]["awakenings"] = stages.get("disturbance_count")

        if "fatigue_indicators" not in state_updates:
            state_updates["fatigue_indicators"] = {}

        state_updates["fatigue_indicators"]["sleep"] = {
            "last_night_hours": sleep_hours,
            "7d_avg_hours": avg_sleep_hours,
            "quality": "good" if latest_sleep.get("sleep_performance", 0) > 70 else "fair" if latest_sleep.get("sleep_performance", 0) > 50 else "poor",
        }

    # Load and update athlete state
    athletes_dir = Path(__file__).parent.parent / "athletes"
    state_path = athletes_dir / athlete_name / "athlete_state.json"

    if not state_path.exists():
        print(f"\n  Error: Athlete state file not found: {state_path}")
        return None

    with open(state_path) as f:
        state = json.load(f)

    # Deep merge
    def deep_merge(base, updates):
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            elif value is not None:
                base[key] = value

    deep_merge(state, state_updates)

    # Update metadata
    state["_meta"]["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state["_meta"]["updated_by"] = "whoop_sync"

    # Save
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    # Print summary
    print(f"\n  Updated {athlete_name}/athlete_state.json:")
    if latest_recovery:
        print(f"    Recovery Score: {latest_recovery.get('recovery_score')}%")
        print(f"    HRV: {hrv_value} ms")
        print(f"    Resting HR: {latest_recovery.get('resting_hr')} bpm")
    if latest_sleep:
        print(f"    Sleep: {sleep_hours} hours")
    if avg_recovery:
        print(f"    7-day avg recovery: {avg_recovery}%")
    if avg_hrv:
        print(f"    7-day avg HRV: {avg_hrv} ms")

    return state_updates


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Sync WHOOP data to athlete state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Setup:
    1. Create app at https://developer.whoop.com/dashboard
    2. Set redirect URI to: http://localhost:8080/callback
    3. Export credentials:
       export WHOOP_CLIENT_ID="your_client_id"
       export WHOOP_CLIENT_SECRET="your_client_secret"

Examples:
    # First time authentication
    python3 scripts/whoop_sync.py --auth

    # Sync data to athlete state
    python3 scripts/whoop_sync.py --athlete-name matti-rowe

    # Sync more history
    python3 scripts/whoop_sync.py --athlete-name matti-rowe --days 14
        """
    )

    parser.add_argument("--auth", action="store_true",
                        help="Run OAuth authentication flow")
    parser.add_argument("--athlete-name",
                        help="Athlete folder name (e.g., matti-rowe)")
    parser.add_argument("--days", type=int, default=7,
                        help="Days of history to fetch (default: 7)")
    parser.add_argument("--client-id",
                        default=os.environ.get("WHOOP_CLIENT_ID"),
                        help="WHOOP OAuth client ID")
    parser.add_argument("--client-secret",
                        default=os.environ.get("WHOOP_CLIENT_SECRET"),
                        help="WHOOP OAuth client secret")

    args = parser.parse_args()

    # Check credentials
    if not args.client_id or not args.client_secret:
        print("Error: WHOOP credentials not provided.")
        print()
        print("Set environment variables:")
        print("  export WHOOP_CLIENT_ID='your_client_id'")
        print("  export WHOOP_CLIENT_SECRET='your_client_secret'")
        print()
        print("Or get credentials at: https://developer.whoop.com/dashboard")
        sys.exit(1)

    # Auth mode
    if args.auth:
        result = authenticate(args.client_id, args.client_secret)
        sys.exit(0 if result else 1)

    # Sync mode
    if not args.athlete_name:
        print("Error: --athlete-name required for sync")
        print("Usage: python3 scripts/whoop_sync.py --athlete-name matti-rowe")
        sys.exit(1)

    result = sync_whoop_data(
        client_id=args.client_id,
        client_secret=args.client_secret,
        athlete_name=args.athlete_name,
        days=args.days
    )

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
