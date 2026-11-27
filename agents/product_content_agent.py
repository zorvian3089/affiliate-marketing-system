"""
Product Content Agent (SITE_MODE=getupsignal)
Writes helpful website-monitoring guides that mention our own product, GetUpSignal.

Nothing it writes goes live by itself: pieces are saved as drafts and must be approved
at /review. Product statements are limited to PRODUCT_FACTS below.
"""
import logging
import re
from datetime import datetime
from agents.base_agent import BaseAgent
from database.database import get_db
from database.models import Niche, NicheStatus, ContentPiece, ContentStatus
from config.settings import PRODUCT_URL, PRODUCT_NICHE

logger = logging.getLogger(__name__)

MAX_PENDING_DRAFTS = 4  # don't pile up more than the owner can review

# Taken from getupsignal.com (checked 2026-11-27). Features marked "Soon" there are left out,
# and so are paid-plan prices until checkout is confirmed working. Update when the product changes.
PRODUCT_FACTS = f"""GetUpSignal ({PRODUCT_URL}) is an uptime monitoring service.
- Monitor types: website, keyword on a page, TCP port, heartbeat for cron jobs/backups.
- Also: SSL certificate and domain expiry checks, maintenance windows, public status pages.
- Free plan: 10 monitors, checks every 5 minutes, email and Telegram alerts, 1 status page.
- Sign-up page: {PRODUCT_URL}/signup"""

TOPICS = [
    "how to get website down alerts on Telegram",
    "how to monitor client websites as a freelancer",
    "how to check when an SSL certificate expires",
    "how to monitor a cron job so you know when it stops running",
    "what is keyword monitoring and when a 200 OK is not enough",
    "how to create a status page for your clients",
    "how often should you check your website uptime",
    "what to do when your website returns a 503 error",
    "how to avoid losing a domain because it expired",
    "website monitoring checklist for small businesses",
    "how to check if a server port is open and stay alerted",
    "how to reduce false alerts from uptime monitoring",
]

SYSTEM_PROMPT = f"""You write practical, accurate technical guides about website monitoring.
The publisher of this site also makes GetUpSignal, one of the tools you may mention.

PRODUCT FACTS (the ONLY things you may say about GetUpSignal):
{PRODUCT_FACTS}

Rules:
- Teach first. The guide must be useful to someone who never signs up.
- Include concrete steps, and free manual methods where they exist.
- Mention GetUpSignal at most twice, and say clearly that it is our own product.
- Never invent features, prices, customers, testimonials, statistics or studies.
- Never claim personal experience or test results. Do not compare with named competitors.
- Do not invent commands or settings you are unsure about."""


class ProductContentAgent(BaseAgent):
    name = "ProductContentAgent"

    def execute(self, **kwargs) -> dict:
        niche_id = self._ensure_niche()
        with get_db() as db:
            pending = db.query(ContentPiece).filter(
                ContentPiece.niche_id == niche_id, ContentPiece.status == ContentStatus.draft).count()
            done = {(k or "").lower() for (k,) in db.query(ContentPiece.target_keyword)
                    .filter(ContentPiece.niche_id == niche_id).all()}
        if pending >= MAX_PENDING_DRAFTS:
            return {"created": 0, "reason": f"{pending} drafts waiting for approval at /review"}

        topic = next((t for t in TOPICS if t.lower() not in done), None)
        if not topic:
            return {"created": 0, "reason": "all topics written — add more to TOPICS"}

        # Plain text, not JSON: long markdown inside JSON strings often fails to parse.
        reply = self.ask_claude(SYSTEM_PROMPT, f"""Current year: {datetime.utcnow().year}.
Write a guide of about 900 words answering: "{topic}".

Reply in exactly this format, with no code fence around it:
TITLE: <clear title on one line>
META: <description under 155 characters on one line>

<the guide in markdown with ## headings>""", max_tokens=8192)

        title, meta, body = self._parse(reply, topic)
        if len(body.split()) < 300:
            return {"created": 0, "reason": f"reply too short ({len(body.split())} words), try again"}
        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:90]
        with get_db() as db:
            db.add(ContentPiece(
                niche_id=niche_id, title=title, slug=slug, content_type="how_to_guide", body=body,
                meta_description=meta[:159], target_keyword=topic,
                word_count=len(body.split()), status=ContentStatus.draft,
            ))
        return {"created": 1, "title": title, "review_at": "/review"}

    @staticmethod
    def _parse(reply: str, topic: str) -> tuple[str, str, str]:
        text = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", reply.strip())
        title = re.search(r"^\W*TITLE:\s*(.+)$", text, re.M)
        meta = re.search(r"^\W*META:\s*(.+)$", text, re.M)
        body = re.sub(r"^\W*(TITLE|META):.*$\n?", "", text, count=2, flags=re.M).strip()
        clean = lambda m: m.group(1).strip().strip("*# ") if m else ""
        return (clean(title) or topic.capitalize())[:299], clean(meta), body

    @staticmethod
    def _ensure_niche() -> int:
        with get_db() as db:
            niche = db.query(Niche).filter(Niche.name == PRODUCT_NICHE).first()
            if not niche:
                niche = Niche(name=PRODUCT_NICHE, keywords=TOPICS, status=NicheStatus.active)
                db.add(niche)
                db.flush()
            return niche.id
