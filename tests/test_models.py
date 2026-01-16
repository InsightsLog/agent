"""Tests for the models module."""

import pytest
from datetime import datetime

from src.macroeconomic_agent.models import (
    NewsItem,
    EconomicIndicator,
    SentimentBriefing,
    UpcomingRelease,
    ImpactLevel,
    Sentiment,
)


class TestNewsItem:
    """Tests for NewsItem model."""

    def test_create_news_item(self):
        """Test creating a basic news item."""
        item = NewsItem(
            id="test123",
            title="Test Headline",
            content="Test content here.",
            source="TestSource",
            published_at=datetime(2024, 1, 15, 10, 0, 0),
        )
        assert item.id == "test123"
        assert item.title == "Test Headline"
        assert item.impact_level == ImpactLevel.MEDIUM  # Default
        assert item.is_noise is False  # Default
        assert item.sentiment == Sentiment.NEUTRAL  # Default

    def test_news_item_with_all_fields(self):
        """Test creating a news item with all fields."""
        item = NewsItem(
            id="test456",
            title="High Impact News",
            content="Important economic data.",
            source="EconomicCalendar",
            url="https://example.com/news",
            published_at=datetime(2024, 1, 15, 10, 0, 0),
            impact_level=ImpactLevel.HIGH,
            is_noise=False,
            is_manipulation=True,
            raw_sentiment_score=0.75,
            sentiment=Sentiment.BULLISH,
        )
        assert item.impact_level == ImpactLevel.HIGH
        assert item.is_manipulation is True
        assert item.raw_sentiment_score == 0.75
        assert item.sentiment == Sentiment.BULLISH


class TestEconomicIndicator:
    """Tests for EconomicIndicator model."""

    def test_create_indicator(self):
        """Test creating an economic indicator."""
        indicator = EconomicIndicator(
            id="nfp_2024_01",
            name="Non-Farm Payrolls",
            country="US",
            release_time=datetime(2024, 1, 15, 13, 30, 0),
            impact_level=ImpactLevel.HIGH,
        )
        assert indicator.name == "Non-Farm Payrolls"
        assert indicator.country == "US"
        assert indicator.impact_level == ImpactLevel.HIGH
        assert indicator.actual_value is None  # Optional

    def test_indicator_with_values(self):
        """Test creating an indicator with all values."""
        indicator = EconomicIndicator(
            id="cpi_2024_01",
            name="Consumer Price Index",
            country="US",
            release_time=datetime(2024, 1, 15, 13, 30, 0),
            impact_level=ImpactLevel.HIGH,
            previous_value="3.2%",
            forecast_value="3.0%",
            actual_value="2.9%",
        )
        assert indicator.previous_value == "3.2%"
        assert indicator.forecast_value == "3.0%"
        assert indicator.actual_value == "2.9%"


class TestSentimentBriefing:
    """Tests for SentimentBriefing model."""

    def test_create_briefing(self):
        """Test creating a sentiment briefing."""
        briefing = SentimentBriefing(
            id="brief_2024_01_15",
            briefing_type="daily",
            title="Daily Macro Briefing",
            summary="Market sentiment is neutral.",
            overall_sentiment=Sentiment.NEUTRAL,
        )
        assert briefing.id == "brief_2024_01_15"
        assert briefing.briefing_type == "daily"
        assert briefing.overall_sentiment == Sentiment.NEUTRAL
        assert briefing.sent is False  # Default
        assert briefing.key_points == []  # Default empty list

    def test_briefing_with_items(self):
        """Test creating a briefing with news items."""
        news_item = NewsItem(
            id="item1",
            title="Test News",
            content="Content",
            source="Test",
            published_at=datetime.utcnow(),
        )
        indicator = EconomicIndicator(
            id="ind1",
            name="Test Indicator",
            country="US",
            release_time=datetime.utcnow(),
            impact_level=ImpactLevel.MEDIUM,
        )

        briefing = SentimentBriefing(
            id="brief123",
            briefing_type="high_impact",
            title="High Impact Alert",
            summary="Important release.",
            overall_sentiment=Sentiment.BULLISH,
            key_points=["Point 1", "Point 2"],
            news_items=[news_item],
            indicators=[indicator],
            content_hash="abc123",
        )

        assert len(briefing.news_items) == 1
        assert len(briefing.indicators) == 1
        assert len(briefing.key_points) == 2
        assert briefing.content_hash == "abc123"


class TestUpcomingRelease:
    """Tests for UpcomingRelease model."""

    def test_create_upcoming_release(self):
        """Test creating an upcoming release."""
        indicator = EconomicIndicator(
            id="ind1",
            name="GDP",
            country="US",
            release_time=datetime(2024, 1, 20, 13, 30, 0),
            impact_level=ImpactLevel.HIGH,
        )
        release = UpcomingRelease(indicator=indicator)

        assert release.indicator.name == "GDP"
        assert release.notified is False  # Default


class TestEnums:
    """Tests for enum types."""

    def test_impact_level_values(self):
        """Test ImpactLevel enum values."""
        assert ImpactLevel.LOW.value == "low"
        assert ImpactLevel.MEDIUM.value == "medium"
        assert ImpactLevel.HIGH.value == "high"

    def test_sentiment_values(self):
        """Test Sentiment enum values."""
        assert Sentiment.BULLISH.value == "bullish"
        assert Sentiment.BEARISH.value == "bearish"
        assert Sentiment.NEUTRAL.value == "neutral"
