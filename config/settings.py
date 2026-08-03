import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

# Gemini API (free tier)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"

# Database — PostgreSQL on Render (DATABASE_URL set automatically), SQLite locally
_raw_db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/database/affiliate.db")
# Render gives postgres:// but SQLAlchemy requires postgresql://
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1)

# Affiliate Networks
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY", "")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY", "")
CLICKBANK_API_KEY = os.getenv("CLICKBANK_API_KEY", "")
SHAREASALE_TOKEN = os.getenv("SHAREASALE_TOKEN", "")
SHAREASALE_SECRET = os.getenv("SHAREASALE_SECRET", "")
SHAREASALE_MERCHANT_ID = os.getenv("SHAREASALE_MERCHANT_ID", "")

# Email (SMTP)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")
FROM_NAME = os.getenv("FROM_NAME", "Affiliate Newsletter")

# Social Media
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", "")

# SEO / Search APIs
SERP_API_KEY = os.getenv("SERP_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")

# App settings
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))  # Render sets PORT automatically
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-random-string-here")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Scheduling intervals (seconds)
CONTENT_CREATION_INTERVAL = 3600 * 6     # every 6 hours
SOCIAL_POST_INTERVAL = 3600 * 4          # every 4 hours
EMAIL_CAMPAIGN_INTERVAL = 3600 * 24      # daily
ANALYTICS_INTERVAL = 3600 * 1            # hourly
PRODUCT_DISCOVERY_INTERVAL = 3600 * 12   # twice daily
NICHE_RESEARCH_INTERVAL = 3600 * 24 * 7  # weekly
SEO_AUDIT_INTERVAL = 3600 * 24           # daily
LINK_CHECK_INTERVAL = 3600 * 6           # every 6 hours

# Content settings — ALL high-value ClickBank niches
TARGET_NICHES = os.getenv("TARGET_NICHES", ",".join([
    "weight loss",
    "diabetes blood sugar",
    "keto diet",
    "anxiety stress sleep",
    "make money online",
    "manifestation law of attraction",
    "relationship dating men",
    "relationship dating women",
    "dog training",
    "survival prepping",
    "joint pain arthritis",
    "muscle building",
    "tinnitus hearing",
    "memory brain health",
    "solar off grid",
    "golf improvement",
    "cat health",
    "vision eyesight",
    "gardening homesteading",
    "forex trading",
])).split(",")

CONTENT_LANGUAGES = ["en"]
MIN_ARTICLE_WORDS = 1500
MAX_ARTICLES_PER_DAY = 10

# ClickBank settings
CLICKBANK_NICKNAME = os.getenv("CLICKBANK_NICKNAME", "")  # Your ClickBank account nickname
CLICKBANK_MIN_GRAVITY = float(os.getenv("CLICKBANK_MIN_GRAVITY", "20"))
CLICKBANK_MIN_COMMISSION = float(os.getenv("CLICKBANK_MIN_COMMISSION", "30"))

# Customer acquisition channels (enable/disable)
ENABLE_SEO = os.getenv("ENABLE_SEO", "true").lower() == "true"
ENABLE_PINTEREST = os.getenv("ENABLE_PINTEREST", "false").lower() == "true"
ENABLE_QUORA = os.getenv("ENABLE_QUORA", "false").lower() == "true"
ENABLE_YOUTUBE_SCRIPTS = os.getenv("ENABLE_YOUTUBE_SCRIPTS", "true").lower() == "true"
ENABLE_TWITTER = os.getenv("ENABLE_TWITTER", "false").lower() == "true"
ENABLE_REDDIT = os.getenv("ENABLE_REDDIT", "false").lower() == "true"
ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "false").lower() == "true"

# Bluesky
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD", "")

# WordPress.com publishing
WORDPRESS_SITE = os.getenv("WORDPRESS_SITE", "healthreviewshub5.wordpress.com")
WORDPRESS_TOKEN = os.getenv("WORDPRESS_TOKEN", "")
WORDPRESS_CLIENT_ID = os.getenv("WORDPRESS_CLIENT_ID", "143041")
WORDPRESS_CLIENT_SECRET = os.getenv("WORDPRESS_CLIENT_SECRET", "")

# Blogger (Google) — primary publishing platform
BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "")
BLOGGER_BLOG_URL = os.getenv("BLOGGER_BLOG_URL", "https://producttrustreview.blogspot.com")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "")
