import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from google import genai

logger = logging.getLogger(__name__)

# Limit concurrent Gemini calls to stay safely within TPM limits
_INTER_CALL_DELAY = 0.2  # seconds between calls per worker

SCORING_PROMPT = """You are a top-tier healthcare management consultant and biopharma strategist. Evaluate the news article and score its strategic market impact from 0 to 100.

ARTICLE:
Title: {title}
Summary: {summary}

---
EVALUATION RUBRIC (Mental Sandbox):
Evaluate across 3 dimensions to determine the final score (0-100):

1. Market & Commercial Impact (~45% weight)
- High: Expands TAM significantly (e.g., blockbusters >$1B), strong pricing power, high barriers to entry.
- Low: Crowded indication, extreme pricing pressure, low moat.

2. Strategic Fit & Competitive Landscape (~35% weight)
- High: Disrupts Standard of Care (SoC) for a major indication, solves a major Loss of Exclusivity (LOE) patent cliff, or triggers immediate M&A/licensing.
- Low: Incremental addition (e.g., 3rd line therapy), irrelevant to major portfolio strategies.

3. Scientific Differentiation (~20% weight)
- High: Genuine First-in-class platform validation or explicit Head-to-Head clinical superiority.
- Low: "Me-too" drug, single-arm trial without comparison.

RULES:
- Routine updates (e.g., small trial enrollments, minor executive shifts without strategic context, generic launches) MUST score below 40.
- "Other" category (non-pharma/biotech news) ALWAYS scores 0.

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "category": "Regulatory|Clinical_RD|Corporate_Financial|Commercial_Market|Other",
  "score": <integer 0-100>,
  "strategic_implication": "<1-2 sentences explaining EXACTLY HOW this news shifts the competitive landscape, alters the standard of care, or impacts commercial viability>",
  "reasoning": "<Concise justification citing the 3 dimensions. e.g., 'High commercial potential due to large TAM, but low scientific differentiation as a me-too PD-1.'>"
}}"""


def _call_gemini(title: str, summary: str, client: genai.Client, retries: int = 3) -> dict | None:
    prompt = SCORING_PROMPT.format(title=title, summary=summary or "(no summary available)")
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                },
            )

            # Safety / empty response guard
            candidates = getattr(response, "candidates", [])
            if not candidates:
                logger.warning(f"No candidates returned (safety block?) for: {title[:60]}")
                return None

            finish_reason = str(getattr(candidates[0], "finish_reason", ""))
            if finish_reason and "STOP" not in finish_reason and finish_reason not in ("None", "1"):
                logger.warning(f"Unexpected finish_reason={finish_reason} for: {title[:60]}")
                return None

            try:
                text = response.text.strip()
            except Exception as e:
                logger.warning(f"Response text unavailable (safety block?) for: {title[:60]}: {e}")
                return None

            result = json.loads(text)
            time.sleep(_INTER_CALL_DELAY)
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1} for '{title[:50]}': {e}")
            if attempt < retries - 1:
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Gemini API error on attempt {attempt + 1} for '{title[:50]}': {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def score_articles(articles: list[dict]) -> list[dict]:
    """
    Score and classify each article using Gemini.
    Returns articles with added scoring fields; drops 'Other' or failed articles.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key, http_options={"timeout": 60})

    def score_one(idx_article):
        idx, article = idx_article
        result = _call_gemini(article["title"], article["summary"], client)
        return idx, article, result

    total_timeout = max(300, len(articles) * 15)
    scored_map = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(score_one, (i, a)): i
            for i, a in enumerate(articles)
        }
        try:
            for future in as_completed(futures, timeout=total_timeout):
                idx, article, result = future.result()
                logger.info(f"Scored [{idx + 1}/{len(articles)}]: {article['title'][:70]}")
                if result is None:
                    logger.warning(f"Skipping article (scoring failed): {article['title'][:60]}")
                    continue
                category = result.get("category", "Other")
                score = result.get("score", 0)
                if category == "Other" or score == 0:
                    continue
                scored_map[idx] = {
                    **article,
                    "category": category,
                    "score": score,
                    "strategic_implication": result.get("strategic_implication", ""),
                    "reasoning": result.get("reasoning", ""),
                }
        except FuturesTimeoutError:
            logger.error(
                f"Scoring timed out after {total_timeout}s; "
                f"proceeding with {len(scored_map)} scored articles so far."
            )

    scored = [scored_map[i] for i in sorted(scored_map)]
    logger.info(f"Scored {len(scored)} eligible articles out of {len(articles)}")
    return scored
