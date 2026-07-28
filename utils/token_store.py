"""
Lightweight runtime token store.
Agents and API routes both import from here — no circular dependencies.
"""
import os

_runtime_token: str = ""


def get_active_token() -> str:
    """Return best available WP token: runtime cache → env var."""
    return _runtime_token or os.getenv("WORDPRESS_TOKEN", "")


def set_active_token(token: str):
    global _runtime_token
    _runtime_token = token
