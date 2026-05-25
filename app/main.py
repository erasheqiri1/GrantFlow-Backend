import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.middleware.auth import AuthMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.logging import LoggingMiddleware

from app.routers import auth, profile, tenants, grants, team, users, applications, criteria, audit

# Sigurohemi që direktoria uploads ekziston
os.makedirs("uploads/attachments", exist_ok=True)




app = FastAPI(
    title="GrantFlow API",
    description="Platformë SaaS për menaxhimin e granteve",
    version="1.0.0",
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


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "GrantFlow API"}