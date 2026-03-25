RSS_FEEDS = [
    "https://www.fiercepharma.com/rss/xml",
    "https://www.fiercebiotech.com/rss/xml",
    "https://feeds.reuters.com/reuters/healthNews",
    "https://www.biospace.com/all-news.rss",
    "https://feeds.bbci.co.uk/news/topics/cg1lkvgedv8t/rss.xml",
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.pharmavoice.com/feeds/news/",
]

# Daily article quota per category
CATEGORY_QUOTAS = {
    "Regulatory": 3,
    "Clinical_RD": 3,
    "Corporate_Financial": 2,
    "Commercial_Market": 1,
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

# If same event covered by 3+ distinct sources, force include BEST article only
MULTI_SOURCE_THRESHOLD = 3

# Only fetch articles published within the last N hours (based on pubDate)
FETCH_HOURS = 24

RECIPIENT_EMAIL = "ctc04114@gmail.com"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
