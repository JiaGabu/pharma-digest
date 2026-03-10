import json
import logging
import os
import time

import google.generativeai as genai

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are a senior pharmaceutical industry analyst. Analyze the article below and score it using the exact rubric provided.

ARTICLE:
Title: {title}
Summary: {summary}

---
SCORING RUBRIC:

## Step 1: Classify into ONE category (or "Other" if not pharma/biotech relevant)
- Regulatory
- Clinical_RD
- Corporate_Financial
- Commercial_Market
- Other

## Step 2: Assign base score based on the event type

### Clinical_RD base scores:
- Phase 3 data readout: 55
- Phase 2 data readout: 35
- Phase 1 data readout: 25
- Phase 3 trial termination: 55
- Phase 2 trial termination: 35
- Phase 1 trial termination: 0 (not included)

### Regulatory base scores:
- Regulatory framework/policy change affecting entire treatment paradigm: 65
- FDA approval or rejection (CRL): 60
- New Black Box Warning added: 55
- EMA approval or rejection: 50
- AdCom meeting result: 50
- Label expansion or restriction: 45 (add +10 if new indication expands target market >50%)
- PDUFA date set: 30

### Corporate_Financial base scores:
- M&A deal $10B+: 70
- M&A deal $1B–$10B: 55
- M&A deal $500M–$1B: 40
- M&A deal <$500M: 0 (not included)
- Licensing deal $1B+: 60
- Licensing deal $500M–$1B: 45
- Licensing deal <$500M: 0 (not included)
- Patent cliff or major patent litigation: 55
- Large share buyback program: 50
- Institutional holding change >5%: 55
- Institutional holding change 1%–5%: 40
- Institutional holding change <1%: 0 (not included)
- CEO or CFO change: 50
- CMO, CSO or other scientific leadership change: 35
- IPO: 45

### Commercial_Market base scores:
- IRA drug price negotiation result: 65
- CMS Medicare/Medicaid coverage decision: 60
- Major commercial insurance formulary change: 50
- Official product launch: 50
- Earnings beat/miss >20% or absolute gap >$500M: 45
- Pricing strategy announcement: 40
- Significant market share change: 40

## Step 3: Add bonus points (HARD CAP: bonus total cannot exceed 40 for any category)

### Clinical_RD bonuses:
- Large market (indication revenue potential $1B+): +12 (if Phase 1: +20 instead)
- First-in-class: +10
- High unmet need (few existing treatment options): +10
- Best-in-class with clear comparator data: +8

### Regulatory bonuses:
- Large market (indication revenue potential $1B+): +12
- First-in-class or only approved therapy: +10
- Directly changes competitive landscape in TA (winners and losers, not just market expansion): +10
- Involves major company's core product: +8

### Corporate_Financial bonuses:
- Directly changes competitive landscape in TA: +15
- Involves platform technology (not a single drug): +12
- Buyer or seller is industry leader ($50B+ market cap): +8
- Deal covers multiple indication pipelines: +5

### Commercial_Market bonuses:
- Affects $1B+ market: +15
- Directly changes competitive landscape in TA: +12
- Involves core product of industry leader: +8
- Affects coverage/formulary status of multiple competitors: +5

## Pass thresholds (minimum score to be eligible):
- Regulatory: 65
- Clinical_RD: 65
- Corporate_Financial: 65
- Commercial_Market: 70
- Other: not eligible

## RULES:
- If base score rules say "not included" or score is 0, set total_score to 0
- bonus_score is capped at 40; never exceed this cap
- total_score = base_score + bonus_score
- "Other" category always has total_score of 0

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "category": "Regulatory|Clinical_RD|Corporate_Financial|Commercial_Market|Other",
  "base_score": <integer>,
  "bonus_score": <integer>,
  "total_score": <integer>,
  "one_line_summary": "<one sentence in English summarizing the key news>",
  "reasoning": "<1-2 sentences explaining classification and scoring>"
}}"""


def _call_gemini(title: str, summary: str, model, retries: int = 3) -> dict | None:
    prompt = SCORING_PROMPT.format(title=title, summary=summary or "(no summary available)")
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Gemini API error on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def score_articles(articles: list[dict]) -> list[dict]:
    """
    Score and classify each article using Gemini 1.5 Pro.
    Returns articles with added scoring fields; drops 'Other' or failed articles.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")

    scored = []
    for i, article in enumerate(articles):
        logger.info(f"Scoring [{i + 1}/{len(articles)}]: {article['title'][:70]}")
        result = _call_gemini(article["title"], article["summary"], model)

        if result is None:
            logger.warning(f"Skipping article (scoring failed): {article['title'][:60]}")
            continue

        category = result.get("category", "Other")
        total_score = result.get("total_score", 0)

        if category == "Other" or total_score == 0:
            continue

        scored.append(
            {
                **article,
                "category": category,
                "base_score": result.get("base_score", 0),
                "bonus_score": result.get("bonus_score", 0),
                "total_score": total_score,
                "one_line_summary": result.get("one_line_summary", ""),
                "reasoning": result.get("reasoning", ""),
            }
        )
        # Small delay to avoid rate limiting
        time.sleep(0.5)

    logger.info(f"Scored {len(scored)} eligible articles out of {len(articles)}")
    return scored
