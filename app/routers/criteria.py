from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies.auth import get_tenant_db, require_permission
from app.schemas.criteria import (
    CriteriaCreate, CriteriaUpdate, CriteriaResponse,
    QuestionCreate, QuestionUpdate, QuestionResponse,
)
from app.services.criteria import CriteriaService

router = APIRouter(prefix="/grants", tags=["Criteria & Questions"])


# ─────────────────────────────────────────
# Kriteret
# ─────────────────────────────────────────

@router.post(
    "/{grant_id}/criteria",
    response_model=List[CriteriaResponse],
    status_code=201,
    summary="Shto kritere vlerësimi",
    description="""
Shton një ose më shumë kritere vlerësimi për grantin.

**Kërkon rolin:** `ORG_ADMIN`

Kriteret përdoren nga komisionerët gjatë shqyrtimit të aplikimeve.
""",
    responses={
        201: {"description": "Kriteret u shtuan me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Granti nuk u gjet"},
    },
)
def create_criteria(
    grant_id: str,
    data: List[CriteriaCreate],
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return [CriteriaService(db).create_criteria(grant_id, item) for item in data]


@router.get(
    "/{grant_id}/criteria",
    response_model=List[CriteriaResponse],
    summary="Merr kriteret e grantit",
    description="""
Kthen listën e kritereve të vlerësimit për grantin e specifikuar.

**Kërkon rolin:** `ORG_ADMIN` ose `COMMISSIONER`
""",
    responses={
        200: {"description": "Lista e kritereve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        404: {"description": "Granti nuk u gjet"},
    },
)
def get_criteria(
    grant_id: str,
    user=Depends(require_permission("grants:read")),
    db: Session = Depends(get_tenant_db),
):
    return CriteriaService(db).get_criteria(grant_id)


@router.patch(
    "/{grant_id}/criteria/{criteria_id}",
    response_model=CriteriaResponse,
    summary="Përditëso kriter",
    description="""
Përditëson një kriter vlerësimi ekzistues.

**Kërkon rolin:** `ORG_ADMIN`
""",
    responses={
        200: {"description": "Kriteri u përditësua"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Kriteri nuk u gjet"},
    },
)
def update_criteria(
    grant_id: str,
    criteria_id: str,
    data: CriteriaUpdate,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return CriteriaService(db).update_criteria(grant_id, criteria_id, data)


@router.delete(
    "/{grant_id}/criteria/{criteria_id}",
    status_code=204,
    response_model=None,
    summary="Fshi kriter",
    description="""
Fshin një kriter vlerësimi nga granti.

**Kërkon rolin:** `ORG_ADMIN`
""",
    responses={
        204: {"description": "Kriteri u fshi me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Kriteri nuk u gjet"},
    },
)
def delete_criteria(
    grant_id: str,
    criteria_id: str,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    CriteriaService(db).delete_criteria(grant_id, criteria_id)


# ─────────────────────────────────────────
# Pyetjet
# ─────────────────────────────────────────

@router.post(
    "/{grant_id}/questions",
    response_model=List[QuestionResponse],
    status_code=201,
    summary="Shto pyetje aplikimi",
    description="""
Shton një ose më shumë pyetje që aplikantët duhet të përgjigjen gjatë aplikimit.

**Kërkon rolin:** `ORG_ADMIN`
""",
    responses={
        201: {"description": "Pyetjet u shtuan me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Granti nuk u gjet"},
    },
)
def create_question(
    grant_id: str,
    data: List[QuestionCreate],
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return [CriteriaService(db).create_question(grant_id, item) for item in data]


@router.get(
    "/{grant_id}/questions",
    response_model=List[QuestionResponse],
    summary="Merr pyetjet e grantit",
    description="""
Kthen listën e pyetjeve të aplikimit për grantin e specifikuar.

**Kërkon rolin:** `ORG_ADMIN`, `COMMISSIONER` ose `APPLICANT`
""",
    responses={
        200: {"description": "Lista e pyetjeve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
        404: {"description": "Granti nuk u gjet"},
    },
)
def get_questions(
    grant_id: str,
    user=Depends(require_permission("grants:read")),
    db: Session = Depends(get_tenant_db),
):
    return CriteriaService(db).get_questions(grant_id)


@router.patch(
    "/{grant_id}/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Përditëso pyetje",
    description="""
Përditëson tekstin ose parametrat e një pyetjeje ekzistuese.

**Kërkon rolin:** `ORG_ADMIN`
""",
    responses={
        200: {"description": "Pyetja u përditësua"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Pyetja nuk u gjet"},
    },
)
def update_question(
    grant_id: str,
    question_id: str,
    data: QuestionUpdate,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    return CriteriaService(db).update_question(grant_id, question_id, data)


@router.delete(
    "/{grant_id}/questions/{question_id}",
    status_code=204,
    response_model=None,
    summary="Fshi pyetje",
    description="""
Fshin një pyetje nga granti.

**Kërkon rolin:** `ORG_ADMIN`
""",
    responses={
        204: {"description": "Pyetja u fshi me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        404: {"description": "Pyetja nuk u gjet"},
    },
)
def delete_question(
    grant_id: str,
    question_id: str,
    user=Depends(require_permission("grants:update")),
    db: Session = Depends(get_tenant_db),
):
    CriteriaService(db).delete_question(grant_id, question_id)
