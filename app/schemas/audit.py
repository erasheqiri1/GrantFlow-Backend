from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: str
    action: str
    entity: Optional[str]
    entity_id: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime
    user_email: Optional[str]
    tenant_slug: Optional[str]
    tenant_name: Optional[str]


class PaginatedAuditLogResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[AuditLogResponse]
