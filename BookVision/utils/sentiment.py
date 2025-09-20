from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import logging
# The line "from typing import str" has been removed as 'str' is a built-in type.

logger = logging.getLogger(__name__)

SENTIMENT_POSITIVE: str = "Positive"
SENTIMENT_NEGATIVE: str = "Negative"
SENTIMENT_NEUTRAL: str = "Neutral"

try:
    analyzer = SentimentIntensityAnalyzer()
    logger.info("VADER SentimentIntensityAnalyzer initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize VADER SentimentIntensityAnalyzer: {e}", exc_info=True)
    analyzer = None

def get_sentiment(text: str) -> str:
    if not text.strip():
        logger.warning("Attempted to analyze sentiment of empty text.")
        return SENTIMENT_NEUTRAL

    if analyzer is None:
        logger.error("VADER analyzer not available. Cannot perform full sentiment analysis.")
        try:
            blob_sentiment: float = TextBlob(text).sentiment.polarity
            logger.info(f"VADER unavailable, using TextBlob only. Polarity: {blob_sentiment:.4f}")
            if blob_sentiment >= 0.05: return SENTIMENT_POSITIVE
            if blob_sentiment <= -0.05: return SENTIMENT_NEGATIVE
            return SENTIMENT_NEUTRAL
        except Exception as e_tb:
            logger.error(f"Error during TextBlob sentiment analysis fallback: {e_tb}", exc_info=True)
            return "Error in sentiment analysis"

    logger.info(f"Starting sentiment analysis for text of length {len(text)}.")
    try:
        blob_sentiment: float = TextBlob(text).sentiment.polarity
        vader_scores: dict = analyzer.polarity_scores(text)
        vader_compound_sentiment: float = vader_scores['compound']

        logger.debug(f"TextBlob polarity: {blob_sentiment:.4f}, VADER compound: {vader_compound_sentiment:.4f}")

        avg_sentiment: float = (blob_sentiment + vader_compound_sentiment) / 2
        logger.info(f"Average sentiment score: {avg_sentiment:.4f}")

        if avg_sentiment >= 0.05:
            return SENTIMENT_POSITIVE
        elif avg_sentiment <= -0.05:
            return SENTIMENT_NEGATIVE
        else:
            return SENTIMENT_NEUTRAL
            
    except Exception as e:
        logger.error(f"Error during sentiment analysis: {e}", exc_info=True)
        return "Error in sentiment analysis"
