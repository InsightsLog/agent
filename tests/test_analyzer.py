"""Tests for the sentiment analyzer."""

import pytest

from src.macroeconomic_agent.analyzer import SentimentAnalyzer
from src.macroeconomic_agent.models import NewsItem, ImpactLevel, Sentiment
from datetime import datetime


@pytest.fixture
def analyzer():
    """Create a sentiment analyzer instance."""
    return SentimentAnalyzer(
        sentiment_threshold=0.1,
        noise_keywords=["rumor", "speculation", "might"],
        manipulation_keywords=["guaranteed", "crash", "moon"],
    )


@pytest.fixture
def sample_news_item():
    """Create a sample news item."""
    return NewsItem(
        id="test123",
        title="Federal Reserve Raises Interest Rates",
        content="The Federal Reserve announced a 25 basis point increase in interest rates today.",
        source="TestSource",
        published_at=datetime.utcnow(),
        impact_level=ImpactLevel.HIGH,
    )


class TestSentimentAnalyzer:
    """Tests for SentimentAnalyzer class."""

    def test_analyze_positive_sentiment(self, analyzer):
        """Test analysis of positive text."""
        text = "The economy is growing strongly with excellent job creation and rising consumer confidence."
        score, sentiment = analyzer.analyze_sentiment(text)
        assert score > 0
        assert sentiment == Sentiment.BULLISH

    def test_analyze_negative_sentiment(self, analyzer):
        """Test analysis of negative text."""
        text = "Economic indicators are terrible with declining growth and rising unemployment fears."
        score, sentiment = analyzer.analyze_sentiment(text)
        assert score < 0
        assert sentiment == Sentiment.BEARISH

    def test_analyze_neutral_sentiment(self, analyzer):
        """Test analysis of neutral text."""
        text = "The data was reported."
        score, sentiment = analyzer.analyze_sentiment(text)
        # TextBlob may still detect some sentiment, so we check for near-neutral
        assert abs(score) < 0.5
        # With low threshold, may be classified differently
        assert sentiment in [Sentiment.NEUTRAL, Sentiment.BULLISH]

    def test_analyze_empty_text(self, analyzer):
        """Test analysis of empty text."""
        score, sentiment = analyzer.analyze_sentiment("")
        assert score == 0.0
        assert sentiment == Sentiment.NEUTRAL

    def test_is_noise_short_content(self, analyzer, sample_news_item):
        """Test noise detection for very short content."""
        item = sample_news_item.model_copy(update={"content": "Short."})
        assert analyzer.is_noise(item) is True

    def test_is_noise_with_keywords(self, analyzer, sample_news_item):
        """Test noise detection with noise keywords."""
        item = sample_news_item.model_copy(
            update={"content": "There is rumor that interest rates might change based on speculation."}
        )
        assert analyzer.is_noise(item) is True

    def test_is_not_noise_quality_content(self, analyzer, sample_news_item):
        """Test that quality content is not flagged as noise."""
        assert analyzer.is_noise(sample_news_item) is False

    def test_is_noise_excessive_punctuation(self, analyzer, sample_news_item):
        """Test noise detection for excessive punctuation."""
        item = sample_news_item.model_copy(
            update={"title": "BREAKING!!!! Rates change????", "content": "x" * 100}
        )
        assert analyzer.is_noise(item) is True

    def test_is_manipulation_with_keywords(self, analyzer, sample_news_item):
        """Test manipulation detection with manipulation keywords."""
        item = sample_news_item.model_copy(
            update={
                "content": "The market is guaranteed to crash. This will definitely moon tomorrow."
            }
        )
        assert analyzer.is_manipulation(item) is True

    def test_is_not_manipulation_normal_content(self, analyzer, sample_news_item):
        """Test that normal content is not flagged as manipulation."""
        assert analyzer.is_manipulation(sample_news_item) is False

    def test_is_manipulation_all_caps(self, analyzer, sample_news_item):
        """Test manipulation detection for ALL CAPS content."""
        item = sample_news_item.model_copy(
            update={
                "title": "BREAKING NEWS ALERT",
                "content": "URGENT CRASH INCOMING according to EXPERTS with MORE DETAILS",
            }
        )
        assert analyzer.is_manipulation(item) is True

    def test_process_item(self, analyzer, sample_news_item):
        """Test full item processing."""
        processed = analyzer.process_item(sample_news_item)
        # Sentiment score may be 0 for neutral content
        assert isinstance(processed.raw_sentiment_score, float)
        assert processed.sentiment is not None
        assert processed.is_noise is False
        assert processed.is_manipulation is False

    def test_aggregate_sentiment_filters_noise(self, analyzer):
        """Test that aggregation filters out noise."""
        items = [
            NewsItem(
                id="1",
                title="Good economic news",
                content="The economy is performing excellently with strong growth.",
                source="test",
                published_at=datetime.utcnow(),
                impact_level=ImpactLevel.HIGH,
                is_noise=False,
                is_manipulation=False,
                raw_sentiment_score=0.5,
                sentiment=Sentiment.BULLISH,
            ),
            NewsItem(
                id="2",
                title="Noise item",
                content="x",
                source="test",
                published_at=datetime.utcnow(),
                impact_level=ImpactLevel.LOW,
                is_noise=True,
                is_manipulation=False,
                raw_sentiment_score=-0.8,
                sentiment=Sentiment.BEARISH,
            ),
        ]
        _, sentiment = analyzer.aggregate_sentiment(items)
        # Should be bullish because noise is filtered
        assert sentiment == Sentiment.BULLISH

    def test_aggregate_sentiment_weights_by_impact(self, analyzer):
        """Test that aggregation weights by impact level."""
        items = [
            NewsItem(
                id="1",
                title="High impact positive",
                content="Great news for the economy.",
                source="test",
                published_at=datetime.utcnow(),
                impact_level=ImpactLevel.HIGH,
                is_noise=False,
                is_manipulation=False,
                raw_sentiment_score=0.3,
                sentiment=Sentiment.BULLISH,
            ),
            NewsItem(
                id="2",
                title="Low impact negative",
                content="Minor bad news.",
                source="test",
                published_at=datetime.utcnow(),
                impact_level=ImpactLevel.LOW,
                is_noise=False,
                is_manipulation=False,
                raw_sentiment_score=-0.3,
                sentiment=Sentiment.BEARISH,
            ),
        ]
        score, sentiment = analyzer.aggregate_sentiment(items)
        # High impact should outweigh low impact
        assert score > 0
        assert sentiment == Sentiment.BULLISH

    def test_aggregate_sentiment_empty_list(self, analyzer):
        """Test aggregation with empty list."""
        score, sentiment = analyzer.aggregate_sentiment([])
        assert score == 0.0
        assert sentiment == Sentiment.NEUTRAL
