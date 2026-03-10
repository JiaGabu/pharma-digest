import feedparser
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from config.settings import FETCH_HOURS

logger = logging.getLogger(__name__)


def fetch_all_feeds(feed_urls: list[str]) -> list[dict]:
    """
    Fetch articles from all RSS feeds published within the last FETCH_HOURS hours.
    Deduplicates by URL. Returns a list of article dicts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FETCH_HOURS)
    articles = []
    seen_urls = set()

    for url in feed_urls:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            source_name = feed.feed.get("title", url)
            logger.info(f"Fetched {len(feed.entries)} entries from {source_name}")

            for entry in feed.entries:
                link = entry.get("link", "").strip()
                title = entry.get("title", "").strip()

                if not title:
                    continue
                if link and link in seen_urls:
                    continue

                # Parse pubDate
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass
                if pub_date is None and hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    try:
                        pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                # Only include articles within the last FETCH_HOURS (skip if no date)
                if pub_date is None:
                    logger.debug(f"Skipping article with no pubDate: {title[:60]}")
                    continue
                if pub_date < cutoff:
                    continue

                if link:
                    seen_urls.add(link)

                article_id = (
                    hashlib.md5(link.encode()).hexdigest()
                    if link
                    else hashlib.md5(title.encode()).hexdigest()
                )

                summary = entry.get("summary", entry.get("description", "")).strip()
                # Strip basic HTML tags from summary
                import re
                summary = re.sub(r"<[^>]+>", " ", summary)
                summary = re.sub(r"\s+", " ", summary).strip()

                articles.append(
                    {
                        "id": article_id,
                        "title": title,
                        "link": link,
                        "summary": summary[:1000],  # Limit for API calls
                        "published": pub_date,
                        "source": source_name,
                        "source_url": url,
                    }
                )

        except Exception as e:
            logger.error(f"Failed to fetch feed {url}: {e}")

    logger.info(f"Total articles fetched (last {FETCH_HOURS}h): {len(articles)}")
    return articles
