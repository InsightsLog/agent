"""Base notifier interface."""

from abc import ABC, abstractmethod

from ..models import SentimentBriefing


class Notifier(ABC):
    """Abstract base class for notification channels."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return the name of this notification channel."""
        pass

    @abstractmethod
    async def send(self, briefing: SentimentBriefing) -> bool:
        """Send a briefing notification.

        Args:
            briefing: The briefing to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass

    def format_briefing(self, briefing: SentimentBriefing) -> str:
        """Format a briefing for notification.

        Args:
            briefing: The briefing to format.

        Returns:
            Formatted string representation.
        """
        lines = [
            f"# {briefing.title}",
            "",
            f"**Sentiment: {briefing.overall_sentiment.value.upper()}**",
            "",
            briefing.summary,
            "",
            "## Key Points",
        ]

        for point in briefing.key_points:
            lines.append(f"• {point}")

        if briefing.indicators:
            lines.append("")
            lines.append("## Upcoming High-Impact Releases")
            for indicator in briefing.indicators:
                release_str = indicator.release_time.strftime("%Y-%m-%d %H:%M UTC")
                lines.append(f"• **{indicator.country} {indicator.name}** - {release_str}")
                if indicator.forecast_value:
                    lines.append(f"  Forecast: {indicator.forecast_value}")
                if indicator.previous_value:
                    lines.append(f"  Previous: {indicator.previous_value}")

        lines.append("")
        lines.append(f"_Generated: {briefing.created_at.strftime('%Y-%m-%d %H:%M UTC')}_")

        return "\n".join(lines)

    async def close(self) -> None:
        """Clean up any resources.

        Override if the notifier needs cleanup.
        """
        pass
