
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.public.models import User, Role, RolePermission, Permission

bearer_scheme = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Jo i autentikuar")

    return {
        "user_id":     request.state.user_id,
        "role":        request.state.role,
        "tenant_slug": request.state.tenant_slug,
    }


def get_tenant_db(request: Request):
    tenant_slug = getattr(request.state, "tenant_slug", None)
    if not tenant_slug:
        raise HTTPException(
            status_code=400,
            detail="Duhet të jesh i kyçur me tenant_slug. Kyçu sërish me 'tenant_slug' në login."
        )
    db = SessionLocal()
    try:
        schema_name = f"tenant_{tenant_slug.replace('-', '_')}"
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
        yield db
    finally:
        db.close()


def require_permission(permission_codename: str):

    def checker(
        request: Request,
        db: Session = Depends(get_tenant_db)
    ):
        role_name = getattr(request.state, "role", None)
        if not role_name:
            raise HTTPException(status_code=401, detail="Jo i autentikuar")


        role = db.query(Role).filter_by(name=role_name).first()
        if not role:
            raise HTTPException(status_code=403, detail="Roli nuk u gjet")


        has_permission = (
            db.query(RolePermission)
            .join(Permission)
            .filter(
                RolePermission.role_id == role.id,
                Permission.codename == permission_codename
            )
            .first()
        )

        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"Nuk ke leje: {permission_codename}"
            )

        return {
            "user_id":     request.state.user_id,
            "role":        role_name,
            "tenant_slug": request.state.tenant_slug,
        }

    return checker