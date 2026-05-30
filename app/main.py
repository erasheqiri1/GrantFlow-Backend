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
from app.core.config import settings

from app.routers import auth, profile, tenants, grants, team, users, applications, criteria, audit, permissions, payments, chatbot

logger = logging.getLogger("grantflow")

# Sigurohemi që direktoria uploads ekziston
os.makedirs("uploads/attachments", exist_ok=True)

# /docs dhe /redoc aktive vetëm në development
_ENV = os.getenv("ENV", "development")
_docs_url    = "/docs"         if _ENV != "production" else None
_redoc_url   = "/redoc"        if _ENV != "production" else None
_openapi_url = "/openapi.json" if _ENV != "production" else None

app = FastAPI(
    title="GrantFlow API",
    description="""
## Platformë SaaS për menaxhimin e granteve

### Autentikimi
Të gjitha endpoint-at (përveç `/auth/*` dhe `/tenants/public-stats`) kërkojnë **Bearer Token** në header:
```
Authorization: Bearer <access_token>
```

### Rolet
| Rol | Përshkrim |
|-----|-----------|
| `SUPER_ADMIN` | Menaxhon platformën, aprovon organizata |
| `ORG_ADMIN` | Menaxhon organizatën, grantet dhe ekipin |
| `COMMISSIONER` | Shqyrton dhe vlerëson aplikimet |
| `APPLICANT` | Aplikon për grante |

### Rate Limiting
- Login: **3 tentativa / minutë** për IP
- Forgot Password: **5 tentativa / minutë** për IP

### Variablat e mjedisit (`.env`)
| Variabla | Development | Production |
|----------|-------------|------------|
| `ENV` | `development` | `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | `15` (rekomandohet) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | `7` |
| `FRONTEND_URL` | `http://localhost:3000` | `https://domain-yt.com` |
""",
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
    openapi_tags=[
        {"name": "Auth",         "description": "Regjistrim, kyçje, logout, reset fjalëkalimi"},
        {"name": "Profile",      "description": "Profili i userit të kyçur"},
        {"name": "Grants",       "description": "Menaxhimi i granteve"},
        {"name": "Applications", "description": "Aplikimet për grante"},
        {"name": "Team",         "description": "Ekipi i organizatës dhe ftesa"},
        {"name": "Tenants",      "description": "Menaxhimi i organizatave (Super Admin)"},
        {"name": "Users",        "description": "Menaxhimi i përdoruesve (Super Admin)"},
        {"name": "Audit",        "description": "Log-et e veprimeve në platformë"},
    ],
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
    allow_origins=[settings.FRONTEND_URL],
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
app.include_router(payments.router)
app.include_router(chatbot.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "GrantFlow API"}