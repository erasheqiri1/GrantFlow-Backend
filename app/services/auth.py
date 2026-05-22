# app/services/auth.py

import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.public.models import User, Tenant, Role, UserRole, PasswordResetToken, TenantStatus, UserProfile, ApplicantProfile
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
# REGISTER — Applicant
# ─────────────────────────────────────────

def register_user(data: RegisterRequest, db: Session) -> TokenResponse:
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
            is_active=True,
        )
        db.add(user)
        db.flush()

        role = db.query(Role).filter(Role.name == "APPLICANT").first()
        user_role = UserRole(user_id=user.id, role_id=role.id, tenant_id=None)
        db.add(user_role)

        db.add(UserProfile(user_id=user.id))
        db.add(ApplicantProfile(user_id=user.id))

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Gabim gjatë regjistrimit")

    token = create_token(user.id, "APPLICANT", None)
    return TokenResponse(access_token=token, role="APPLICANT", user_id=str(user.id))


# ─────────────────────────────────────────
# REGISTER — Organization
# ─────────────────────────────────────────

def register_org(data: RegisterOrgRequest, db: Session) -> TokenResponse:
    # kontrollo slug
    existing_tenant = db.query(Tenant).filter(Tenant.slug == data.org_slug).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Ky slug ekziston tashmë")

    # kontrollo email
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email ekziston tashmë")

    schema_name = f"tenant_{data.org_slug.replace('-', '_')}"

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
            is_active=True,
        )
        db.add(user)
        db.flush()

        role = db.query(Role).filter(Role.name == "ORG_ADMIN").first()
        user_role = UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant.id)
        db.add(user_role)

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Gabim gjatë regjistrimit të organizatës")

    return {"message": "Organizata u regjistrua me sukses. Prisni aprovimin nga Super Admin."}


def _create_tenant_schema(db: Session, schema_name: str):
    """Krijon schema dhe të 17 tabelat dinamikisht."""
    db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    tables_sql = f"""
    CREATE TABLE IF NOT EXISTS "{schema_name}".grants (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        title VARCHAR(255) NOT NULL,
        description TEXT,
        total_budget NUMERIC(12,2),
        max_applicants INTEGER,
        deadline TIMESTAMPTZ,
        status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
        created_by UUID REFERENCES public.users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".criteria (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        grant_id UUID NOT NULL REFERENCES "{schema_name}".grants(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        weight NUMERIC(3,2) DEFAULT 1.0,
        is_required BOOLEAN DEFAULT TRUE
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".grant_tags (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        grant_id UUID NOT NULL REFERENCES "{schema_name}".grants(id) ON DELETE CASCADE,
        tag VARCHAR(100) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".application_questions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        grant_id UUID NOT NULL REFERENCES "{schema_name}".grants(id) ON DELETE CASCADE,
        question TEXT NOT NULL,
        is_required BOOLEAN DEFAULT TRUE,
        order_index INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".applications (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        grant_id UUID NOT NULL REFERENCES "{schema_name}".grants(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES public.users(id),
        status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
        motivation_letter TEXT,
        submitted_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".application_answers (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES "{schema_name}".applications(id) ON DELETE CASCADE,
        question_id UUID NOT NULL REFERENCES "{schema_name}".application_questions(id),
        answer TEXT
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".cvs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES "{schema_name}".applications(id) ON DELETE CASCADE,
        file_path VARCHAR(500),
        file_name VARCHAR(255),
        parsed_text TEXT,
        uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".attachments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES "{schema_name}".applications(id) ON DELETE CASCADE,
        file_path VARCHAR(500),
        file_name VARCHAR(255),
        file_type VARCHAR(100),
        size_bytes INTEGER
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".ai_scores (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES "{schema_name}".applications(id) ON DELETE CASCADE,
        score NUMERIC(5,2),
        justification TEXT,
        model_used VARCHAR(100),
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        is_cached BOOLEAN DEFAULT FALSE
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".commissioner_scores (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES "{schema_name}".applications(id) ON DELETE CASCADE,
        commissioner_id UUID NOT NULL REFERENCES public.users(id),
        score NUMERIC(5,2),
        notes TEXT,
        scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".commissioner_decisions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES "{schema_name}".applications(id) ON DELETE CASCADE,
        commissioner_id UUID NOT NULL REFERENCES public.users(id),
        decision VARCHAR(20) NOT NULL,
        reason TEXT,
        decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_decision_application UNIQUE (application_id)
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".commissioner_workload (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        commissioner_id UUID NOT NULL REFERENCES public.users(id),
        grant_id UUID NOT NULL REFERENCES "{schema_name}".grants(id) ON DELETE CASCADE,
        assigned_count INTEGER DEFAULT 0,
        CONSTRAINT uq_commissioner_grant UNIQUE (commissioner_id, grant_id)
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".invitations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL,
        token VARCHAR(255) NOT NULL UNIQUE,
        invited_by UUID REFERENCES public.users(id),
        is_used BOOLEAN DEFAULT FALSE,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".notifications (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
        title VARCHAR(255),
        message TEXT,
        type VARCHAR(20) DEFAULT 'IN_APP',
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".email_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        to_email VARCHAR(255) NOT NULL,
        subject VARCHAR(255),
        status VARCHAR(20) DEFAULT 'PENDING',
        sent_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS "{schema_name}".application_status_updates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES "{schema_name}".applications(id) ON DELETE CASCADE,
        old_status VARCHAR(30),
        new_status VARCHAR(30) NOT NULL,
        changed_by UUID REFERENCES public.users(id),
        changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    db.execute(text(tables_sql))


# ─────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────

def login_user(data: LoginRequest, db: Session) -> TokenResponse:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ose fjalëkalim i gabuar")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Llogaria është joaktive")

    # gjej rolin
    tenant_slug_for_token = data.tenant_slug

    if data.tenant_slug:
        # Slug i dhënë eksplicitisht — valido dhe gjej rolin
        tenant = db.query(Tenant).filter(Tenant.slug == data.tenant_slug).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
        if tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Organizata nuk është aprovuar ende")

        user_role = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.tenant_id == tenant.id
        ).first()

        # fallback te roli global nëse nuk ka rol specifik tenant
        if not user_role:
            user_role = db.query(UserRole).filter(
                UserRole.user_id == user.id,
                UserRole.tenant_id == None
            ).first()
    else:
        # Pa slug — provoj rolin global (applicant)
        user_role = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.tenant_id == None
        ).first()

        if not user_role:
            # Nuk ka rol global — auto-detekto tenant-in nga user_roles
            tenant_roles = (
                db.query(UserRole)
                .filter(UserRole.user_id == user.id, UserRole.tenant_id != None)
                .all()
            )

            if len(tenant_roles) == 1:
                # Vetëm një tenant — kyçu automatikisht pa slug
                user_role = tenant_roles[0]
                tenant = db.query(Tenant).filter(Tenant.id == user_role.tenant_id).first()
                if tenant:
                    if tenant.status != TenantStatus.ACTIVE:
                        raise HTTPException(status_code=403, detail="Organizata nuk është aprovuar ende")
                    tenant_slug_for_token = tenant.slug
            elif len(tenant_roles) > 1:
                # Shumë tenantë — kërko slug eksplicit
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
    # nuk tregojmë nëse ekziston apo jo — security
    if not user:
        return {"message": "Nëse email ekziston, do të marrësh udhëzime."}

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

    # TODO: dërgo email me token (Celery task)
    # send_reset_email.delay(user.email, token)

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
    # gjej invitation në tenant schema
    # NOTE: tenant_slug duhet të vijë nga token — këtu e marrim nga JWT i ftesës
    # Për thjeshtësi, invitation token kodon tenant_slug brenda

    # decode token i ftesës për të marrë tenant_slug
    try:
        payload = jwt.decode(data.token, settings.SECRET_KEY, algorithms=["HS256"])
        tenant_slug = payload.get("tenant_slug")
        invite_email = payload.get("email")
        invite_role = payload.get("role")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Ftesa ka skaduar")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token i pavlefshëm")

    # Gjej tenant nëse ka slug (SUPER_ADMIN nuk ka tenant)
    tenant = None
    if tenant_slug:
        tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organizata nuk u gjet")

    # kontrollo nëse email ekziston
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