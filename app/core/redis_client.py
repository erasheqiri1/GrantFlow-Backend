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
    """Kthe vlerën nga cache ose None nëse nuk ekziston."""
    try:
        value = get_redis().get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def cache_set(key: str, value, ttl: int = 60):
    """Ruaj vlerën në cache me TTL (sekonda)."""
    try:
        get_redis().setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete_pattern(pattern: str):
    """Fshi të gjitha çelësat që përputhen me pattern-in (p.sh. 'grants:public:*')."""
    try:
        r = get_redis()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass
