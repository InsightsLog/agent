"""Alpha Vantage data source for economic indicators.

This module provides integration with the Alpha Vantage API to fetch
economic indicator data for the Economic Calendar functionality.
"""

import hashlib
from datetime import datetime, timezone
from typing import AsyncIterator

import aiohttp

from ..models import EconomicIndicator, ImpactLevel, NewsItem
from .base import DataSource


class AlphaVantageSource(DataSource):
    """Data source for fetching economic indicators from Alpha Vantage API.

    Alpha Vantage provides access to various US economic indicators including
    GDP, CPI, unemployment rate, federal funds rate, retail sales, and more.
    """

    # Base URL for Alpha Vantage API
    BASE_URL = "https://www.alphavantage.co/query"

    # Mapping of indicator functions to display names and impact levels
    INDICATORS = {
        "REAL_GDP": {
            "name": "Real Gross Domestic Product",
            "country": "US",
            "impact": ImpactLevel.HIGH,
            "interval": "quarterly",
        },
        "REAL_GDP_PER_CAPITA": {
            "name": "Real GDP Per Capita",
            "country": "US",
            "impact": ImpactLevel.MEDIUM,
            "interval": "quarterly",
        },
        "TREASURY_YIELD": {
            "name": "Treasury Yield",
            "country": "US",
            "impact": ImpactLevel.MEDIUM,
            "interval": "monthly",
        },
        "FEDERAL_FUNDS_RATE": {
            "name": "Federal Funds Rate",
            "country": "US",
            "impact": ImpactLevel.HIGH,
            "interval": "monthly",
        },
        "CPI": {
            "name": "Consumer Price Index",
            "country": "US",
            "impact": ImpactLevel.HIGH,
            "interval": "monthly",
        },
        "INFLATION": {
            "name": "Inflation Rate",
            "country": "US",
            "impact": ImpactLevel.HIGH,
            "interval": "annual",
        },
        "RETAIL_SALES": {
            "name": "Retail Sales",
            "country": "US",
            "impact": ImpactLevel.HIGH,
            "interval": "monthly",
        },
        "DURABLES": {
            "name": "Durable Goods Orders",
            "country": "US",
            "impact": ImpactLevel.MEDIUM,
            "interval": "monthly",
        },
        "UNEMPLOYMENT": {
            "name": "Unemployment Rate",
            "country": "US",
            "impact": ImpactLevel.HIGH,
            "interval": "monthly",
        },
        "NONFARM_PAYROLL": {
            "name": "Non-Farm Payrolls",
            "country": "US",
            "impact": ImpactLevel.HIGH,
            "interval": "monthly",
        },
    }

    def __init__(self, api_key: str | None = None):
        """Initialize the Alpha Vantage data source.

        Args:
            api_key: Alpha Vantage API key. Required for API access.
        """
        self._api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        """Return the name of this data source."""
        return "AlphaVantage"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _fetch_indicator(self, function: str, interval: str | None = None) -> dict | None:
        """Fetch a single indicator from Alpha Vantage API.

        Args:
            function: The API function name (e.g., 'CPI', 'REAL_GDP').
            interval: Optional interval parameter for the API.

        Returns:
            API response as dictionary, or None if request failed.
        """
        if not self._api_key:
            return None

        session = await self._get_session()

        params = {
            "function": function,
            "apikey": self._api_key,
            "datatype": "json",
        }
        if interval:
            params["interval"] = interval

        try:
            async with session.get(
                self.BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

                # Check for error responses
                if "Error Message" in data or "Note" in data:
                    return None

                return data
        except Exception:
            return None

    async def fetch_economic_indicator(self, function: str) -> EconomicIndicator | None:
        """Fetch a specific economic indicator.

        Args:
            function: The Alpha Vantage function name (e.g., 'CPI', 'REAL_GDP').

        Returns:
            EconomicIndicator object or None if not found.
        """
        if function not in self.INDICATORS:
            return None

        indicator_info = self.INDICATORS[function]
        data = await self._fetch_indicator(function, indicator_info.get("interval"))

        if not data or "data" not in data:
            return None

        # Get the most recent data point
        data_points = data.get("data", [])
        if not data_points:
            return None

        latest = data_points[0]
        previous = data_points[1] if len(data_points) > 1 else None

        # Parse the date
        date_str = latest.get("date", "")
        try:
            release_time = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            release_time = datetime.now(timezone.utc)

        # Generate unique ID
        indicator_id = hashlib.sha256(f"alpha_vantage:{function}:{date_str}".encode()).hexdigest()[
            :16
        ]

        # Format values with unit if available
        unit = data.get("unit", "")
        actual_value = latest.get("value")
        if actual_value and unit:
            actual_value = f"{actual_value} {unit}".strip()
        previous_value = previous.get("value") if previous else None
        if previous_value and unit:
            previous_value = f"{previous_value} {unit}".strip()

        return EconomicIndicator(
            id=indicator_id,
            name=indicator_info["name"],
            country=indicator_info["country"],
            release_time=release_time,
            impact_level=indicator_info["impact"],
            previous_value=previous_value,
            actual_value=actual_value,
        )

    async def fetch_indicators(self) -> AsyncIterator[EconomicIndicator]:
        """Fetch all available economic indicators from Alpha Vantage.

        Yields:
            EconomicIndicator objects for each available indicator.
        """
        if not self._api_key:
            return

        for function in self.INDICATORS:
            indicator = await self.fetch_economic_indicator(function)
            if indicator:
                yield indicator

    async def fetch_news(self) -> AsyncIterator[NewsItem]:
        """Fetch news items from economic indicator releases.

        Converts economic indicator data into news items for
        unified processing in the sentiment analysis pipeline.

        Yields:
            NewsItem objects for each economic indicator release.
        """
        async for indicator in self.fetch_indicators():
            # Convert indicator to news item
            item_id = hashlib.sha256(f"{indicator.id}:news".encode()).hexdigest()[:16]

            # Create news content from indicator data
            content_parts = [f"Economic indicator release: {indicator.name}"]
            if indicator.actual_value:
                content_parts.append(f"Actual: {indicator.actual_value}")
            if indicator.previous_value:
                content_parts.append(f"Previous: {indicator.previous_value}")

            yield NewsItem(
                id=item_id,
                title=f"{indicator.country} {indicator.name} Release",
                content=" | ".join(content_parts),
                source=self.name,
                url=None,
                published_at=indicator.release_time,
                impact_level=indicator.impact_level,
            )

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def get_available_indicators(self) -> list[str]:
        """Get list of available indicator function names.

        Returns:
            List of Alpha Vantage function names for economic indicators.
        """
        return list(self.INDICATORS.keys())
