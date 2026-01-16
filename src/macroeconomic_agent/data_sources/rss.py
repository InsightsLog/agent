"""RSS Feed data source implementation."""

import hashlib
from datetime import datetime
from typing import AsyncIterator
import aiohttp
import feedparser

from .base import DataSource
from ..models import NewsItem, ImpactLevel


class RSSFeedSource(DataSource):
    """Data source for RSS feeds."""

    def __init__(self, feed_urls: list[str], name: str = "RSS"):
        """Initialize RSS feed source.

        Args:
            feed_urls: List of RSS feed URLs to monitor.
            name: Display name for this source.
        """
        self._feed_urls = feed_urls
        self._name = name
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        """Return the name of this data source."""
        return self._name

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def fetch_news(self) -> AsyncIterator[NewsItem]:
        """Fetch news items from RSS feeds.

        Yields:
            NewsItem objects parsed from RSS entries.
        """
        session = await self._get_session()

        for feed_url in self._feed_urls:
            try:
                async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        continue
                    content = await resp.text()

                feed = feedparser.parse(content)

                for entry in feed.entries:
                    # Generate unique ID from link or title
                    id_source = entry.get("link", entry.get("title", str(datetime.utcnow())))
                    item_id = hashlib.sha256(id_source.encode()).hexdigest()[:16]

                    # Parse published date
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    if published:
                        published_at = datetime(*published[:6])
                    else:
                        published_at = datetime.utcnow()

                    # Get content
                    content = ""
                    if "content" in entry:
                        content = entry.content[0].get("value", "")
                    elif "summary" in entry:
                        content = entry.summary
                    elif "description" in entry:
                        content = entry.description

                    yield NewsItem(
                        id=item_id,
                        title=entry.get("title", "Untitled"),
                        content=content,
                        source=f"{self._name}:{feed.feed.get('title', feed_url)}",
                        url=entry.get("link"),
                        published_at=published_at,
                        impact_level=ImpactLevel.MEDIUM,
                    )

            except Exception:
                # Log and continue with next feed
                continue

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
