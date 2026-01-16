"""Economic Calendar API data source implementation."""

import hashlib
from datetime import datetime, timedelta
from typing import AsyncIterator

import aiohttp

from .base import DataSource
from ..models import NewsItem, EconomicIndicator, ImpactLevel


class EconomicCalendarAPI(DataSource):
    """Data source for economic calendar APIs.

    This implementation provides a framework for connecting to economic calendar
    APIs like Trading Economics, Investing.com, or ForexFactory. Configure with
    your preferred API endpoint and credentials.
    """

    # High-impact indicators that trigger immediate briefings
    HIGH_IMPACT_INDICATORS = {
        "Non-Farm Payrolls",
        "NFP",
        "Federal Funds Rate",
        "Fed Interest Rate Decision",
        "CPI",
        "Consumer Price Index",
        "GDP",
        "Gross Domestic Product",
        "Retail Sales",
        "ISM Manufacturing PMI",
        "ISM Services PMI",
        "Unemployment Rate",
        "Initial Jobless Claims",
        "ECB Interest Rate Decision",
        "BOE Interest Rate Decision",
        "BOJ Interest Rate Decision",
        "FOMC Statement",
        "Jackson Hole",
    }

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        name: str = "EconomicCalendar",
    ):
        """Initialize economic calendar API source.

        Args:
            api_url: Base URL for the economic calendar API.
            api_key: API key for authentication.
            name: Display name for this source.
        """
        self._api_url = api_url
        self._api_key = api_key
        self._name = name
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        """Return the name of this data source."""
        return self._name

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    def _classify_impact(self, indicator_name: str, api_impact: str | None = None) -> ImpactLevel:
        """Classify the impact level of an indicator.

        Args:
            indicator_name: Name of the economic indicator.
            api_impact: Impact level from API if available.

        Returns:
            ImpactLevel classification.
        """
        # Check if it's a known high-impact indicator
        indicator_upper = indicator_name.upper()
        for high_impact in self.HIGH_IMPACT_INDICATORS:
            if high_impact.upper() in indicator_upper:
                return ImpactLevel.HIGH

        # Use API-provided impact if available
        if api_impact:
            api_impact_lower = api_impact.lower()
            if "high" in api_impact_lower:
                return ImpactLevel.HIGH
            elif "low" in api_impact_lower:
                return ImpactLevel.LOW

        return ImpactLevel.MEDIUM

    async def fetch_news(self) -> AsyncIterator[NewsItem]:
        """Fetch news items related to economic releases.

        This converts economic indicator releases into news items for
        sentiment analysis.

        Yields:
            NewsItem objects for each economic release.
        """
        async for indicator in self.fetch_indicators():
            # Convert indicator to news item for unified processing
            item_id = hashlib.sha256(f"{indicator.id}:news".encode()).hexdigest()[:16]

            # Create news content from indicator data
            content_parts = [f"Economic indicator release: {indicator.name}"]
            if indicator.actual_value:
                content_parts.append(f"Actual: {indicator.actual_value}")
            if indicator.forecast_value:
                content_parts.append(f"Forecast: {indicator.forecast_value}")
            if indicator.previous_value:
                content_parts.append(f"Previous: {indicator.previous_value}")

            yield NewsItem(
                id=item_id,
                title=f"{indicator.country} {indicator.name} Release",
                content=" | ".join(content_parts),
                source=self._name,
                url=None,
                published_at=indicator.release_time,
                impact_level=indicator.impact_level,
            )

    async def fetch_indicators(self) -> AsyncIterator[EconomicIndicator]:
        """Fetch economic indicators from the calendar API.

        This is a framework implementation. In production, you would connect
        to an actual economic calendar API.

        Yields:
            EconomicIndicator objects.
        """
        if not self._api_url:
            # Return sample data for demonstration
            async for indicator in self._get_sample_indicators():
                yield indicator
            return

        session = await self._get_session()

        try:
            # Example API call structure - adjust for your actual API
            today = datetime.utcnow().date()
            params = {
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=7)).isoformat(),
            }

            async with session.get(
                self._api_url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()

                # Process API response - structure depends on specific API
                for item in data.get("events", []):
                    indicator_id = hashlib.sha256(
                        f"{item.get('id', item.get('name'))}".encode()
                    ).hexdigest()[:16]

                    yield EconomicIndicator(
                        id=indicator_id,
                        name=item.get("name", "Unknown"),
                        country=item.get("country", "Unknown"),
                        release_time=datetime.fromisoformat(
                            item.get("datetime", datetime.utcnow().isoformat())
                        ),
                        impact_level=self._classify_impact(
                            item.get("name", ""), item.get("impact")
                        ),
                        previous_value=item.get("previous"),
                        forecast_value=item.get("forecast"),
                        actual_value=item.get("actual"),
                    )

        except Exception:
            # Log and return
            pass

    async def _get_sample_indicators(self) -> AsyncIterator[EconomicIndicator]:
        """Generate sample indicators for demonstration.

        Yields:
            Sample EconomicIndicator objects.
        """
        now = datetime.utcnow()

        sample_indicators = [
            EconomicIndicator(
                id="sample_nfp",
                name="Non-Farm Payrolls",
                country="US",
                release_time=now + timedelta(days=1),
                impact_level=ImpactLevel.HIGH,
                previous_value="150K",
                forecast_value="175K",
            ),
            EconomicIndicator(
                id="sample_cpi",
                name="Consumer Price Index (YoY)",
                country="US",
                release_time=now + timedelta(days=3),
                impact_level=ImpactLevel.HIGH,
                previous_value="3.2%",
                forecast_value="3.0%",
            ),
            EconomicIndicator(
                id="sample_retail",
                name="Retail Sales (MoM)",
                country="US",
                release_time=now + timedelta(days=5),
                impact_level=ImpactLevel.MEDIUM,
                previous_value="0.4%",
                forecast_value="0.3%",
            ),
        ]

        for indicator in sample_indicators:
            yield indicator

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
