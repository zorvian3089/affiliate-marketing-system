import requests as _requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.database import get_db_session
from database.models import (
    AgentLog, RevenueSnapshot, ContentPiece, ContentStatus, EmailSubscriber,
    Product, Niche, SocialPost, AffiliateLink
)
from agents.analytics_agent import AnalyticsAgent
from config.settings import WORDPRESS_SITE

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def get_overview(db: Session = Depends(get_db_session)):
    """Main dashboard stats."""
    # Revenue
    snapshots = db.query(RevenueSnapshot).order_by(RevenueSnapshot.date.desc()).limit(30).all()
    total_revenue_30d = sum(s.total_revenue or 0 for s in snapshots)
    total_clicks_30d = sum(s.total_clicks or 0 for s in snapshots)
    today = snapshots[0] if snapshots else None

    # Counts
    content_count = db.query(ContentPiece).count()
    published_count = db.query(ContentPiece).filter(ContentPiece.status == "published").count()
    subscriber_count = db.query(EmailSubscriber).filter(EmailSubscriber.is_active == True).count()
    product_count = db.query(Product).count()
    active_links = db.query(AffiliateLink).filter(AffiliateLink.is_active == True).count()

    return {
        "revenue": {
            "today": today.total_revenue if today else 0,
            "last_30_days": round(total_revenue_30d, 2),
            "projected_monthly": round(total_revenue_30d, 2),
        },
        "traffic": {
            "clicks_today": today.total_clicks if today else 0,
            "clicks_30d": total_clicks_30d,
            "conversions_today": today.total_conversions if today else 0,
        },
        "content": {
            "total": content_count,
            "published": published_count,
            "draft": content_count - published_count,
        },
        "email": {"subscribers": subscriber_count},
        "products": {"total": product_count, "active_links": active_links},
    }


@router.get("/revenue-chart")
def get_revenue_chart(days: int = 30, db: Session = Depends(get_db_session)):
    snapshots = db.query(RevenueSnapshot).order_by(
        RevenueSnapshot.date.asc()
    ).limit(days).all()
    return [
        {"date": s.date, "revenue": s.total_revenue, "clicks": s.total_clicks}
        for s in snapshots
    ]


@router.get("/agent-logs")
def get_agent_logs(limit: int = 50, db: Session = Depends(get_db_session)):
    logs = db.query(AgentLog).order_by(AgentLog.started_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "agent": l.agent_name,
            "task": l.task,
            "status": l.status,
            "summary": l.result_summary,
            "duration": l.duration_seconds,
            "started": l.started_at.isoformat() if l.started_at else None,
        }
        for l in logs
    ]


@router.get("/top-performers")
def get_top_performers(db: Session = Depends(get_db_session)):
    agent = AnalyticsAgent()
    return agent.get_top_performers()


@router.get("/published-posts")
def get_published_posts(db: Session = Depends(get_db_session)):
    """All published articles from DB + live view counts from WordPress.com."""
    from api.routes.wp_auth import get_active_token

    posts = (
        db.query(ContentPiece)
        .filter(ContentPiece.status == ContentStatus.published)
        .order_by(ContentPiece.published_at.desc())
        .all()
    )

    # Fetch live top-post view stats from WordPress.com (best effort)
    wp_views: dict[str, int] = {}
    token = get_active_token()
    if token and WORDPRESS_SITE:
        try:
            resp = _requests.get(
                f"https://public-api.wordpress.com/rest/v1.1/sites/{WORDPRESS_SITE}/stats/top-posts"
                f"?period=month&num=100",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8,
            )
            if resp.ok:
                for item in resp.json().get("top-posts", []):
                    url = (item.get("href") or "").rstrip("/")
                    if url:
                        wp_views[url] = item.get("views", 0)
        except Exception:
            pass

    result = []
    for p in posts:
        url = (p.published_url or "").rstrip("/")
        platform = "WordPress" if "wordpress.com" in url else "Blogger" if "blogspot.com" in url else "Other"
        live_views = wp_views.get(url, p.views or 0)
        result.append({
            "id": p.id,
            "title": p.title,
            "url": p.published_url,
            "platform": platform,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "views": live_views,
            "keyword": p.target_keyword or "",
            "word_count": p.word_count or 0,
        })

    return result


@router.get("/site-stats")
def get_site_stats():
    """WordPress.com site-wide traffic stats."""
    from api.routes.wp_auth import get_active_token
    token = get_active_token()
    if not token:
        return {"views_today": 0, "views_week": 0, "views_total": 0, "available": False}

    try:
        resp = _requests.get(
            f"https://public-api.wordpress.com/rest/v1.1/sites/{WORDPRESS_SITE}/stats/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if not resp.ok:
            return {"views_today": 0, "views_week": 0, "views_total": 0, "available": False}

        s = resp.json().get("stats", {})
        return {
            "views_today": s.get("views_today", 0),
            "views_week": s.get("views_this_week", 0),
            "views_total": s.get("views", 0),
            "visitors_today": s.get("visitors_today", 0),
            "available": True,
        }
    except Exception:
        return {"views_today": 0, "views_week": 0, "views_total": 0, "available": False}


products_router = APIRouter(tags=["products"])


@products_router.get("/api/products")
def list_products(db: Session = Depends(get_db_session)):
    products = db.query(Product).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "vendor_id": p.vendor_id,
            "niche": p.niche,
            "price": p.price,
            "commission_rate": p.commission_rate,
            "affiliate_url": p.affiliate_url,
            "is_active": p.is_active,
        }
        for p in products
    ]
