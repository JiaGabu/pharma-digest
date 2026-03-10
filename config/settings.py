RSS_FEEDS = [
    "https://www.fiercepharma.com/rss/xml",
    "https://endpts.com/feed",
    "https://www.statnews.com/feed/",
    "https://www.biospace.com/all-news.rss",
    "https://feeds.bbci.co.uk/news/topics/cg1lkvgedv8t/rss.xml",
    "https://www.biopharmadive.com/feeds/news/",
]

# Daily article quota per category
CATEGORY_QUOTAS = {
    "Regulatory": 3,
    "Clinical_RD": 3,
    "Corporate_Financial": 2,
    "Commercial_Market": 1,
}

# Minimum score to be eligible for selection
PASS_THRESHOLDS = {
    "Regulatory": 65,
    "Clinical_RD": 65,
    "Corporate_Financial": 65,
    "Commercial_Market": 70,
}

# Display names for email formatting
CATEGORY_DISPLAY = {
    "Regulatory": "Regulatory",
    "Clinical_RD": "Clinical / R&D",
    "Corporate_Financial": "Corporate & Financial",
    "Commercial_Market": "Commercial & Market Access",
}

# Category display order in email
CATEGORY_ORDER = ["Regulatory", "Clinical_RD", "Corporate_Financial", "Commercial_Market"]

# If same event covered by 3+ distinct sources, force include
MULTI_SOURCE_THRESHOLD = 3

# Only fetch articles published within the last N hours (based on pubDate)
FETCH_HOURS = 24

RECIPIENT_EMAIL = "ctc04114@gmail.com"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
