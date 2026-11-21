"""Public (no admin key) endpoints used by the static site: subscribe + unsubscribe."""
import re
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from database.database import get_db
from database.models import EmailSubscriber
from utils.unsub import verify_token
from datetime import datetime

router = APIRouter(tags=["public"])
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


class SubscribeRequest(BaseModel):
    email: str
    first_name: str = ""
    niche: str = "general"
    website: str = ""  # honeypot: real users leave this empty


@router.post("/api/subscribe")
def subscribe(req: SubscribeRequest):
    email = req.email.strip().lower()
    if req.website:  # bot filled the hidden field — pretend success
        return {"ok": True}
    if not _EMAIL_RE.match(email) or len(email) > 200:
        return {"ok": False, "error": "Please enter a valid email address."}
    with get_db() as db:
        sub = db.query(EmailSubscriber).filter(EmailSubscriber.email == email).first()
        if sub:
            if not sub.is_active:  # re-subscribe
                sub.is_active, sub.unsubscribed_at = True, None
        else:
            db.add(EmailSubscriber(
                email=email, first_name=req.first_name.strip()[:100] or None,
                niche=req.niche[:100], source="website", sequence_step=0, is_active=True,
            ))
    return {"ok": True}


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(e: str = "", t: str = ""):
    e = e.strip().lower()
    if not e or not verify_token(e, t):
        return HTMLResponse("<h3>Invalid unsubscribe link.</h3>", status_code=400)
    with get_db() as db:
        sub = db.query(EmailSubscriber).filter(EmailSubscriber.email == e).first()
        if sub:
            sub.is_active, sub.unsubscribed_at = False, datetime.utcnow()
    return HTMLResponse("<body style='font-family:system-ui;max-width:480px;margin:80px auto'>"
                        "<h3>You're unsubscribed.</h3><p>You won't receive any more emails from us.</p></body>")
