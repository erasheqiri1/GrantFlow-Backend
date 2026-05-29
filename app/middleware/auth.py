from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import jwt
from app.core.config import settings
from app.core.redis_client import is_token_blacklisted


PUBLIC_PATHS = [
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/register",
    "/auth/login",
    "/auth/logout",
    "/auth/register-org",
    "/auth/register-org/upload-doc",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/invite/accept",
    "/auth/verify-email",
    "/auth/refresh",
    "/tenants/public-stats",
]

PUBLIC_PREFIXES = [
    "/uploads",
    "/tenants/public-stats",
]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token mungon"}
            )

        try:
            token = auth_header.split(" ")[1]

            # Kontrollo blacklist para decode
            if is_token_blacklisted(token):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token është invaliduar. Kyçu sërish."}
                )

            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )

            request.state.user_id = payload.get("user_id")
            request.state.role = payload.get("role")
            request.state.tenant_slug = payload.get("tenant_slug")

        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token ka skaduar"}
            )
        except jwt.InvalidTokenError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token i pavlefshëm"}
            )

        return await call_next(request)
