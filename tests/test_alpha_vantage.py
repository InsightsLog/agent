"""Tests for the Alpha Vantage data source."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.macroeconomic_agent.data_sources.alpha_vantage import AlphaVantageSource
from src.macroeconomic_agent.models import ImpactLevel


class TestAlphaVantageSource:
    """Tests for AlphaVantageSource class."""

    def test_init(self):
        """Test initialization with and without API key."""
        source = AlphaVantageSource()
        assert source._api_key is None
        assert source.name == "AlphaVantage"

        source_with_key = AlphaVantageSource(api_key="test_key")
        assert source_with_key._api_key == "test_key"

    def test_name_property(self):
        """Test the name property returns correct value."""
        source = AlphaVantageSource()
        assert source.name == "AlphaVantage"

    def test_get_available_indicators(self):
        """Test getting list of available indicators."""
        source = AlphaVantageSource()
        indicators = source.get_available_indicators()

        assert isinstance(indicators, list)
        assert "CPI" in indicators
        assert "REAL_GDP" in indicators
        assert "UNEMPLOYMENT" in indicators
        assert "NONFARM_PAYROLL" in indicators
        assert "FEDERAL_FUNDS_RATE" in indicators

    def test_indicators_metadata(self):
        """Test that all indicators have required metadata."""
        source = AlphaVantageSource()

        for code, info in source.INDICATORS.items():
            assert "name" in info, f"Missing 'name' for {code}"
            assert "country" in info, f"Missing 'country' for {code}"
            assert "impact" in info, f"Missing 'impact' for {code}"
            assert "interval" in info, f"Missing 'interval' for {code}"
            assert isinstance(info["impact"], ImpactLevel)

    @pytest.mark.asyncio
    async def test_fetch_indicator_without_api_key(self):
        """Test that fetching without API key returns None."""
        source = AlphaVantageSource()
        result = await source._fetch_indicator("CPI")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_economic_indicator_invalid(self):
        """Test fetching an invalid indicator returns None."""
        source = AlphaVantageSource(api_key="test_key")
        result = await source.fetch_economic_indicator("INVALID_INDICATOR")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_indicators_without_api_key(self):
        """Test that fetch_indicators yields nothing without API key."""
        source = AlphaVantageSource()
        indicators = []
        async for indicator in source.fetch_indicators():
            indicators.append(indicator)
        assert len(indicators) == 0

    @pytest.mark.asyncio
    async def test_fetch_news_without_api_key(self):
        """Test that fetch_news yields nothing without API key."""
        source = AlphaVantageSource()
        news_items = []
        async for item in source.fetch_news():
            news_items.append(item)
        assert len(news_items) == 0

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing the session."""
        source = AlphaVantageSource(api_key="test_key")
        # Create a mock session
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        source._session = mock_session

        await source.close()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        """Test closing when session is already closed."""
        source = AlphaVantageSource(api_key="test_key")
        mock_session = MagicMock()
        mock_session.closed = True
        source._session = mock_session

        # Should not raise
        await source.close()

    @pytest.mark.asyncio
    async def test_fetch_economic_indicator_success(self):
        """Test successful indicator fetch with mocked response."""
        source = AlphaVantageSource(api_key="test_key")

        mock_response = {
            "name": "Consumer Price Index",
            "interval": "monthly",
            "unit": "%",
            "data": [
                {"date": "2024-01-01", "value": "3.1"},
                {"date": "2023-12-01", "value": "3.4"},
            ],
        }

        with patch.object(source, "_fetch_indicator", return_value=mock_response):
            result = await source.fetch_economic_indicator("CPI")

            assert result is not None
            assert result.name == "Consumer Price Index"
            assert result.country == "US"
            assert result.impact_level == ImpactLevel.HIGH
            assert result.actual_value == "3.1 %"
            assert result.previous_value == "3.4 %"

    @pytest.mark.asyncio
    async def test_fetch_economic_indicator_empty_data(self):
        """Test indicator fetch with empty data array."""
        source = AlphaVantageSource(api_key="test_key")

        mock_response = {
            "name": "Consumer Price Index",
            "data": [],
        }

        with patch.object(source, "_fetch_indicator", return_value=mock_response):
            result = await source.fetch_economic_indicator("CPI")
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_economic_indicator_no_data_key(self):
        """Test indicator fetch with missing data key."""
        source = AlphaVantageSource(api_key="test_key")

        mock_response = {"name": "Consumer Price Index"}

        with patch.object(source, "_fetch_indicator", return_value=mock_response):
            result = await source.fetch_economic_indicator("CPI")
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_news_from_indicators(self):
        """Test fetching news items from indicators."""
        source = AlphaVantageSource(api_key="test_key")

        mock_response = {
            "name": "Real GDP",
            "interval": "quarterly",
            "unit": "USD",
            "data": [
                {"date": "2024-01-01", "value": "28000"},
                {"date": "2023-10-01", "value": "27500"},
            ],
        }

        with patch.object(source, "_fetch_indicator", return_value=mock_response):
            # Mock fetch_indicators to only return one indicator
            async def mock_fetch_indicators():
                indicator = await source.fetch_economic_indicator("REAL_GDP")
                if indicator:
                    yield indicator

            with patch.object(source, "fetch_indicators", mock_fetch_indicators):
                news_items = []
                async for item in source.fetch_news():
                    news_items.append(item)

                assert len(news_items) == 1
                assert "Real Gross Domestic Product" in news_items[0].title
                assert news_items[0].source == "AlphaVantage"


class TestAlphaVantageSourceIntegration:
    """Integration-style tests for Alpha Vantage source.

    These tests verify the source works correctly with mocked HTTP responses.
    """

    @pytest.mark.asyncio
    async def test_full_fetch_flow(self):
        """Test the complete fetch flow with mocked HTTP."""
        source = AlphaVantageSource(api_key="test_key")

        # Mock the aiohttp session
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "name": "Unemployment Rate",
                "interval": "monthly",
                "unit": "percent",
                "data": [
                    {"date": "2024-01-01", "value": "3.7"},
                    {"date": "2023-12-01", "value": "3.8"},
                ],
            }
        )

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))
        mock_session.close = AsyncMock()

        source._session = mock_session

        result = await source.fetch_economic_indicator("UNEMPLOYMENT")

        assert result is not None
        assert result.name == "Unemployment Rate"
        assert "3.7" in result.actual_value
        assert "3.8" in result.previous_value

        await source.close()


class AsyncContextManager:
    """Helper class to mock async context managers."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, *args):
        pass
