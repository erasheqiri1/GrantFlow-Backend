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


class TeamService:

    def __init__(self, db: Session):
        self.db = db

    def _get_tenant(self, tenant_slug: str) -> Tenant:
        tenant = self.db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
        return tenant

    def send_invite(self, data: InviteRequest, current_user: dict) -> dict:
        tenant_slug = current_user["tenant_slug"]
        if not tenant_slug:
            raise HTTPException(status_code=403, detail="Nuk je pjese e nje organizate")

        tenant = self._get_tenant(tenant_slug)

        existing_user = self.db.query(User).filter(User.email == data.email).first()
        if existing_user:
            already_member = (
                self.db.query(UserRole)
                .filter(UserRole.user_id == existing_user.id, UserRole.tenant_id == tenant.id)
                .first()
            )
            if already_member:
                raise HTTPException(status_code=400, detail="Ky user eshte tashme anetar i org-ut")

        role = self.db.query(Role).filter(Role.name == data.role).first()
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
        self.db.add(invitation)
        self.db.commit()
        log_action(current_user["user_id"], "INVITE_USER", "invitation",
                   tenant_id=str(tenant.id), details={"email": data.email, "role": data.role})

        invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={invite_token}"
        email_sent = False
        try:
            from app.tasks.email import send_invitation_email
            send_invitation_email.delay(data.email, invite_link, data.role, tenant.name)
            email_sent = True
        except Exception:
            pass

        return {
            "message": "Ftesa u gjenerua" if not email_sent else "Ftesa u dërgua me email",
            "token": invite_token,
            "invite_link": invite_link,
        }

    def get_team(
        self,
        current_user: dict,
        sort_by: str = "email",
        sort_dir: str = "asc",
        page: int = 1,
        size: int = 50,
    ) -> dict:
        tenant_slug = current_user["tenant_slug"]
        if not tenant_slug:
            raise HTTPException(status_code=403, detail="Nuk je pjese e nje organizate")

        tenant = self._get_tenant(tenant_slug)

        col_map = {
            "email":      User.email,
            "first_name": User.first_name,
            "last_name":  User.last_name,
            "role":       Role.name,
        }
        col = col_map.get(sort_by, User.email)
        order = col.asc() if sort_dir == "asc" else col.desc()

        query = (
            self.db.query(User, Role)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(UserRole.tenant_id == tenant.id)
        )
        total = query.count()
        rows = query.order_by(order).offset((page - 1) * size).limit(size).all()

        items = [
            TeamMemberResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role=role.name.value,
            )
            for user, role in rows
        ]
        return {"total": total, "page": page, "size": size, "items": items}

    def remove_member(self, member_id: str, current_user: dict) -> None:
        if member_id == current_user["user_id"]:
            raise HTTPException(status_code=400, detail="Nuk mund te largosh veten")

        tenant = self._get_tenant(current_user["tenant_slug"])

        user_role = (
            self.db.query(UserRole)
            .filter(
                UserRole.user_id == uuid.UUID(member_id),
                UserRole.tenant_id == tenant.id,
            )
            .first()
        )
        if not user_role:
            raise HTTPException(status_code=404, detail="Anetari nuk u gjet ne kete organizate")

        self.db.delete(user_role)
        self.db.commit()
