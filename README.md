# Daily Pharma News Digest

Automated daily pharmaceutical industry news digest. Fetches 6 RSS sources, scores articles with Google Gemini 1.5 Pro, selects the top 8 by category quota, and emails a formatted HTML digest to your Gmail at 07:00 Taipei time.

## Setup

### 1. Install dependencies

```bash
cd ~/Desktop/pharma-digest
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Place Gmail credentials

Put your `credentials.json` (Google Cloud OAuth Desktop App) in the project root.

### 4. First run (OAuth setup)

```bash
python3 main.py
```

A browser window will open for Gmail authorization. After approving, `token.json` is saved automatically. Subsequent runs are fully automated.

### 5. Schedule daily runs (macOS launchd)

```bash
cp com.pharmadigest.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.pharmadigest.daily.plist
```

Runs every day at **07:00 Taipei time** (requires macOS timezone set to Asia/Taipei).

## Article Selection Logic

| Category | Quota | Pass Threshold |
|----------|-------|----------------|
| Regulatory | 3 | 65 |
| Clinical / R&D | 3 | 65 |
| Corporate & Financial | 2 | 65 |
| Commercial & Market Access | 1 | 70 |

- Articles published in the **last 24 hours** only (by RSS pubDate)
- Same event covered by **3+ sources** → force included regardless of score
- Category quota **vacancies** are backfilled by highest-scoring articles from other categories

## Tech Stack

- Python 3, feedparser, google-generativeai, google-api-python-client, python-dotenv
- Scheduler: macOS launchd
