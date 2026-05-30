import re
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from app.core.database import SessionLocal
import jwt
from app.core.config import settings

_SLUG_RE = re.compile(r'^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$')


PUBLIC_PATHS = [
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/register",
    "/auth/login",
    "/auth/register-org",
    "/auth/register-org/upload-doc",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/invite/accept",
    "/auth/verify-email",
    "/tenants/public-stats",
]


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/tenants/public-stats"):
            return await call_next(request)


        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request)

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )
            tenant_slug = payload.get("tenant_slug")

            if tenant_slug:

                if not _SLUG_RE.match(tenant_slug):
                    return await call_next(request)

                db = SessionLocal()
                try:
                    db.execute(
                        text(f'SET search_path TO "{tenant_slug}", public')
                    )
                    request.state.tenant_slug = tenant_slug
                    request.state.db = db
                finally:
                    db.close()

        except Exception:
            pass

        return await call_next(request)
