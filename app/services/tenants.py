from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.tenant_schema import create_tenant_schema
from app.models.public.models import Tenant, TenantStatus, User, UserRole, Role, RoleName
from app.services.audit import log_action


def get_tenants(db: Session, status: Optional[str] = None) -> dict:
    query = db.query(Tenant)
    if status:
        try:
            status_enum = TenantStatus(status.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Status i pavlefshëm: '{status}'. Vlerat e lejuara: PENDING, ACTIVE, REJECTED",
            )
        query = query.filter(Tenant.status == status_enum)
    tenants = query.order_by(Tenant.created_at.desc()).all()
    return {"total": len(tenants), "items": tenants}


def approve_tenant(db: Session, tenant_id: str, user_id: str) -> dict:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
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
        db.query(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.tenant_id == tenant.id, Role.name == RoleName.ORG_ADMIN)
        .first()
    )
    if org_admin_role:
        org_admin_user = db.query(User).filter(User.id == org_admin_role.user_id).first()
        if org_admin_user:
            org_admin_user.is_active = True
    db.commit()
    create_tenant_schema(db, tenant.slug)
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


def reject_tenant(db: Session, tenant_id: str, user_id: str) -> dict:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
    if tenant.status != TenantStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Organizata ka status '{tenant.status}'. Vetëm PENDING mund të refuzohet.",
        )
    tenant.status = TenantStatus.REJECTED
    org_admin_role = (
        db.query(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.tenant_id == tenant.id, Role.name == RoleName.ORG_ADMIN)
        .first()
    )
    if org_admin_role:
        org_admin_user = db.query(User).filter(User.id == org_admin_role.user_id).first()
        if org_admin_user:
            org_admin_user.is_active = False
    db.commit()
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


def get_platform_stats(db: Session) -> dict:
    tenants = db.query(Tenant).all()
    total_grants = 0
    total_applications = 0
    for tenant in tenants:
        schema = f"tenant_{tenant.slug.replace('-', '_')}"
        try:
            g = db.execute(
                text(f'SELECT COUNT(*) FROM "{schema}".grants WHERE status != :s'),
                {"s": "DRAFT"},
            ).scalar() or 0
            total_grants += g
        except Exception:
            pass
        try:
            a = db.execute(
                text(f'SELECT COUNT(*) FROM "{schema}".applications'),
            ).scalar() or 0
            total_applications += a
        except Exception:
            pass
    return {
        "total_grants":       total_grants,
        "total_applications": total_applications,
        "total_tenants":      len(tenants),
    }
