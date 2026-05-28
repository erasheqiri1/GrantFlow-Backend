from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, HTTPException

from app.dependencies.auth import get_tenant_db, require_permission
from app.schemas.payments import PaymentResponse, MarkPaidRequest, PaginatedPaymentResponse
from app.services import payments as payment_service
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get(
    "",
    response_model=PaginatedPaymentResponse,
    summary="Lista e pagesave",
    description="""
Kthen listën e paginuar të pagesave për organizatën aktuale.

**Kërkon rolin:** `ORG_ADMIN`

Filtro sipas statusit: `PENDING` (të papaguara), `PAID` (të kryera).
""",
    responses={
        200: {"description": "Listë e paginuar e pagesave"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
    },
)
def list_payments(
    status: Optional[str] = Query(None, description="PENDING | PAID"),
    page:   int = Query(1,  ge=1),
    size:   int = Query(20, ge=1, le=100),
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return payment_service.get_payments(db, status, page, size)


@router.get(
    "/application/{application_id}",
    response_model=PaymentResponse,
    summary="Pagesa e një aplikimi (ORG_ADMIN)",
    description="""
Kthen detajet e pagesës për një aplikim specifik.

**Kërkon rolin:** `ORG_ADMIN` — kërkon tenant context.

Për APPLICANT përdor `/payments/my/{application_id}`.
""",
    responses={
        200: {"description": "Detajet e pagesës"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        404: {"description": "Pagesa nuk u gjet"},
    },
)
def get_payment(
    application_id: str,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return payment_service.get_payment_by_application(application_id, db)


@router.get(
    "/my/{application_id}",
    response_model=PaymentResponse,
    summary="Pagesa ime (APPLICANT)",
    description="""
APPLICANT shikon statusin e pagesës për aplikimin e tij.

**Kërkon rolin:** `APPLICANT`

Ndryshon nga `/payments/application/{id}` — nuk kërkon tenant context në JWT.
Sistemi gjen vetë schemën e duhur.
""",
    responses={
        200: {"description": "Detajet e pagesës"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        404: {"description": "Pagesa ose aplikimi nuk u gjet"},
    },
)
def get_my_payment(
    request: Request,
    application_id: str,
    user=Depends(require_permission("applications:read_own")),
):
    """
    Punon edhe pa tenant_slug në JWT — gjen schemën nga application_id.
    """
    pub_db = SessionLocal()
    try:
        # 1. Gjej schemën nga application_id
        slug = getattr(request.state, "tenant_slug", None)
        if slug:
            schema_name = f"tenant_{slug.replace('-', '_')}"
        else:
            # Kërko nëpër të gjitha schemat aktive
            from app.services.applications import find_schema_for_application
            schema_name = find_schema_for_application(application_id, pub_db)

        # 2. Verifiko që aplikimi i takon userit aktual
        pub_db.execute(text(f'SET search_path TO "{schema_name}", public'))
        row = pub_db.execute(
            text(f'SELECT user_id FROM "{schema_name}".applications WHERE id = :aid'),
            {"aid": application_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Aplikimi nuk u gjet")
        if str(row[0]) != str(user["user_id"]):
            raise HTTPException(status_code=403, detail="Ky aplikim nuk është yti")

        # 3. Merr pagesën
        return payment_service.get_payment_by_application(application_id, pub_db)
    finally:
        pub_db.close()


@router.patch(
    "/application/{application_id}/mark-paid",
    response_model=PaymentResponse,
    summary="Shëno pagesën si të kryer",
    description="""
ORG_ADMIN konfirmon që transferi bankar u bë.

**Kërkon rolin:** `ORG_ADMIN`

⚠️ Pagesa e shënuar si PAID nuk mund të ndryshohet më.

Fushat opsionale:
- `reference` — referenca bankare e transferit
- `note` — shënim shtesë
""",
    responses={
        200: {"description": "Pagesa u shënua si e kryer"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Pagesa nuk u gjet"},
        409: {"description": "Pagesa është shënuar si e kryer tashmë"},
    },
)
def mark_paid(
    application_id: str,
    data: MarkPaidRequest,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return payment_service.mark_as_paid(application_id, data, user, db)
