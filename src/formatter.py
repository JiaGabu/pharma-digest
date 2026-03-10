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
    """
    Returns (subject, html_body) for the daily digest email.
    Articles are grouped by category in the defined order, sorted by score desc.
    """
    today = datetime.now(TAIPEI_TZ).strftime("%Y/%m/%d")
    subject = f"Pharma News Digest｜{today}"

    # Group by category
    groups: dict[str, list[dict]] = defaultdict(list)
    for article in articles:
        groups[article["category"]].append(article)

    for cat in groups:
        groups[cat].sort(key=lambda a: a["total_score"], reverse=True)

    # Build HTML
    category_html_parts = []
    for cat in CATEGORY_ORDER:
        cat_articles = groups.get(cat, [])
        if not cat_articles:
            continue

        display_name = CATEGORY_DISPLAY.get(cat, cat)
        article_html = ""
        for a in cat_articles:
            pub_str = _format_date(a.get("published"))
            article_html += f"""
            <div class="article">
              <div class="article-title">
                <span class="score">[{a['total_score']}]</span> {a['title']}
              </div>
              <div class="meta">Source: {a['source']} | {pub_str}</div>
              <div class="summary">{a.get('one_line_summary', '')}</div>
              <div><a class="link" href="{a['link']}">Read full article →</a></div>
            </div>"""

        category_html_parts.append(f"""
        <div class="category">
          <div class="category-title">{display_name}</div>
          {article_html}
        </div>""")

    total = len(articles)
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pharma News Digest｜{today}</title>
  <style>
    body {{
      margin: 0; padding: 0;
      background-color: #f0f2f5;
      font-family: 'Helvetica Neue', Arial, sans-serif;
      color: #222;
    }}
    .wrapper {{
      max-width: 680px;
      margin: 30px auto;
      background: #ffffff;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }}
    .header {{
      background: #1A1A1A;
      color: #ffffff;
      padding: 28px 30px;
      text-align: center;
    }}
    .header h1 {{
      margin: 0 0 6px;
      font-size: 22px;
      letter-spacing: 0.5px;
    }}
    .header p {{
      margin: 0;
      color: #aaaaaa;
      font-size: 13px;
    }}
    .body-content {{
      padding: 20px 30px 30px;
    }}
    .category {{
      margin-bottom: 28px;
    }}
    .category-title {{
      background: #007BFF;
      color: #ffffff;
      padding: 8px 14px;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      border-radius: 4px;
      margin-bottom: 12px;
    }}
    .article {{
      border-left: 3px solid #007BFF;
      padding: 10px 14px;
      margin-bottom: 14px;
      background: #f8f9fa;
      border-radius: 0 4px 4px 0;
    }}
    .article-title {{
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 5px;
      line-height: 1.4;
    }}
    .score {{
      color: #007BFF;
      font-weight: 700;
    }}
    .meta {{
      font-size: 11px;
      color: #888888;
      margin-bottom: 6px;
    }}
    .summary {{
      font-size: 13px;
      color: #444444;
      line-height: 1.5;
      margin-bottom: 8px;
    }}
    .link {{
      color: #007BFF;
      text-decoration: none;
      font-size: 12px;
      font-weight: 600;
    }}
    .footer {{
      background: #1A1A1A;
      color: #666666;
      text-align: center;
      padding: 16px;
      font-size: 11px;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>Pharma News Digest</h1>
      <p>{today} &nbsp;|&nbsp; {total} articles selected</p>
    </div>
    <div class="body-content">
      {''.join(category_html_parts)}
    </div>
    <div class="footer">
      Generated automatically every day at 07:00 Taipei Time
    </div>
  </div>
</body>
</html>"""

    return subject, body
