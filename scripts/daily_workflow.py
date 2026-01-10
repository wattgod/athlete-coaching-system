#!/usr/bin/env python3
"""
Daily Workflow Orchestrator

Combines the morning survey and daily briefing into a single workflow.

Usage:
    # Send morning survey (run at 6am via cron)
    python3 scripts/daily_workflow.py matti-rowe --survey

    # Run full briefing after check-in (run manually after completing check-in)
    python3 scripts/daily_workflow.py matti-rowe --briefing

    # Interactive check-in + briefing (all in one)
    python3 scripts/daily_workflow.py matti-rowe --interactive

    # Full workflow: sync, calculate, email briefing
    python3 scripts/daily_workflow.py matti-rowe --briefing --sync --email

Cron Examples:
    # Send survey every morning at 6am
    0 6 * * * cd /path/to/athlete-coaching-system && python3 scripts/daily_workflow.py matti-rowe --survey --email

    # After check-in, run briefing (manual trigger)
    python3 scripts/daily_workflow.py matti-rowe --briefing --sync --email

Environment Variables:
    GMAIL_ADDRESS       - Sender Gmail address
    GMAIL_APP_PASSWORD  - Gmail App Password
    INTERVALS_API_KEY   - Intervals.icu API key (optional, for sync)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_scripts_dir() -> Path:
    """Get the scripts directory."""
    return Path(__file__).parent


def run_script(script_name: str, args: list, verbose: bool = False) -> bool:
    """Run a script and return success status."""
    script_path = get_scripts_dir() / script_name

    if not script_path.exists():
        if verbose:
            print(f"Script not found: {script_path}")
        return False

    cmd = ["python3", str(script_path)] + args

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=not verbose, text=True, timeout=120)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"Timeout running {script_name}")
        return False
    except Exception as e:
        print(f"Error running {script_name}: {e}")
        return False


def send_survey(athlete_name: str, email: bool = False, to: str = None, verbose: bool = False) -> bool:
    """Send the morning survey."""
    args = [athlete_name]
    if email:
        args.append("--email")
        if to:
            args.extend(["--to", to])

    return run_script("morning_survey_email.py", args, verbose)


def run_check_in(athlete_name: str, verbose: bool = False) -> bool:
    """Run interactive check-in."""
    args = [athlete_name]
    # For interactive mode, we need to pass through stdin/stdout
    script_path = get_scripts_dir() / "morning_check_in.py"

    try:
        result = subprocess.run(["python3", str(script_path), athlete_name], timeout=300)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running check-in: {e}")
        return False


def run_sync(athlete_name: str, verbose: bool = False) -> bool:
    """Run data sync."""
    success = True

    # Intervals.icu sync
    result = run_script("intervals_sync.py", ["--sync-state", "--athlete-name", athlete_name], verbose)
    if verbose:
        print(f"Intervals sync: {'OK' if result else 'SKIPPED/FAILED'}")

    # WHOOP sync
    result = run_script("whoop_sync.py", ["--athlete-name", athlete_name], verbose)
    if verbose:
        print(f"WHOOP sync: {'OK' if result else 'SKIPPED/FAILED'}")

    return True  # Don't fail if syncs fail - they're optional


def run_readiness(athlete_name: str, verbose: bool = False) -> bool:
    """Run readiness calculation."""
    return run_script("calculate_readiness.py", [athlete_name], verbose)


def run_briefing(athlete_name: str, email: bool = False, to: str = None, verbose: bool = False) -> bool:
    """Run daily briefing."""
    args = [athlete_name]
    if email:
        args.append("--email")
        if to:
            args.extend(["--to", to])

    return run_script("daily_briefing.py", args, verbose)


def main():
    parser = argparse.ArgumentParser(description="Daily workflow orchestrator")
    parser.add_argument("athlete_name", help="Athlete folder name")

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--survey", action="store_true", help="Send morning survey only")
    mode_group.add_argument("--briefing", action="store_true", help="Run full briefing (sync + calculate + send)")
    mode_group.add_argument("--interactive", action="store_true", help="Interactive check-in + briefing")

    # Options
    parser.add_argument("--email", action="store_true", help="Send results via email")
    parser.add_argument("--to", type=str, help="Email recipient")
    parser.add_argument("--sync", action="store_true", help="Sync data sources before briefing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Verify athlete exists
    athlete_path = Path(__file__).parent.parent / "athletes" / args.athlete_name
    if not athlete_path.exists():
        print(f"Error: Athlete '{args.athlete_name}' not found")
        sys.exit(1)

    # Execute workflow
    if args.survey:
        # Morning survey mode
        print("Sending morning survey...")
        if send_survey(args.athlete_name, args.email, args.to, args.verbose):
            print("Survey sent successfully")
        else:
            print("Failed to send survey")
            sys.exit(1)

    elif args.briefing:
        # Full briefing mode
        print("Running daily briefing workflow...")

        if args.sync:
            print("\n1. Syncing data sources...")
            run_sync(args.athlete_name, args.verbose)

        print("\n2. Calculating readiness...")
        if not run_readiness(args.athlete_name, args.verbose):
            print("Warning: Readiness calculation failed, continuing with existing data")

        print("\n3. Generating briefing...")
        if run_briefing(args.athlete_name, args.email, args.to, args.verbose):
            if args.email:
                print("\nBriefing sent successfully")
            else:
                print("\nBriefing generated (use --email to send)")
        else:
            print("Failed to generate briefing")
            sys.exit(1)

    elif args.interactive:
        # Interactive mode: check-in + briefing
        print("Starting interactive daily workflow...")

        print("\n1. Morning check-in...")
        if not run_check_in(args.athlete_name, args.verbose):
            print("Check-in cancelled or failed")
            sys.exit(1)

        if args.sync:
            print("\n2. Syncing data sources...")
            run_sync(args.athlete_name, args.verbose)

        print("\n3. Calculating readiness...")
        run_readiness(args.athlete_name, args.verbose)

        print("\n4. Generating briefing...")
        run_briefing(args.athlete_name, args.email, args.to, args.verbose)

        print("\nWorkflow complete!")

    else:
        # No mode specified - show help
        print("Daily Workflow Options:")
        print("")
        print("  Morning (6am cron):")
        print(f"    python3 scripts/daily_workflow.py {args.athlete_name} --survey --email")
        print("")
        print("  After check-in:")
        print(f"    python3 scripts/daily_workflow.py {args.athlete_name} --briefing --sync --email")
        print("")
        print("  All-in-one interactive:")
        print(f"    python3 scripts/daily_workflow.py {args.athlete_name} --interactive --sync --email")


if __name__ == "__main__":
    main()
