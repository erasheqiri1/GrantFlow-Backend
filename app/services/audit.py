import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text


def log_action(
    user_id: str,
    action: str,
    entity: str,
    entity_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO public.audit_logs
                    (id, user_id, tenant_id, action, entity, entity_id, details, ip_address, created_at)
                VALUES
                    (:id, :user_id, :tenant_id, :action, :entity, :entity_id, :details, :ip_address, :created_at)
            """),
            {
                "id":         str(uuid.uuid4()),
                "user_id":    user_id,
                "tenant_id":  tenant_id,
                "action":     action,
                "entity":     entity,
                "entity_id":  entity_id,
                "details":    json.dumps(details) if details else None,
                "ip_address": ip_address,
                "created_at": datetime.now(timezone.utc),
            }
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def get_audit_logs(
    db: Session,
    action: Optional[str] = None,
    tenant_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    size: int = 20,
) -> dict:
    filters = ["1=1"]
    params: dict = {"limit": size, "offset": (page - 1) * size}

    if action:
        filters.append("action = :action")
        params["action"] = action

    if tenant_id:
        filters.append("tenant_id = :tenant_id::UUID")
        params["tenant_id"] = tenant_id

    if from_date:
        filters.append("created_at >= :from_date")
        params["from_date"] = from_date

    if to_date:
        filters.append("created_at <= :to_date")
        params["to_date"] = to_date

    where = " AND ".join(filters)

    allowed_cols = {"created_at": "al.created_at", "action": "al.action", "user_email": "u.email"}
    order_col = allowed_cols.get(sort_by, "al.created_at")
    order_dir = "ASC" if sort_dir == "asc" else "DESC"

    total = db.execute(
        text(f"SELECT COUNT(*) FROM public.audit_logs al WHERE {where}"),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    ).scalar() or 0

    rows = db.execute(
        text(f"""
            SELECT
                al.id, al.action, al.entity, al.entity_id,
                al.details, al.ip_address, al.created_at,
                u.email   AS user_email,
                t.slug    AS tenant_slug,
                t.name    AS tenant_name
            FROM public.audit_logs al
            LEFT JOIN public.users   u ON u.id = al.user_id
            LEFT JOIN public.tenants t ON t.id = al.tenant_id
            WHERE {where}
            ORDER BY {order_col} {order_dir}
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).fetchall()

    items = [
        {
            "id":          str(row.id),
            "action":      row.action,
            "entity":      row.entity,
            "entity_id":   str(row.entity_id) if row.entity_id else None,
            "details":     row.details,
            "ip_address":  row.ip_address,
            "created_at":  row.created_at,
            "user_email":  row.user_email,
            "tenant_slug": row.tenant_slug,
            "tenant_name": row.tenant_name,
        }
        for row in rows
    ]
    return {"total": total, "page": page, "size": size, "items": items}
