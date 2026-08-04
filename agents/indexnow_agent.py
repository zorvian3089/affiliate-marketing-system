"""
Search Engine Ping Agent
Notifies Google, Bing, Yandex, and DuckDuckGo about new articles
the moment they're published. Gets articles indexed in hours, not weeks.
No API keys needed for sitemap pings.
IndexNow covers Bing + Yandex + DuckDuckGo in one call.
"""
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, SocialPost, ContentStatus
from config.settings import WORDPRESS_SITE, INDEXNOW_KEY

logger = logging.getLogger(__name__)

SITEMAP_URL = f"https://{WORDPRESS_SITE}/sitemap.xml"


class IndexNowAgent(BaseAgent):
    name = "IndexNowAgent"

    def __init__(self):
        self.client = None
        self.model = None

    def execute(self, **kwargs) -> dict:
        urls = self._get_unsubmitted_urls()
        if not urls:
            logger.info("No new URLs to submit to search engines")
            return {"submitted": 0}

        results = {}
        results["google"] = self._ping_google()
        results["bing"] = self._ping_bing()
        results["indexnow"] = self._submit_indexnow(urls) if INDEXNOW_KEY else False

        submitted = len(urls)
        for url_info in urls:
            self._mark_submitted(url_info["id"])

        logger.info(f"Search engines pinged for {submitted} URLs: {results}")
        return {"submitted": submitted, "results": results, "urls": [u["url"] for u in urls]}

    def _get_unsubmitted_urls(self) -> list[dict]:
        with get_db() as db:
            submitted_ids = {
                p.content_id for p in
                db.query(SocialPost).filter(SocialPost.platform == "indexnow").all()
                if p.content_id
            }
            articles = (
                db.query(ContentPiece)
                .filter(
                    ContentPiece.status == ContentStatus.published,
                    ContentPiece.published_url.isnot(None),
                    ~ContentPiece.id.in_(submitted_ids) if submitted_ids else True,
                )
                .order_by(ContentPiece.published_at.desc())
                .limit(10)
                .all()
            )
            return [{"id": a.id, "url": a.published_url} for a in articles]

    def _ping_google(self) -> bool:
        """Ping Google to re-crawl the sitemap."""
        try:
            resp = requests.get(
                f"https://www.google.com/ping",
                params={"sitemap": SITEMAP_URL},
                timeout=10,
            )
            logger.info(f"Google ping: {resp.status_code}")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Google ping failed: {e}")
            return False

    def _ping_bing(self) -> bool:
        """Ping Bing to re-crawl the sitemap."""
        try:
            resp = requests.get(
                f"https://www.bing.com/ping",
                params={"sitemap": SITEMAP_URL},
                timeout=10,
            )
            logger.info(f"Bing ping: {resp.status_code}")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Bing ping failed: {e}")
            return False

    def _submit_indexnow(self, url_infos: list[dict]) -> bool:
        """Submit URLs via IndexNow protocol (Bing + Yandex + DuckDuckGo)."""
        url_list = [u["url"] for u in url_infos if u["url"]]
        if not url_list:
            return False
        try:
            resp = requests.post(
                "https://api.indexnow.org/indexnow",
                json={
                    "host": WORDPRESS_SITE,
                    "key": INDEXNOW_KEY,
                    "keyLocation": f"https://{WORDPRESS_SITE}/{INDEXNOW_KEY}.txt",
                    "urlList": url_list,
                },
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=10,
            )
            logger.info(f"IndexNow: {resp.status_code}")
            return resp.status_code in (200, 202)
        except Exception as e:
            logger.error(f"IndexNow submit failed: {e}")
            return False

    def _mark_submitted(self, content_id: int):
        with get_db() as db:
            db.add(SocialPost(
                content_id=content_id,
                platform="indexnow",
                post_text="search_engines",
                status="posted",
                posted_at=datetime.utcnow(),
            ))
