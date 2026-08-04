"""
Medium Agent
Cross-posts WordPress articles to Medium with a canonical URL back to
the original. Drives Medium's internal audience to your content and
adds a quality backlink for SEO.
"""
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, SocialPost, ContentStatus
from config.settings import MEDIUM_TOKEN, WORDPRESS_SITE
from utils.token_store import get_active_token

logger = logging.getLogger(__name__)
MEDIUM_API = "https://api.medium.com/v1"


def _is_configured() -> bool:
    return bool(MEDIUM_TOKEN)


class MediumAgent(BaseAgent):
    name = "MediumAgent"

    def execute(self, **kwargs) -> dict:
        if not _is_configured():
            logger.warning("MEDIUM_TOKEN not set — skipping")
            return {"skipped": True, "reason": "MEDIUM_TOKEN not configured"}

        user = self._get_medium_user()
        if not user:
            return {"posted": 0, "error": "Could not authenticate with Medium"}

        article = self._get_unposted_article()
        if not article:
            logger.info("No new articles to cross-post to Medium")
            return {"posted": 0}

        wp_body = self._fetch_wp_body(article["url"])
        medium_url = self._publish_to_medium(user["id"], article, wp_body)
        if medium_url:
            self._mark_posted(article["id"], medium_url)
            logger.info(f"Medium: published '{article['title'][:60]}' → {medium_url}")
            return {"posted": 1, "title": article["title"], "medium_url": medium_url}

        return {"posted": 0}

    def _get_medium_user(self) -> dict | None:
        try:
            resp = requests.get(
                f"{MEDIUM_API}/me",
                headers={"Authorization": f"Bearer {MEDIUM_TOKEN}"},
                timeout=10,
            )
            if resp.ok:
                return resp.json().get("data", {})
            logger.error(f"Medium auth failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Medium user fetch failed: {e}")
        return None

    def _get_unposted_article(self) -> dict | None:
        with get_db() as db:
            posted_ids = {
                p.content_id for p in
                db.query(SocialPost).filter(SocialPost.platform == "medium").all()
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
                    "body": article.body or "",
                    "tags": [article.target_keyword or "health"],
                    "meta": article.meta_description or "",
                }
        return None

    def _fetch_wp_body(self, wp_url: str) -> str:
        """Try to get full HTML body from WordPress API."""
        token = get_active_token()
        if not (token and WORDPRESS_SITE):
            return ""
        try:
            resp = requests.get(
                f"https://public-api.wordpress.com/rest/v1.1/sites/{WORDPRESS_SITE}/posts"
                f"?number=1&status=publish&fields=content,URL",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.ok:
                posts = resp.json().get("posts", [])
                for p in posts:
                    if p.get("URL") == wp_url:
                        return p.get("content", "")
                if posts:
                    return posts[0].get("content", "")
        except Exception as e:
            logger.error(f"WP body fetch failed: {e}")
        return ""

    def _publish_to_medium(self, user_id: str, article: dict, body_html: str) -> str | None:
        canonical = article["url"]
        content = body_html or f"<p>{article['meta']}</p><p><a href='{canonical}'>Read the full article</a></p>"

        # Add canonical notice at end
        content += f"\n<p><em>Originally published at <a href='{canonical}'>{canonical}</a></em></p>"

        tags = article.get("tags", ["health"])[:5]
        tag_list = [t.strip()[:25] for t in tags if t.strip()]

        try:
            resp = requests.post(
                f"{MEDIUM_API}/users/{user_id}/posts",
                headers={
                    "Authorization": f"Bearer {MEDIUM_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "title": article["title"],
                    "contentFormat": "html",
                    "content": content,
                    "canonicalUrl": canonical,
                    "tags": tag_list,
                    "publishStatus": "public",
                },
                timeout=15,
            )
            if resp.ok:
                return resp.json().get("data", {}).get("url", "")
            logger.error(f"Medium publish failed: {resp.status_code} {resp.text[:300]}")
        except Exception as e:
            logger.error(f"Medium publish error: {e}")
        return None

    def _mark_posted(self, content_id: int, medium_url: str):
        with get_db() as db:
            db.add(SocialPost(
                content_id=content_id,
                platform="medium",
                post_text=medium_url,
                status="posted",
                posted_at=datetime.utcnow(),
            ))
