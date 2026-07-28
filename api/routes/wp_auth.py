"""
WordPress Token Refresh
Provides a one-click OAuth flow to refresh the WordPress.com token.
The /wp-auth page handles the implicit grant redirect and saves the new token.
"""
import os
import requests
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from config.settings import WORDPRESS_CLIENT_ID, WORDPRESS_SITE
from utils.token_store import get_active_token, set_active_token

router = APIRouter(tags=["wp-auth"])

OAUTH_URL = (
    f"https://public-api.wordpress.com/oauth2/authorize"
    f"?client_id={WORDPRESS_CLIENT_ID}"
    f"&redirect_uri=https://affiliate-marketing-system-7994.onrender.com/wp-auth"
    f"&response_type=token"
    f"&scope=posts+global"
)


@router.get("/wp-auth", response_class=HTMLResponse)
def wp_auth_page():
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>WordPress Token Refresh</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 540px; margin: 80px auto; padding: 24px;
         background: #f0f4f8; color: #1e293b; }
  .card { background: white; border-radius: 14px; padding: 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
  h2 { margin: 0 0 8px; font-size: 20px; }
  p  { color: #64748b; font-size: 14px; margin: 0 0 20px; }
  .btn { display: block; width: 100%; padding: 14px; background: #10b981; color: white;
         border: none; border-radius: 8px; font-size: 15px; font-weight: 700;
         cursor: pointer; text-decoration: none; text-align: center; }
  .btn:hover { background: #059669; }
  .status { margin-top: 20px; padding: 14px; border-radius: 8px; font-size: 14px; display: none; }
  .ok  { background: #d1fae5; color: #065f46; }
  .err { background: #fee2e2; color: #991b1b; }
  code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
</style>
</head>
<body>
<div class="card">
  <h2 id="title">WordPress Token Refresh</h2>
  <p id="msg">Click the button to re-authenticate with WordPress.com and get a fresh token.</p>
  <a class="btn" id="auth-btn" href="OAUTH_URL">Connect WordPress.com</a>
  <div class="status" id="status"></div>
</div>
<script>
  document.getElementById('auth-btn').href = "OAUTH_URL_JS";

  const hash = window.location.hash;
  if (hash && hash.includes('access_token')) {
    const params = new URLSearchParams(hash.slice(1));
    const token = params.get('access_token');
    if (token) {
      document.getElementById('title').textContent = 'Saving token...';
      document.getElementById('msg').textContent = 'Detected new token — saving automatically.';
      document.getElementById('auth-btn').style.display = 'none';

      fetch('/api/wp/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
      })
      .then(r => r.json())
      .then(data => {
        const el = document.getElementById('status');
        el.style.display = 'block';
        if (data.ok) {
          el.className = 'status ok';
          el.innerHTML = '✅ Token saved! Publishing will resume automatically.<br><br>' +
            '<strong>Important:</strong> Also update <code>WORDPRESS_TOKEN</code> in Render ' +
            'environment variables so the token survives a server restart.';
          document.getElementById('title').textContent = '✅ Token Refreshed!';
        } else {
          el.className = 'status err';
          el.textContent = '❌ Failed: ' + (data.error || 'unknown error');
        }
      })
      .catch(e => {
        const el = document.getElementById('status');
        el.style.display = 'block';
        el.className = 'status err';
        el.textContent = '❌ Error: ' + e.message;
      });
    }
  }
</script>
</body>
</html>""".replace("OAUTH_URL", OAUTH_URL).replace("OAUTH_URL_JS", OAUTH_URL))


@router.post("/api/wp/token")
def save_wp_token(payload: dict):
    token = (payload.get("token") or "").strip()
    if not token:
        return JSONResponse({"ok": False, "error": "token is empty"}, status_code=400)

    try:
        resp = requests.get(
            f"https://public-api.wordpress.com/rest/v1.1/sites/{WORDPRESS_SITE}/posts?number=1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 401:
            return JSONResponse({"ok": False, "error": "Token rejected by WordPress"}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    set_active_token(token)
    _try_update_render_env(token)
    return {"ok": True, "message": "Token saved. Publishing will resume on next run."}


@router.get("/api/wp/status")
def wp_token_status():
    token = get_active_token()
    if not token:
        return {"valid": False, "reason": "No token configured"}
    try:
        resp = requests.get(
            f"https://public-api.wordpress.com/rest/v1.1/sites/{WORDPRESS_SITE}/posts?number=1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        valid = resp.status_code == 200
        return {
            "valid": valid,
            "reason": "OK" if valid else f"HTTP {resp.status_code}",
            "refresh_url": "https://affiliate-marketing-system-7994.onrender.com/wp-auth",
        }
    except Exception as e:
        return {"valid": False, "reason": str(e)}


def _try_update_render_env(token: str):
    render_key = os.getenv("RENDER_API_KEY", "")
    service_id = os.getenv("RENDER_SERVICE_ID", "srv-d9kgs8qjnfac73ampuv0")
    if not render_key:
        return
    try:
        requests.put(
            f"https://api.render.com/v1/services/{service_id}/env-vars",
            headers={"Authorization": f"Bearer {render_key}", "Accept": "application/json"},
            json=[{"key": "WORDPRESS_TOKEN", "value": token}],
            timeout=10,
        )
    except Exception:
        pass
