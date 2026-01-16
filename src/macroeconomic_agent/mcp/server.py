"""MCP server for Economic Calendar functionality using Alpha Vantage.

This module exposes economic calendar data via MCP (Model Context Protocol)
endpoints, allowing AI agents to query economic indicators and calendar data.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..config import settings
from ..data_sources.alpha_vantage import AlphaVantageSource


class EconomicCalendarMCP:
    """MCP server wrapper for Economic Calendar functionality.

    Provides tools and resources for accessing economic calendar data
    via the Model Context Protocol.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize the MCP server.

        Args:
            api_key: Alpha Vantage API key. If not provided, uses config settings.
        """
        self._api_key = api_key or settings.alpha_vantage_api_key
        self._source: AlphaVantageSource | None = None

    def _get_source(self) -> AlphaVantageSource:
        """Get or create the Alpha Vantage data source."""
        if self._source is None:
            self._source = AlphaVantageSource(api_key=self._api_key)
        return self._source

    async def get_economic_indicator(self, indicator: str) -> dict[str, Any]:
        """Fetch a specific economic indicator from Alpha Vantage.

        Args:
            indicator: The indicator function name (e.g., 'CPI', 'REAL_GDP',
                      'UNEMPLOYMENT', 'NONFARM_PAYROLL', 'FEDERAL_FUNDS_RATE').

        Returns:
            Dictionary containing indicator data with fields:
            - name: Display name of the indicator
            - country: Country code (e.g., 'US')
            - release_time: ISO timestamp of the release
            - impact_level: Impact level (high, medium, low)
            - actual_value: Most recent actual value
            - previous_value: Previous value for comparison
            - error: Error message if request failed
        """
        source = self._get_source()
        result = await source.fetch_economic_indicator(indicator.upper())

        if result is None:
            return {
                "error": f"Failed to fetch indicator '{indicator}'. "
                "Check API key and indicator name."
            }

        return {
            "id": result.id,
            "name": result.name,
            "country": result.country,
            "release_time": result.release_time.isoformat(),
            "impact_level": result.impact_level.value,
            "actual_value": result.actual_value,
            "previous_value": result.previous_value,
            "forecast_value": result.forecast_value,
        }

    async def list_available_indicators(self) -> dict[str, Any]:
        """List all available economic indicators.

        Returns:
            Dictionary containing:
            - indicators: List of available indicator codes with descriptions
        """
        source = self._get_source()
        indicators = []

        for code, info in source.INDICATORS.items():
            indicators.append(
                {
                    "code": code,
                    "name": info["name"],
                    "country": info["country"],
                    "impact_level": info["impact"].value,
                    "interval": info["interval"],
                }
            )

        return {"indicators": indicators}

    async def get_economic_calendar(self, indicators: list[str] | None = None) -> dict[str, Any]:
        """Fetch economic calendar data for multiple indicators.

        Args:
            indicators: Optional list of indicator codes to fetch.
                       If not provided, fetches all available indicators.

        Returns:
            Dictionary containing:
            - calendar: List of economic indicator data
            - count: Number of indicators returned
        """
        source = self._get_source()

        if indicators is None:
            indicators = source.get_available_indicators()
        else:
            # Normalize to uppercase
            indicators = [i.upper() for i in indicators]

        calendar_data = []
        for indicator_code in indicators:
            result = await source.fetch_economic_indicator(indicator_code)
            if result:
                calendar_data.append(
                    {
                        "id": result.id,
                        "code": indicator_code,
                        "name": result.name,
                        "country": result.country,
                        "release_time": result.release_time.isoformat(),
                        "impact_level": result.impact_level.value,
                        "actual_value": result.actual_value,
                        "previous_value": result.previous_value,
                    }
                )

        return {"calendar": calendar_data, "count": len(calendar_data)}

    async def get_high_impact_indicators(self) -> dict[str, Any]:
        """Fetch only high-impact economic indicators.

        Returns:
            Dictionary containing high-impact indicator data.
        """
        source = self._get_source()
        high_impact_codes = [
            code for code, info in source.INDICATORS.items() if info["impact"].value == "high"
        ]

        return await self.get_economic_calendar(high_impact_codes)

    async def close(self) -> None:
        """Close resources."""
        if self._source:
            await self._source.close()
            self._source = None


def create_mcp_server(
    name: str = "EconomicCalendar",
    api_key: str | None = None,
) -> FastMCP:
    """Create an MCP server for Economic Calendar functionality.

    This function creates a FastMCP server instance with tools for
    querying economic calendar data from Alpha Vantage.

    Args:
        name: Name for the MCP server.
        api_key: Alpha Vantage API key. If not provided, uses config settings.

    Returns:
        Configured FastMCP server instance.

    Example:
        >>> mcp = create_mcp_server(api_key="your-api-key")
        >>> mcp.run()  # Start the server
    """
    mcp = FastMCP(name)
    calendar_mcp = EconomicCalendarMCP(api_key=api_key)

    @mcp.tool()
    async def get_economic_indicator(indicator: str) -> dict[str, Any]:
        """Fetch a specific economic indicator from Alpha Vantage.

        Args:
            indicator: The indicator code. Available codes:
                - REAL_GDP: Real Gross Domestic Product
                - CPI: Consumer Price Index
                - UNEMPLOYMENT: Unemployment Rate
                - NONFARM_PAYROLL: Non-Farm Payrolls
                - FEDERAL_FUNDS_RATE: Federal Funds Rate
                - RETAIL_SALES: Retail Sales
                - INFLATION: Inflation Rate
                - DURABLES: Durable Goods Orders
                - TREASURY_YIELD: Treasury Yield
                - REAL_GDP_PER_CAPITA: Real GDP Per Capita

        Returns:
            Economic indicator data including current and previous values.
        """
        return await calendar_mcp.get_economic_indicator(indicator)

    @mcp.tool()
    async def list_economic_indicators() -> dict[str, Any]:
        """List all available economic indicators.

        Returns:
            List of indicator codes with their descriptions and metadata.
        """
        return await calendar_mcp.list_available_indicators()

    @mcp.tool()
    async def get_economic_calendar(indicators: list[str] | None = None) -> dict[str, Any]:
        """Fetch economic calendar data for multiple indicators.

        Args:
            indicators: Optional list of indicator codes. If not provided,
                       fetches all available indicators.

        Returns:
            Economic calendar data with current values for requested indicators.
        """
        return await calendar_mcp.get_economic_calendar(indicators)

    @mcp.tool()
    async def get_high_impact_releases() -> dict[str, Any]:
        """Fetch only high-impact economic indicators.

        High-impact indicators include GDP, CPI, unemployment, NFP,
        Fed funds rate, retail sales, and inflation.

        Returns:
            Economic calendar data for high-impact releases only.
        """
        return await calendar_mcp.get_high_impact_indicators()

    @mcp.resource("economic://indicators")
    def get_indicators_resource() -> str:
        """Resource listing all available economic indicators."""
        source = calendar_mcp._get_source()
        lines = ["# Available Economic Indicators\n"]
        for code, info in source.INDICATORS.items():
            lines.append(
                f"- **{code}**: {info['name']} ({info['country']}) "
                f"- Impact: {info['impact'].value}, Interval: {info['interval']}"
            )
        return "\n".join(lines)

    return mcp


def run_server(api_key: str | None = None, transport: str = "stdio") -> None:
    """Run the MCP server.

    Args:
        api_key: Alpha Vantage API key.
        transport: Transport type ('stdio' or 'streamable-http').
    """
    mcp = create_mcp_server(api_key=api_key)
    mcp.run(transport=transport)


if __name__ == "__main__":
    run_server()
