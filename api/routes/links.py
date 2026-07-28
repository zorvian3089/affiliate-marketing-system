from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database.database import get_db_session
from database.models import AffiliateLink
from agents.link_manager_agent import LinkManagerAgent

router = APIRouter(tags=["links"])


@router.get("/go/{short_code}")
def redirect_affiliate_link(short_code: str, request: Request):
    """Affiliate link redirect — tracks click and forwards to destination."""
    agent = LinkManagerAgent()
    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")

    # Determine traffic source
    source = "direct"
    if "email" in referrer.lower() or "mail" in referrer.lower():
        source = "email"
    elif any(s in referrer.lower() for s in ["twitter", "t.co", "x.com"]):
        source = "twitter"
    elif "reddit" in referrer.lower():
        source = "reddit"
    elif referrer:
        source = "referral"

    destination = agent.track_click(short_code, ip, user_agent, referrer, source)
    if not destination:
        raise HTTPException(status_code=404, detail="Link not found or inactive")

    return RedirectResponse(url=destination, status_code=302)


@router.get("/api/links")
def list_links(db: Session = Depends(get_db_session)):
    agent = LinkManagerAgent()
    return agent.get_link_stats()


@router.post("/api/links/{product_id}")
def create_link(product_id: int):
    agent = LinkManagerAgent()
    result = agent.create_affiliate_link(product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.delete("/api/links/{short_code}")
def deactivate_link(short_code: str):
    agent = LinkManagerAgent()
    success = agent.deactivate_link(short_code)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"deactivated": True}
