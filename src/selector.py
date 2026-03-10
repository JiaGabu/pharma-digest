import logging
import re
from collections import defaultdict

from config.settings import (
    CATEGORY_ORDER,
    CATEGORY_QUOTAS,
    MULTI_SOURCE_THRESHOLD,
    PASS_THRESHOLDS,
)

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "will", "its", "it", "as", "up", "new", "says",
    "said", "after", "over", "about", "that", "this", "their",
}


def _normalize_title(title: str) -> set[str]:
    """Lowercase, remove punctuation, remove stopwords, return word set."""
    words = re.sub(r"[^a-z0-9\s]", " ", title.lower()).split()
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _detect_multi_source_events(articles: list[dict]) -> list[list[dict]]:
    """
    Group articles covering the same event (Jaccard > 0.3 on title keywords,
    from different sources). Returns groups of 2+ articles.
    """
    normalized = [_normalize_title(a["title"]) for a in articles]
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
            if _jaccard(normalized[i], normalized[j]) >= 0.3:
                group.append(articles[j])
                visited[j] = True
        if len(group) > 1:
            groups.append(group)

    return groups


def _best_in_group(group: list[dict]) -> dict:
    """Pick the most information-rich article (longest summary as proxy)."""
    return max(group, key=lambda a: len(a.get("summary", "")))


def select_articles(scored: list[dict]) -> list[dict]:
    """
    Select up to 8 articles according to quotas and rules:
    1. Force-include articles covered by MULTI_SOURCE_THRESHOLD+ distinct sources.
    2. Fill remaining slots per category from highest-scoring eligible articles.
    3. If a category has fewer eligible articles than its quota, fill vacant
       slots with highest-scoring unused articles from other categories.
    """
    # --- Step 1: Detect multi-source events ---
    event_groups = _detect_multi_source_events(scored)
    forced_ids = set()
    forced_articles = []

    for group in event_groups:
        distinct_sources = {a["source"] for a in group}
        if len(distinct_sources) >= MULTI_SOURCE_THRESHOLD:
            best = _best_in_group(group)
            if best["id"] not in forced_ids:
                forced_ids.add(best["id"])
                forced_articles.append(best)
                logger.info(
                    f"[FORCED] {len(distinct_sources)} sources: {best['title'][:60]}"
                )

    # --- Step 2: Bucket remaining eligible articles by category ---
    # Eligible = passes threshold and not already forced
    buckets: dict[str, list[dict]] = defaultdict(list)
    for article in scored:
        if article["id"] in forced_ids:
            continue
        threshold = PASS_THRESHOLDS.get(article["category"], 999)
        if article["total_score"] >= threshold:
            buckets[article["category"]].append(article)

    for cat in buckets:
        buckets[cat].sort(key=lambda a: a["total_score"], reverse=True)

    # --- Step 3: Count forced articles against category quotas ---
    quotas = dict(CATEGORY_QUOTAS)
    selected = []

    # Place forced articles into their category quota first
    for article in forced_articles:
        cat = article["category"]
        if quotas.get(cat, 0) > 0:
            selected.append(article)
            quotas[cat] -= 1
        else:
            # Forced but quota full — still include (override quota slightly)
            selected.append(article)
            logger.info(f"[FORCED OVERRIDE] quota full for {cat}, still including")

    # --- Step 4: Fill per-category quotas ---
    unfilled_slots = []
    for cat in CATEGORY_ORDER:
        remaining = quotas.get(cat, 0)
        pool = buckets.get(cat, [])
        taken = 0
        for article in pool:
            if remaining <= 0:
                break
            if article["id"] not in {a["id"] for a in selected}:
                selected.append(article)
                remaining -= 1
                taken += 1
        # Track unfilled slots (category + count)
        if remaining > 0:
            unfilled_slots.append((cat, remaining))
            logger.info(f"Category '{cat}' has {remaining} unfilled slot(s)")

    # --- Step 5: Fill vacant slots from other categories ---
    if unfilled_slots:
        total_vacant = sum(n for _, n in unfilled_slots)
        selected_ids = {a["id"] for a in selected}

        # Gather all remaining eligible articles not yet selected, sorted by score
        all_remaining = []
        for cat, pool in buckets.items():
            for article in pool:
                if article["id"] not in selected_ids:
                    all_remaining.append(article)
        all_remaining.sort(key=lambda a: a["total_score"], reverse=True)

        for article in all_remaining:
            if total_vacant <= 0:
                break
            selected.append(article)
            total_vacant -= 1
            logger.info(
                f"[BACKFILL] {article['category']} → {article['title'][:60]} "
                f"(score {article['total_score']})"
            )

    logger.info(f"Final selection: {len(selected)} articles")
    return selected
