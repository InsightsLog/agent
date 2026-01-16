"""Base data source interface."""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..models import NewsItem, EconomicIndicator


class DataSource(ABC):
    """Abstract base class for all data sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this data source."""
        pass

    @abstractmethod
    async def fetch_news(self) -> AsyncIterator[NewsItem]:
        """Fetch news items from this source.

        Yields:
            NewsItem objects as they are fetched.
        """
        pass

    async def fetch_indicators(self) -> AsyncIterator[EconomicIndicator]:
        """Fetch economic indicators from this source.

        Override this method if the source provides indicator data.

        Yields:
            EconomicIndicator objects as they are fetched.
        """
        # Default implementation yields nothing - this is a no-op async generator
        if False:  # pragma: no cover
            yield

    async def close(self) -> None:
        """Clean up any resources.

        Override if the source needs cleanup.
        """
        pass
