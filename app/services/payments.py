from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.tenant.models import Payment, PaymentStatus, Application, ApplicationStatus, Grant
from app.schemas.payments import PaymentResponse, MarkPaidRequest


def _to_response(payment: Payment, db: Session) -> dict:
    """Kthen payment me info shtesë për aplikantin dhe grantin."""
    applicant_name  = None
    applicant_email = None
    applicant_iban  = None
    grant_title     = None

    try:
        app = db.query(Application).filter(Application.id == payment.application_id).first()
        if app:
            row = db.execute(
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

            grant = db.query(Grant).filter(Grant.id == app.grant_id).first()
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


def create_payment_for_application(application_id, amount, currency: str, db: Session) -> Payment:
    """
    Krijohet automatikisht nga finalize_grant() për çdo aplikim APPROVED.
    Nëse ekziston tashmë, nuk krijon duplikat.
    """
    existing = db.query(Payment).filter(Payment.application_id == application_id).first()
    if existing:
        return existing

    payment = Payment(
        application_id=application_id,
        amount=amount,
        currency=currency or "EUR",
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.flush()
    return payment


def get_payments(
    db: Session,
    status: str = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    """Lista e pagesave për organizatën (ORG_ADMIN)."""
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == status)
    query = query.order_by(Payment.created_at.desc())

    total  = query.count()
    items  = query.offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page":  page,
        "size":  size,
        "items": [_to_response(p, db) for p in items],
    }


def get_payment_by_application(application_id: str, db: Session) -> dict:
    """Merr pagesën e një aplikimi specifik."""
    payment = db.query(Payment).filter(
        Payment.application_id == application_id
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pagesa nuk u gjet")
    return _to_response(payment, db)


def mark_as_paid(application_id: str, data: MarkPaidRequest, user: dict, db: Session) -> dict:
    """
    ORG_ADMIN shënon pagesën si të kryer.
    Rregull: pagesa PAID nuk mund të ndryshohet (njëjtë si SmartRestaurant).
    """
    payment = db.query(Payment).filter(
        Payment.application_id == application_id
    ).with_for_update().first()  # SELECT FOR UPDATE — lock rreshtin deri sa commit-on
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
    db.commit()

    return _to_response(payment, db)
