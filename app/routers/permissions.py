import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.models.public.models import Role, Permission, RolePermission

router = APIRouter(prefix="/permissions", tags=["Permissions"])


class ToggleRequest(BaseModel):
    permission_codename: str


@router.get("/matrix")
def get_matrix(
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("users:assign_role")),
):
    """Kthen matricën e plotë roles × permissions."""
    permissions = (
        db.query(Permission)
        .order_by(Permission.resource, Permission.action)
        .all()
    )
    roles = db.query(Role).order_by(Role.name).all()

    # role_name -> set e permission_id-ve aktive
    role_perm_map: dict[str, set] = {}
    for role in roles:
        rps = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        role_perm_map[role.name.value] = {str(rp.permission_id) for rp in rps}

    return {
        "permissions": [
            {
                "id":       str(p.id),
                "codename": p.codename,
                "resource": p.resource,
                "action":   p.action,
            }
            for p in permissions
        ],
        "roles": [
            {"id": str(r.id), "name": r.name.value}
            for r in roles
        ],
        # role_name -> [codenames aktive]
        "mappings": {
            role_name: [
                p.codename
                for p in permissions
                if str(p.id) in perm_ids
            ]
            for role_name, perm_ids in role_perm_map.items()
        },
    }


@router.patch("/roles/{role_name}")
def toggle_permission(
    role_name: str,
    data: ToggleRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("users:assign_role")),
):
    """Shton ose heq një leje nga një rol (toggle)."""
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Roli nuk u gjet")

    perm = db.query(Permission).filter(Permission.codename == data.permission_codename).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Leja nuk u gjet")

    existing = db.query(RolePermission).filter(
        RolePermission.role_id   == role.id,
        RolePermission.permission_id == perm.id,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"action": "revoked", "role": role_name, "permission": data.permission_codename}
    else:
        db.add(RolePermission(
            id=uuid.uuid4(),
            role_id=role.id,
            permission_id=perm.id,
        ))
        db.commit()
        return {"action": "granted", "role": role_name, "permission": data.permission_codename}
