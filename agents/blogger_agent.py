"""
Blogger Agent
Auto-publishes AI-generated articles to producttrustreview.blogspot.com
Uses Google Blogger API v3 with OAuth2 refresh tokens.
"""
import re
import json
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, ContentStatus, AffiliateLink
from config.settings import (
    BLOGGER_BLOG_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
)

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGGER_API_BASE = "https://www.googleapis.com/blogger/v3"

# Publish 1 article per run — safe pace Google won't flag as spam
MAX_PUBLISH_PER_RUN = 1


class BloggerAgent(BaseAgent):
    name = "BloggerAgent"

    def execute(self, **kwargs) -> dict:
        if not self._is_configured():
            logger.warning("Blogger credentials not set — skipping publish")
            return {"skipped": True, "reason": "Missing Blogger credentials in .env"}

        published = self._publish_pending_articles()
        return {"articles_published": published}

    # ── Public helpers ─────────────────────────────────────────────────────────

    def publish_article_now(self, content_id: int) -> dict:
        """Manually trigger publish for a specific article."""
        if not self._is_configured():
            return {"error": "Blogger not configured — run setup_blogger_auth.py first"}

        with get_db() as db:
            piece = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
            if not piece:
                return {"error": f"Article {content_id} not found"}
            article = self._piece_to_dict(piece)

        try:
            token = self._get_access_token()
            url = self._post_to_blogger(article, token)
            if url:
                self._mark_published(content_id, url)
                return {"published": True, "url": url}
            return {"published": False, "error": "Blogger API returned no URL"}
        except Exception as e:
            logger.error(f"Manual publish failed: {e}")
            return {"published": False, "error": str(e)}

    # ── Private ────────────────────────────────────────────────────────────────

    def _is_configured(self) -> bool:
        return all([BLOGGER_BLOG_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN])

    def _get_access_token(self) -> str:
        resp = requests.post(GOOGLE_TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _publish_pending_articles(self) -> int:
        with get_db() as db:
            drafts = (
                db.query(ContentPiece)
                .filter(
                    ContentPiece.status == ContentStatus.draft,
                    ContentPiece.published_url == None,  # noqa: E711
                )
                .order_by(ContentPiece.created_at.asc())
                .limit(MAX_PUBLISH_PER_RUN)
                .all()
            )
            articles = [self._piece_to_dict(p) for p in drafts]

        if not articles:
            logger.info("No unpublished draft articles found")
            return 0

        token = self._get_access_token()
        published = 0

        for article in articles:
            try:
                url = self._post_to_blogger(article, token)
                if url:
                    self._mark_published(article["id"], url)
                    published += 1
                    logger.info(f"Published to Blogger: '{article['title']}' → {url}")
            except Exception as e:
                logger.error(f"Failed to publish '{article['title']}': {e}")

        return published

    def _post_to_blogger(self, article: dict, token: str) -> str | None:
        html_body = self._markdown_to_html(article["body"])
        html_body = self._inject_affiliate_links(html_body, article["target_keyword"])

        # Build label list from keyword
        labels = []
        if article.get("target_keyword"):
            labels.append(article["target_keyword"][:50])

        post_data = {
            "kind": "blogger#post",
            "title": article["title"],
            "content": html_body,
            "labels": labels,
        }

        url = f"{BLOGGER_API_BASE}/blogs/{BLOGGER_BLOG_ID}/posts"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(url, json=post_data, headers=headers, timeout=30)
        if resp.status_code in [200, 201]:
            return resp.json().get("url", "")
        logger.error(f"Blogger API {resp.status_code}: {resp.text[:400]}")
        return None

    def _markdown_to_html(self, md_text: str) -> str:
        """Convert markdown to HTML. Falls back to basic conversion if markdown lib unavailable."""
        if not md_text:
            return ""
        try:
            import markdown
            return markdown.markdown(md_text, extensions=["extra", "toc", "nl2br"])
        except ImportError:
            # Basic fallback: wrap paragraphs and convert headings
            lines = md_text.split("\n")
            html_lines = []
            for line in lines:
                if line.startswith("### "):
                    html_lines.append(f"<h3>{line[4:]}</h3>")
                elif line.startswith("## "):
                    html_lines.append(f"<h2>{line[3:]}</h2>")
                elif line.startswith("# "):
                    html_lines.append(f"<h1>{line[2:]}</h1>")
                elif line.startswith("**") and line.endswith("**"):
                    html_lines.append(f"<strong>{line[2:-2]}</strong>")
                elif line.strip():
                    html_lines.append(f"<p>{line}</p>")
            return "\n".join(html_lines)

    def _inject_affiliate_links(self, html: str, keyword: str) -> str:
        """Replace [AFFILIATE_LINK] placeholders with direct ClickBank hoplinks."""
        if "[AFFILIATE_LINK]" not in html:
            return html

        # Use direct hoplinks (server is local, not public — tracker won't work for readers)
        with get_db() as db:
            from database.models import Product
            product = db.query(Product).filter(
                Product.affiliate_url != None,  # noqa: E711
                Product.affiliate_url != "",
            ).first()
            if product and product.affiliate_url:
                html = html.replace("[AFFILIATE_LINK]", product.affiliate_url)

        return html

    def _mark_published(self, content_id: int, url: str):
        with get_db() as db:
            piece = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
            if piece:
                piece.status = ContentStatus.published
                piece.published_url = url
                piece.published_at = datetime.utcnow()

    @staticmethod
    def _piece_to_dict(piece: ContentPiece) -> dict:
        return {
            "id": piece.id,
            "title": piece.title,
            "body": piece.body or "",
            "target_keyword": piece.target_keyword or "",
            "meta_description": piece.meta_description or "",
        }
