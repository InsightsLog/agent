# Macroeconomic News Release Analyst Agent

An intelligent agent that generates sentiment briefings for macroeconomic news releases, filters out noise and emotional manipulation, and delivers notifications via email or webhook (Discord, Slack).

## Features

- **Daily Sentiment Briefings**: Automated daily summaries of market sentiment
- **High-Impact Release Alerts**: Immediate briefings when major economic indicators are released
- **Multi-Channel Notifications**: Support for email, Discord, Slack, and custom webhooks
- **Noise Filtering**: Automatically filters out low-impact speculation and rumors
- **Manipulation Detection**: Flags content with emotional manipulation tactics
- **Duplicate Prevention**: Avoids spamming the same stories repeatedly
- **Release Schedule Tracking**: Maintains a calendar of upcoming high-impact releases

## Data Sources

The agent can pull data from multiple sources:

- **RSS Feeds**: Financial news RSS feeds
- **Economic Calendar APIs**: Integration with economic calendar providers
- **Web Scraping**: Configurable web scraping for specific news sites
- **MCP Endpoints**: Extensible architecture for MCP integrations

## Installation

```bash
# Clone the repository
git clone https://github.com/InsightsLog/agent.git
cd agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Download TextBlob corpora (required for sentiment analysis)
python -m textblob.download_corpora
```

## Configuration

Create a `.env` file in the project root:

```env
# Database
MACRO_AGENT_DATABASE_PATH=data/briefings.db

# Email Notifications
MACRO_AGENT_EMAIL_ENABLED=false
MACRO_AGENT_EMAIL_HOST=smtp.gmail.com
MACRO_AGENT_EMAIL_PORT=587
MACRO_AGENT_EMAIL_USERNAME=your-email@gmail.com
MACRO_AGENT_EMAIL_PASSWORD=your-app-password
MACRO_AGENT_EMAIL_FROM=your-email@gmail.com
MACRO_AGENT_EMAIL_TO=recipient@example.com

# Webhook Notifications (Discord/Slack)
MACRO_AGENT_WEBHOOK_ENABLED=true
MACRO_AGENT_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Scheduling
MACRO_AGENT_DAILY_BRIEFING_TIME=08:00
MACRO_AGENT_MIN_NOTIFICATION_INTERVAL_MINUTES=30

# Analysis Settings
MACRO_AGENT_SENTIMENT_THRESHOLD=0.1
MACRO_AGENT_NOISE_FILTER_KEYWORDS=rumor,speculation,might,could,possibly
MACRO_AGENT_MANIPULATION_KEYWORDS=guaranteed,certain,crash,moon,rocket

# Data Sources
MACRO_AGENT_RSS_FEEDS=https://feeds.example.com/finance.rss
MACRO_AGENT_ECONOMIC_CALENDAR_API_KEY=your-api-key
```

## Usage

### Generate a Briefing

```bash
# Generate and display a daily briefing
macro-agent briefing

# Generate a high-impact briefing
macro-agent briefing --type high_impact

# Generate and send via configured channels
macro-agent briefing --send
```

### View Upcoming Releases

```bash
# Show releases in the next 7 days
macro-agent schedule

# Show only high-impact releases in the next 72 hours
macro-agent schedule --hours 72 --high-impact-only
```

### Run Continuously

```bash
# Run the agent with scheduler (daily briefings + high-impact monitoring)
macro-agent run
```

### Programmatic Usage

```python
import asyncio
from macroeconomic_agent import MacroeconomicAgent

async def main():
    async with MacroeconomicAgent() as agent:
        # Generate a briefing
        briefing = await agent.run_daily_briefing()
        print(f"Sentiment: {briefing.overall_sentiment}")
        
        # Check for high-impact releases
        alerts = await agent.check_high_impact_releases()
        
        # Start continuous monitoring
        agent.start_scheduler()
        
asyncio.run(main())
```

## Architecture

```
src/macroeconomic_agent/
├── __init__.py          # Package init
├── agent.py             # Main agent orchestration
├── analyzer.py          # Sentiment analysis & filtering
├── cli.py               # Command-line interface
├── config.py            # Configuration management
├── models.py            # Data models (Pydantic)
├── data_sources/        # Data source implementations
│   ├── base.py          # Abstract base class
│   ├── rss.py           # RSS feed source
│   ├── api.py           # Economic calendar API
│   └── web_scraper.py   # Web scraping source
├── memory/              # Storage & persistence
│   └── storage.py       # SQLite-based storage
└── notifications/       # Notification channels
    ├── notifier.py      # Base notifier interface
    ├── email_notifier.py
    └── webhook_notifier.py
```

## High-Impact Indicators

The agent monitors these key economic indicators:

- Non-Farm Payrolls (NFP)
- Federal Reserve Interest Rate Decisions
- Consumer Price Index (CPI)
- Gross Domestic Product (GDP)
- Retail Sales
- ISM Manufacturing/Services PMI
- Unemployment Rate
- Initial Jobless Claims
- ECB/BOE/BOJ Rate Decisions
- FOMC Statements

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/macroeconomic_agent

# Run specific test file
pytest tests/test_analyzer.py -v
```

## License

MIT License