# CLAUDE.md - Daily Pharma News Digest

> **Documentation Version**: 1.0
> **Last Updated**: 2026-03-11
> **Project**: Daily Pharma News Digest
> **Description**: Automated system that fetches pharma RSS feeds every 24 hours, scores and classifies articles using Gemini 1.5 Pro, selects the top 8 articles by category quota, and sends a formatted HTML digest to ctc04114@gmail.com at 07:00 Taipei time via Gmail OAuth.
> **Features**: GitHub auto-backup, Task agents, technical debt prevention

## 🚨 CRITICAL RULES - READ FIRST

### ❌ ABSOLUTE PROHIBITIONS
- **NEVER** create new files in root directory → use `src/` for modules
- **NEVER** commit `.env`, `credentials.json`, or `token.json` → all in .gitignore
- **NEVER** hardcode API keys → always use `os.environ` via dotenv
- **NEVER** use `find`, `grep`, `cat`, `head`, `tail`, `ls` → use Read, Grep, Glob tools
- **NEVER** create duplicate modules (scorer_v2.py, selector_new.py) → extend originals
- **NEVER** create documentation files unless explicitly asked

### 📝 MANDATORY REQUIREMENTS
- **COMMIT** after every completed task
- **GITHUB BACKUP** after every commit: `git push origin main`
- **READ FILES FIRST** before editing
- **SEARCH FIRST** before creating new files

### 🔄 RULE ACKNOWLEDGMENT
Before starting ANY task: "✅ CRITICAL RULES ACKNOWLEDGED"

## 🏗️ PROJECT STRUCTURE

```
pharma-digest/
├── main.py                          # Entry point / orchestrator
├── run.sh                           # Shell wrapper for launchd
├── com.pharmadigest.daily.plist     # macOS launchd schedule (07:00 Taipei)
├── requirements.txt
├── .env                             # GEMINI_API_KEY (NOT committed)
├── credentials.json                 # Gmail OAuth credentials (NOT committed)
├── token.json                       # Gmail OAuth token (NOT committed, auto-generated)
├── config/
│   └── settings.py                  # All constants: feeds, quotas, thresholds
├── src/
│   ├── fetcher.py                   # RSS fetching (last 24h by pubDate)
│   ├── scorer.py                    # Gemini 1.5 Pro classification + scoring
│   ├── selector.py                  # Quota selection + multi-source forced inclusion
│   ├── formatter.py                 # HTML email formatter
│   └── gmail_sender.py              # Gmail OAuth sender
└── logs/
    ├── app.log                      # Application logs
    └── launchd.log                  # launchd stdout
```

## 🔧 TECHNOLOGY STACK

- **Language**: Python 3
- **AI**: Google Gemini 1.5 Pro (`google-generativeai`)
- **RSS**: `feedparser`
- **Email**: Gmail API via OAuth2 (`google-api-python-client`)
- **Config**: `python-dotenv`
- **Scheduler**: macOS `launchd`

## 📋 BUSINESS LOGIC

### Article Fetch
- Fetch all 6 RSS feeds
- Filter to articles published in the **last 24 hours** (by `pubDate`)
- Deduplicate by URL

### Scoring (Gemini 1.5 Pro)
- Categories: `Regulatory`, `Clinical_RD`, `Corporate_Financial`, `Commercial_Market`
- Pass thresholds: Regulatory 65, Clinical_RD 65, Corporate_Financial 65, Commercial_Market 70
- Bonus cap: +40 per article

### Selection Rules
1. **Forced inclusion**: same event covered by 3+ distinct sources → best version (longest summary) forced in
2. **Quota**: Regulatory 3, Clinical_RD 3, Corporate_Financial 2, Commercial_Market 1
3. **Backfill**: if a category has fewer eligible articles than its quota, vacant slots filled by highest-scoring unused articles from other categories

### Email
- Subject: `Pharma News Digest｜YYYY/MM/DD`
- Articles grouped by category, sorted by score desc
- Each article: [score] Title / Source | Date / One-line English summary / Link

## 🔑 ENVIRONMENT VARIABLES

```
GEMINI_API_KEY=...   # Gemini 1.5 Pro API key
```

## 🚀 COMMON COMMANDS

```bash
# Install dependencies
cd ~/Desktop/pharma-digest
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# First run (triggers Gmail OAuth in browser)
python3 main.py

# Install launchd job
cp com.pharmadigest.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.pharmadigest.daily.plist

# Uninstall launchd job
launchctl unload ~/Library/LaunchAgents/com.pharmadigest.daily.plist

# Check launchd status
launchctl list | grep pharmadigest
```

## 🔑 SENSITIVE FILES (never commit)

| File | Purpose |
|------|---------|
| `.env` | Gemini API key |
| `credentials.json` | Gmail OAuth app credentials |
| `token.json` | Gmail OAuth user token (auto-generated on first run) |
