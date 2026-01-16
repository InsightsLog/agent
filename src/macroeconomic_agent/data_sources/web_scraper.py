"""Web scraper data source implementation."""

import hashlib
from datetime import datetime
from typing import AsyncIterator
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from .base import DataSource
from ..models import NewsItem, ImpactLevel


class ScrapingConfig:
    """Configuration for scraping a specific website."""

    def __init__(
        self,
        url: str,
        article_selector: str,
        title_selector: str,
        content_selector: str | None = None,
        link_selector: str | None = None,
        date_selector: str | None = None,
        name: str | None = None,
    ):
        """Initialize scraping configuration.

        Args:
            url: Base URL to scrape.
            article_selector: CSS selector for article containers.
            title_selector: CSS selector for title within article.
            content_selector: CSS selector for content within article.
            link_selector: CSS selector for link within article.
            date_selector: CSS selector for date within article.
            name: Display name for this source.
        """
        self.url = url
        self.article_selector = article_selector
        self.title_selector = title_selector
        self.content_selector = content_selector
        self.link_selector = link_selector
        self.date_selector = date_selector
        self.name = name or url


class WebScraperSource(DataSource):
    """Data source that scrapes web pages for news."""

    def __init__(self, configs: list[ScrapingConfig], name: str = "WebScraper"):
        """Initialize web scraper source.

        Args:
            configs: List of scraping configurations.
            name: Display name for this source.
        """
        self._configs = configs
        self._name = name
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        """Return the name of this data source."""
        return self._name

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def fetch_news(self) -> AsyncIterator[NewsItem]:
        """Fetch news items by scraping configured websites.

        Yields:
            NewsItem objects parsed from web pages.
        """
        session = await self._get_session()

        for config in self._configs:
            try:
                async with session.get(
                    config.url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()

                soup = BeautifulSoup(html, "lxml")
                articles = soup.select(config.article_selector)

                for article in articles:
                    # Extract title
                    title_elem = article.select_one(config.title_selector)
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    # Extract content
                    content = ""
                    if config.content_selector:
                        content_elem = article.select_one(config.content_selector)
                        if content_elem:
                            content = content_elem.get_text(strip=True)

                    # Extract link
                    url = None
                    if config.link_selector:
                        link_elem = article.select_one(config.link_selector)
                        if link_elem:
                            href = link_elem.get("href")
                            if href:
                                url = urljoin(config.url, href)
                    elif title_elem.name == "a":
                        href = title_elem.get("href")
                        if href:
                            url = urljoin(config.url, href)

                    # Generate unique ID
                    id_source = url or title
                    item_id = hashlib.sha256(id_source.encode()).hexdigest()[:16]

                    yield NewsItem(
                        id=item_id,
                        title=title,
                        content=content,
                        source=f"{self._name}:{config.name}",
                        url=url,
                        published_at=datetime.utcnow(),  # Would parse from date_selector if available
                        impact_level=ImpactLevel.MEDIUM,
                    )

            except Exception:
                # Log and continue with next config
                continue

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
