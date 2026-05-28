import os
import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.middleware.auth import AuthMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.logging import LoggingMiddleware

from app.routers import auth, profile, tenants, grants, team, users, applications, criteria, audit, permissions

logger = logging.getLogger("grantflow")

# Sigurohemi që direktoria uploads ekziston
os.makedirs("uploads/attachments", exist_ok=True)


app = FastAPI(
    title="GrantFlow API",
    description="Platformë SaaS për menaxhimin e granteve",
    version="1.0.0",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Kap çdo gabim të papritur — loggon stack trace, kthek klientit mesazh të sigurt."""
    logger.error(
        "Gabim i papritur: %s %s\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Gabim i brendshëm i serverit. Ju lutemi provoni përsëri."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(TenantMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(tenants.router)

app.include_router(users.router)

app.include_router(grants.router)
app.include_router(team.router)
app.include_router(applications.router)
app.include_router(criteria.router)
app.include_router(audit.router)
app.include_router(permissions.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "GrantFlow API"}