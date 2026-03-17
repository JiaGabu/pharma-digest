from collections import defaultdict
from datetime import datetime, timezone, timedelta

from config.settings import CATEGORY_DISPLAY, CATEGORY_ORDER

TAIPEI_TZ = timezone(timedelta(hours=8))


def _format_date(pub_date) -> str:
    if pub_date is None:
        return "N/A"
    taipei_time = pub_date.astimezone(TAIPEI_TZ)
    return taipei_time.strftime("%Y/%m/%d")


def format_email(articles: list[dict]) -> tuple[str, str]:
    today = datetime.now(TAIPEI_TZ).strftime("%Y/%m/%d")
    subject = f"Daily Pharma News｜{today}"

    groups: dict[str, list[dict]] = defaultdict(list)
    for article in articles:
        groups[article["category"]].append(article)

    for cat in groups:
        groups[cat].sort(key=lambda a: a["score"], reverse=True)

    category_html_parts = []
    for cat in CATEGORY_ORDER:
        cat_articles = groups.get(cat, [])
        if not cat_articles:
            continue

        display_name = CATEGORY_DISPLAY.get(cat, cat)
        article_html_parts = []
        for a in cat_articles:
            pub_str = _format_date(a.get("published"))
            score = a.get("score", 0)
            image_url = a.get("image_url", "")

            image_html = (
                f'<img src="{image_url}" class="article-image" alt="" />'
                if image_url else ""
            )

            article_html_parts.append(f"""
            <div class="article">
              {image_html}
              <div class="article-header">
                <span class="article-title">{a['title']}</span>
              </div>
              <div class="meta">
                <span class="source">{a['source']}</span>
                <span class="dot-divider">·</span>
                <span class="date">{pub_str}</span>
                <span class="dot-divider">·</span>
                <span class="score-badge">{score}</span>
              </div>
              <div class="strategic-implication">{a.get('strategic_implication', '')}</div>
              <div class="reasoning">{a.get('reasoning', '')}</div>
              <a class="link" href="{a['link']}">Read full article →</a>
            </div>""")

        article_html = '<hr class="article-divider">'.join(article_html_parts)

        category_html_parts.append(f"""
        <div class="category-block">
          <div class="category-header">
            <span class="category-label">{display_name}</span>
          </div>
          {article_html}
        </div>""")

    total_count = len(articles)
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <title>Pharma News Digest｜{today}</title>
  <style>
    :root {{
      --navy:   #0D1B2A;
      --navy2:  #162032;
      --gold:   #C9A84C;
      --gold-light: #E8C97A;
      --text:   #1A1A2E;
      --muted:  #6B7280;
      --border: #E5E8EF;
      --bg:     #F4F6FA;
      --white:  #FFFFFF;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background-color: var(--bg);
      font-family: 'Noto Sans', sans-serif;
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }}

    .wrapper {{
      max-width: 660px;
      margin: 24px auto;
      background: var(--white);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 4px 24px rgba(13,27,42,0.10);
    }}

    /* ── Header ── */
    .header {{
      background: var(--navy);
      padding: 32px 36px 28px;
      position: relative;
      border-bottom: 3px solid var(--gold);
    }}
    .header-eyebrow {{
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--gold);
      margin-bottom: 8px;
    }}
    .header h1 {{
      font-size: 26px;
      font-weight: 700;
      color: var(--white);
      letter-spacing: 0.3px;
      margin-bottom: 6px;
    }}
    .header-meta {{
      font-size: 14px;
      color: rgba(255,255,255,0.45);
      font-weight: 400;
    }}

    /* ── Body ── */
    .body-content {{
      padding: 28px 32px 36px;
    }}

    /* ── Category block ── */
    .category-block {{
      margin-bottom: 32px;
    }}
    .category-header {{
      display: flex;
      align-items: center;
      margin-bottom: 16px;
      gap: 12px;
    }}
    .category-label {{
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--navy);
      padding: 5px 12px;
      border: 1.5px solid var(--navy);
      border-radius: 3px;
    }}
    .category-header::after {{
      content: '';
      flex: 1;
      height: 1px;
      background: var(--border);
    }}

    /* ── Article card ── */
    .article {{
      padding: 20px 0;
    }}

    .article-image {{
      width: 100%;
      max-height: 200px;
      object-fit: cover;
      border-radius: 6px;
      margin-bottom: 12px;
      display: block;
    }}

    .article-divider {{
      border: none;
      border-top: 1px solid var(--border);
      margin: 0;
    }}

    .article-header {{
      margin-bottom: 7px;
    }}
    .score-badge {{
      display: inline-block;
      background: var(--gold);
      color: var(--navy);
      font-size: 11px;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 3px;
      letter-spacing: 0.3px;
      vertical-align: middle;
    }}
    .article-title {{
      font-size: 17px;
      font-weight: 600;
      color: var(--text);
      line-height: 1.45;
    }}

    .meta {{
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 8px;
      padding-left: 0;
    }}
    .source {{
      font-weight: 500;
    }}
    .dot-divider {{
      margin: 0 5px;
      color: var(--border);
    }}

    .strategic-implication {{
      font-size: 15px;
      color: #1e3a5f;
      font-style: italic;
      line-height: 1.6;
      margin-bottom: 8px;
      padding: 8px 12px;
      background: #f0f5ff;
      border-left: 3px solid var(--gold);
      border-radius: 0 4px 4px 0;
    }}

    .reasoning {{
      font-size: 13px;
      color: #9CA3AF;
      line-height: 1.6;
      margin-bottom: 10px;
    }}

    .link {{
      display: inline-block;
      font-size: 13px;
      font-weight: 600;
      color: var(--gold);
      text-decoration: none;
      letter-spacing: 0.3px;
      border-bottom: 1px solid transparent;
      transition: border-color 0.2s;
    }}
    .link:hover {{
      border-bottom-color: var(--gold-light);
    }}

    /* ── Footer ── */
    .footer {{
      background: var(--navy);
      padding: 16px 32px;
      font-size: 12.5px;
      color: rgba(255,255,255,0.3);
      text-align: center;
      letter-spacing: 0.5px;
      border-top: 1px solid rgba(201,168,76,0.25);
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>Daily Pharma News</h1>
      <div class="header-meta">{today} &nbsp;·&nbsp; {total_count} articles curated</div>
    </div>
    <div class="body-content">
      {''.join(category_html_parts)}
    </div>
    <div class="footer">
      Generated automatically · 07:00 Taipei Time · For personal use only
    </div>
  </div>
</body>
</html>"""

    return subject, body
