"""MCP (Model Context Protocol) server package for the Macroeconomic Agent."""

from .server import EconomicCalendarMCP, create_mcp_server

__all__ = ["create_mcp_server", "EconomicCalendarMCP"]
