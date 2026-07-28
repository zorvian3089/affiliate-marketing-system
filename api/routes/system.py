"""
System health & warnings endpoint.
Checks all credentials, token validity, and recent agent failures.
Returns a list of actionable warnings for the dashboard.
"""
import os
import requests
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.database import get_db_session
from database.models import AgentLog
from config.settings import (
    ANTHROPIC_API_KEY, BLUESKY_HANDLE, BLUESKY_APP_PASSWORD,
    CLICKBANK_NICKNAME, WORDPRESS_SITE,
)
from api.routes.wp_auth import get_active_token

router = APIRouter(tags=["system"])

RENDER_URL = "https://affiliate-marketing-system-7994.onrender.com"


def _check_wp_token() -> dict | None:
    token = get_active_token()
    if not token:
        return {
            "id": "wp_token_missing",
            "level": "error",
            "title": "WordPress Token Missing",
            "message": "No token set. WordPress publishing is completely disabled.",
            "action_label": "Connect WordPress",
            "action_url": f"{RENDER_URL}/wp-auth",
        }
    try:
        resp = requests.get(
            f"https://public-api.wordpress.com/rest/v1.1/sites/{WORDPRESS_SITE}/posts?number=1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if resp.status_code == 401:
            return {
                "id": "wp_token_expired",
                "level": "error",
                "title": "WordPress Token Expired",
                "message": "Articles cannot be published. Token rejected by WordPress.com.",
                "action_label": "Refresh Token",
                "action_url": f"{RENDER_URL}/wp-auth",
            }
    except Exception:
        return {
            "id": "wp_token_unreachable",
            "level": "warning",
            "title": "WordPress API Unreachable",
            "message": "Could not contact WordPress.com to verify token. Will retry on next agent run.",
            "action_label": None,
            "action_url": None,
        }
    return None


def _check_anthropic() -> dict | None:
    if not ANTHROPIC_API_KEY:
        return {
            "id": "anthropic_missing",
            "level": "error",
            "title": "Claude API Key Missing",
            "message": "ANTHROPIC_API_KEY not set. Content creation and all AI agents are disabled.",
            "action_label": "Add to Render",
            "action_url": "https://dashboard.render.com",
        }
    return None


def _check_bluesky() -> dict | None:
    if not (BLUESKY_HANDLE and BLUESKY_APP_PASSWORD):
        return {
            "id": "bluesky_missing",
            "level": "warning",
            "title": "Bluesky Not Configured",
            "message": "BLUESKY_HANDLE or BLUESKY_APP_PASSWORD missing. Auto-posting to Bluesky is disabled.",
            "action_label": "Add to Render",
            "action_url": "https://dashboard.render.com",
        }
    return None


def _check_clickbank() -> dict | None:
    if not CLICKBANK_NICKNAME:
        return {
            "id": "clickbank_missing",
            "level": "warning",
            "title": "ClickBank Nickname Not Set",
            "message": "CLICKBANK_NICKNAME missing. Affiliate hoplinks will use the default fallback link.",
            "action_label": "Add to Render",
            "action_url": "https://dashboard.render.com",
        }
    return None


def _check_agent_failures(db: Session) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    failed = (
        db.query(AgentLog)
        .filter(AgentLog.status == "failed", AgentLog.started_at >= cutoff)
        .order_by(AgentLog.started_at.desc())
        .limit(5)
        .all()
    )
    if not failed:
        return []

    names = list({log.agent_name for log in failed})
    return [{
        "id": "agent_failures",
        "level": "warning",
        "title": f"{len(failed)} Agent Failure{'s' if len(failed) > 1 else ''} (Last 24h)",
        "message": f"Agents failed: {', '.join(names)}. Check the Logs page for details.",
        "action_label": "View Logs",
        "action_url": None,
        "action_page": "logs",
    }]


def _static_warnings() -> list[dict]:
    return [
        {
            "id": "blogger_restricted",
            "level": "warning",
            "title": "Blogger API Restricted",
            "message": "Google restricted auto-publishing. Appeal submitted — response expected soon. Articles are queuing and will auto-publish once restored.",
            "action_label": "Appeal Status",
            "action_url": "https://console.cloud.google.com/apis/library",
        }
    ]


@router.get("/api/system/warnings")
def get_warnings(db: Session = Depends(get_db_session)):
    warnings = []

    # Critical credential checks
    for check_fn in [_check_anthropic, _check_wp_token, _check_bluesky, _check_clickbank]:
        w = check_fn()
        if w:
            warnings.append(w)

    # Agent failures from DB
    warnings.extend(_check_agent_failures(db))

    # Known static issues
    warnings.extend(_static_warnings())

    # Sort: errors first, then warnings, then info
    order = {"error": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: order.get(w["level"], 3))

    return {
        "warnings": warnings,
        "error_count": sum(1 for w in warnings if w["level"] == "error"),
        "warning_count": sum(1 for w in warnings if w["level"] == "warning"),
    }
