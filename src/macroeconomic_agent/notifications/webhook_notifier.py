"""Webhook notification implementation (Discord, Slack, etc.)."""

import aiohttp

from .notifier import Notifier
from ..models import SentimentBriefing


class WebhookNotifier(Notifier):
    """Send briefings via webhook (Discord, Slack, custom)."""

    def __init__(self, webhook_url: str, webhook_type: str = "discord"):
        """Initialize webhook notifier.

        Args:
            webhook_url: The webhook URL to POST to.
            webhook_type: Type of webhook (discord, slack, generic).
        """
        self._webhook_url = webhook_url
        self._webhook_type = webhook_type
        self._session: aiohttp.ClientSession | None = None

    @property
    def channel_name(self) -> str:
        """Return the name of this notification channel."""
        return f"webhook:{self._webhook_type}"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(self, briefing: SentimentBriefing) -> bool:
        """Send a briefing via webhook.

        Args:
            briefing: The briefing to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        session = await self._get_session()

        try:
            if self._webhook_type == "discord":
                payload = self._format_discord(briefing)
            elif self._webhook_type == "slack":
                payload = self._format_slack(briefing)
            else:
                payload = self._format_generic(briefing)

            async with session.post(
                self._webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                return resp.status in (200, 204)

        except Exception:
            return False

    def _format_discord(self, briefing: SentimentBriefing) -> dict:
        """Format briefing for Discord webhook.

        Args:
            briefing: The briefing to format.

        Returns:
            Discord webhook payload.
        """
        sentiment_colors = {
            "bullish": 0x22C55E,  # Green
            "bearish": 0xEF4444,  # Red
            "neutral": 0x6B7280,  # Gray
        }

        sentiment_emojis = {
            "bullish": "🟢",
            "bearish": "🔴",
            "neutral": "⚪",
        }

        color = sentiment_colors.get(briefing.overall_sentiment.value, 0x6B7280)
        emoji = sentiment_emojis.get(briefing.overall_sentiment.value, "⚪")

        # Build key points field
        key_points_text = "\n".join(f"• {point}" for point in briefing.key_points[:5])

        fields = [
            {
                "name": "📊 Overall Sentiment",
                "value": f"{emoji} **{briefing.overall_sentiment.value.upper()}**",
                "inline": True,
            },
            {
                "name": "📝 Key Points",
                "value": key_points_text or "No key points",
                "inline": False,
            },
        ]

        # Add upcoming releases if any
        if briefing.indicators:
            releases_text = "\n".join(
                f"• **{ind.country} {ind.name}** - "
                f"{ind.release_time.strftime('%m/%d %H:%M UTC')}"
                for ind in briefing.indicators[:3]
            )
            fields.append(
                {
                    "name": "📅 Upcoming High-Impact Releases",
                    "value": releases_text,
                    "inline": False,
                }
            )

        return {
            "embeds": [
                {
                    "title": briefing.title,
                    "description": briefing.summary,
                    "color": color,
                    "fields": fields,
                    "footer": {
                        "text": f"Generated at {briefing.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
                    },
                }
            ]
        }

    def _format_slack(self, briefing: SentimentBriefing) -> dict:
        """Format briefing for Slack webhook.

        Args:
            briefing: The briefing to format.

        Returns:
            Slack webhook payload.
        """
        sentiment_emojis = {
            "bullish": ":large_green_circle:",
            "bearish": ":red_circle:",
            "neutral": ":white_circle:",
        }

        emoji = sentiment_emojis.get(briefing.overall_sentiment.value, ":white_circle:")

        key_points_text = "\n".join(f"• {point}" for point in briefing.key_points[:5])

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": briefing.title, "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": briefing.summary},
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Sentiment:* {emoji} {briefing.overall_sentiment.value.upper()}",
                    }
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Key Points:*\n{key_points_text}"},
            },
        ]

        if briefing.indicators:
            releases_text = "\n".join(
                f"• *{ind.country} {ind.name}* - "
                f"{ind.release_time.strftime('%m/%d %H:%M UTC')}"
                for ind in briefing.indicators[:3]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Upcoming High-Impact Releases:*\n{releases_text}",
                    },
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Generated at {briefing.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
                    }
                ],
            }
        )

        return {"blocks": blocks}

    def _format_generic(self, briefing: SentimentBriefing) -> dict:
        """Format briefing for generic webhook.

        Args:
            briefing: The briefing to format.

        Returns:
            Generic webhook payload.
        """
        return {
            "id": briefing.id,
            "title": briefing.title,
            "summary": briefing.summary,
            "sentiment": briefing.overall_sentiment.value,
            "key_points": briefing.key_points,
            "indicators": [ind.model_dump(mode="json") for ind in briefing.indicators],
            "created_at": briefing.created_at.isoformat(),
        }

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
