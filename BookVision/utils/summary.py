from transformers import pipeline, set_seed
import logging
from typing import List, Dict, Union, Any

logger = logging.getLogger(__name__)

SUMMARIZATION_MODEL: str = "sshleifer/distilbart-cnn-12-6"
MAX_CHUNK_SIZE_TOKENS: int = 1024
SUMMARIZER_MAX_LENGTH: int = 150
SUMMARIZER_MIN_LENGTH: int = 30

try:
    logger.info(f"Loading summarization model: {SUMMARIZATION_MODEL}")
    summarizer = pipeline("summarization", model=SUMMARIZATION_MODEL, truncation=True)
    set_seed(42)
    logger.info("Summarization model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load summarization model {SUMMARIZATION_MODEL}: {e}", exc_info=True)
    summarizer = None


def generate_summary(text: str) -> str:
    if summarizer is None:
        logger.error("Summarizer not available. Cannot generate summary.")
        return "Summary generation service is currently unavailable."

    if not text.strip():
        logger.warning("Attempted to summarize empty text.")
        return "No content to summarize."

    logger.info(f"Starting summary generation for text of length {len(text)}.")
    
    normalized_text: str = " ".join(text.split())
    
    char_chunks: List[str] = [
        normalized_text[i:i + MAX_CHUNK_SIZE_TOKENS * 4]
        for i in range(0, len(normalized_text), MAX_CHUNK_SIZE_TOKENS * 4)
    ]
    
    if not char_chunks:
        logger.warning("No chunks created for summarization, though text was present.")
        return "Could not process text for summarization."

    logger.info(f"Text divided into {len(char_chunks)} chunk(s) for summarization.")
    summary_parts: List[str] = []

    for i, chunk in enumerate(char_chunks):
        try:
            logger.debug(f"Summarizing chunk {i+1}/{len(char_chunks)} (length: {len(chunk)} chars)")
            result: List[Dict[str, Any]] = summarizer(
                chunk, 
                max_length=SUMMARIZER_MAX_LENGTH, 
                min_length=SUMMARIZER_MIN_LENGTH, 
                do_sample=False
            )
            if result and isinstance(result, list) and result[0] and 'summary_text' in result[0]:
                 summary_parts.append(result[0]['summary_text'])
                 logger.debug(f"Chunk {i+1} summarized successfully.")
            else:
                logger.warning(f"Summarization for chunk {i+1} returned an unexpected result or no summary: {result}")
        except Exception as e:
            logger.error(f"Error summarizing chunk {i+1}: {e}", exc_info=True)
            summary_parts.append(f"[Error summarizing part {i+1}]")

    final_summary: str = "\n".join(summary_parts).strip()
    logger.info(f"Summary generation complete. Final summary length: {len(final_summary)} chars.")
    return final_summary if final_summary else "Could not generate a summary for the provided text."
