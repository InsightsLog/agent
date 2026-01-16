"""Main agent module for the Macroeconomic News Release Analyst."""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .analyzer import SentimentAnalyzer
from .config import settings
from .data_sources import DataSource, RSSFeedSource, EconomicCalendarAPI
from .memory import BriefingStorage
from .models import (
    SentimentBriefing,
    NewsItem,
    EconomicIndicator,
    ImpactLevel,
    Sentiment,
    UpcomingRelease,
)
from .notifications import Notifier, EmailNotifier, WebhookNotifier


class MacroeconomicAgent:
    """Main agent class that orchestrates all components.

    The agent:
    1. Fetches news from multiple data sources
    2. Analyzes sentiment and filters noise/manipulation
    3. Generates briefings (daily or on high-impact releases)
    4. Stores briefings and prevents duplicate notifications
    5. Sends notifications via email or webhook
    """

    def __init__(
        self,
        data_sources: list[DataSource] | None = None,
        notifiers: list[Notifier] | None = None,
        storage: BriefingStorage | None = None,
        analyzer: SentimentAnalyzer | None = None,
    ):
        """Initialize the agent.

        Args:
            data_sources: List of data sources to fetch news from.
            notifiers: List of notification channels.
            storage: Storage backend for briefings.
            analyzer: Sentiment analyzer instance.
        """
        self._data_sources = data_sources or self._create_default_sources()
        self._notifiers = notifiers or self._create_default_notifiers()
        self._storage = storage or BriefingStorage(settings.database_path)
        self._analyzer = analyzer or SentimentAnalyzer()
        self._scheduler: AsyncIOScheduler | None = None
        self._running = False

    def _create_default_sources(self) -> list[DataSource]:
        """Create default data sources from settings."""
        sources: list[DataSource] = []

        # RSS feeds
        if settings.rss_feeds:
            feed_urls = [url.strip() for url in settings.rss_feeds.split(",") if url.strip()]
            if feed_urls:
                sources.append(RSSFeedSource(feed_urls, name="RSS"))

        # Economic calendar API
        sources.append(
            EconomicCalendarAPI(
                api_key=settings.economic_calendar_api_key,
                name="EconomicCalendar",
            )
        )

        return sources

    def _create_default_notifiers(self) -> list[Notifier]:
        """Create default notifiers from settings."""
        notifiers: list[Notifier] = []

        # Email notifier
        if (
            settings.email_enabled
            and settings.email_username
            and settings.email_password
            and settings.email_from
            and settings.email_to
        ):
            notifiers.append(
                EmailNotifier(
                    host=settings.email_host,
                    port=settings.email_port,
                    username=settings.email_username,
                    password=settings.email_password,
                    from_addr=settings.email_from,
                    to_addr=settings.email_to,
                )
            )

        # Webhook notifier
        if settings.webhook_enabled and settings.webhook_url:
            # Detect webhook type from URL
            webhook_type = "generic"
            if "discord" in settings.webhook_url.lower():
                webhook_type = "discord"
            elif "slack" in settings.webhook_url.lower():
                webhook_type = "slack"

            notifiers.append(WebhookNotifier(settings.webhook_url, webhook_type))

        return notifiers

    async def initialize(self) -> None:
        """Initialize the agent and its components."""
        await self._storage.initialize()

    async def fetch_all_news(self) -> list[NewsItem]:
        """Fetch news from all data sources.

        Returns:
            List of news items from all sources.
        """
        all_items: list[NewsItem] = []

        for source in self._data_sources:
            try:
                async for item in source.fetch_news():
                    # Process item through analyzer
                    processed_item = self._analyzer.process_item(item)
                    all_items.append(processed_item)
            except Exception:
                # Log and continue with other sources
                continue

        return all_items

    async def fetch_all_indicators(self) -> list[EconomicIndicator]:
        """Fetch economic indicators from all data sources.

        Returns:
            List of economic indicators.
        """
        all_indicators: list[EconomicIndicator] = []

        for source in self._data_sources:
            try:
                async for indicator in source.fetch_indicators():
                    all_indicators.append(indicator)
            except Exception:
                continue

        return all_indicators

    async def update_release_schedule(self) -> None:
        """Update the schedule of upcoming economic releases."""
        indicators = await self.fetch_all_indicators()

        for indicator in indicators:
            if indicator.release_time > datetime.utcnow():
                release = UpcomingRelease(indicator=indicator)
                await self._storage.save_upcoming_release(release)

    def _generate_key_points(self, news_items: list[NewsItem]) -> list[str]:
        """Generate key points from news items.

        Args:
            news_items: Processed news items.

        Returns:
            List of key bullet points.
        """
        # Filter to valid, non-noise, non-manipulation items
        valid_items = [
            item
            for item in news_items
            if not item.is_noise and not item.is_manipulation
        ]

        # Sort by impact and recency
        valid_items.sort(
            key=lambda x: (
                {"high": 0, "medium": 1, "low": 2}[x.impact_level.value],
                -x.published_at.timestamp(),
            )
        )

        # Take top items and create key points
        key_points = []
        for item in valid_items[:5]:
            # Truncate long titles
            title = item.title[:100] + "..." if len(item.title) > 100 else item.title
            key_points.append(title)

        return key_points

    def _generate_summary(
        self, news_items: list[NewsItem], overall_sentiment: Sentiment
    ) -> str:
        """Generate an executive summary.

        Args:
            news_items: Processed news items.
            overall_sentiment: The overall sentiment.

        Returns:
            Executive summary string.
        """
        valid_count = sum(
            1 for item in news_items if not item.is_noise and not item.is_manipulation
        )
        noise_count = sum(1 for item in news_items if item.is_noise)
        manipulation_count = sum(1 for item in news_items if item.is_manipulation)

        sentiment_descriptions = {
            Sentiment.BULLISH: "bullish with positive market sentiment",
            Sentiment.BEARISH: "bearish with cautious market sentiment",
            Sentiment.NEUTRAL: "neutral with mixed market signals",
        }

        summary_parts = [
            f"Market sentiment is {sentiment_descriptions[overall_sentiment]}.",
            f"Analyzed {valid_count} relevant news items.",
        ]

        if noise_count > 0:
            summary_parts.append(f"Filtered {noise_count} low-impact noise items.")

        if manipulation_count > 0:
            summary_parts.append(
                f"Flagged {manipulation_count} items for potential manipulation."
            )

        return " ".join(summary_parts)

    async def generate_briefing(
        self,
        briefing_type: str = "daily",
        trigger_indicator: EconomicIndicator | None = None,
    ) -> SentimentBriefing:
        """Generate a sentiment briefing.

        Args:
            briefing_type: Type of briefing ('daily' or 'high_impact').
            trigger_indicator: The indicator that triggered this briefing (if any).

        Returns:
            The generated briefing.
        """
        # Fetch and analyze news
        news_items = await self.fetch_all_news()

        # Aggregate sentiment
        avg_score, overall_sentiment = self._analyzer.aggregate_sentiment(news_items)

        # Get upcoming high-impact releases
        upcoming_releases = await self._storage.get_upcoming_releases(
            hours_ahead=168, high_impact_only=True
        )
        indicators = [r.indicator for r in upcoming_releases]

        # If this is a high-impact briefing, add the trigger indicator
        if trigger_indicator:
            indicators = [trigger_indicator] + [
                i for i in indicators if i.id != trigger_indicator.id
            ]

        # Generate title
        if briefing_type == "daily":
            title = f"Daily Macro Briefing - {datetime.utcnow().strftime('%Y-%m-%d')}"
        else:
            indicator_name = trigger_indicator.name if trigger_indicator else "Economic"
            title = f"High-Impact Alert: {indicator_name}"

        # Generate content
        key_points = self._generate_key_points(news_items)
        summary = self._generate_summary(news_items, overall_sentiment)

        # Compute content hash for duplicate detection
        hash_content = f"{overall_sentiment.value}:{':'.join(key_points)}"
        content_hash = hashlib.sha256(hash_content.encode()).hexdigest()

        briefing = SentimentBriefing(
            id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            briefing_type=briefing_type,
            title=title,
            summary=summary,
            overall_sentiment=overall_sentiment,
            key_points=key_points,
            news_items=news_items[:10],  # Include top 10 items
            indicators=indicators[:5],  # Include top 5 indicators
            content_hash=content_hash,
        )

        # Save to storage
        await self._storage.save_briefing(briefing)

        return briefing

    async def send_briefing(self, briefing: SentimentBriefing) -> bool:
        """Send a briefing through all notification channels.

        Checks for duplicate content and rate limiting before sending.

        Args:
            briefing: The briefing to send.

        Returns:
            True if sent successfully through at least one channel.
        """
        # Check for duplicate content
        if await self._storage.is_duplicate(briefing.content_hash):
            return False

        # Check rate limiting
        if not await self._storage.can_send_notification(
            settings.min_notification_interval_minutes
        ):
            return False

        # Send through all channels
        sent = False
        for notifier in self._notifiers:
            try:
                success = await notifier.send(briefing)
                await self._storage.log_notification(
                    briefing.id, notifier.channel_name, success
                )
                if success:
                    sent = True
            except Exception as e:
                await self._storage.log_notification(
                    briefing.id, notifier.channel_name, False, str(e)
                )

        if sent:
            await self._storage.mark_briefing_sent(briefing.id)

        return sent

    async def run_daily_briefing(self) -> Optional[SentimentBriefing]:
        """Generate and send the daily briefing.

        Returns:
            The generated briefing, or None if not sent.
        """
        briefing = await self.generate_briefing(briefing_type="daily")
        await self.send_briefing(briefing)
        return briefing

    async def check_high_impact_releases(self) -> list[SentimentBriefing]:
        """Check for high-impact releases and generate briefings.

        Returns:
            List of briefings generated.
        """
        # Update schedule first
        await self.update_release_schedule()

        briefings = []

        # Get releases in the next hour
        upcoming = await self._storage.get_upcoming_releases(
            hours_ahead=1, high_impact_only=True
        )

        for release in upcoming:
            if not release.notified:
                # Generate high-impact briefing
                briefing = await self.generate_briefing(
                    briefing_type="high_impact",
                    trigger_indicator=release.indicator,
                )
                await self.send_briefing(briefing)
                await self._storage.mark_release_notified(release.indicator.id)
                briefings.append(briefing)

        return briefings

    def start_scheduler(self) -> None:
        """Start the background scheduler for periodic tasks."""
        if self._scheduler is not None:
            return

        self._scheduler = AsyncIOScheduler()

        # Daily briefing
        hour, minute = settings.daily_briefing_time.split(":")
        self._scheduler.add_job(
            self.run_daily_briefing,
            CronTrigger(hour=int(hour), minute=int(minute)),
            id="daily_briefing",
        )

        # Check for high-impact releases every 15 minutes
        self._scheduler.add_job(
            self.check_high_impact_releases,
            "interval",
            minutes=15,
            id="high_impact_check",
        )

        self._scheduler.start()
        self._running = True

    def stop_scheduler(self) -> None:
        """Stop the background scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown()
            self._scheduler = None
            self._running = False

    async def close(self) -> None:
        """Clean up all resources."""
        self.stop_scheduler()

        # Close data sources
        for source in self._data_sources:
            await source.close()

        # Close notifiers
        for notifier in self._notifiers:
            await notifier.close()

        # Close storage
        await self._storage.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


async def main():
    """Main entry point for running the agent."""
    async with MacroeconomicAgent() as agent:
        # Run an initial briefing
        print("Generating initial briefing...")
        briefing = await agent.run_daily_briefing()
        print(f"Generated: {briefing.title}")
        print(f"Sentiment: {briefing.overall_sentiment.value}")
        print(f"Summary: {briefing.summary}")
        print("\nKey Points:")
        for point in briefing.key_points:
            print(f"  • {point}")

        # Start scheduler for continuous operation
        print("\nStarting scheduler...")
        agent.start_scheduler()

        # Run until interrupted
        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    asyncio.run(main())
