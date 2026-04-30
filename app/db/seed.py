import uuid
from sqlalchemy.orm import Session
from app.models.public.models import Role, Permission, RolePermission, RoleName

PERMISSIONS = [
    {"codename": "tenants:approve",       "resource": "tenants",      "action": "approve"},
    {"codename": "tenants:reject",        "resource": "tenants",      "action": "reject"},
    {"codename": "tenants:read",          "resource": "tenants",      "action": "read"},
    {"codename": "users:read",            "resource": "users",        "action": "read"},
    {"codename": "users:deactivate",      "resource": "users",        "action": "deactivate"},
    {"codename": "users:assign_role",     "resource": "users",        "action": "assign_role"},
    {"codename": "users:reset_password",  "resource": "users",        "action": "reset_password"},
    {"codename": "grants:create",         "resource": "grants",       "action": "create"},
    {"codename": "grants:read",           "resource": "grants",       "action": "read"},
    {"codename": "grants:update",         "resource": "grants",       "action": "update"},
    {"codename": "grants:publish",        "resource": "grants",       "action": "publish"},
    {"codename": "grants:close",          "resource": "grants",       "action": "close"},
    {"codename": "applications:submit",   "resource": "applications", "action": "submit"},
    {"codename": "applications:read_own", "resource": "applications", "action": "read_own"},
    {"codename": "applications:read_all", "resource": "applications", "action": "read_all"},
    {"codename": "applications:approve",  "resource": "applications", "action": "approve"},
    {"codename": "applications:reject",   "resource": "applications", "action": "reject"},
    {"codename": "ai_scores:read",        "resource": "ai_scores",    "action": "read"},
    {"codename": "invitations:send",      "resource": "invitations",  "action": "send"},
    {"codename": "committees:manage",     "resource": "committees",   "action": "manage"},
    {"codename": "audit_logs:read",       "resource": "audit_logs",   "action": "read"},
    {"codename": "commissioner:score",    "resource": "commissioner", "action": "score"},
    {"codename": "commissioner:decide",   "resource": "commissioner", "action": "decide"},
]

ROLE_PERMISSIONS = {
    RoleName.SUPER_ADMIN: [p["codename"] for p in PERMISSIONS],
    RoleName.ORG_ADMIN: [
        "grants:create", "grants:read", "grants:update",
        "grants:publish", "grants:close",
        "applications:read_all",
        "users:assign_role", "users:reset_password",
        "invitations:send", "committees:manage",
        "audit_logs:read",
    ],
    RoleName.COMMISSIONER: [
        "grants:read",
        "applications:read_all",
        "applications:approve", "applications:reject",
        "ai_scores:read",
        "commissioner:score", "commissioner:decide",
    ],
    RoleName.APPLICANT: [
        "grants:read",
        "applications:submit", "applications:read_own",
    ],
}


def seed(db: Session) -> None:
    perm_map = {}
    for p in PERMISSIONS:
        obj = db.query(Permission).filter_by(codename=p["codename"]).first()
        if not obj:
            obj = Permission(id=uuid.uuid4(), **p)
            db.add(obj)
            db.flush()
        perm_map[p["codename"]] = obj

    role_map = {}
    for rn in RoleName:
        obj = db.query(Role).filter_by(name=rn).first()
        if not obj:
            obj = Role(id=uuid.uuid4(), name=rn, description=f"Roli {rn.value}")
            db.add(obj)
            db.flush()
        role_map[rn] = obj

    for rn, codenames in ROLE_PERMISSIONS.items():
        role = role_map[rn]
        for c in codenames:
            perm = perm_map.get(c)
            if not perm:
                continue
            exists = db.query(RolePermission).filter_by(
                role_id=role.id, permission_id=perm.id
            ).first()
            if not exists:
                db.add(RolePermission(
                    id=uuid.uuid4(),
                    role_id=role.id,
                    permission_id=perm.id
                ))
    db.commit()
    print("Rolet dhe lejet u shtuan.")


if __name__ == "__main__":
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()