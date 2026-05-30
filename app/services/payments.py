from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.tenant.models import Payment, PaymentStatus, Application, Grant
from app.schemas.payments import MarkPaidRequest


class PaymentService:

    def __init__(self, db: Session):
        self.db = db

    def _to_response(self, payment: Payment) -> dict:
        applicant_name  = None
        applicant_email = None
        applicant_iban  = None
        grant_title     = None

        try:
            app = self.db.query(Application).filter(Application.id == payment.application_id).first()
            if app:
                row = self.db.execute(
                    text("""
                        SELECT u.email, u.first_name, u.last_name, up.iban
                        FROM public.users u
                        LEFT JOIN public.user_profiles up ON up.user_id = u.id
                        WHERE u.id = :uid
                    """),
                    {"uid": str(app.user_id)}
                ).fetchone()
                if row:
                    applicant_email = row.email
                    applicant_name  = f"{row.first_name} {row.last_name}".strip() or row.email
                    applicant_iban  = row.iban

                grant = self.db.query(Grant).filter(Grant.id == app.grant_id).first()
                if grant:
                    grant_title = grant.title
        except Exception:
            pass

        return {
            "id":               str(payment.id),
            "application_id":   str(payment.application_id),
            "amount":           float(payment.amount) if payment.amount else None,
            "currency":         payment.currency,
            "status":           payment.status.value if hasattr(payment.status, "value") else payment.status,
            "reference":        payment.reference,
            "paid_at":          payment.paid_at,
            "note":             payment.note,
            "created_at":       payment.created_at,
            "applicant_name":   applicant_name,
            "applicant_email":  applicant_email,
            "applicant_iban":   applicant_iban,
            "grant_title":      grant_title,
        }

    def create_payment_for_application(self, application_id, amount, currency: str) -> Payment:
        existing = self.db.query(Payment).filter(Payment.application_id == application_id).first()
        if existing:
            return existing

        payment = Payment(
            application_id=application_id,
            amount=amount,
            currency=currency or "EUR",
            status=PaymentStatus.PENDING,
        )
        self.db.add(payment)
        self.db.flush()
        return payment

    def get_payments(self, status: str = None, page: int = 1, size: int = 20) -> dict:
        query = self.db.query(Payment)
        if status:
            query = query.filter(Payment.status == status)
        query = query.order_by(Payment.created_at.desc())

        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()

        return {
            "total": total,
            "page":  page,
            "size":  size,
            "items": [self._to_response(p) for p in items],
        }

    def get_payment_by_application(self, application_id: str) -> dict:
        payment = self.db.query(Payment).filter(
            Payment.application_id == application_id
        ).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Pagesa nuk u gjet")
        return self._to_response(payment)

    def mark_as_paid(self, application_id: str, data: MarkPaidRequest, user: dict) -> dict:
        payment = self.db.query(Payment).filter(
            Payment.application_id == application_id
        ).with_for_update().first()
        if not payment:
            raise HTTPException(status_code=404, detail="Pagesa nuk u gjet")

        if payment.status == PaymentStatus.PAID:
            raise HTTPException(
                status_code=409,
                detail="Pagesa është shënuar si e kryer tashmë — nuk mund të ndryshohet"
            )

        payment.status    = PaymentStatus.PAID
        payment.paid_at   = datetime.now(timezone.utc)
        payment.paid_by   = user["user_id"]
        payment.reference = data.reference
        payment.note      = data.note
        self.db.commit()

        return self._to_response(payment)
