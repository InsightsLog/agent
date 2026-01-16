"""Configuration settings for the Macroeconomic News Release Analyst Agent."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_path: str = Field(default="data/briefings.db", description="Path to SQLite database")

    # Notification settings
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    email_host: str = Field(default="smtp.gmail.com", description="SMTP server host")
    email_port: int = Field(default=587, description="SMTP server port")
    email_username: Optional[str] = Field(default=None, description="SMTP username")
    email_password: Optional[str] = Field(default=None, description="SMTP password")
    email_from: Optional[str] = Field(default=None, description="From email address")
    email_to: Optional[str] = Field(default=None, description="To email address")

    webhook_enabled: bool = Field(default=False, description="Enable webhook notifications")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL (e.g., Discord)")

    # Scheduling
    daily_briefing_time: str = Field(default="08:00", description="Time for daily briefing (HH:MM)")
    min_notification_interval_minutes: int = Field(
        default=30, description="Minimum minutes between notifications"
    )

    # Analysis settings
    sentiment_threshold: float = Field(
        default=0.1, description="Minimum sentiment score to consider significant"
    )
    noise_filter_keywords: str = Field(
        default="rumor,speculation,might,could,possibly,unconfirmed",
        description="Comma-separated keywords to filter as noise",
    )
    manipulation_keywords: str = Field(
        default="guaranteed,certain,definitely,crash,moon,rocket,doom",
        description="Comma-separated keywords indicating emotional manipulation",
    )

    # Data sources
    rss_feeds: str = Field(
        default="",
        description="Comma-separated RSS feed URLs",
    )
    economic_calendar_api_key: Optional[str] = Field(
        default=None, description="API key for economic calendar"
    )

    class Config:
        """Pydantic config."""

        env_prefix = "MACRO_AGENT_"
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
