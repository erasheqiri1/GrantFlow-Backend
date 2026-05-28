import hashlib
import json
import redis
from app.core.config import settings

# Lidhja me Redis — DB 1 për cache (DB 0 është për Celery)
_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, db=1, decode_responses=True)
    return _client


def cache_get(key: str):
    """Kthen vleren nga cache ose None nese nuk ekziston."""
    try:
        value = get_redis().get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def cache_set(key: str, value, ttl: int = 60):
    """Ruajn vlerën në cache me TTL."""
    try:
        get_redis().setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete_pattern(pattern: str):
    """Fshin te gjitha qelesat qe perputhen me pattern."""
    try:
        r = get_redis()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


# ── Token blacklist ──────────────────────────────────────────────────────────

def blacklist_token(token: str, ttl_seconds: int) -> None:
    """Vendos token-in në blacklist deri sa të skadojë."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        get_redis().setex(f"bl:{token_hash}", max(ttl_seconds, 1), "1")
    except Exception:
        pass


def is_token_blacklisted(token: str) -> bool:
    """Kontrollon nëse token-i është në blacklist."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        return bool(get_redis().exists(f"bl:{token_hash}"))
    except Exception:
        return False


# ── Rate limiting ────────────────────────────────────────────────────────────

def rate_limit_check(key: str, max_requests: int, window_seconds: int) -> bool:
    """
    Kthen True nëse kërkesa lejohet, False nëse kufiri është tejkaluar.
    Nëse Redis nuk është aktiv, lejon kalimin (fail-open).
    """
    try:
        r = get_redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, window_seconds)
        return count <= max_requests
    except Exception:
        return True
