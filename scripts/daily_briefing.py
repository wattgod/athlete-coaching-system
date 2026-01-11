#!/usr/bin/env python3
"""
Daily Briefing Script

Generates and optionally emails the daily coaching briefing.
Includes readiness score, health gates, and session recommendations.

Usage:
    # Print briefing to console
    python3 scripts/daily_briefing.py matti-rowe

    # Send via email
    python3 scripts/daily_briefing.py matti-rowe --email

    # Send to specific address
    python3 scripts/daily_briefing.py matti-rowe --email --to gravelgodcoaching@gmail.com

    # Include data sync before briefing
    python3 scripts/daily_briefing.py matti-rowe --sync --email

Environment Variables (for email):
    GMAIL_ADDRESS     - Your Gmail address (sender)
    GMAIL_APP_PASSWORD - Gmail App Password (NOT your regular password)

To get an App Password:
    1. Enable 2FA on your Google account
    2. Go to: https://myaccount.google.com/apppasswords
    3. Create a new app password for "Mail"
    4. Set GMAIL_APP_PASSWORD to the generated password
"""

import argparse
import json
import os
import smtplib
import subprocess
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from blindspot_rules import get_blindspot_prompts, get_blindspot_adjustments


# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def get_athlete_path(athlete_name: str) -> Path:
    """Get path to athlete folder."""
    return Path(__file__).parent.parent / "athletes" / athlete_name


def load_state(athlete_name: str) -> dict:
    """Load athlete state from JSON file."""
    state_path = get_athlete_path(athlete_name) / "athlete_state.json"
    with open(state_path) as f:
        return json.load(f)


def load_profile(athlete_name: str) -> dict:
    """Load athlete profile from YAML file."""
    import yaml
    profile_path = get_athlete_path(athlete_name) / "profile.yaml"
    with open(profile_path) as f:
        return yaml.safe_load(f)


def run_sync(athlete_name: str, verbose: bool = False) -> bool:
    """Run data sync scripts."""
    scripts_dir = Path(__file__).parent

    # Try to sync from Intervals.icu
    intervals_script = scripts_dir / "intervals_sync.py"
    if intervals_script.exists() and os.environ.get("INTERVALS_API_KEY"):
        try:
            result = subprocess.run(
                ["python3", str(intervals_script), "--sync-state", "--athlete-name", athlete_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            if verbose:
                print(f"Intervals.icu sync: {'OK' if result.returncode == 0 else 'FAILED'}")
        except Exception as e:
            if verbose:
                print(f"Intervals.icu sync error: {e}")

    # Try to sync from WHOOP
    whoop_script = scripts_dir / "whoop_sync.py"
    if whoop_script.exists():
        try:
            result = subprocess.run(
                ["python3", str(whoop_script), "--athlete-name", athlete_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            if verbose:
                print(f"WHOOP sync: {'OK' if result.returncode == 0 else 'FAILED'}")
        except Exception as e:
            if verbose:
                print(f"WHOOP sync error: {e}")

    return True


def run_readiness_calculation(athlete_name: str, verbose: bool = False) -> bool:
    """Run readiness calculation script."""
    scripts_dir = Path(__file__).parent
    readiness_script = scripts_dir / "calculate_readiness.py"

    if readiness_script.exists():
        try:
            result = subprocess.run(
                ["python3", str(readiness_script), athlete_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if verbose:
                print(f"Readiness calculation: {'OK' if result.returncode == 0 else 'FAILED'}")
            return result.returncode == 0
        except Exception as e:
            if verbose:
                print(f"Readiness calculation error: {e}")
            return False
    return False


def get_session_recommendation(readiness: dict, health_gates: dict) -> dict:
    """Generate session recommendation based on readiness."""
    score = readiness.get("score", 50)
    gates_pass = health_gates.get("overall", {}).get("all_gates_pass", True)
    intensity_allowed = health_gates.get("overall", {}).get("intensity_allowed", True)

    if not gates_pass or not intensity_allowed:
        return {
            "type": "recovery",
            "color": "red",
            "message": "Health gate blocked - recovery day recommended",
            "examples": ["Rest", "Light stretching", "Easy walk", "Yoga"],
        }

    if score >= 70:
        return {
            "type": "key",
            "color": "green",
            "message": "Ready for intensity - key session eligible",
            "examples": ["Threshold work", "VO2max intervals", "G-Spot session", "Race simulation"],
        }
    elif score >= 45:
        return {
            "type": "support",
            "color": "yellow",
            "message": "Moderate readiness - support session recommended",
            "examples": ["Endurance ride", "Tempo work", "Skill drills", "Easy group ride"],
        }
    else:
        return {
            "type": "recovery",
            "color": "red",
            "message": "Low readiness - recovery day recommended",
            "examples": ["Rest", "Active recovery", "Light spin", "Mobility work"],
        }


def format_health_gates(health_gates: dict) -> str:
    """Format health gates for display."""
    gates = ["sleep", "energy", "autonomic", "musculoskeletal", "stress"]
    lines = []

    for gate in gates:
        gate_data = health_gates.get(gate, {})
        passed = gate_data.get("gate_pass", True)
        status = "PASS" if passed else "FAIL"
        icon = "✓" if passed else "✗"
        lines.append(f"  {icon} {gate.capitalize()}: {status}")

    return "\n".join(lines)


def format_subjective_data(subjective: dict) -> str:
    """Format subjective check-in data for display."""
    if not subjective:
        return "  No check-in data - run morning_check_in.py first"

    lines = []
    if "sleep_quality" in subjective:
        lines.append(f"  Sleep Quality:  {subjective['sleep_quality']}/10")
    if "fatigue_level" in subjective:
        lines.append(f"  Fatigue Level:  {subjective['fatigue_level']}/10")
    if "stress_level" in subjective:
        lines.append(f"  Life Stress:    {subjective['stress_level']}/10")
    if "soreness_level" in subjective:
        lines.append(f"  Soreness:       {subjective['soreness_level']}/10")
    if "motivation" in subjective:
        lines.append(f"  Motivation:     {subjective['motivation']}/10")
    if "subjective_score" in subjective:
        lines.append(f"\n  Subjective Score: {subjective['subjective_score']}/100")

    return "\n".join(lines) if lines else "  No check-in data"


def generate_briefing(athlete_name: str, state: dict, profile: dict = None) -> str:
    """Generate the daily briefing text."""
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")

    readiness = state.get("readiness", {})
    health_gates = state.get("health_gates", {})
    pmc = state.get("performance_management", {})
    subjective = state.get("subjective_data", {})
    recent_training = state.get("recent_training", {})

    # Get recommendation
    recommendation = get_session_recommendation(readiness, health_gates)

    # Build briefing
    lines = [
        "=" * 60,
        f"  DAILY COACHING BRIEFING",
        f"  {date_str}",
        "=" * 60,
        "",
        f"Good morning{', ' + athlete_name.replace('-', ' ').title() if athlete_name else ''}!",
        "",
    ]

    # Readiness Score
    score = readiness.get("score", "N/A")
    color_map = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    color = color_map.get(recommendation["color"], "⚪")

    lines.extend([
        "─" * 40,
        "READINESS SCORE",
        "─" * 40,
        f"",
        f"  {color} Score: {score}/100",
        f"",
        f"  {recommendation['message']}",
        "",
    ])

    # Health Gates
    lines.extend([
        "─" * 40,
        "HEALTH GATES",
        "─" * 40,
        format_health_gates(health_gates),
        "",
    ])

    # Subjective Data
    lines.extend([
        "─" * 40,
        "TODAY'S CHECK-IN",
        "─" * 40,
        format_subjective_data(subjective),
        "",
    ])

    # PMC Data
    if pmc:
        lines.extend([
            "─" * 40,
            "TRAINING LOAD",
            "─" * 40,
            f"  CTL (Fitness): {pmc.get('ctl', 'N/A')}",
            f"  ATL (Fatigue): {pmc.get('atl', 'N/A')}",
            f"  TSB (Form):    {pmc.get('tsb', 'N/A')}",
            "",
        ])

    # Recent Training
    if recent_training:
        zone_dist = recent_training.get("zone_distribution", {})
        if zone_dist:
            z12 = zone_dist.get("z1_z2_percent", "N/A")
            z3 = zone_dist.get("z3_percent", "N/A")
            z4 = zone_dist.get("z4_plus_percent", "N/A")
            lines.extend([
                "─" * 40,
                "ZONE DISTRIBUTION (7 DAYS)",
                "─" * 40,
                f"  Z1-Z2: {z12}% (target: 84%)",
                f"  Z3:    {z3}% (target: 6%)",
                f"  Z4+:   {z4}% (target: 10%)",
                "",
            ])

    # Recommendation
    lines.extend([
        "─" * 40,
        "TODAY'S RECOMMENDATION",
        "─" * 40,
        f"",
        f"  Session Type: {recommendation['type'].upper()}",
        f"",
        f"  Options:",
    ])
    for example in recommendation["examples"]:
        lines.append(f"    • {example}")

    lines.extend([
        "",
        "─" * 40,
        "",
        "Remember: Respond to your body, not just the plan.",
        "Recovery makes you fast.",
        "",
        "─" * 40,
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
    ])

    return "\n".join(lines)


def generate_html_briefing(athlete_name: str, state: dict, profile: dict = None) -> str:
    """Generate Neo-Brutalist HTML version of the briefing for email."""
    now = datetime.now()
    date_str = now.strftime("%A, %B %d").upper()

    readiness = state.get("readiness", {})
    health_gates = state.get("health_gates", {})
    pmc = state.get("performance_management", {})
    subjective = state.get("subjective_data", {})
    ans_quadrant = readiness.get("ans_quadrant", {})

    recommendation = get_session_recommendation(readiness, health_gates)

    score = readiness.get("score", "—")

    # Determine status badge with color
    if recommendation["color"] == "green":
        status_text = "KEY SESSION"
        status_bg = "#22c55e"  # Green
        score_color = "#22c55e"
    elif recommendation["color"] == "yellow":
        status_text = "SUPPORT"
        status_bg = "#eab308"  # Yellow
        score_color = "#eab308"
    else:
        status_text = "RECOVERY"
        status_bg = "#ef4444"  # Red
        score_color = "#ef4444"

    # ANS quadrant display
    quadrant_names = {0: "UNKNOWN", 1: "Q1 RECOVERY", 2: "Q2 READY", 3: "Q3 OVERREACH", 4: "Q4 OVERTRAINED"}
    ans_status = quadrant_names.get(ans_quadrant.get("quadrant", 0), "UNKNOWN")

    html = f"""
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
        }}
        .header-title {{
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 0.2em;
            margin-bottom: 4px;
        }}
        .header-date {{
            font-size: 11px;
            font-weight: 400;
            opacity: 0.7;
        }}
        .score-section {{
            padding: 24px;
            border-bottom: 3px solid #000;
        }}
        .score-display {{
            display: table;
            width: 100%;
        }}
        .score-main {{
            display: table-cell;
            vertical-align: middle;
        }}
        .score-number {{
            font-size: 64px;
            font-weight: 700;
            line-height: 1;
            color: {score_color};
        }}
        .score-label {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #666;
            margin-top: 4px;
        }}
        .score-status {{
            display: table-cell;
            vertical-align: middle;
            text-align: right;
        }}
        .status-badge {{
            display: inline-block;
            background: {status_bg};
            color: #fff;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }}
        .ans-badge {{
            display: inline-block;
            background: #f5f5f5;
            color: #000;
            padding: 6px 12px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 8px;
            border: 2px solid #000;
        }}
        .section {{
            padding: 20px 24px;
            border-bottom: 2px solid #000;
        }}
        .section:last-child {{
            border-bottom: none;
        }}
        .section-title {{
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: #666;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #000;
        }}
        .metrics-grid {{
            display: table;
            width: 100%;
            border: 2px solid #000;
        }}
        .metric-row {{
            display: table-row;
        }}
        .metric-label {{
            display: table-cell;
            padding: 12px 14px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid #000;
            border-right: 2px solid #000;
            background: #f5f5f5;
            width: 60%;
        }}
        .metric-value {{
            display: table-cell;
            padding: 12px 14px;
            font-size: 14px;
            font-weight: 700;
            text-align: right;
            border-bottom: 1px solid #000;
        }}
        .metric-row:last-child .metric-label,
        .metric-row:last-child .metric-value {{
            border-bottom: none;
        }}
        .gate-pass {{
            color: #000;
        }}
        .gate-fail {{
            color: #000;
            background: #000;
            color: #fff;
        }}
        .recommendation-box {{
            background: #000;
            color: #fff;
            padding: 20px;
            text-align: center;
        }}
        .recommendation-type {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            opacity: 0.7;
            margin-bottom: 8px;
        }}
        .recommendation-text {{
            font-size: 16px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }}
        .options-list {{
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #333;
        }}
        .options-list span {{
            display: inline-block;
            margin: 4px 8px 4px 0;
            padding: 4px 8px;
            background: #333;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .footer {{
            padding: 20px 24px;
            background: #000;
            color: #fff;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
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
            <div class="header-title">DAILY BRIEFING</div>
            <div class="header-date">{date_str}</div>
        </div>

        <div class="score-section">
            <div class="score-display">
                <div class="score-main">
                    <div class="score-number">{score}</div>
                    <div class="score-label">Readiness Score</div>
                </div>
                <div class="score-status">
                    <div class="status-badge">{status_text}</div>
                    <div class="ans-badge">{ans_status}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Health Gates</div>
            <div class="metrics-grid">
"""

    for gate in ["sleep", "energy", "autonomic", "musculoskeletal", "stress"]:
        gate_data = health_gates.get(gate, {})
        passed = gate_data.get("gate_pass", True)
        status_text_gate = "PASS" if passed else "FAIL"
        value_class = "gate-pass" if passed else "gate-fail"
        html += f"""
                <div class="metric-row">
                    <div class="metric-label">{gate.upper()}</div>
                    <div class="metric-value {value_class}">{status_text_gate}</div>
                </div>
"""

    html += """
            </div>
        </div>

        <div class="section">
            <div class="section-title">Today's Check-In</div>
            <div class="metrics-grid">
"""

    if subjective:
        metrics = [
            ("SLEEP QUALITY", subjective.get("sleep_quality"), "/10"),
            ("FATIGUE", subjective.get("fatigue_level"), "/10"),
            ("STRESS", subjective.get("stress_level"), "/10"),
            ("SORENESS", subjective.get("soreness_level"), "/10"),
            ("MOTIVATION", subjective.get("motivation"), "/10"),
        ]
        for label, value, suffix in metrics:
            if value is not None:
                html += f"""
                <div class="metric-row">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}{suffix}</div>
                </div>
"""
    else:
        html += """
                <div class="metric-row">
                    <div class="metric-label">STATUS</div>
                    <div class="metric-value">NO DATA</div>
                </div>
"""

    html += """
            </div>
        </div>
"""

    if pmc:
        html += f"""
        <div class="section">
            <div class="section-title">Training Load</div>
            <div class="metrics-grid">
                <div class="metric-row">
                    <div class="metric-label">CTL (FITNESS)</div>
                    <div class="metric-value">{pmc.get('ctl', '—')}</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">ATL (FATIGUE)</div>
                    <div class="metric-value">{pmc.get('atl', '—')}</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">TSB (FORM)</div>
                    <div class="metric-value">{pmc.get('tsb', '—')}</div>
                </div>
            </div>
        </div>
"""

    html += f"""
        <div class="recommendation-box">
            <div class="recommendation-type">Today's Session</div>
            <div class="recommendation-text">{recommendation['type'].upper()}</div>
            <div class="options-list">
"""

    for example in recommendation["examples"]:
        html += f"                <span>{example}</span>\n"

    html += f"""
            </div>
        </div>
"""

    # Add blindspot prompts section if profile has blindspots
    if profile:
        blindspots = profile.get('inferred', {}).get('blindspots', [])
        if blindspots:
            # Get daily prompts
            daily_prompts = get_blindspot_prompts(profile, context='daily')
            # Get context-specific prompts based on recommendation
            if recommendation["color"] == "green":
                context_prompts = get_blindspot_prompts(profile, context='pre_ride')
            elif recommendation["color"] == "red":
                context_prompts = get_blindspot_prompts(profile, context='recovery')
            else:
                context_prompts = []

            all_prompts = list(set(daily_prompts + context_prompts))  # Dedupe

            if all_prompts:
                html += """
        <div class="section">
            <div class="section-title">Today's Reminders</div>
            <div style="font-size: 12px; line-height: 1.6;">
"""
                for prompt in all_prompts[:4]:  # Max 4 prompts
                    html += f"""                <div style="padding: 8px 12px; background: #f5f5f5; border-left: 3px solid #000; margin-bottom: 8px;">{prompt}</div>
"""
                html += """            </div>
        </div>
"""

            # Show adjusted thresholds if different from defaults
            adjustments = get_blindspot_adjustments(profile)
            if adjustments.key_session_threshold != 65:
                html += f"""
        <div class="section" style="background: #fffbeb; border-top: 2px solid #000;">
            <div class="section-title" style="color: #92400e;">Blindspot Adjustments Active</div>
            <div style="font-size: 11px; color: #78350f;">
                Key session threshold: {adjustments.key_session_threshold} (normally 65) •
                Max ramp: {adjustments.ramp_rate_max} TSS/day •
                Min rest: {adjustments.min_rest_days_per_week} days/week
            </div>
        </div>
"""

    html += """
        <div class="footer">
            ATHLETE OS — GRAVEL GOD COACHING
            <div class="footer-quote">"RESPOND TO YOUR BODY, NOT JUST THE PLAN"</div>
        </div>
    </div>
</body>
</html>
"""

    return html


def send_email(to_address: str, subject: str, text_body: str, html_body: str) -> bool:
    """Send email via Gmail SMTP."""
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        print("Error: Email credentials not configured")
        print("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables")
        print("\nTo get an App Password:")
        print("  1. Enable 2FA on your Google account")
        print("  2. Go to: https://myaccount.google.com/apppasswords")
        print("  3. Create a new app password for 'Mail'")
        return False

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_address

    # Attach both plain text and HTML versions
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


def main():
    parser = argparse.ArgumentParser(description="Generate and send daily coaching briefing")
    parser.add_argument("athlete_name", help="Athlete folder name (e.g., 'matti-rowe')")
    parser.add_argument("--email", action="store_true", help="Send briefing via email")
    parser.add_argument("--to", type=str, help="Recipient email address (default: uses GMAIL_ADDRESS)")
    parser.add_argument("--sync", action="store_true", help="Sync data before generating briefing")
    parser.add_argument("--calculate", action="store_true", help="Run readiness calculation before briefing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Check athlete exists
    athlete_path = get_athlete_path(args.athlete_name)
    if not athlete_path.exists():
        print(f"Error: Athlete '{args.athlete_name}' not found")
        sys.exit(1)

    # Optional: Run sync
    if args.sync:
        if args.verbose:
            print("Syncing data sources...")
        run_sync(args.athlete_name, args.verbose)

    # Optional: Run readiness calculation
    if args.calculate:
        if args.verbose:
            print("Calculating readiness...")
        run_readiness_calculation(args.athlete_name, args.verbose)

    # Load data
    state = load_state(args.athlete_name)

    try:
        profile = load_profile(args.athlete_name)
    except Exception:
        profile = None

    # Generate briefing
    text_briefing = generate_briefing(args.athlete_name, state, profile)
    html_briefing = generate_html_briefing(args.athlete_name, state, profile)

    if args.email:
        # Send via email
        to_address = args.to or os.environ.get("GMAIL_ADDRESS")
        if not to_address:
            print("Error: No recipient address. Use --to or set GMAIL_ADDRESS")
            sys.exit(1)

        now = datetime.now()
        subject = f"Daily Briefing - {now.strftime('%b %d')} - Readiness: {state.get('readiness', {}).get('score', 'N/A')}"

        if args.verbose:
            print(f"Sending briefing to {to_address}...")

        if send_email(to_address, subject, text_briefing, html_briefing):
            print(f"Briefing sent to {to_address}")
        else:
            print("Failed to send email")
            sys.exit(1)
    else:
        # Print to console
        print(text_briefing)


if __name__ == "__main__":
    main()
