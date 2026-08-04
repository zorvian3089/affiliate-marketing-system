"""
Telegram Agent
Posts every new WordPress article to a Telegram channel automatically.
Telegram Bot API is free and unlimited. Health channels grow fast.
"""
import logging
import requests
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import ContentPiece, SocialPost, ContentStatus
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID)


class TelegramAgent(BaseAgent):
    name = "TelegramAgent"

    def __init__(self):
        self.client = None
        self.model = None

    def execute(self, **kwargs) -> dict:
        if not _is_configured():
            logger.warning("Telegram credentials not set — skipping")
            return {"skipped": True, "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set"}

        article = self._get_unposted_article()
        if not article:
            logger.info("No new articles to post to Telegram")
            return {"posted": 0}

        success = self._send_message(article)
        if success:
            self._mark_posted(article["id"])
            logger.info(f"Telegram: posted '{article['title'][:60]}'")
            return {"posted": 1, "title": article["title"]}

        return {"posted": 0}

    def _get_unposted_article(self) -> dict | None:
        with get_db() as db:
            posted_ids = {
                p.content_id for p in
                db.query(SocialPost).filter(SocialPost.platform == "telegram").all()
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
                    "keyword": article.target_keyword or "",
                }
        return None

    def _build_message(self, article: dict) -> str:
        title = article["title"]
        url = article["url"]
        excerpt = article["meta"][:200] if article["meta"] else ""

        # Build hashtags from keyword
        keyword = article.get("keyword", "health")
        tags = " ".join(
            f"#{w.strip().replace(' ', '')}"
            for w in keyword.split()[:4]
            if w.strip()
        )
        if not tags:
            tags = "#health #supplements #wellness"

        msg = f"🌿 *New Health Review*\n\n"
        msg += f"*{title}*\n\n"
        if excerpt:
            msg += f"{excerpt}\n\n"
        msg += f"📖 Read the full review:\n{url}\n\n"
        msg += tags

        return msg[:4096]  # Telegram message limit

    def _send_message(self, article: dict) -> bool:
        text = self._build_message(article)
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHANNEL_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                },
                timeout=15,
            )
            if resp.ok:
                return True
            logger.error(f"Telegram API error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
        return False

    def _mark_posted(self, content_id: int):
        with get_db() as db:
            db.add(SocialPost(
                content_id=content_id,
                platform="telegram",
                post_text="telegram",
                status="posted",
                posted_at=datetime.utcnow(),
            ))
