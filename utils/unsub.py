"""Signed unsubscribe links (CAN-SPAM requires a working opt-out in every marketing email)."""
import hmac
import hashlib
from urllib.parse import quote
from config.settings import SECRET_KEY, BASE_URL


def make_token(email: str) -> str:
    return hmac.new(SECRET_KEY.encode(), email.lower().encode(), hashlib.sha256).hexdigest()[:32]


def verify_token(email: str, token: str) -> bool:
    return hmac.compare_digest(make_token(email), token or "")


def unsubscribe_url(email: str) -> str:
    return f"{BASE_URL.rstrip('/')}/unsubscribe?e={quote(email)}&t={make_token(email)}"
