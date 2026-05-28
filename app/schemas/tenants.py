from uuid import UUID
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.public.models import TenantStatus


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    email: str
    nipt: Optional[str]
    doc_path: Optional[str] = None
    status: TenantStatus
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    total: int
    page:  int
    size:  int
    items: List[TenantResponse]
