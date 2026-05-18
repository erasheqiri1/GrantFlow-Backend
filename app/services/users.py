import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.public.models import (
    User, UserRole, Role, Tenant,
    UserProfile, ApplicantProfile
)


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
        items.append({
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "role": _get_role_name(user, db),
            "created_at": user.created_at,
        })
    return {"total": len(items), "items": items}


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
