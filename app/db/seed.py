import uuid
import bcrypt
from sqlalchemy.orm import Session
from app.models.public.models import Role, Permission, RolePermission, RoleName, User, UserRole
from app.core.config import settings

PERMISSIONS = [
    # --- Platform (SUPER_ADMIN) ---
    {"codename": "tenants:approve",       "resource": "tenants",      "action": "approve"},
    {"codename": "tenants:reject",        "resource": "tenants",      "action": "reject"},
    {"codename": "tenants:read",          "resource": "tenants",      "action": "read"},
    {"codename": "tenants:deactivate",    "resource": "tenants",      "action": "deactivate"},

    {"codename": "users:read",            "resource": "users",        "action": "read"},        # platform-level
    {"codename": "users:deactivate",      "resource": "users",        "action": "deactivate"},  # platform-level
    {"codename": "users:assign_role",     "resource": "users",        "action": "assign_role"}, # platform-level

    {"codename": "audit:read",            "resource": "audit",        "action": "read"},

    # --- Org-level team (ORG_ADMIN) ---
    {"codename": "team:read",             "resource": "team",         "action": "read"},    # shiko antarët e org-ës
    {"codename": "team:manage",           "resource": "team",         "action": "manage"},  # largo antarë

    # --- Grants ---
    {"codename": "grants:create",         "resource": "grants",       "action": "create"},
    {"codename": "grants:read",           "resource": "grants",       "action": "read"},
    {"codename": "grants:update",         "resource": "grants",       "action": "update"},
    {"codename": "grants:publish",        "resource": "grants",       "action": "publish"},
    {"codename": "grants:delete",         "resource": "grants",       "action": "delete"},
    # grants:close dhe grants:finalize hequr — bëhet automatikisht nga sistemi

    # --- Applications ---
    {"codename": "applications:submit",   "resource": "applications", "action": "submit"},
    {"codename": "applications:read_own", "resource": "applications", "action": "read_own"},
    {"codename": "applications:read_all", "resource": "applications", "action": "read_all"},

    # --- Invitations ---
    {"codename": "invitations:send",      "resource": "invitations",  "action": "send"},

    # --- Profile ---
    {"codename": "profile:read",          "resource": "profile",      "action": "read"},
    {"codename": "profile:update",        "resource": "profile",      "action": "update"},
]

ROLE_PERMISSIONS = {
    # Platform-level: menaxhon organizata, usera global, audit
    RoleName.SUPER_ADMIN: [
        "tenants:approve",
        "tenants:reject",
        "tenants:read",
        "tenants:deactivate",
        "users:read",
        "users:deactivate",
        "users:assign_role",
        "audit:read",
        "profile:read",
        "profile:update",
    ],

    # Org-level: menaxhon grantet, ekipin e vet, aplikimet brenda org-ës
    RoleName.ORG_ADMIN: [
        "grants:create",
        "grants:read",
        "grants:update",
        "grants:publish",
        "grants:delete",
        "applications:read_all",
        "invitations:send",
        "team:read",
        "team:manage",
        "profile:read",
        "profile:update",
    ],

    # Vlerëson aplikime brenda org-ës
    RoleName.COMMISSIONER: [
        "grants:read",
        "applications:read_all",  # mbulon edhe vlerësimin e skorit
        "profile:read",
        "profile:update",
    ],

    # Aplikon për grante
    RoleName.APPLICANT: [
        "grants:read",
        "applications:submit",
        "applications:read_own",
        "profile:read",
        "profile:update",
    ],
}


def seed(db: Session) -> None:
    # 1. Shto permissions që mungojnë
    perm_map = {}
    for p in PERMISSIONS:
        obj = db.query(Permission).filter_by(codename=p["codename"]).first()
        if not obj:
            obj = Permission(id=uuid.uuid4(), **p)
            db.add(obj)
            db.flush()
            print(f"  [+] Permission: {p['codename']}")
        perm_map[p["codename"]] = obj

    # 2. Shto rolet që mungojnë
    role_map = {}
    for rn in RoleName:
        obj = db.query(Role).filter_by(name=rn).first()
        if not obj:
            obj = Role(id=uuid.uuid4(), name=rn)
            db.add(obj)
            db.flush()
        role_map[rn] = obj

    # 3. Cleanup: hiq lejet e gabuara / të vjetruara
    REMOVE_FROM_ROLE = {
        RoleName.ORG_ADMIN:    ["users:read", "users:deactivate", "users:assign_role",
                                 "grants:close", "grants:finalize"],
        RoleName.COMMISSIONER: ["applications:approve", "applications:reject"],
    }
    for rn, to_remove in REMOVE_FROM_ROLE.items():
        role = role_map[rn]
        for codename in to_remove:
            perm = db.query(Permission).filter_by(codename=codename).first()
            if not perm:
                continue
            rp = db.query(RolePermission).filter_by(
                role_id=role.id, permission_id=perm.id
            ).first()
            if rp:
                db.delete(rp)
                print(f"  [-] Hequr nga {rn.value}: {codename}")

    # 4. Shto role-permission mappings që mungojnë
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
                    permission_id=perm.id,
                ))
                print(f"  [+] {rn.value} -> {c}")

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