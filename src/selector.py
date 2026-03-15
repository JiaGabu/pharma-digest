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
    words = re.sub(r"[^a-z0-9\s]", " ", title.lower()).split()
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _detect_multi_source_events(articles: list[dict]) -> list[list[dict]]:
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


def _info_score(article: dict) -> float:
    """
    Score information richness by counting specific facts rather than raw length.
    Looks for: dollar amounts, percentages, phase numbers, p-values, trial IDs,
    regulatory terms, and numeric milestones.
    """
    text = " ".join([
        article.get("title", ""),
        article.get("summary", ""),
        article.get("one_line_summary", ""),
    ])
    specifics = re.findall(
        r'\$[\d.,]+\s*(?:[MBK]|million|billion)?'   # dollar amounts
        r'|[\d.]+\s*(?:%|percent)'                   # percentages
        r'|[Pp]hase\s*[0-9I-V]+'                     # clinical phases
        r'|[Pp]\s*[<>=]\s*0\.[\d]+'                  # p-values
        r'|\b(?:FDA|EMA|NDA|BLA|sNDA|sBLA|PDUFA|IND|AdCom|CRL)\b'  # regulatory
        r'|\b\d{4}\b'                                # specific years
        r'|\b\d+\s*(?:mg|mg/kg|mcg|kg)\b',          # dosing details
        text,
    )
    # Secondary: normalized summary length (caps at 1.0 for summaries ≥500 chars)
    length_bonus = min(len(article.get("summary", "")) / 500, 1.0)
    return len(specifics) * 2 + length_bonus


def _best_in_group(group: list[dict]) -> dict:
    """Pick the most information-rich article using fact density, not raw length."""
    return max(group, key=_info_score)


def select_articles(scored: list[dict]) -> list[dict]:
    """
    Select up to 8 articles according to quotas and rules:
    1. Detect similar-topic groups; for each group keep only the most info-rich article
       and exclude all others from selection (those slots go to backfill).
    2. For groups covered by 3+ distinct sources, force-include the best article.
    3. Fill each category quota with: priority candidates first, then highest-scoring eligible.
    4. Strictly respect quotas — never exceed per-category limits.
    5. If a category has fewer eligible articles than its quota, backfill from other categories.
    """
    # --- Step 1: Deduplicate similar-topic articles across all groups ---
    event_groups = _detect_multi_source_events(scored)
    priority_ids = set()
    excluded_ids: set[str] = set()

    for group in event_groups:
        best = _best_in_group(group)
        distinct_sources = {a["source"] for a in group}

        # Exclude every non-best article in this group from selection
        for article in group:
            if article["id"] != best["id"]:
                excluded_ids.add(article["id"])
                logger.info(
                    f"[DEDUP] Excluded duplicate: {article['title'][:60]} "
                    f"(kept: {best['title'][:60]})"
                )

        # Force-include best if 3+ distinct sources cover the same event
        if len(distinct_sources) >= MULTI_SOURCE_THRESHOLD:
            priority_ids.add(best["id"])
            logger.info(
                f"[PRIORITY] {len(distinct_sources)} sources → {best['title'][:60]}"
            )

    # --- Step 2: Bucket eligible articles by category (excluding duplicates) ---
    buckets: dict[str, list[dict]] = defaultdict(list)
    for article in scored:
        if article["id"] in excluded_ids:
            continue
        threshold = PASS_THRESHOLDS.get(article["category"], 999)
        if article["total_score"] >= threshold:
            buckets[article["category"]].append(article)

    # Sort each bucket: priority articles first, then by score descending
    for cat in buckets:
        buckets[cat].sort(
            key=lambda a: (a["id"] in priority_ids, a["total_score"]),
            reverse=True
        )

    # --- Step 3: Fill per-category quotas strictly ---
    selected = []
    selected_ids = set()
    quotas = dict(CATEGORY_QUOTAS)

    for cat in CATEGORY_ORDER:
        quota = quotas.get(cat, 0)
        pool = buckets.get(cat, [])
        taken = 0
        for article in pool:
            if taken >= quota:
                break
            if article["id"] not in selected_ids:
                selected.append(article)
                selected_ids.add(article["id"])
                taken += 1
        if taken < quota:
            logger.info(f"Category '{cat}' filled {taken}/{quota} slots")

    # --- Step 4: Backfill vacant slots from other categories ---
    total_target = sum(CATEGORY_QUOTAS.values())
    vacant = total_target - len(selected)

    if vacant > 0:
        all_remaining = []
        for cat, pool in buckets.items():
            for article in pool:
                if article["id"] not in selected_ids:
                    all_remaining.append(article)
        all_remaining.sort(key=lambda a: a["total_score"], reverse=True)

        for article in all_remaining:
            if vacant <= 0:
                break
            selected.append(article)
            selected_ids.add(article["id"])
            vacant -= 1
            logger.info(
                f"[BACKFILL] {article['category']} → {article['title'][:60]} "
                f"(score {article['total_score']})"
            )

    logger.info(f"Final selection: {len(selected)} articles")
    return selected
