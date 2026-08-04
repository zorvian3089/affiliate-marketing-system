"""
Tumblr Agent
Cross-posts articles to Tumblr. Health, wellness, and supplement
content has an active community there. Uses OAuth 1.0a via requests_oauthlib.
"""
import logging
import requests
from datetime import datetime
from requests_oauthlib import OAuth1
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, SocialPost, ContentStatus
from config.settings import (
    TUMBLR_CONSUMER_KEY, TUMBLR_CONSUMER_SECRET,
    TUMBLR_TOKEN, TUMBLR_TOKEN_SECRET, TUMBLR_BLOG_NAME,
)

logger = logging.getLogger(__name__)
TUMBLR_API = "https://api.tumblr.com/v2"


def _is_configured() -> bool:
    return bool(
        TUMBLR_CONSUMER_KEY and TUMBLR_CONSUMER_SECRET
        and TUMBLR_TOKEN and TUMBLR_TOKEN_SECRET and TUMBLR_BLOG_NAME
    )


class TumblrAgent(BaseAgent):
    name = "TumblrAgent"

    def __init__(self):
        self.client = None
        self.model = None

    def execute(self, **kwargs) -> dict:
        if not _is_configured():
            logger.warning("Tumblr credentials not set — skipping")
            return {"skipped": True, "reason": "Tumblr credentials not configured"}

        article = self._get_unposted_article()
        if not article:
            logger.info("No new articles to post to Tumblr")
            return {"posted": 0}

        success = self._post_to_tumblr(article)
        if success:
            self._mark_posted(article["id"])
            logger.info(f"Tumblr: posted '{article['title'][:60]}'")
            return {"posted": 1, "title": article["title"]}

        return {"posted": 0}

    def _get_unposted_article(self) -> dict | None:
        with get_db() as db:
            posted_ids = {
                p.content_id for p in
                db.query(SocialPost).filter(SocialPost.platform == "tumblr").all()
                if p.content_id
            }
            article = (
                db.query(ContentPiece)
                .filter(
                    ContentPiece.status == ContentStatus.published,
                    ContentPiece.published_url.isnot(None),
                    ~ContentPiece.id.in_(posted_ids) if posted_ids else True,
                )
                .order_by(ContentPiece.published_at.desc())
                .first()
            )
            if article:
                return {
                    "id": article.id,
                    "title": article.title,
                    "url": article.published_url,
                    "meta": article.meta_description or "",
                    "keyword": article.target_keyword or "health",
                    "body": article.body or "",
                }
        return None

    def _post_to_tumblr(self, article: dict) -> bool:
        auth = OAuth1(
            TUMBLR_CONSUMER_KEY, TUMBLR_CONSUMER_SECRET,
            TUMBLR_TOKEN, TUMBLR_TOKEN_SECRET,
        )
        tags = [t.strip() for t in article["keyword"].split() if t.strip()]
        tags += ["health", "supplements", "wellness", "review"]

        # Use link post type — clean and drives traffic
        try:
            resp = requests.post(
                f"{TUMBLR_API}/blog/{TUMBLR_BLOG_NAME}/post",
                auth=auth,
                json={
                    "type": "link",
                    "title": article["title"],
                    "url": article["url"],
                    "description": article["meta"][:512],
                    "tags": list(dict.fromkeys(tags))[:20],  # dedupe, max 20
                    "native_inline_images": True,
                },
                timeout=15,
            )
            if resp.ok:
                return True
            logger.error(f"Tumblr post failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Tumblr post error: {e}")
        return False

    def _mark_posted(self, content_id: int):
        with get_db() as db:
            db.add(SocialPost(
                content_id=content_id,
                platform="tumblr",
                post_text="tumblr",
                status="posted",
                posted_at=datetime.utcnow(),
            ))
