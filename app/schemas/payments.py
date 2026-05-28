from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PaymentResponse(BaseModel):
    id: str
    application_id: str
    amount: Optional[float] = None
    currency: str
    status: str
    reference: Optional[str] = None
    paid_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime

    # Info shtesë për frontend
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_iban: Optional[str] = None
    grant_title: Optional[str] = None

    class Config:
        from_attributes = True


class MarkPaidRequest(BaseModel):
    reference: Optional[str] = None   # referenca bankare
    note: Optional[str] = None        # shënim opsional


class PaginatedPaymentResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[PaymentResponse]
