import hashlib
import logging
import re
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta, timezone

import feedparser

from config.settings import FETCH_HOURS

logger = logging.getLogger(__name__)

_IMAGE_FETCH_TIMEOUT = 4    # per-request HTTP timeout (seconds)
_IMAGE_TOTAL_TIMEOUT = 15   # total wall-clock budget for all image fetches (seconds)


def _rss_image(entry) -> str | None:
    """Try to extract image URL from RSS entry metadata."""
    if getattr(entry, "media_thumbnail", None):
        return entry.media_thumbnail[0].get("url")
    for mc in getattr(entry, "media_content", []):
        url = mc.get("url", "")
        if url:
            return url
    for enc in getattr(entry, "enclosures", []):
        href = enc.get("href") or enc.get("url", "")
        t = enc.get("type", "")
        if href and ("image" in t or href.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            return href
    return None


def _og_image(url: str, timeout: int = _IMAGE_FETCH_TIMEOUT) -> str | None:
    """Fetch og:image from article page."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(65536).decode("utf-8", errors="ignore")
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
        return m.group(1) if m else None
    except Exception:
        return None


def fetch_images(articles: list[dict]) -> None:
    """Parallel og:image fetch for articles without an image from RSS.

    Uses a bounded ThreadPoolExecutor with a hard total timeout so a slow
    or hung HTTP request never blocks the rest of the pipeline.
    """
    def fetch_one(article):
        if not article.get("image_url") and article.get("link"):
            article["image_url"] = _og_image(article["link"])

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_one, a): a for a in articles}
        try:
            for future in as_completed(futures, timeout=_IMAGE_TOTAL_TIMEOUT):
                try:
                    future.result()
                except Exception as e:
                    logger.debug(f"Image fetch error: {e}")
        except FuturesTimeoutError:
            logger.warning(
                f"Image fetching exceeded {_IMAGE_TOTAL_TIMEOUT}s total budget; "
                "proceeding without remaining images."
            )


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
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(30)
            try:
                feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            finally:
                socket.setdefaulttimeout(old_timeout)
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
                summary = re.sub(r"<[^>]+>", " ", summary)
                summary = re.sub(r"\s+", " ", summary).strip()

                articles.append(
                    {
                        "id": article_id,
                        "title": title,
                        "link": link,
                        "summary": summary[:1000],
                        "published": pub_date,
                        "source": source_name,
                        "source_url": url,
                        "image_url": _rss_image(entry),
                    }
                )

        except Exception as e:
            logger.error(f"Failed to fetch feed {url}: {e}")

    logger.info(f"Total articles fetched (last {FETCH_HOURS}h): {len(articles)}")
    return articles
