"""Command-line interface for the Macroeconomic News Release Analyst Agent."""

import argparse
import asyncio
import sys

from .agent import MacroeconomicAgent


async def run_briefing(agent: MacroeconomicAgent, briefing_type: str = "daily") -> None:
    """Generate and display a briefing.

    Args:
        agent: The agent instance.
        briefing_type: Type of briefing to generate.
    """
    print(f"\n{'=' * 60}")
    print(f"Generating {briefing_type} briefing...")
    print("=" * 60)

    briefing = await agent.generate_briefing(briefing_type=briefing_type)

    print(f"\n📊 {briefing.title}")
    print(f"\n🎯 Sentiment: {briefing.overall_sentiment.value.upper()}")
    print(f"\n📝 Summary:\n{briefing.summary}")

    if briefing.key_points:
        print("\n🔑 Key Points:")
        for point in briefing.key_points:
            print(f"  • {point}")

    if briefing.indicators:
        print("\n📅 Upcoming High-Impact Releases:")
        for indicator in briefing.indicators:
            release_str = indicator.release_time.strftime("%Y-%m-%d %H:%M UTC")
            print(f"  • {indicator.country} {indicator.name} - {release_str}")
            if indicator.forecast_value:
                print(f"    Forecast: {indicator.forecast_value}")

    print(f"\n{'=' * 60}\n")

    return briefing


async def run_continuous(agent: MacroeconomicAgent) -> None:
    """Run the agent continuously with scheduler.

    Args:
        agent: The agent instance.
    """
    print("\n🚀 Starting Macroeconomic News Release Analyst Agent")
    print("=" * 60)
    print("The agent will:")
    print("  • Generate daily briefings at the configured time")
    print("  • Check for high-impact releases every 15 minutes")
    print("  • Send notifications via configured channels")
    print("\nPress Ctrl+C to stop.")
    print("=" * 60)

    agent.start_scheduler()

    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n⏹️  Shutting down agent...")


async def async_main(args: argparse.Namespace) -> int:
    """Async main entry point.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    async with MacroeconomicAgent() as agent:
        if args.command == "briefing":
            await run_briefing(agent, args.type)
            if args.send:
                print("Sending briefing...")
                briefing = await agent.generate_briefing(briefing_type=args.type)
                sent = await agent.send_briefing(briefing)
                if sent:
                    print("✅ Briefing sent successfully!")
                else:
                    print("❌ Failed to send briefing (may be duplicate or rate-limited)")

        elif args.command == "schedule":
            print("\n📅 Upcoming Economic Releases:")
            print("-" * 40)
            releases = await agent._storage.get_upcoming_releases(
                hours_ahead=args.hours, high_impact_only=args.high_impact_only
            )
            if not releases:
                print("No upcoming releases found.")
            else:
                for release in releases:
                    indicator = release.indicator
                    release_str = indicator.release_time.strftime("%Y-%m-%d %H:%M UTC")
                    impact = indicator.impact_level.value.upper()
                    print(f"  [{impact}] {indicator.country} {indicator.name}")
                    print(f"         Release: {release_str}")
                    if indicator.forecast_value:
                        print(f"         Forecast: {indicator.forecast_value}")
                    print()

        elif args.command == "run":
            await run_continuous(agent)

        else:
            # Default: run a single briefing
            await run_briefing(agent)

    return 0


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        description="Macroeconomic News Release Analyst Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  macro-agent briefing              Generate a daily briefing
  macro-agent briefing --type high_impact --send
                                    Generate and send a high-impact briefing
  macro-agent schedule --hours 72   Show releases in next 72 hours
  macro-agent run                   Run continuously with scheduler
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Briefing command
    briefing_parser = subparsers.add_parser("briefing", help="Generate a briefing")
    briefing_parser.add_argument(
        "--type",
        choices=["daily", "high_impact"],
        default="daily",
        help="Type of briefing to generate",
    )
    briefing_parser.add_argument(
        "--send",
        action="store_true",
        help="Send the briefing via configured notification channels",
    )

    # Schedule command
    schedule_parser = subparsers.add_parser(
        "schedule", help="Show upcoming economic releases"
    )
    schedule_parser.add_argument(
        "--hours",
        type=int,
        default=168,
        help="Hours to look ahead (default: 168 = 7 days)",
    )
    schedule_parser.add_argument(
        "--high-impact-only",
        action="store_true",
        help="Only show high-impact releases",
    )

    # Run command
    subparsers.add_parser("run", help="Run the agent continuously")

    args = parser.parse_args()

    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
