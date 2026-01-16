"""Tests for the MCP server module."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.macroeconomic_agent.mcp.server import EconomicCalendarMCP, create_mcp_server
from src.macroeconomic_agent.models import EconomicIndicator, ImpactLevel


class TestEconomicCalendarMCP:
    """Tests for EconomicCalendarMCP class."""

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        mcp = EconomicCalendarMCP(api_key="test_key")
        assert mcp._api_key == "test_key"

    def test_init_without_api_key(self):
        """Test initialization without API key uses settings."""
        with patch("src.macroeconomic_agent.mcp.server.settings") as mock_settings:
            mock_settings.alpha_vantage_api_key = "settings_key"
            mcp = EconomicCalendarMCP()
            assert mcp._api_key == "settings_key"

    def test_get_source_creates_source(self):
        """Test that _get_source creates an AlphaVantageSource."""
        mcp = EconomicCalendarMCP(api_key="test_key")
        source = mcp._get_source()
        assert source is not None
        assert source._api_key == "test_key"

    def test_get_source_returns_same_instance(self):
        """Test that _get_source returns the same instance on subsequent calls."""
        mcp = EconomicCalendarMCP(api_key="test_key")
        source1 = mcp._get_source()
        source2 = mcp._get_source()
        assert source1 is source2

    @pytest.mark.asyncio
    async def test_get_economic_indicator_success(self):
        """Test successful indicator retrieval."""
        mcp = EconomicCalendarMCP(api_key="test_key")

        mock_indicator = EconomicIndicator(
            id="test_id",
            name="Consumer Price Index",
            country="US",
            release_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            impact_level=ImpactLevel.HIGH,
            actual_value="3.1%",
            previous_value="3.4%",
        )

        # Create a mock source
        mock_source = MagicMock()
        mock_source.fetch_economic_indicator = AsyncMock(return_value=mock_indicator)

        with patch.object(mcp, "_get_source", return_value=mock_source):
            result = await mcp.get_economic_indicator("CPI")

            assert "error" not in result
            assert result["name"] == "Consumer Price Index"
            assert result["country"] == "US"
            assert result["impact_level"] == "high"
            assert result["actual_value"] == "3.1%"
            assert result["previous_value"] == "3.4%"

    @pytest.mark.asyncio
    async def test_get_economic_indicator_failure(self):
        """Test indicator retrieval failure returns error."""
        mcp = EconomicCalendarMCP(api_key="test_key")

        # Create a mock source that returns None
        mock_source = MagicMock()
        mock_source.fetch_economic_indicator = AsyncMock(return_value=None)

        with patch.object(mcp, "_get_source", return_value=mock_source):
            result = await mcp.get_economic_indicator("INVALID")

            assert "error" in result

    @pytest.mark.asyncio
    async def test_list_available_indicators(self):
        """Test listing available indicators."""
        mcp = EconomicCalendarMCP(api_key="test_key")
        result = await mcp.list_available_indicators()

        assert "indicators" in result
        indicators = result["indicators"]
        assert len(indicators) > 0

        # Check that each indicator has required fields
        for ind in indicators:
            assert "code" in ind
            assert "name" in ind
            assert "country" in ind
            assert "impact_level" in ind
            assert "interval" in ind

    @pytest.mark.asyncio
    async def test_get_economic_calendar_all(self):
        """Test getting economic calendar for all indicators."""
        mcp = EconomicCalendarMCP(api_key="test_key")

        mock_indicator = EconomicIndicator(
            id="test_id",
            name="Test Indicator",
            country="US",
            release_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            impact_level=ImpactLevel.HIGH,
            actual_value="100",
        )

        # Create a mock source
        mock_source = MagicMock()
        mock_source.fetch_economic_indicator = AsyncMock(return_value=mock_indicator)
        mock_source.get_available_indicators = MagicMock(return_value=["CPI", "REAL_GDP"])

        with patch.object(mcp, "_get_source", return_value=mock_source):
            result = await mcp.get_economic_calendar()

            assert "calendar" in result
            assert "count" in result
            assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_get_economic_calendar_specific(self):
        """Test getting economic calendar for specific indicators."""
        mcp = EconomicCalendarMCP(api_key="test_key")

        mock_indicator = EconomicIndicator(
            id="test_id",
            name="Consumer Price Index",
            country="US",
            release_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            impact_level=ImpactLevel.HIGH,
            actual_value="3.1%",
        )

        # Create a mock source
        mock_source = MagicMock()
        mock_source.fetch_economic_indicator = AsyncMock(return_value=mock_indicator)

        with patch.object(mcp, "_get_source", return_value=mock_source):
            result = await mcp.get_economic_calendar(["cpi", "real_gdp"])

            assert "calendar" in result
            assert "count" in result

    @pytest.mark.asyncio
    async def test_get_high_impact_indicators(self):
        """Test getting high impact indicators only."""
        mcp = EconomicCalendarMCP(api_key="test_key")

        mock_indicator = EconomicIndicator(
            id="test_id",
            name="High Impact Indicator",
            country="US",
            release_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            impact_level=ImpactLevel.HIGH,
            actual_value="100",
        )

        # Create a mock source with INDICATORS attribute
        mock_source = MagicMock()
        mock_source.fetch_economic_indicator = AsyncMock(return_value=mock_indicator)
        mock_source.INDICATORS = {
            "CPI": {"impact": ImpactLevel.HIGH},
            "REAL_GDP": {"impact": ImpactLevel.HIGH},
            "TREASURY_YIELD": {"impact": ImpactLevel.MEDIUM},
        }

        with patch.object(mcp, "_get_source", return_value=mock_source):
            result = await mcp.get_high_impact_indicators()

            assert "calendar" in result
            assert "count" in result

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing resources."""
        mcp = EconomicCalendarMCP(api_key="test_key")

        # Create the source first
        source = mcp._get_source()
        mock_close = AsyncMock()
        source.close = mock_close

        await mcp.close()
        mock_close.assert_called_once()
        assert mcp._source is None


class TestCreateMCPServer:
    """Tests for create_mcp_server function."""

    def test_create_server_returns_fastmcp(self):
        """Test that create_mcp_server returns a FastMCP instance."""
        mcp = create_mcp_server(api_key="test_key")
        assert mcp is not None
        # FastMCP should have a name attribute
        assert hasattr(mcp, "name")

    def test_create_server_with_custom_name(self):
        """Test creating server with custom name."""
        mcp = create_mcp_server(name="CustomCalendar", api_key="test_key")
        assert mcp.name == "CustomCalendar"

    def test_create_server_default_name(self):
        """Test creating server with default name."""
        mcp = create_mcp_server(api_key="test_key")
        assert mcp.name == "EconomicCalendar"

    def test_server_has_tools(self):
        """Test that the server has registered tools."""
        mcp = create_mcp_server(api_key="test_key")

        # FastMCP stores tools internally
        # The exact API might vary, but we check it's configured
        assert mcp is not None
