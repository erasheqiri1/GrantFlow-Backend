import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.public.models import (
    User, UserRole, Role, Tenant, TenantStatus,
    UserProfile, ApplicantProfile, RoleName
)
from app.services.audit import log_action


def _get_role_name(user: User, db: Session) -> Optional[str]:
    user_role = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id)
        .order_by(UserRole.created_at.desc())
        .first()
    )
    if not user_role:
        return None
    role = db.query(Role).filter(Role.id == user_role.role_id).first()
    return role.name.value if role else None


def _get_tenant(user: User, db: Session) -> Optional[Tenant]:
    user_role = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id, UserRole.tenant_id.isnot(None))
        .order_by(UserRole.created_at.desc())
        .first()
    )
    if not user_role or not user_role.tenant_id:
        return None
    return db.query(Tenant).filter(Tenant.id == user_role.tenant_id).first()


def get_users(db: Session) -> dict:
    users = db.query(User).order_by(User.created_at.desc()).all()
    items = []
    for user in users:
        # SQL direkt për tenant_status — shmang çdo problem me ORM/enum
        row = db.execute(
            text("""
                SELECT t.status::text
                FROM public.user_roles ur
                JOIN public.tenants t ON t.id = ur.tenant_id
                WHERE ur.user_id = :uid
                  AND ur.tenant_id IS NOT NULL
                LIMIT 1
            """),
            {"uid": str(user.id)}
        ).fetchone()

        items.append({
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "role": _get_role_name(user, db),
            "created_at": user.created_at,
            "tenant_status": row[0] if row else None,
        })
    return {"total": len(items), "items": items}


def toggle_user_active(db: Session, user_id: str, requester_id: str) -> dict:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID i pavlefshëm")

    if str(uid) == requester_id:
        raise HTTPException(status_code=400, detail="Nuk mund ta deaktivizoni llogarinë tuaj")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Useri nuk u gjet")

    user.is_active = not user.is_active
    db.commit()

    action = "ACTIVATE_USER" if user.is_active else "DEACTIVATE_USER"
    log_action(requester_id, action, "user", user_id,
               details={"email": user.email})

    status = "aktivizuar" if user.is_active else "deaktivizuar"
    return {"message": f"Useri u {status} me sukses.", "is_active": user.is_active}


def create_super_admin(db: Session, data) -> dict:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email ekziston tashmë")

    password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=data.email,
        password_hash=password_hash,
        first_name=data.first_name,
        last_name=data.last_name,
        is_active=True,
    )
    db.add(user)
    db.flush()

    role = db.query(Role).filter(Role.name == RoleName.SUPER_ADMIN).first()
    db.add(UserRole(id=uuid.uuid4(), user_id=user.id, role_id=role.id, tenant_id=None))
    db.commit()

    log_action(str(user.id), "CREATE_SUPER_ADMIN", "user", str(user.id),
               details={"email": data.email})

    return {"message": f"Super Admin '{data.email}' u krijua me sukses."}


def invite_super_admin(db: Session, email: str, requester_id: str) -> dict:
    """Dërgon ftesë me email për Super Admin të ri (Celery background task)."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ky email ekziston tashmë")

    # Krijo token invitation (skadon pas 48 orësh)
    token = jwt.encode(
        {
            "email": email,
            "role":  "SUPER_ADMIN",
            "tenant_slug": None,
            "exp":   datetime.now(timezone.utc) + timedelta(hours=48),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"

    # Celery task — dërgon email në background
    from app.tasks.email import send_invitation_email
    send_invitation_email.delay(email, invite_link, "SUPER_ADMIN")

    log_action(requester_id, "INVITE_SUPER_ADMIN", "user", None,
               details={"email": email})

    return {"message": f"Ftesa u dërgua te '{email}'. Linku skadon pas 48 orësh."}


def get_user(db: Session, user_id: str) -> dict:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID i pavlefshëm")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Useri nuk u gjet")

    profile = db.query(UserProfile).filter(UserProfile.user_id == uid).first()
    applicant = db.query(ApplicantProfile).filter(ApplicantProfile.user_id == uid).first()
    tenant = _get_tenant(user, db)
    role_name = _get_role_name(user, db)

    return {
        # Bazë
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
        "role": role_name,
        "created_at": user.created_at,

        # Profili
        "phone": profile.phone if profile else None,
        "profile_picture": profile.profile_picture if profile else None,
        "address": profile.address if profile else None,

        # Tenant
        "tenant_name": tenant.name if tenant else None,
        "tenant_slug": tenant.slug if tenant else None,

        # Applicant profili
        "applicant_type": applicant.applicant_type.value if applicant and applicant.applicant_type else None,
        "has_prev_grant": applicant.has_prev_grant if applicant else None,
        "description": applicant.description if applicant else None,

        "study_level": applicant.study_level if applicant else None,
        "study_status": applicant.study_status if applicant else None,
        "study_year": applicant.study_year if applicant else None,
        "faculty": applicant.faculty if applicant else None,
        "study_program": applicant.study_program if applicant else None,
        "university": applicant.university if applicant else None,

        "business_name": applicant.business_name if applicant else None,
        "business_type": applicant.business_type if applicant else None,
        "activity_field": applicant.activity_field if applicant else None,
        "num_employees": applicant.num_employees if applicant else None,
        "founded_year": applicant.founded_year if applicant else None,

        "org_name": applicant.org_name if applicant else None,
        "org_type": applicant.org_type if applicant else None,
        "org_field": applicant.org_field if applicant else None,
        "num_staff": applicant.num_staff if applicant else None,
        "org_founded_year": applicant.org_founded_year if applicant else None,
        "reg_number": applicant.reg_number if applicant else None,

        "profession": applicant.profession if applicant else None,
        "experience_years": applicant.experience_years if applicant else None,
        "key_skills": applicant.key_skills if applicant else None,
        "portfolio_url": applicant.portfolio_url if applicant else None,
        "cv_path": applicant.cv_path if applicant else None,

        "role_title": applicant.role_title if applicant else None,
        "interest_field": applicant.interest_field if applicant else None,
        "relevant_link": applicant.relevant_link if applicant else None,
    }
