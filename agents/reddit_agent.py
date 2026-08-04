"""
Reddit Agent
Posts affiliate articles to relevant health/wellness subreddits as
genuine discussion posts. One article per subreddit, spaced to avoid spam.
"""
import logging
import time
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, SocialPost, ContentStatus
from config.settings import (
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USERNAME, REDDIT_PASSWORD,
)

logger = logging.getLogger(__name__)

# Subreddits that allow health/supplement discussion posts (no direct spam)
NICHE_SUBREDDITS = {
    "weight loss":          ["WeightLossSupport", "loseit", "Fitness"],
    "keto diet":            ["keto", "ketodiet", "ketorecipes"],
    "diabetes blood sugar": ["diabetes", "diabetes_t2", "prediabetes"],
    "anxiety stress sleep": ["Anxiety", "sleep", "stress"],
    "joint pain arthritis": ["ChronicPain", "Arthritis"],
    "memory brain health":  ["Nootropics", "LifeProTips"],
    "muscle building":      ["bodybuilding", "gainit", "naturalbodybuilding"],
    "make money online":    ["passive_income", "Entrepreneur", "WorkOnline"],
    "manifestation":        ["lawofattraction", "Meditation"],
    "dog training":         ["Dogtraining", "dogs"],
    "vision eyesight":      ["optometry", "HealthyLiving"],
    "tinnitus hearing":     ["tinnitus", "hearing"],
    "default":              ["HealthyLiving", "supplements", "Wellbeing"],
}

SYSTEM_PROMPT = """You are writing a helpful Reddit post for a health community.
Rules:
- Sound like a genuine person sharing useful information
- Lead with the value/insight, not the product
- URL goes naturally at the end: "Full details here: [URL]"
- No salesy language, no "click here", no "limited time"
- Match the casual, helpful tone of Reddit
Return JSON only."""


def _is_configured() -> bool:
    return bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET and REDDIT_USERNAME and REDDIT_PASSWORD)


class RedditAgent(BaseAgent):
    name = "RedditAgent"

    def execute(self, **kwargs) -> dict:
        if not _is_configured():
            logger.warning("Reddit credentials not set — skipping")
            return {"skipped": True, "reason": "Reddit credentials not configured"}

        article = self._get_unposted_article()
        if not article:
            logger.info("No new articles to post to Reddit")
            return {"posted": 0}

        subreddits = self._pick_subreddits(article)
        posted = 0
        for sub in subreddits[:2]:  # max 2 subreddits per run to avoid spam
            success = self._post_to_subreddit(article, sub)
            if success:
                self._mark_posted(article["id"], sub)
                posted += 1
                time.sleep(30)  # space posts out

        return {"posted": posted, "article": article["title"], "subreddits": subreddits[:2]}

    def _get_unposted_article(self) -> dict | None:
        """Get the latest published article not yet posted to Reddit."""
        with get_db() as db:
            posted_content_ids = {
                p.content_id for p in
                db.query(SocialPost).filter(SocialPost.platform == "reddit").all()
                if p.content_id
            }
            article = (
                db.query(ContentPiece)
                .filter(
                    ContentPiece.status == ContentStatus.published,
                    ContentPiece.published_url.isnot(None),
                    ~ContentPiece.id.in_(posted_content_ids) if posted_content_ids else True,
                )
                .order_by(ContentPiece.published_at.desc())
                .first()
            )
            if article:
                return {
                    "id": article.id,
                    "title": article.title,
                    "url": article.published_url,
                    "keyword": article.target_keyword or "",
                    "meta": article.meta_description or "",
                    "niche": article.target_keyword or "health",
                }
        return None

    def _pick_subreddits(self, article: dict) -> list[str]:
        niche = article.get("niche", "").lower()
        for key, subs in NICHE_SUBREDDITS.items():
            if key in niche or any(word in niche for word in key.split()):
                return subs
        return NICHE_SUBREDDITS["default"]

    def _build_post_content(self, article: dict, subreddit: str) -> dict | None:
        prompt = f"""Write a Reddit post for r/{subreddit} about this article:

Title: {article['title']}
URL: {article['url']}
Topic: {article.get('keyword', '')}
Summary: {article.get('meta', '')}

Return JSON:
{{
  "title": "engaging Reddit post title (not clickbait, max 200 chars)",
  "body": "2-3 paragraph helpful post body. End with: Full article here: {article['url']}"
}}"""
        try:
            return self.ask_claude_json(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"Reddit post content generation failed: {e}")
            return None

    def _post_to_subreddit(self, article: dict, subreddit: str) -> bool:
        content = self._build_post_content(article, subreddit)
        if not content:
            return False
        try:
            import praw
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                username=REDDIT_USERNAME,
                password=REDDIT_PASSWORD,
                user_agent=f"HealthReviewBot/1.0 by u/{REDDIT_USERNAME}",
            )
            sub = reddit.subreddit(subreddit)
            sub.submit(
                title=content.get("title", article["title"])[:300],
                selftext=content.get("body", f"Check this out: {article['url']}"),
            )
            logger.info(f"Reddit: posted to r/{subreddit} — {article['title'][:50]}")
            return True
        except Exception as e:
            logger.error(f"Reddit post to r/{subreddit} failed: {e}")
            return False

    def _mark_posted(self, content_id: int, subreddit: str):
        with get_db() as db:
            db.add(SocialPost(
                content_id=content_id,
                platform="reddit",
                post_text=f"r/{subreddit}",
                status="posted",
                posted_at=datetime.utcnow(),
            ))
