"""
Bluesky Agent
Auto-posts new WordPress articles to Bluesky using the AT Protocol API.
Free, open — no API verification needed.
Runs once per day, posts the latest published article.
"""
import logging
import requests
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from config.settings import BLUESKY_HANDLE, BLUESKY_APP_PASSWORD, WORDPRESS_SITE
from utils.token_store import get_active_token

logger = logging.getLogger(__name__)
BSKY_API = "https://bsky.social/xrpc"

HEALTH_HASHTAGS = "#health #wellness #supplements #weightloss #healthylifestyle"


def _create_session() -> dict:
    resp = requests.post(
        f"{BSKY_API}/com.atproto.server.createSession",
        json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_APP_PASSWORD},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _make_post(session: dict, text: str, url: str) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    text_bytes = text.encode("utf-8")
    url_bytes = url.encode("utf-8")
    url_start = text_bytes.find(url_bytes)
    facets = []
    if url_start >= 0:
        facets.append({
            "index": {"byteStart": url_start, "byteEnd": url_start + len(url_bytes)},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
        })

    record = {"$type": "app.bsky.feed.post", "text": text, "createdAt": now}
    if facets:
        record["facets"] = facets

    resp = requests.post(
        f"{BSKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


class BlueskyAgent(BaseAgent):
    name = "BlueskyAgent"

    def execute(self, **kwargs) -> dict:
        if not (BLUESKY_HANDLE and BLUESKY_APP_PASSWORD):
            logger.warning("Bluesky credentials missing — skipping")
            return {"skipped": True, "reason": "BLUESKY credentials not set"}

        article = self._get_latest_wp_article()
        if not article:
            logger.info("No WordPress articles found to post")
            return {"posted": 0}

        try:
            session = _create_session()
            text = self._build_post(article)
            _make_post(session, text, article["url"])
            logger.info(f"Bluesky posted: {article['title'][:60]}")
            return {"posted": 1, "title": article["title"]}
        except Exception as e:
            logger.error(f"Bluesky post failed: {e}")
            return {"posted": 0, "error": str(e)}

    def _get_latest_wp_article(self) -> dict | None:
        token = get_active_token()
        if not (WORDPRESS_SITE and token):
            return None
        try:
            resp = requests.get(
                f"https://public-api.wordpress.com/rest/v1.1/sites/{WORDPRESS_SITE}/posts"
                f"?number=1&status=publish&fields=title,URL,excerpt",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            posts = resp.json().get("posts", [])
            if posts:
                p = posts[0]
                import re
                excerpt = re.sub(r"<[^>]+>", "", p.get("excerpt", "")).strip()[:120]
                return {"title": p.get("title", ""), "url": p.get("URL", ""), "excerpt": excerpt}
        except Exception as e:
            logger.error(f"WordPress fetch failed: {e}")
        return None

    def _build_post(self, article: dict) -> str:
        title = article["title"][:80]
        url = article["url"]
        excerpt = article.get("excerpt", "")

        # Build post — stay under 300 graphemes
        body = f"New review: {title}"
        if excerpt:
            body += f"\n\n{excerpt[:80]}"
        body += f"\n\nRead more: {url}\n\n{HEALTH_HASHTAGS}"

        # Hard-truncate to 300 chars if needed
        if len(body) > 300:
            budget = 300 - len(url) - len(HEALTH_HASHTAGS) - 25
            body = f"New review: {title[:budget]}\n\nRead more: {url}\n\n{HEALTH_HASHTAGS}"

        return body[:300]
