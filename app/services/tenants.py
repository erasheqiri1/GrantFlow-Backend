from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.tenant_schema import create_tenant_schema
<<<<<<< Updated upstream
from app.models.public.models import Tenant, TenantStatus, User, UserRole, Role, RoleName
from app.services.audit import log_action


def get_platform_stats(db: Session) -> dict:
    """Numëron grante dhe aplikime nga të gjitha tenant-schemat aktive."""
    active_tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()

    total_grants       = 0
    total_applications = 0

    for tenant in active_tenants:
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
    }
=======
from app.models.public.models import Tenant, TenantStatus, User, UserRole, Role
>>>>>>> Stashed changes


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


<<<<<<< Updated upstream
def approve_tenant(db: Session, tenant_id: str, user_id: str) -> dict:
=======
def _get_org_admin_user(db: Session, tenant_id) -> Optional[User]:
    """Merr ORG_ADMIN user-in e lidhur me tenant."""
    org_admin_role = db.query(Role).filter(Role.name == "ORG_ADMIN").first()
    if not org_admin_role:
        return None
    user_role = (
        db.query(UserRole)
        .filter(UserRole.tenant_id == tenant_id, UserRole.role_id == org_admin_role.id)
        .first()
    )
    if not user_role:
        return None
    return db.query(User).filter(User.id == user_role.user_id).first()


def approve_tenant(db: Session, tenant_id: str) -> dict:
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
    # aktivizo ORG_ADMIN-in e kësaj organizate
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
=======
    # Aktivizo ORG_ADMIN user-in
    org_admin = _get_org_admin_user(db, tenant.id)
    if org_admin:
        org_admin.is_active = True

    # create_tenant_schema krijon 17 tabelat dhe bën commit
>>>>>>> Stashed changes
    create_tenant_schema(db, tenant.slug)

    log_action(user_id, "APPROVE_TENANT", "tenant", tenant_id,
               details={"org_name": tenant.name})

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

<<<<<<< Updated upstream
    # çaktivizo ORG_ADMIN-in e kësaj organizate
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
=======
    # Deaktivizo ORG_ADMIN user-in
    org_admin = _get_org_admin_user(db, tenant.id)
    if org_admin:
        org_admin.is_active = False
>>>>>>> Stashed changes

    db.commit()

    log_action(user_id, "REJECT_TENANT", "tenant", tenant_id,
               details={"org_name": tenant.name})

    return {"message": f"Organizata '{tenant.name}' u refuzua."}


def get_platform_stats(db: Session) -> dict:
    """Numëron grant-et dhe aplikimet aktive nëpër të gjitha tenant skemat aktive."""
    active_tenants = db.query(Tenant).filter(Tenant.status == TenantStatus.ACTIVE).all()

    total_grants = 0
    total_applications = 0

    for tenant in active_tenants:
        schema = f"tenant_{tenant.slug.replace('-', '_')}"
        try:
            g_row = db.execute(
                text(f'SELECT COUNT(*) FROM "{schema}".grants')
            ).scalar()
            a_row = db.execute(
                text(f'SELECT COUNT(*) FROM "{schema}".applications')
            ).scalar()
            total_grants += g_row or 0
            total_applications += a_row or 0
        except Exception:
            # Skema mund të mos ekzistojë ende
            pass

    return {
        "total_grants": total_grants,
        "total_applications": total_applications,
        "total_tenants": len(active_tenants),
    }
