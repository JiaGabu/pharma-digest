#!/usr/bin/env python3
"""
Daily Pharma News Digest
Fetches RSS feeds, scores articles with Gemini, selects top articles,
and sends a formatted HTML email via Gmail.
"""
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing modules that need GEMINI_API_KEY
load_dotenv(Path(__file__).parent / ".env")

from config.settings import RECIPIENT_EMAIL, RSS_FEEDS
from src.fetcher import fetch_all_feeds
from src.formatter import format_email
from src.gmail_sender import send_email
from src.scorer import score_articles
from src.selector import select_articles


def setup_logging():
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== Pharma Digest starting ===")

    # 1. Fetch articles from the last 24 hours
    articles = fetch_all_feeds(RSS_FEEDS)
    if not articles:
        logger.warning("No articles fetched. Exiting.")
        return

    # 2. Score and classify with Gemini
    scored = score_articles(articles)
    if not scored:
        logger.warning("No articles passed scoring. Exiting.")
        return

    # 3. Select up to 8 articles per quota rules
    selected = select_articles(scored)
    if not selected:
        logger.warning("No articles selected. Exiting.")
        return

    # 4. Format email
    subject, html_body = format_email(selected)

    # 5. Send via Gmail
    send_email(subject, html_body, RECIPIENT_EMAIL)
    logger.info("=== Pharma Digest completed successfully ===")


if __name__ == "__main__":
    main()
