import logging
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

import numpy as np
from google import genai

from config.settings import (
    CATEGORY_ORDER,
    CATEGORY_QUOTAS,
    MULTI_SOURCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-10 else 0.0


def _embed_articles(articles: list[dict], client: genai.Client) -> list[list[float]]:
    """Embed each article title+summary using gemini-embedding-001, in parallel with timeout."""
    texts = [f"{a['title']} {a.get('summary', '')}" for a in articles]
    results = [None] * len(texts)

    def embed_one(idx_text):
        idx, text = idx_text
        response = client.models.embed_content(model="gemini-embedding-001", contents=text)
        return idx, response.embeddings[0].values

    timeout = max(120, len(texts) * 5)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(embed_one, (i, t)): i for i, t in enumerate(texts)}
        try:
            for future in as_completed(futures, timeout=timeout):
                idx, vec = future.result()
                results[idx] = vec
        except FuturesTimeoutError:
            logger.warning(f"Embedding timed out after {timeout}s; some articles may be skipped.")

    # Filter out articles whose embedding failed (None)
    valid = [(a, v) for a, v in zip(articles, results) if v is not None]
    if len(valid) < len(articles):
        logger.warning(f"Embedding failed for {len(articles) - len(valid)} articles; excluded from dedup.")
    articles_out = [a for a, _ in valid]
    vectors_out = [v for _, v in valid]
    return articles_out, vectors_out


def _info_score(article: dict) -> float:
    """Score information richness by counting specific facts."""
    text = " ".join([
        article.get("title", ""),
        article.get("summary", ""),
        article.get("strategic_implication", ""),
    ])
    specifics = re.findall(
        r'\$[\d.,]+\s*(?:[MBK]|million|billion)?'
        r'|[\d.]+\s*(?:%|percent)'
        r'|[Pp]hase\s*[0-9I-V]+'
        r'|[Pp]\s*[<>=]\s*0\.[\d]+'
        r'|\b(?:FDA|EMA|NDA|BLA|sNDA|sBLA|PDUFA|IND|AdCom|CRL)\b'
        r'|\b\d{4}\b'
        r'|\b\d+\s*(?:mg|mg/kg|mcg|kg)\b',
        text,
    )
    length_bonus = min(len(article.get("summary", "")) / 500, 1.0)
    return len(specifics) * 2 + length_bonus


def _best_in_group(group: list[dict]) -> dict:
    return max(group, key=_info_score)


def _detect_multi_source_events(articles: list[dict], client: genai.Client) -> list[list[dict]]:
    if not articles:
        return []

    articles, embeddings = _embed_articles(articles, client)
    if not articles:
        return []
    visited = [False] * len(articles)
    groups = []

    for i in range(len(articles)):
        if visited[i]:
            continue
        group = [articles[i]]
        visited[i] = True
        for j in range(i + 1, len(articles)):
            if visited[j]:
                continue
            if articles[j]["source"] == articles[i]["source"]:
                continue
            if _cosine(embeddings[i], embeddings[j]) >= 0.85:
                group.append(articles[j])
                visited[j] = True
        if len(group) > 1:
            groups.append(group)

    return groups


def select_articles(scored: list[dict]) -> list[dict]:
    """
    Select up to 9 articles according to quotas and deduplication rules:
    1. Embed all articles; group semantically identical articles across sources.
    2. For each group keep only the most info-rich article; exclude the rest.
    3. Groups covered by 3+ distinct sources force-include the best article.
    4. Fill per-category quotas by score descending; backfill vacant slots.
    """
    if not scored:
        logger.warning("No scored articles available for selection.")
        return []

    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key, http_options={"timeout": 60})

    # --- Step 1: Semantic deduplication ---
    event_groups = _detect_multi_source_events(scored, client)
    priority_ids = set()
    excluded_ids: set[str] = set()

    for group in event_groups:
        best = _best_in_group(group)
        distinct_sources = {a["source"] for a in group}

        for article in group:
            if article["id"] != best["id"]:
                excluded_ids.add(article["id"])
                logger.info(
                    f"[DEDUP] Excluded duplicate: {article['title'][:60]} "
                    f"(kept: {best['title'][:60]})"
                )

        if len(distinct_sources) >= MULTI_SOURCE_THRESHOLD:
            priority_ids.add(best["id"])
            logger.info(f"[PRIORITY] {len(distinct_sources)} sources → {best['title'][:60]}")

    # --- Step 2: Bucket by category ---
    buckets: dict[str, list[dict]] = defaultdict(list)
    for article in scored:
        if article["id"] not in excluded_ids:
            buckets[article["category"]].append(article)

    if not buckets:
        logger.warning("All articles excluded after deduplication.")
        return []

    for cat in buckets:
        buckets[cat].sort(
            key=lambda a: (a["id"] in priority_ids, a["score"]),
            reverse=True,
        )

    # --- Step 3: Fill per-category quotas ---
    selected = []
    selected_ids = set()

    for cat in CATEGORY_ORDER:
        quota = CATEGORY_QUOTAS.get(cat, 0)
        taken = 0
        for article in buckets.get(cat, []):
            if taken >= quota:
                break
            if article["id"] not in selected_ids:
                selected.append(article)
                selected_ids.add(article["id"])
                taken += 1
        if taken < quota:
            logger.info(f"Category '{cat}' filled {taken}/{quota} slots")

    # --- Step 4: Backfill vacant slots ---
    total_target = sum(CATEGORY_QUOTAS.values())
    vacant = total_target - len(selected)

    if vacant > 0:
        all_remaining = [
            a for pool in buckets.values()
            for a in pool if a["id"] not in selected_ids
        ]
        all_remaining.sort(key=lambda a: a["score"], reverse=True)
        for article in all_remaining:
            if vacant <= 0:
                break
            selected.append(article)
            selected_ids.add(article["id"])
            vacant -= 1
            logger.info(
                f"[BACKFILL] {article['category']} → {article['title'][:60]} "
                f"(score {article['score']})"
            )

    logger.info(f"Final selection: {len(selected)} articles")
    return selected
