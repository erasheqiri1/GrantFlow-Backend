from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.tenant_schema import create_tenant_schema
from app.models.public.models import Tenant, TenantStatus


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


def approve_tenant(db: Session, tenant_id: str) -> dict:
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
    # create_tenant_schema krijon 17 tabelat dhe bën commit
    create_tenant_schema(db, tenant.slug)

    return {"message": f"Organizata '{tenant.name}' u aprovua. Schema '{tenant.slug}' u krijua me sukses."}


def reject_tenant(db: Session, tenant_id: str) -> dict:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Organizata nuk u gjet")

    if tenant.status != TenantStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Organizata ka status '{tenant.status}'. Vetëm PENDING mund të refuzohet.",
        )

    tenant.status = TenantStatus.REJECTED
    db.commit()

    return {"message": f"Organizata '{tenant.name}' u refuzua."}
