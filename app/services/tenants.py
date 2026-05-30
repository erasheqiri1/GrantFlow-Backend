from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.tenant_schema import create_tenant_schema
from app.models.public.models import Tenant, TenantStatus, User, UserRole, Role, RoleName
from app.services.audit import log_action


class TenantService:
    """Shërbimi për menaxhimin e organizatave (tenants)."""

    def __init__(self, db: Session):
        self.db = db

    def get_tenants(
        self,
        status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        size: int = 20,
    ) -> dict:
        query = self.db.query(Tenant)
        if status:
            try:
                status_enum = TenantStatus(status.upper())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Status i pavlefshëm: '{status}'. Vlerat e lejuara: PENDING, ACTIVE, REJECTED",
                )
            query = query.filter(Tenant.status == status_enum)
        col_map = {"created_at": Tenant.created_at, "name": Tenant.name}
        col = col_map.get(sort_by, Tenant.created_at)
        order = col.desc() if sort_dir == "desc" else col.asc()
        total = query.count()
        tenants = query.order_by(order).offset((page - 1) * size).limit(size).all()
        return {"total": total, "page": page, "size": size, "items": tenants}

    def approve_tenant(self, tenant_id: str, user_id: str) -> dict:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
        if tenant.status != TenantStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Organizata ka status '{tenant.status}'. Vetëm PENDING mund të aprovohet.",
            )
        tenant.status = TenantStatus.ACTIVE
        tenant.is_active = True
        org_admin_role = (
            self.db.query(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .filter(UserRole.tenant_id == tenant.id, Role.name == RoleName.ORG_ADMIN)
            .first()
        )
        org_admin_user = None
        if org_admin_role:
            org_admin_user = self.db.query(User).filter(User.id == org_admin_role.user_id).first()
            if org_admin_user:
                org_admin_user.is_active = True
        self.db.commit()
        create_tenant_schema(self.db, tenant.slug)
        log_action(user_id, "APPROVE_TENANT", "tenant", tenant_id,
                   details={"org_name": tenant.name})

        if org_admin_role and org_admin_user:
            from app.tasks.email import send_org_approval_email
            from app.core.config import settings
            login_url = f"{settings.FRONTEND_URL}/login"
            full_name = f"{org_admin_user.first_name} {org_admin_user.last_name}"
            try:
                send_org_approval_email.delay(org_admin_user.email, tenant.name, full_name, login_url)
            except Exception:
                pass

        return {"message": f"Organizata '{tenant.name}' u aprovua."}

    def reject_tenant(self, tenant_id: str, user_id: str) -> dict:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
        if tenant.status != TenantStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Organizata ka status '{tenant.status}'. Vetëm PENDING mund të refuzohet.",
            )
        tenant.status = TenantStatus.REJECTED
        org_admin_role = (
            self.db.query(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .filter(UserRole.tenant_id == tenant.id, Role.name == RoleName.ORG_ADMIN)
            .first()
        )
        org_admin_user = None
        if org_admin_role:
            org_admin_user = self.db.query(User).filter(User.id == org_admin_role.user_id).first()
            if org_admin_user:
                org_admin_user.is_active = False
        self.db.commit()
        log_action(user_id, "REJECT_TENANT", "tenant", tenant_id,
                   details={"org_name": tenant.name})

        if org_admin_role and org_admin_user:
            from app.tasks.email import send_org_rejection_email
            full_name = f"{org_admin_user.first_name} {org_admin_user.last_name}"
            try:
                send_org_rejection_email.delay(org_admin_user.email, tenant.name, full_name)
            except Exception:
                pass

        return {"message": f"Organizata '{tenant.name}' u refuzua."}

    def get_platform_stats(self) -> dict:
        tenants = self.db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE, Tenant.is_active == True).all()
        total_grants = 0
        total_applications = 0
        for tenant in tenants:
            schema = f"tenant_{tenant.slug.replace('-', '_')}"
            try:
                g = self.db.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".grants WHERE status != :s'),
                    {"s": "DRAFT"},
                ).scalar() or 0
                total_grants += g
            except Exception:
                self.db.rollback()
            try:
                a = self.db.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".applications'),
                ).scalar() or 0
                total_applications += a
            except Exception:
                self.db.rollback()
        return {
            "total_grants":       total_grants,
            "total_applications": total_applications,
            "total_tenants":      len(tenants),
        }
