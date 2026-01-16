"""Storage module for persisting briefings and preventing duplicates."""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from ..models import SentimentBriefing, EconomicIndicator, UpcomingRelease


class BriefingStorage:
    """SQLite-based storage for sentiment briefings and schedules.

    Provides:
    - Persistent storage for generated briefings
    - Reference to past briefings for context
    - Duplicate detection to prevent spam
    - Upcoming release schedule tracking
    """

    def __init__(self, db_path: str = "data/briefings.db"):
        """Initialize storage.

        Args:
            db_path: Path to SQLite database file.
        """
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Initialize the database and create tables if needed."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)

        self._connection = await aiosqlite.connect(self._db_path)
        await self._create_tables()

    async def _create_tables(self) -> None:
        """Create database tables."""
        assert self._connection is not None

        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS briefings (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                briefing_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                overall_sentiment TEXT NOT NULL,
                key_points TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                sent_at TEXT,
                full_data TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_briefings_created_at
                ON briefings(created_at);
            CREATE INDEX IF NOT EXISTS idx_briefings_content_hash
                ON briefings(content_hash);
            CREATE INDEX IF NOT EXISTS idx_briefings_type
                ON briefings(briefing_type);

            CREATE TABLE IF NOT EXISTS upcoming_releases (
                id TEXT PRIMARY KEY,
                indicator_name TEXT NOT NULL,
                country TEXT NOT NULL,
                release_time TEXT NOT NULL,
                impact_level TEXT NOT NULL,
                notified INTEGER DEFAULT 0,
                full_data TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_releases_time
                ON upcoming_releases(release_time);

            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                briefing_id TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                channel TEXT NOT NULL,
                success INTEGER NOT NULL,
                error_message TEXT
            );
        """
        )
        await self._connection.commit()

    async def save_briefing(self, briefing: SentimentBriefing) -> None:
        """Save a briefing to the database.

        Args:
            briefing: The briefing to save.
        """
        assert self._connection is not None

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO briefings
            (id, created_at, briefing_type, title, summary, overall_sentiment,
             key_points, content_hash, sent, sent_at, full_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                briefing.id,
                briefing.created_at.isoformat(),
                briefing.briefing_type,
                briefing.title,
                briefing.summary,
                briefing.overall_sentiment.value,
                json.dumps(briefing.key_points),
                briefing.content_hash,
                1 if briefing.sent else 0,
                briefing.sent_at.isoformat() if briefing.sent_at else None,
                briefing.model_dump_json(),
            ),
        )
        await self._connection.commit()

    async def get_briefing(self, briefing_id: str) -> Optional[SentimentBriefing]:
        """Retrieve a briefing by ID.

        Args:
            briefing_id: The briefing ID.

        Returns:
            The briefing if found, None otherwise.
        """
        assert self._connection is not None

        async with self._connection.execute(
            "SELECT full_data FROM briefings WHERE id = ?", (briefing_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return SentimentBriefing.model_validate_json(row[0])
        return None

    async def get_recent_briefings(
        self, limit: int = 10, briefing_type: str | None = None
    ) -> list[SentimentBriefing]:
        """Get recent briefings for context.

        Args:
            limit: Maximum number of briefings to return.
            briefing_type: Filter by type ('daily' or 'high_impact').

        Returns:
            List of recent briefings.
        """
        assert self._connection is not None

        if briefing_type:
            query = """
                SELECT full_data FROM briefings
                WHERE briefing_type = ?
                ORDER BY created_at DESC LIMIT ?
            """
            params = (briefing_type, limit)
        else:
            query = """
                SELECT full_data FROM briefings
                ORDER BY created_at DESC LIMIT ?
            """
            params = (limit,)

        briefings = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                briefings.append(SentimentBriefing.model_validate_json(row[0]))
        return briefings

    async def is_duplicate(
        self, content_hash: str, hours_lookback: int = 24
    ) -> bool:
        """Check if a briefing with similar content was recently sent.

        This prevents spamming the same story repeatedly.

        Args:
            content_hash: Hash of the briefing content.
            hours_lookback: Number of hours to look back.

        Returns:
            True if a similar briefing was recently sent.
        """
        assert self._connection is not None

        cutoff = (datetime.utcnow() - timedelta(hours=hours_lookback)).isoformat()

        async with self._connection.execute(
            """
            SELECT COUNT(*) FROM briefings
            WHERE content_hash = ? AND sent = 1 AND created_at > ?
        """,
            (content_hash, cutoff),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] > 0 if row else False

    async def get_last_notification_time(self) -> Optional[datetime]:
        """Get the timestamp of the last sent notification.

        Returns:
            Datetime of last notification, or None if no notifications sent.
        """
        assert self._connection is not None

        async with self._connection.execute(
            """
            SELECT sent_at FROM briefings
            WHERE sent = 1 AND sent_at IS NOT NULL
            ORDER BY sent_at DESC LIMIT 1
        """
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
        return None

    async def can_send_notification(self, min_interval_minutes: int = 30) -> bool:
        """Check if enough time has passed since last notification.

        This prevents message spam.

        Args:
            min_interval_minutes: Minimum minutes between notifications.

        Returns:
            True if a notification can be sent.
        """
        last_time = await self.get_last_notification_time()
        if last_time is None:
            return True

        elapsed = datetime.utcnow() - last_time
        return elapsed >= timedelta(minutes=min_interval_minutes)

    async def mark_briefing_sent(self, briefing_id: str) -> None:
        """Mark a briefing as sent.

        Args:
            briefing_id: The briefing ID.
        """
        assert self._connection is not None

        await self._connection.execute(
            """
            UPDATE briefings SET sent = 1, sent_at = ? WHERE id = ?
        """,
            (datetime.utcnow().isoformat(), briefing_id),
        )
        await self._connection.commit()

    async def save_upcoming_release(self, release: UpcomingRelease) -> None:
        """Save an upcoming release to the schedule.

        Args:
            release: The upcoming release.
        """
        assert self._connection is not None

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO upcoming_releases
            (id, indicator_name, country, release_time, impact_level, notified, full_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                release.indicator.id,
                release.indicator.name,
                release.indicator.country,
                release.indicator.release_time.isoformat(),
                release.indicator.impact_level.value,
                1 if release.notified else 0,
                json.dumps(
                    {
                        "indicator": release.indicator.model_dump(mode="json"),
                        "notified": release.notified,
                    }
                ),
            ),
        )
        await self._connection.commit()

    async def get_upcoming_releases(
        self, hours_ahead: int = 168, high_impact_only: bool = False
    ) -> list[UpcomingRelease]:
        """Get upcoming economic releases.

        Args:
            hours_ahead: Hours to look ahead (default 7 days).
            high_impact_only: Only return high-impact releases.

        Returns:
            List of upcoming releases.
        """
        assert self._connection is not None

        now = datetime.utcnow()
        cutoff = (now + timedelta(hours=hours_ahead)).isoformat()

        if high_impact_only:
            query = """
                SELECT full_data FROM upcoming_releases
                WHERE release_time > ? AND release_time <= ? AND impact_level = 'high'
                ORDER BY release_time ASC
            """
        else:
            query = """
                SELECT full_data FROM upcoming_releases
                WHERE release_time > ? AND release_time <= ?
                ORDER BY release_time ASC
            """

        releases = []
        async with self._connection.execute(
            query, (now.isoformat(), cutoff)
        ) as cursor:
            async for row in cursor:
                data = json.loads(row[0])
                indicator = EconomicIndicator.model_validate(data["indicator"])
                releases.append(
                    UpcomingRelease(indicator=indicator, notified=data["notified"])
                )
        return releases

    async def mark_release_notified(self, indicator_id: str) -> None:
        """Mark a release as notified.

        Args:
            indicator_id: The indicator ID.
        """
        assert self._connection is not None

        await self._connection.execute(
            "UPDATE upcoming_releases SET notified = 1 WHERE id = ?",
            (indicator_id,),
        )
        await self._connection.commit()

    async def log_notification(
        self,
        briefing_id: str,
        channel: str,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """Log a notification attempt.

        Args:
            briefing_id: The briefing ID.
            channel: Notification channel (email, webhook).
            success: Whether the notification succeeded.
            error_message: Error message if failed.
        """
        assert self._connection is not None

        await self._connection.execute(
            """
            INSERT INTO notification_log (briefing_id, sent_at, channel, success, error_message)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                briefing_id,
                datetime.utcnow().isoformat(),
                channel,
                1 if success else 0,
                error_message,
            ),
        )
        await self._connection.commit()

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute a hash of content for duplicate detection.

        Args:
            content: The content to hash.

        Returns:
            SHA256 hash of the content.
        """
        return hashlib.sha256(content.encode()).hexdigest()

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
