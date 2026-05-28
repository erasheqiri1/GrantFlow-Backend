# app/routers/auth.py

import os
import time
import uuid as _uuid

import jwt as _jwt
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import blacklist_token, rate_limit_check
from app.models.public.models import Tenant
from app.schemas.auth import (
    RegisterRequest,
    RegisterOrgRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    InviteAcceptRequest,
    TokenResponse,
    MessageResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=MessageResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Regjistrim i aplikantit të ri — dërgon email verifikimi."""
    return auth_service.register_user(data, db)


@router.post("/register-org", response_model=MessageResponse, status_code=202)
def register_org(data: RegisterOrgRequest, db: Session = Depends(get_db)):
    """Regjistrim i organizatës së re + ORG_ADMIN. Pret aprovimin nga Super Admin."""
    return auth_service.register_org(data, db)


@router.post("/login", response_model=TokenResponse, status_code=200)
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    """Login — kthen JWT token. Max 10 tentativa/minutë për IP."""
    client_ip = (request.client.host if request.client else "unknown")
    if not rate_limit_check(f"rl:login:{client_ip}", 10, 60):
        raise HTTPException(status_code=429, detail="Shumë tentativa. Provo pas 1 minutë.")
    return auth_service.login_user(data, db)


@router.post("/logout", response_model=MessageResponse, status_code=200)
def logout(request: Request):
    """Invalido token-in aktual duke e shtuar në blacklist."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = _jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            ttl = max(int(payload.get("exp", time.time()) - time.time()), 1)
            blacklist_token(token, ttl)
        except Exception:
            pass
    return {"message": "Logout i suksesshëm"}


@router.post("/forgot-password", response_model=MessageResponse, status_code=202)
def forgot_password(request: Request, data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Kërko reset të fjalëkalimit. Max 5 tentativa/minutë për IP."""
    client_ip = (request.client.host if request.client else "unknown")
    if not rate_limit_check(f"rl:forgot:{client_ip}", 5, 60):
        raise HTTPException(status_code=429, detail="Shumë tentativa. Provo pas 1 minutë.")
    return auth_service.forgot_password(data, db)


@router.post("/reset-password", response_model=MessageResponse, status_code=200)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Ndrysho fjalëkalimin me token."""
    return auth_service.reset_password(data, db)


@router.post("/register-org/upload-doc", status_code=200)
async def upload_org_doc(
    org_slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ALLOWED = {"application/pdf", "image/jpeg", "image/png"}
    MAX_SIZE = 5 * 1024 * 1024  # 5 MB

    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=415, detail="Lejohen vetëm PDF, JPG, PNG")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Skedari është shumë i madh (max 5 MB)")

    tenant = db.query(Tenant).filter(Tenant.slug == org_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Organizata nuk u gjet")

    upload_dir = os.path.join("uploads", "org-docs")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "doc")[1] or ".pdf"
    unique_name = f"{_uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, unique_name)

    with open(file_path, "wb") as f:
        f.write(contents)

    tenant.doc_path = file_path
    db.commit()

    return {"message": "Dokumenti u ngarkua me sukses."}


@router.get("/verify-email", response_model=MessageResponse, status_code=200)
def verify_email(token: str, db: Session = Depends(get_db)):
    """Konfirmo emailin me token të dërguar gjatë regjistrimit."""
    return auth_service.verify_email(token, db)


@router.post("/invite/accept", response_model=TokenResponse, status_code=201)
def accept_invite(data: InviteAcceptRequest, db: Session = Depends(get_db)):
    """Personi i ftuar pranon ftesën dhe krijon llogarinë."""
    return auth_service.accept_invite(data, db)