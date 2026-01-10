#!/usr/bin/env python3
"""
Morning Survey Email

Sends the morning check-in survey via email. The athlete can reply with their ratings,
then run morning_check_in.py with the values to trigger the daily briefing.

Usage:
    # Send morning survey
    python3 scripts/morning_survey_email.py matti-rowe --email

    # Send to specific address
    python3 scripts/morning_survey_email.py matti-rowe --email --to gravelgodcoaching@gmail.com

Workflow:
    1. This script sends morning survey email (e.g., via cron at 6am)
    2. Athlete reads email and notes their ratings
    3. Athlete runs: python3 scripts/morning_check_in.py matti-rowe --sleep 8 --fatigue 3 ...
    4. Then runs: python3 scripts/daily_briefing.py matti-rowe --calculate --email

Environment Variables:
    GMAIL_ADDRESS      - Your Gmail address (sender)
    GMAIL_APP_PASSWORD - Gmail App Password
"""

import argparse
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def get_athlete_path(athlete_name: str) -> Path:
    """Get path to athlete folder."""
    return Path(__file__).parent.parent / "athletes" / athlete_name


def generate_survey_text(athlete_name: str) -> str:
    """Generate plain text version of the survey."""
    now = datetime.now()
    date_str = now.strftime("%A, %B %d")

    return f"""
MORNING CHECK-IN - {date_str}

Good morning! Time for your daily readiness check-in.

Rate each item 1-10:

SLEEP QUALITY (1=terrible, 10=amazing)
Your rating: ___

FATIGUE LEVEL (1=fresh, 10=exhausted)
Your rating: ___

LIFE STRESS (1=calm, 10=overwhelmed)
Your rating: ___

MUSCLE SORENESS (1=fresh, 10=very sore)
Your rating: ___

MOTIVATION TO TRAIN (1=not at all, 10=fired up)
Your rating: ___

NOTES (optional):
_______________________

─────────────────────────────────

After completing, run:

python3 scripts/morning_check_in.py {athlete_name} \\
    --sleep-quality X --fatigue X --stress X --soreness X --motivation X

Then get your briefing:

python3 scripts/daily_briefing.py {athlete_name} --calculate --email

─────────────────────────────────
Athlete OS • Gravel God Coaching
"""


def generate_survey_html(athlete_name: str, state: dict = None) -> str:
    """Generate HTML morning briefing with check-in link."""
    now = datetime.now()
    date_str = now.strftime("%A, %B %d").upper()

    # GitHub Pages check-in form
    github_repo = os.environ.get("GITHUB_REPO", "wattgod/athlete-coaching-system")
    github_user = github_repo.split("/")[0]
    repo_name = github_repo.split("/")[1]
    checkin_url = f"https://{github_user}.github.io/{repo_name}/checkin.html"

    # Extract metrics from state if available
    pmc = state.get("performance_management", {}) if state else {}
    readiness = state.get("readiness", {}) if state else {}
    recent = state.get("recent_training", {}) if state else {}

    ctl = pmc.get("ctl", "—")
    atl = pmc.get("atl", "—")
    tsb = pmc.get("tsb", "—")
    last_score = readiness.get("score", "—")

    # Determine TSB status
    if isinstance(tsb, (int, float)):
        if tsb > 5:
            tsb_status = "FRESH"
        elif tsb > -5:
            tsb_status = "BALANCED"
        elif tsb > -15:
            tsb_status = "FATIGUED"
        else:
            tsb_status = "TIRED"
    else:
        tsb_status = "—"

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sometype+Mono:wght@400;600;700&display=swap');

        body {{
            font-family: 'Sometype Mono', 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
            line-height: 1.5;
            color: #000;
            max-width: 600px;
            margin: 0 auto;
            padding: 0;
            background: #fff;
        }}
        .container {{
            background: #fff;
            border: 3px solid #000;
        }}
        .header {{
            background: #000;
            color: #fff;
            padding: 24px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            font-weight: 700;
        }}
        .header-title {{
            font-size: 28px;
            letter-spacing: 0.2em;
            margin-bottom: 4px;
        }}
        .header-date {{
            font-size: 12px;
            font-weight: 400;
            opacity: 0.8;
        }}
        .content {{
            padding: 24px;
        }}
        .section-title {{
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            color: #666;
            margin-bottom: 12px;
            border-bottom: 2px solid #000;
            padding-bottom: 8px;
        }}
        .metrics-grid {{
            display: table;
            width: 100%;
            border: 2px solid #000;
            margin-bottom: 24px;
        }}
        .metric-row {{
            display: table-row;
        }}
        .metric-label {{
            display: table-cell;
            padding: 14px 16px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid #000;
            border-right: 2px solid #000;
            background: #f5f5f5;
            width: 50%;
        }}
        .metric-value {{
            display: table-cell;
            padding: 14px 16px;
            font-size: 16px;
            font-weight: 700;
            text-align: right;
            border-bottom: 1px solid #000;
        }}
        .metric-row:last-child .metric-label,
        .metric-row:last-child .metric-value {{
            border-bottom: none;
        }}
        .status-badge {{
            display: inline-block;
            font-size: 10px;
            padding: 4px 8px;
            margin-left: 8px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .status-fresh {{ background: #000; color: #fff; }}
        .status-balanced {{ background: #666; color: #fff; }}
        .status-fatigued {{ background: #999; color: #fff; }}
        .status-tired {{ background: #ccc; color: #000; }}
        .checkin-section {{
            margin-top: 24px;
        }}
        .checkin-btn {{
            display: block;
            background: #000;
            color: #fff;
            text-align: center;
            padding: 20px 24px;
            text-decoration: none;
            font-weight: 700;
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            font-family: 'Sometype Mono', monospace;
            border: 3px solid #000;
        }}
        .checkin-btn:hover {{
            background: #333;
        }}
        .checkin-hint {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #666;
            text-align: center;
            margin-top: 12px;
        }}
        .footer {{
            padding: 20px 24px;
            background: #000;
            color: #fff;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            text-align: center;
        }}
        .footer-quote {{
            margin-top: 8px;
            font-weight: 400;
            letter-spacing: 0.05em;
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-title">MORNING BRIEF</div>
            <div class="header-date">{date_str}</div>
        </div>

        <div class="content">
            <div class="section-title">CURRENT STATUS</div>

            <div class="metrics-grid">
                <div class="metric-row">
                    <div class="metric-label">Last Readiness</div>
                    <div class="metric-value">{last_score}</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">Fitness (CTL)</div>
                    <div class="metric-value">{ctl}</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">Fatigue (ATL)</div>
                    <div class="metric-value">{atl}</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">Form (TSB)</div>
                    <div class="metric-value">{tsb}<span class="status-badge status-{tsb_status.lower()}">{tsb_status}</span></div>
                </div>
            </div>

            <div class="checkin-section">
                <a href="{checkin_url}" class="checkin-btn">
                    CHECK IN NOW →
                </a>
                <div class="checkin-hint">
                    Rate: Sleep / Fatigue / Stress / Soreness / Motivation (1-10)
                </div>
            </div>
        </div>

        <div class="footer">
            ATHLETE OS — GRAVEL GOD COACHING
            <div class="footer-quote">"RESPOND TO YOUR BODY, NOT JUST THE PLAN"</div>
        </div>
    </div>
</body>
</html>
"""


def send_email(to_address: str, subject: str, text_body: str, html_body: str) -> bool:
    """Send email via Gmail SMTP."""
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        print("Error: Email credentials not configured")
        print("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_address

    part1 = MIMEText(text_body, "plain")
    part2 = MIMEText(html_body, "html")
    msg.attach(part1)
    msg.attach(part2)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, to_address, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        print("Error: Gmail authentication failed")
        print("Make sure you're using an App Password, not your regular password")
        return False
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def load_athlete_state(athlete_name: str) -> dict:
    """Load athlete state from JSON file."""
    import json
    state_path = get_athlete_path(athlete_name) / "athlete_state.json"
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {}


def main():
    parser = argparse.ArgumentParser(description="Send morning briefing with check-in link")
    parser.add_argument("athlete_name", help="Athlete folder name (e.g., 'matti-rowe')")
    parser.add_argument("--email", action="store_true", help="Send via email")
    parser.add_argument("--to", type=str, help="Recipient email address")
    parser.add_argument("--print", action="store_true", dest="print_only", help="Print to console")

    args = parser.parse_args()

    # Verify athlete exists
    athlete_path = get_athlete_path(args.athlete_name)
    if not athlete_path.exists():
        print(f"Error: Athlete '{args.athlete_name}' not found")
        sys.exit(1)

    # Load athlete state for metrics
    state = load_athlete_state(args.athlete_name)

    # Generate briefing
    text_survey = generate_survey_text(args.athlete_name)
    html_survey = generate_survey_html(args.athlete_name, state)

    if args.print_only:
        print(text_survey)
        return

    if args.email:
        to_address = args.to or os.environ.get("GMAIL_ADDRESS")
        if not to_address:
            print("Error: No recipient. Use --to or set GMAIL_ADDRESS")
            sys.exit(1)

        now = datetime.now()
        subject = f"Morning Brief - {now.strftime('%b %d')}"

        if send_email(to_address, subject, text_survey, html_survey):
            print(f"Briefing sent to {to_address}")
        else:
            print("Failed to send email")
            sys.exit(1)
    else:
        # Default: print to console
        print(text_survey)
        print("\nUse --email to send via email")


if __name__ == "__main__":
    main()
