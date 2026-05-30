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


class UserService:
    """Shërbimi për menaxhimin e përdoruesve."""

    def __init__(self, db: Session):
        self.db = db

    def _get_role_name(self, user: User) -> Optional[str]:
        user_role = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user.id)
            .order_by(UserRole.created_at.desc())
            .first()
        )
        if not user_role:
            return None
        role = self.db.query(Role).filter(Role.id == user_role.role_id).first()
        return role.name.value if role else None

    def _get_tenant(self, user: User) -> Optional[Tenant]:
        user_role = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user.id, UserRole.tenant_id.isnot(None))
            .order_by(UserRole.created_at.desc())
            .first()
        )
        if not user_role or not user_role.tenant_id:
            return None
        return self.db.query(Tenant).filter(Tenant.id == user_role.tenant_id).first()

    def get_users(
        self,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        size: int = 20,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> dict:
        col_map = {
            "created_at": User.created_at,
            "email":      User.email,
            "first_name": User.first_name,
            "last_name":  User.last_name,
        }
        col = col_map.get(sort_by, User.created_at)
        order = col.desc() if sort_dir == "desc" else col.asc()

        query = self.db.query(User)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        if role:
            query = (
                query
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .filter(Role.name == role)
            )

        total = query.count()
        users = query.order_by(order).offset((page - 1) * size).limit(size).all()
        items = []
        for user in users:
            row = self.db.execute(
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
                "role": self._get_role_name(user),
                "created_at": user.created_at,
                "tenant_status": row[0] if row else None,
            })
        return {"total": total, "page": page, "size": size, "items": items}

    def get_user(self, user_id: str) -> dict:
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="ID i pavlefshëm")
        user = self.db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=404, detail="Useri nuk u gjet")
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "role": self._get_role_name(user),
            "created_at": user.created_at,
        }

    def toggle_user_active(self, user_id: str, requester_id: str) -> dict:
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="ID i pavlefshëm")
        if str(uid) == requester_id:
            raise HTTPException(status_code=400, detail="Nuk mund ta deaktivizoni llogarinë tuaj")
        user = self.db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=404, detail="Useri nuk u gjet")
        user.is_active = not user.is_active
        self.db.commit()
        return {"id": user_id, "is_active": user.is_active}

    def create_super_admin(self, data) -> dict:
        existing = self.db.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email ekziston tashmë")
        password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
        user = User(
            email=data.email,
            password_hash=password_hash,
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=True,
            email_verified=True,
        )
        self.db.add(user)
        self.db.flush()
        role = self.db.query(Role).filter(Role.name == RoleName.SUPER_ADMIN).first()
        self.db.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=None))
        self.db.commit()
        return {"message": f"Super Admin '{data.email}' u krijua."}

    def invite_super_admin(self, email: str, inviter_id: str) -> dict:
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email ekziston tashmë")
        token_payload = {
            "email": email,
            "role": RoleName.SUPER_ADMIN.value,
            "tenant_slug": None,
            "exp": datetime.now(timezone.utc) + timedelta(days=2),
        }
        invite_token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm="HS256")
        invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={invite_token}"
        try:
            from app.tasks.email import send_invitation_email
            send_invitation_email.delay(email, invite_link, RoleName.SUPER_ADMIN.value)
        except Exception:
            pass
        log_action(inviter_id, "INVITE_SUPER_ADMIN", "user", details={"email": email})
        return {"message": f"Ftesa u dërgua te '{email}'.", "invite_link": invite_link}
