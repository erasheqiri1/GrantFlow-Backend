from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.middleware.auth import AuthMiddleware
from app.middleware.tenant import TenantMiddleware
from app.routers import auth

security = HTTPBearer()

app = FastAPI(
    title="GrantFlow API",
    description="Platformë SaaS për menaxhimin e granteve",
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TenantMiddleware)
app.add_middleware(AuthMiddleware)

app.include_router(auth.router)

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "GrantFlow API"}