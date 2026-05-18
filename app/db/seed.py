import uuid
import bcrypt
from sqlalchemy.orm import Session
from app.models.public.models import Role, Permission, RolePermission, RoleName, User, UserRole
from app.core.config import settings

PERMISSIONS = [
    {"codename": "tenants:approve",       "resource": "tenants",      "action": "approve"},
    {"codename": "tenants:reject",        "resource": "tenants",      "action": "reject"},
    {"codename": "tenants:read",          "resource": "tenants",      "action": "read"},
    {"codename": "tenants:deactivate", "resource": "tenants", "action": "deactivate"},

    {"codename": "users:read",            "resource": "users",        "action": "read"},
    {"codename": "users:deactivate",      "resource": "users",        "action": "deactivate"},
    {"codename": "users:assign_role",     "resource": "users",        "action": "assign_role"},

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

    {"codename": "invitations:send",      "resource": "invitations",  "action": "send"},
]

ROLE_PERMISSIONS = {
    RoleName.SUPER_ADMIN: [
        "tenants:approve",
        "tenants:reject",
        "tenants:read",
        "tenants:deactivate",
        "users:read",
        "users:assign_role",
    ],

    RoleName.ORG_ADMIN: [
        "grants:create",
        "grants:read",
        "grants:update",
        "grants:publish",
        "grants:close",
        "applications:read_all",
        "users:assign_role",
        "users:deactivate",
        "users:read",
        "invitations:send",
    ],

    RoleName.COMMISSIONER: [
        "grants:read",
        "applications:read_all",
        "applications:approve",
        "applications:reject",
    ],

    RoleName.APPLICANT: [
        "grants:read",
        "applications:submit",
        "applications:read_own",
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
            obj = Role(id=uuid.uuid4(), name=rn)
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
    print("Roles and permissions seeded.")

    # krijon Super Admin nëse nuk ekziston
    super_admin_email = settings.SUPER_ADMIN_EMAIL
    existing = db.query(User).filter_by(email=super_admin_email).first()
    if not existing:
        password_hash = bcrypt.hashpw(settings.SUPER_ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
        admin = User(
            id=uuid.uuid4(),
            email=super_admin_email,
            password_hash=password_hash,
            first_name="Super",
            last_name="Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()

        role = db.query(Role).filter_by(name=RoleName.SUPER_ADMIN).first()
        db.add(UserRole(id=uuid.uuid4(), user_id=admin.id, role_id=role.id, tenant_id=None))
        db.commit()
        print(f"Super Admin krijuar: {super_admin_email}")
    else:
        print("Super Admin ekziston tashmë.")


if __name__ == "__main__":
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()