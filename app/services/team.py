import uuid
import jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.models.public.models import User, UserRole, Role, Tenant
from app.models.tenant.models import Invitation
from app.schemas.team import InviteRequest, TeamMemberResponse
from app.services.audit import log_action


def _get_tenant(tenant_slug: str, db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
    return tenant


def send_invite(data: InviteRequest, current_user: dict, db: Session) -> dict:
    tenant_slug = current_user["tenant_slug"]
    if not tenant_slug:
        raise HTTPException(status_code=403, detail="Nuk je pjese e nje organizate")

    tenant = _get_tenant(tenant_slug, db)

    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        already_member = (
            db.query(UserRole)
            .filter(UserRole.user_id == existing_user.id, UserRole.tenant_id == tenant.id)
            .first()
        )
        if already_member:
            raise HTTPException(status_code=400, detail="Ky user eshte tashme anetar i org-ut")

    role = db.query(Role).filter(Role.name == data.role).first()
    if not role:
        raise HTTPException(status_code=400, detail="Roli nuk u gjet")

    token_payload = {
        "email": data.email,
        "role": data.role,
        "tenant_slug": tenant_slug,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    invite_token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm="HS256")

    invitation = Invitation(
        id=uuid.uuid4(),
        email=data.email,
        role_id=role.id,
        invited_by=uuid.UUID(current_user["user_id"]),
        token=invite_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_used=False,
    )
    db.add(invitation)
    db.commit()
    log_action(current_user["user_id"], "INVITE_USER", "invitation",
               tenant_id=str(tenant.id), details={"email": data.email, "role": data.role})

    # TODO: Celery -- dergo email me invite_token
    return {"message": "Ftesa u dergua", "token": invite_token}


def get_team(current_user: dict, db: Session) -> list[TeamMemberResponse]:
    tenant_slug = current_user["tenant_slug"]
    if not tenant_slug:
        raise HTTPException(status_code=403, detail="Nuk je pjese e nje organizate")

    tenant = _get_tenant(tenant_slug, db)

    rows = (
        db.query(User, Role)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.tenant_id == tenant.id)
        .all()
    )

    return [
        TeamMemberResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=role.name.value,
        )
        for user, role in rows
    ]


def remove_member(member_id: str, current_user: dict, db: Session) -> None:
    if member_id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Nuk mund te largosh veten")

    tenant = _get_tenant(current_user["tenant_slug"], db)

    user_role = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == uuid.UUID(member_id),
            UserRole.tenant_id == tenant.id,
        )
        .first()
    )
    if not user_role:
        raise HTTPException(status_code=404, detail="Anetari nuk u gjet ne kete organizate")

    db.delete(user_role)
    db.commit()
