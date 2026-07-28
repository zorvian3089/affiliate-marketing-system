"""
WordPress Agent
Auto-publishes AI-generated articles to healthreviewshub5.wordpress.com
Uses WordPress.com REST API v1.1 with OAuth2 bearer token.
Publishes 1 article per run — safe, steady pace.
"""
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, ContentStatus
from config.settings import WORDPRESS_SITE, WORDPRESS_TOKEN

logger = logging.getLogger(__name__)

WP_API_BASE = "https://public-api.wordpress.com/rest/v1.1"
MAX_PUBLISH_PER_RUN = 1
HOPLINKS = {
    "java burn":   "https://45ac8nryoc61fg08luqaycxi1a.hop.clickbank.net",
    "javaburn":    "https://45ac8nryoc61fg08luqaycxi1a.hop.clickbank.net",
    "resurge":     "https://45ac8nryoc61fg08luqaycxi1a.hop.clickbank.net",
    "joint genesis": "https://b5f4bnw7xlx9ol74p5ymq6tuf8.hop.clickbank.net",
    "jointgen":    "https://b5f4bnw7xlx9ol74p5ymq6tuf8.hop.clickbank.net",
}
AFFILIATE_HOPLINK = "https://b5f4bnw7xlx9ol74p5ymq6tuf8.hop.clickbank.net"  # fallback

def _get_hoplink_for_title(title: str) -> str:
    title_lower = title.lower()
    for keyword, link in HOPLINKS.items():
        if keyword in title_lower:
            return link
    return AFFILIATE_HOPLINK

DISCLAIMER = """<div style="background:#fff8e1;border-left:4px solid #f59e0b;padding:12px 16px;margin-bottom:24px;border-radius:4px;font-size:14px;line-height:1.6;">
<strong>&#9888;&#65039; Affiliate Disclosure:</strong> This article contains affiliate links. If you purchase through our links we may earn a commission at no extra cost to you. We only recommend products we genuinely believe can help.
</div>"""

def _cta_box(product_name: str, label: str = "", link: str = None) -> str:
    url = link or AFFILIATE_HOPLINK
    text = label or f"Get {product_name} at the Lowest Price"
    return (
        '<div style="background:linear-gradient(135deg,#064e3b,#10b981);'
        'padding:28px 24px;border-radius:14px;text-align:center;margin:36px 0;">'
        f'<p style="color:#ffffff;font-size:19px;font-weight:800;margin:0 0 8px;">&#11088; {product_name} — Official Offer</p>'
        '<p style="color:#d1fae5;font-size:14px;margin:0 0 18px;">180-Day Money-Back Guarantee &nbsp;|&nbsp; Limited Stock</p>'
        f'<a href="{url}" style="background:#ffffff;color:#064e3b;padding:14px 36px;'
        'border-radius:8px;text-decoration:none;font-weight:800;font-size:15px;display:inline-block;">'
        f'&#10003; {text} &#8594;</a>'
        '</div>'
    )


class WordPressAgent(BaseAgent):
    name = "WordPressAgent"

    def execute(self, **kwargs) -> dict:
        if not self._is_configured():
            logger.warning("WordPress token not set in .env — skipping")
            return {"skipped": True, "reason": "WORDPRESS_TOKEN missing in .env"}

        published = self._publish_pending_articles()
        return {"platform": "wordpress", "articles_published": published}

    def _is_configured(self) -> bool:
        return bool(WORDPRESS_TOKEN and WORDPRESS_SITE)

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
            logger.info("WordPress: no unpublished drafts found")
            return 0

        published = 0
        for article in articles:
            try:
                url = self._post_to_wordpress(article)
                if url:
                    self._mark_published(article["id"], url)
                    published += 1
                    logger.info(f"WordPress published: '{article['title']}' → {url}")
            except Exception as e:
                logger.error(f"WordPress failed to publish '{article['title']}': {e}")

        return published

    def _post_to_wordpress(self, article: dict) -> str | None:
        hoplink = _get_hoplink_for_title(article["title"])
        html_body = self._markdown_to_html(article["body"])
        html_body = self._inject_ctas(html_body, article["title"], hoplink)
        html_body = DISCLAIMER + html_body

        tags = [t.strip() for t in (article.get("target_keyword") or "").split() if t.strip()]

        resp = requests.post(
            f"{WP_API_BASE}/sites/{WORDPRESS_SITE}/posts/new",
            headers={
                "Authorization": f"Bearer {WORDPRESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "title": article["title"],
                "content": html_body,
                "status": "publish",
                "tags": tags,
                "categories": ["Health Reviews"],
                "excerpt": article.get("meta_description", ""),
                "format": "standard",
            },
            timeout=30,
        )

        if resp.status_code in [200, 201]:
            data = resp.json()
            return data.get("URL", "")

        logger.error(f"WordPress API {resp.status_code}: {resp.text[:400]}")
        return None

    def _inject_ctas(self, html: str, title: str, hoplink: str = None) -> str:
        """Replace plain affiliate links and insert 3 highlighted CTA boxes."""
        # Extract product name from title (first 2-3 words before " Review" or " —")
        import re
        m = re.match(r'^([A-Za-z0-9 ]+?)(?:\s+Review|\s+—|\s+-)', title)
        product_name = m.group(1).strip() if m else "This Product"

        link = hoplink or _get_hoplink_for_title(title)
        cta_top = _cta_box(product_name, f"Check Best Price for {product_name}", link)
        cta_mid = _cta_box(product_name, f"Try {product_name} Risk-Free Today", link)
        cta_bot = _cta_box(product_name, f"Get {product_name} — Official Site", link)

        # Replace any plain [AFFILIATE_LINK] placeholder
        html = html.replace("[AFFILIATE_LINK]", link)
        html = re.sub(
            r'<a\s+href="[^"]*hop\.clickbank\.net[^"]*"[^>]*>(.*?)</a>',
            f'<a href="{link}" style="color:#065f46;font-weight:700;text-decoration:underline;">\\1</a>',
            html
        )

        # Insert CTA after 2nd <h2>, middle <h2>, and at the end
        h2_positions = [m.start() for m in re.finditer(r'<h2', html)]
        inserts = {}
        if len(h2_positions) >= 2:
            inserts[h2_positions[1]] = cta_top
        if len(h2_positions) >= 4:
            mid = h2_positions[len(h2_positions) // 2]
            inserts[mid] = cta_mid
        html_parts = []
        prev = 0
        for pos in sorted(inserts.keys()):
            html_parts.append(html[prev:pos])
            html_parts.append(inserts[pos])
            prev = pos
        html_parts.append(html[prev:])
        html = "".join(html_parts)

        # Always add final CTA at the end
        html += cta_bot
        return html

    def _markdown_to_html(self, md_text: str) -> str:
        if not md_text:
            return ""
        try:
            import markdown
            return markdown.markdown(md_text, extensions=["extra", "toc", "nl2br"])
        except ImportError:
            lines = md_text.split("\n")
            html = []
            for line in lines:
                if line.startswith("### "):
                    html.append(f"<h3>{line[4:]}</h3>")
                elif line.startswith("## "):
                    html.append(f"<h2>{line[3:]}</h2>")
                elif line.startswith("# "):
                    html.append(f"<h1>{line[2:]}</h1>")
                elif line.strip():
                    html.append(f"<p>{line}</p>")
            return "\n".join(html)

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
