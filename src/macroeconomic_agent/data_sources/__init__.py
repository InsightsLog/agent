"""Data sources package for the Macroeconomic News Release Analyst Agent."""

from .base import DataSource
from .rss import RSSFeedSource
from .web_scraper import WebScraperSource
from .api import EconomicCalendarAPI

__all__ = ["DataSource", "RSSFeedSource", "WebScraperSource", "EconomicCalendarAPI"]
