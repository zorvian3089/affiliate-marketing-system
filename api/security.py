"""
Admin protection for every state-changing endpoint.

- Set ADMIN_API_KEY in the environment (Render dashboard / .env).
- Clients send it as header `X-Admin-Key` (or `?key=` for webhook URLs, since networks
  like ClickBank IPN can't set headers).
- If ADMIN_API_KEY is empty, writes are only accepted from localhost (fail closed on Render).
"""
import hmac
from fastapi import Request
from fastapi.responses import JSONResponse
from config.settings import ADMIN_API_KEY

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PROTECTED_GET_PREFIXES = ("/api/agents/bluesky/debug", "/api/agents/clickbank/hoplinks")
_LOCAL = {"127.0.0.1", "::1", "localhost"}


def _authorized(request: Request) -> bool:
    supplied = request.headers.get("x-admin-key") or request.query_params.get("key") or ""
    if ADMIN_API_KEY:
        return hmac.compare_digest(supplied, ADMIN_API_KEY)
    return bool(request.client and request.client.host in _LOCAL)


async def admin_guard(request: Request, call_next):
    needs_auth = request.method in _WRITE_METHODS or request.url.path.startswith(_PROTECTED_GET_PREFIXES)
    # Public: click redirect is a GET anyway; CORS preflight must pass.
    if request.method == "OPTIONS":
        needs_auth = False
    if needs_auth and not _authorized(request):
        return JSONResponse({"detail": "Unauthorized — missing or invalid admin key"}, status_code=401)
    return await call_next(request)
