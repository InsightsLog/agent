"""Email notification implementation."""

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from .notifier import Notifier
from ..models import SentimentBriefing


class EmailNotifier(Notifier):
    """Send briefings via email."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addr: str,
    ):
        """Initialize email notifier.

        Args:
            host: SMTP server host.
            port: SMTP server port.
            username: SMTP username.
            password: SMTP password.
            from_addr: From email address.
            to_addr: To email address.
        """
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_addr = from_addr
        self._to_addr = to_addr

    @property
    def channel_name(self) -> str:
        """Return the name of this notification channel."""
        return "email"

    async def send(self, briefing: SentimentBriefing) -> bool:
        """Send a briefing via email.

        Args:
            briefing: The briefing to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = f"📊 {briefing.title}"
            message["From"] = self._from_addr
            message["To"] = self._to_addr

            # Plain text version
            text_content = self.format_briefing(briefing)
            text_part = MIMEText(text_content, "plain", "utf-8")
            message.attach(text_part)

            # HTML version
            html_content = self._format_html(briefing)
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            await aiosmtplib.send(
                message,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=True,
            )
            return True

        except Exception:
            # Log error
            return False

    def _format_html(self, briefing: SentimentBriefing) -> str:
        """Format briefing as HTML email.

        Args:
            briefing: The briefing to format.

        Returns:
            HTML formatted string.
        """
        sentiment_colors = {
            "bullish": "#22c55e",  # Green
            "bearish": "#ef4444",  # Red
            "neutral": "#6b7280",  # Gray
        }

        sentiment_color = sentiment_colors.get(briefing.overall_sentiment.value, "#6b7280")

        key_points_html = "".join(
            f"<li style='margin: 8px 0;'>{point}</li>" for point in briefing.key_points
        )

        indicators_html = ""
        if briefing.indicators:
            indicator_items = []
            for indicator in briefing.indicators:
                release_str = indicator.release_time.strftime("%Y-%m-%d %H:%M UTC")
                item = f"""
                <li style='margin: 8px 0;'>
                    <strong>{indicator.country} {indicator.name}</strong> - {release_str}
                """
                if indicator.forecast_value:
                    item += f"<br/>Forecast: {indicator.forecast_value}"
                if indicator.previous_value:
                    item += f" | Previous: {indicator.previous_value}"
                item += "</li>"
                indicator_items.append(item)
            indicators_html = f"""
            <h3 style='color: #374151; margin-top: 24px;'>Upcoming High-Impact Releases</h3>
            <ul style='padding-left: 20px;'>
                {''.join(indicator_items)}
            </ul>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style='font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #1f2937;
                     max-width: 600px; margin: 0 auto; padding: 20px;'>
            <h1 style='color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 12px;'>
                {briefing.title}
            </h1>

            <div style='background: {sentiment_color}; color: white; padding: 8px 16px;
                        border-radius: 6px; display: inline-block; font-weight: bold;
                        margin: 16px 0;'>
                Sentiment: {briefing.overall_sentiment.value.upper()}
            </div>

            <p style='font-size: 16px; color: #374151;'>{briefing.summary}</p>

            <h3 style='color: #374151; margin-top: 24px;'>Key Points</h3>
            <ul style='padding-left: 20px;'>
                {key_points_html}
            </ul>

            {indicators_html}

            <hr style='border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;'>
            <p style='font-size: 12px; color: #6b7280;'>
                Generated: {briefing.created_at.strftime('%Y-%m-%d %H:%M UTC')}
            </p>
        </body>
        </html>
        """
