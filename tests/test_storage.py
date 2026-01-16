"""Tests for the storage module."""

import os
import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from src.macroeconomic_agent.memory.storage import BriefingStorage
from src.macroeconomic_agent.models import (
    SentimentBriefing,
    EconomicIndicator,
    UpcomingRelease,
    Sentiment,
    ImpactLevel,
)


@pytest_asyncio.fixture
async def storage(tmp_path):
    """Create a storage instance with a temporary database."""
    db_path = os.path.join(tmp_path, "test_briefings.db")
    storage = BriefingStorage(db_path)
    await storage.initialize()
    yield storage
    await storage.close()


@pytest.fixture
def sample_briefing():
    """Create a sample briefing."""
    return SentimentBriefing(
        id="briefing123",
        created_at=datetime.utcnow(),
        briefing_type="daily",
        title="Test Daily Briefing",
        summary="This is a test summary.",
        overall_sentiment=Sentiment.BULLISH,
        key_points=["Point 1", "Point 2", "Point 3"],
        content_hash="abc123",
    )


@pytest.fixture
def sample_indicator():
    """Create a sample economic indicator."""
    return EconomicIndicator(
        id="indicator123",
        name="Non-Farm Payrolls",
        country="US",
        release_time=datetime.utcnow() + timedelta(days=1),
        impact_level=ImpactLevel.HIGH,
        forecast_value="175K",
        previous_value="150K",
    )


class TestBriefingStorage:
    """Tests for BriefingStorage class."""

    @pytest.mark.asyncio
    async def test_save_and_get_briefing(self, storage, sample_briefing):
        """Test saving and retrieving a briefing."""
        await storage.save_briefing(sample_briefing)
        retrieved = await storage.get_briefing(sample_briefing.id)

        assert retrieved is not None
        assert retrieved.id == sample_briefing.id
        assert retrieved.title == sample_briefing.title
        assert retrieved.overall_sentiment == sample_briefing.overall_sentiment

    @pytest.mark.asyncio
    async def test_get_nonexistent_briefing(self, storage):
        """Test retrieving a non-existent briefing."""
        retrieved = await storage.get_briefing("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_recent_briefings(self, storage, sample_briefing):
        """Test getting recent briefings."""
        await storage.save_briefing(sample_briefing)

        recent = await storage.get_recent_briefings(limit=10)
        assert len(recent) == 1
        assert recent[0].id == sample_briefing.id

    @pytest.mark.asyncio
    async def test_get_recent_briefings_by_type(self, storage, sample_briefing):
        """Test getting recent briefings filtered by type."""
        # Save a daily briefing
        await storage.save_briefing(sample_briefing)

        # Save a high_impact briefing
        high_impact = sample_briefing.model_copy(
            update={"id": "briefing456", "briefing_type": "high_impact"}
        )
        await storage.save_briefing(high_impact)

        # Get only daily briefings
        daily = await storage.get_recent_briefings(limit=10, briefing_type="daily")
        assert len(daily) == 1
        assert daily[0].briefing_type == "daily"

    @pytest.mark.asyncio
    async def test_is_duplicate_true(self, storage, sample_briefing):
        """Test duplicate detection when duplicate exists."""
        sample_briefing.sent = True
        await storage.save_briefing(sample_briefing)
        await storage.mark_briefing_sent(sample_briefing.id)

        is_dup = await storage.is_duplicate(sample_briefing.content_hash)
        assert is_dup is True

    @pytest.mark.asyncio
    async def test_is_duplicate_false(self, storage):
        """Test duplicate detection when no duplicate exists."""
        is_dup = await storage.is_duplicate("unique_hash_123")
        assert is_dup is False

    @pytest.mark.asyncio
    async def test_can_send_notification_first_time(self, storage):
        """Test notification rate limiting on first notification."""
        can_send = await storage.can_send_notification(min_interval_minutes=30)
        assert can_send is True

    @pytest.mark.asyncio
    async def test_can_send_notification_rate_limited(self, storage, sample_briefing):
        """Test notification rate limiting when recently sent."""
        await storage.save_briefing(sample_briefing)
        await storage.mark_briefing_sent(sample_briefing.id)

        can_send = await storage.can_send_notification(min_interval_minutes=30)
        assert can_send is False

    @pytest.mark.asyncio
    async def test_save_and_get_upcoming_release(self, storage, sample_indicator):
        """Test saving and retrieving upcoming releases."""
        release = UpcomingRelease(indicator=sample_indicator)
        await storage.save_upcoming_release(release)

        releases = await storage.get_upcoming_releases(hours_ahead=48)
        assert len(releases) == 1
        assert releases[0].indicator.id == sample_indicator.id

    @pytest.mark.asyncio
    async def test_get_high_impact_releases_only(self, storage, sample_indicator):
        """Test filtering for high-impact releases only."""
        # Save high impact
        high_release = UpcomingRelease(indicator=sample_indicator)
        await storage.save_upcoming_release(high_release)

        # Save low impact
        low_indicator = sample_indicator.model_copy(
            update={"id": "low123", "impact_level": ImpactLevel.LOW}
        )
        low_release = UpcomingRelease(indicator=low_indicator)
        await storage.save_upcoming_release(low_release)

        # Get only high impact
        releases = await storage.get_upcoming_releases(
            hours_ahead=48, high_impact_only=True
        )
        assert len(releases) == 1
        assert releases[0].indicator.impact_level == ImpactLevel.HIGH

    @pytest.mark.asyncio
    async def test_mark_release_notified(self, storage, sample_indicator):
        """Test marking a release as notified."""
        release = UpcomingRelease(indicator=sample_indicator)
        await storage.save_upcoming_release(release)
        await storage.mark_release_notified(sample_indicator.id)

        # Re-fetch to verify
        # Note: We can't directly test this without raw SQL query, but we verify no errors

    @pytest.mark.asyncio
    async def test_log_notification(self, storage, sample_briefing):
        """Test logging a notification."""
        await storage.save_briefing(sample_briefing)
        await storage.log_notification(
            sample_briefing.id, "email", success=True
        )
        # Verify no errors - actual log can be checked via raw SQL if needed

    @pytest.mark.asyncio
    async def test_log_notification_with_error(self, storage, sample_briefing):
        """Test logging a failed notification."""
        await storage.save_briefing(sample_briefing)
        await storage.log_notification(
            sample_briefing.id, "webhook", success=False, error_message="Connection timeout"
        )

    def test_compute_content_hash(self):
        """Test content hash computation."""
        hash1 = BriefingStorage.compute_content_hash("test content")
        hash2 = BriefingStorage.compute_content_hash("test content")
        hash3 = BriefingStorage.compute_content_hash("different content")

        assert hash1 == hash2  # Same content, same hash
        assert hash1 != hash3  # Different content, different hash
        assert len(hash1) == 64  # SHA256 hex length
