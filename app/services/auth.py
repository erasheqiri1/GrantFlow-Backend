# app/services/auth.py

import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.public.models import User, Tenant, Role, UserRole, PasswordResetToken, EmailVerificationToken, TenantStatus, UserProfile, ApplicantProfile
from app.schemas.auth import (
    RegisterRequest,
    RegisterOrgRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    InviteAcceptRequest,
    TokenResponse,
)


# ─────────────────────────────────────────
# HELPERS — Password & JWT
# ─────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, role: str, tenant_slug: str | None) -> str:
    payload = {
        "user_id": str(user_id),
        "role": role,
        "tenant_slug": tenant_slug,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


# ─────────────────────────────────────────
# REGISTER — Aplikanti
# ─────────────────────────────────────────

def register_user(data: RegisterRequest, db: Session) -> dict:
    # kontrollo nëse ekziston email
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email ekziston tashmë")

    try:
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=False,
            email_verified=False,
        )
        db.add(user)
        db.flush()

        role = db.query(Role).filter(Role.name == "APPLICANT").first()
        user_role = UserRole(user_id=user.id, role_id=role.id, tenant_id=None)
        db.add(user_role)

        db.add(UserProfile(user_id=user.id))
        db.add(ApplicantProfile(user_id=user.id))

        token_value = secrets.token_urlsafe(32)
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token=token_value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(verification_token)

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Gabim gjatë regjistrimit")

    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token_value}"
    full_name = f"{data.first_name} {data.last_name}"
    try:
        from app.tasks.email import send_verification_email
        send_verification_email.delay(data.email, verify_link, full_name)
    except Exception:
        pass

    return {"message": "Llogaria u krijua. Kontrollo emailin tënd dhe kliko linkun për të aktivizuar llogarinë."}


# ─────────────────────────────────────────
# REGISTER — Organizata
# ─────────────────────────────────────────

def register_org(data: RegisterOrgRequest, db: Session) -> dict:
    # kontrollo slug
    existing_tenant = db.query(Tenant).filter(Tenant.slug == data.org_slug).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Ky slug ekziston tashmë")

    # kontrollo email
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email ekziston tashmë")

    try:
        tenant = Tenant(
            slug=data.org_slug,
            name=data.org_name,
            email=data.email,
            nipt=data.nipt,
            is_active=False,
            status=TenantStatus.PENDING,
        )
        db.add(tenant)
        db.flush()

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=False,
            email_verified=False,
        )
        db.add(user)
        db.flush()

        role = db.query(Role).filter(Role.name == "ORG_ADMIN").first()
        user_role = UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant.id)
        db.add(user_role)

        token_value = secrets.token_urlsafe(32)
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token=token_value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(verification_token)

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Gabim gjatë regjistrimit të organizatës")

    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token_value}"
    full_name = f"{data.first_name} {data.last_name}"
    print(f"[ORG REGISTER] dergon email te: {data.email}")
    print(f"[ORG REGISTER] verify_link: {verify_link}")
    try:
        from app.tasks.email import send_verification_email
        result = send_verification_email.delay(data.email, verify_link, full_name)
        print(f"[ORG REGISTER] task u enqueue-ua: {result.id}")
    except Exception as e:
        print(f"[ORG REGISTER] GABIM me email: {e}")

    return {"message": "Organizata u regjistrua. Kontrollo emailin tënd për të konfirmuar adresën."}


def verify_email(token: str, db: Session) -> dict:
    verification = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token == token
    ).first()

    if not verification:
        raise HTTPException(status_code=400, detail="Token i pavlefshëm")

    if verification.expires_at < datetime.now(timezone.utc):
        db.delete(verification)
        db.commit()
        raise HTTPException(status_code=400, detail="Token ka skaduar. Regjistrohu përsëri.")

    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Përdoruesi nuk u gjet")

    user.email_verified = True
    user.is_active = True
    db.delete(verification)
    db.commit()

    user_role = db.query(UserRole).filter(UserRole.user_id == user.id).first()
    role_obj  = db.query(Role).filter(Role.id == user_role.role_id).first() if user_role else None
    if role_obj and role_obj.name == "ORG_ADMIN":
        return {"message": "Email u konfirmua! Prisni aprovimin nga administratori para se të kyçeni."}
    return {"message": "Email u konfirmua me sukses. Tani mund të kyçeni."}


# ─────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────

def login_user(data: LoginRequest, db: Session) -> TokenResponse:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ose fjalëkalim i gabuar")

    if not user.is_active:
        if not user.email_verified:
            raise HTTPException(status_code=403, detail="Konfirmo emailin tënd para se të kyçesh")
        raise HTTPException(status_code=403, detail="Llogaria është joaktive")

    # gjen rolin
    tenant_slug_for_token = data.tenant_slug

    if data.tenant_slug:
        tenant = db.query(Tenant).filter(Tenant.slug == data.tenant_slug).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
        if tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Organizata nuk është aprovuar ende")

        user_role = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.tenant_id == tenant.id
        ).first()

        if not user_role:
            user_role = db.query(UserRole).filter(
                UserRole.user_id == user.id,
                UserRole.tenant_id == None
            ).first()
    else:
        user_role = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.tenant_id == None
        ).first()

        if not user_role:
            tenant_roles = (
                db.query(UserRole)
                .filter(UserRole.user_id == user.id, UserRole.tenant_id != None)
                .all()
            )

            if len(tenant_roles) == 1:
                user_role = tenant_roles[0]
                tenant = db.query(Tenant).filter(Tenant.id == user_role.tenant_id).first()
                if tenant:
                    if tenant.status != TenantStatus.ACTIVE:
                        raise HTTPException(status_code=403, detail="Organizata nuk është aprovuar ende")
                    tenant_slug_for_token = tenant.slug
            elif len(tenant_roles) > 1:
                slugs = []
                for tr in tenant_roles:
                    t = db.query(Tenant).filter(Tenant.id == tr.tenant_id).first()
                    if t:
                        slugs.append(t.slug)
                raise HTTPException(
                    status_code=400,
                    detail=f"Keni akses në shumë organizata. Specifikoni slug-un: {', '.join(slugs)}"
                )

    if not user_role:
        raise HTTPException(status_code=403, detail="Nuk ke akses")

    role_name = db.query(Role).filter(Role.id == user_role.role_id).first().name
    token = create_token(user.id, role_name, tenant_slug_for_token)
    return TokenResponse(access_token=token, role=role_name, user_id=str(user.id), tenant_slug=tenant_slug_for_token)


# ─────────────────────────────────────────
# FORGOT PASSWORD
# ─────────────────────────────────────────

def forgot_password(data: ForgotPasswordRequest, db: Session) -> dict:
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Ky email nuk ekziston në sistem.")

    # fshi token të vjetër nëse ekziston
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()

    token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset_token)
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    try:
        from app.tasks.email import send_reset_password_email
        send_reset_password_email.delay(user.email, reset_link)
    except Exception:
        pass

    return {"message": "Nëse email ekziston, do të marrësh udhëzime."}


# ─────────────────────────────────────────
# RESET PASSWORD
# ─────────────────────────────────────────

def reset_password(data: ResetPasswordRequest, db: Session) -> dict:
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == data.token
    ).first()

    if not reset_token:
        raise HTTPException(status_code=400, detail="Token i pavlefshëm")

    if reset_token.expires_at < datetime.now(timezone.utc):
        db.delete(reset_token)
        db.commit()
        raise HTTPException(status_code=400, detail="Token ka skaduar")

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    user.password_hash = hash_password(data.new_password)

    db.delete(reset_token)
    db.commit()

    return {"message": "Fjalëkalimi u ndryshua me sukses"}


# ─────────────────────────────────────────
# INVITE ACCEPT
# ─────────────────────────────────────────

def accept_invite(data: InviteAcceptRequest, db: Session) -> TokenResponse:

    try:
        payload = jwt.decode(data.token, settings.SECRET_KEY, algorithms=["HS256"])
        tenant_slug = payload.get("tenant_slug")
        invite_email = payload.get("email")
        invite_role = payload.get("role")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Ftesa ka skaduar")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token i pavlefshëm")

    tenant = None
    if tenant_slug:
        tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organizata nuk u gjet")

    # kontrollon nëse email ekziston
    existing = db.query(User).filter(User.email == invite_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email ekziston tashmë")

    try:
        user = User(
            email=invite_email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=True,
        )
        db.add(user)
        db.flush()

        role = db.query(Role).filter(Role.name == invite_role).first()
        user_role = UserRole(
            user_id=user.id,
            role_id=role.id,
            tenant_id=tenant.id if tenant else None,
        )
        db.add(user_role)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Gabim gjatë aktivizimit të ftesës")

    token = create_token(user.id, invite_role, tenant_slug)
    return TokenResponse(access_token=token, role=invite_role, user_id=str(user.id), tenant_slug=tenant_slug)