# app/routers/auth.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
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


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Regjistrim i aplikantit të ri."""
    return auth_service.register_user(data, db)


@router.post("/register-org", response_model=MessageResponse, status_code=202)
def register_org(data: RegisterOrgRequest, db: Session = Depends(get_db)):
    """Regjistrim i organizatës së re + ORG_ADMIN. Pret aprovimin nga Super Admin."""
    return auth_service.register_org(data, db)


@router.post("/login", response_model=TokenResponse, status_code=200)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Login — kthen JWT token."""
    return auth_service.login_user(data, db)


@router.post("/forgot-password", response_model=MessageResponse, status_code=202)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Kërko reset të fjalëkalimit."""
    return auth_service.forgot_password(data, db)


@router.post("/reset-password", response_model=MessageResponse, status_code=200)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Ndrysho fjalëkalimin me token."""
    return auth_service.reset_password(data, db)


@router.post("/invite/accept", response_model=TokenResponse, status_code=201)
def accept_invite(data: InviteAcceptRequest, db: Session = Depends(get_db)):
    """Prano ftesën dhe krijo llogarinë."""
    return auth_service.accept_invite(data, db)