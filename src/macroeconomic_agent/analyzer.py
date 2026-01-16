"""Sentiment analysis and noise filtering module."""

import re
from typing import Tuple

from textblob import TextBlob

from .models import NewsItem, Sentiment
from .config import settings


class SentimentAnalyzer:
    """Analyzes sentiment and filters noise/manipulation from news."""

    def __init__(
        self,
        sentiment_threshold: float | None = None,
        noise_keywords: list[str] | None = None,
        manipulation_keywords: list[str] | None = None,
    ):
        """Initialize the sentiment analyzer.

        Args:
            sentiment_threshold: Minimum score for non-neutral sentiment.
            noise_keywords: Keywords indicating low-quality news.
            manipulation_keywords: Keywords indicating emotional manipulation.
        """
        self._sentiment_threshold = sentiment_threshold or settings.sentiment_threshold

        if noise_keywords is not None:
            self._noise_keywords = noise_keywords
        else:
            self._noise_keywords = [
                kw.strip().lower() for kw in settings.noise_filter_keywords.split(",") if kw.strip()
            ]

        if manipulation_keywords is not None:
            self._manipulation_keywords = manipulation_keywords
        else:
            self._manipulation_keywords = [
                kw.strip().lower()
                for kw in settings.manipulation_keywords.split(",")
                if kw.strip()
            ]

    def analyze_sentiment(self, text: str) -> Tuple[float, Sentiment]:
        """Analyze the sentiment of text.

        Args:
            text: The text to analyze.

        Returns:
            Tuple of (raw_score, classified_sentiment).
        """
        if not text:
            return 0.0, Sentiment.NEUTRAL

        blob = TextBlob(text)
        polarity = blob.sentiment.polarity  # -1 to 1

        if polarity > self._sentiment_threshold:
            sentiment = Sentiment.BULLISH
        elif polarity < -self._sentiment_threshold:
            sentiment = Sentiment.BEARISH
        else:
            sentiment = Sentiment.NEUTRAL

        return polarity, sentiment

    def is_noise(self, item: NewsItem) -> bool:
        """Check if a news item should be filtered as noise.

        Noise includes:
        - Unconfirmed rumors
        - Speculation without substance
        - Very short content

        Args:
            item: The news item to check.

        Returns:
            True if the item is noise.
        """
        # Very short content is likely noise
        if len(item.content) < 50:
            return True

        combined_text = f"{item.title} {item.content}".lower()

        # Check for noise keywords
        for keyword in self._noise_keywords:
            if keyword in combined_text:
                return True

        # Check for excessive punctuation (clickbait indicator)
        exclamation_count = combined_text.count("!")
        question_count = combined_text.count("?")
        if exclamation_count > 3 or question_count > 3:
            return True

        return False

    def is_manipulation(self, item: NewsItem) -> bool:
        """Check if a news item contains emotional manipulation.

        Manipulation includes:
        - Extreme language without evidence
        - Fear-mongering or hype
        - Price predictions without basis

        Args:
            item: The news item to check.

        Returns:
            True if the item is manipulative.
        """
        combined_text = f"{item.title} {item.content}".lower()

        # Check for manipulation keywords
        manipulation_count = sum(
            1 for keyword in self._manipulation_keywords if keyword in combined_text
        )

        # Multiple manipulation keywords is a red flag
        if manipulation_count >= 2:
            return True

        # ALL CAPS sections indicate manipulation
        caps_pattern = r"\b[A-Z]{4,}\b"
        caps_matches = re.findall(caps_pattern, f"{item.title} {item.content}")
        if len(caps_matches) > 2:
            return True

        # Extreme sentiment is suspicious
        polarity, _ = self.analyze_sentiment(combined_text)
        if abs(polarity) > 0.8:
            return True

        return False

    def process_item(self, item: NewsItem) -> NewsItem:
        """Process a news item: analyze sentiment and check for noise/manipulation.

        Args:
            item: The news item to process.

        Returns:
            The processed item with sentiment and flags set.
        """
        # Analyze sentiment
        raw_score, sentiment = self.analyze_sentiment(f"{item.title} {item.content}")

        # Check for noise and manipulation
        is_noise = self.is_noise(item)
        is_manipulation = self.is_manipulation(item)

        # Return updated item
        return item.model_copy(
            update={
                "raw_sentiment_score": raw_score,
                "sentiment": sentiment,
                "is_noise": is_noise,
                "is_manipulation": is_manipulation,
            }
        )

    def aggregate_sentiment(self, items: list[NewsItem]) -> Tuple[float, Sentiment]:
        """Aggregate sentiment across multiple news items.

        Filters out noise and manipulation before aggregating.

        Args:
            items: List of processed news items.

        Returns:
            Tuple of (average_score, overall_sentiment).
        """
        # Filter valid items
        valid_items = [
            item for item in items if not item.is_noise and not item.is_manipulation
        ]

        if not valid_items:
            return 0.0, Sentiment.NEUTRAL

        # Weight by impact level
        impact_weights = {"high": 3.0, "medium": 1.5, "low": 1.0}

        weighted_sum = 0.0
        total_weight = 0.0

        for item in valid_items:
            weight = impact_weights.get(item.impact_level.value, 1.0)
            weighted_sum += item.raw_sentiment_score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0, Sentiment.NEUTRAL

        avg_score = weighted_sum / total_weight

        if avg_score > self._sentiment_threshold:
            sentiment = Sentiment.BULLISH
        elif avg_score < -self._sentiment_threshold:
            sentiment = Sentiment.BEARISH
        else:
            sentiment = Sentiment.NEUTRAL

        return avg_score, sentiment
