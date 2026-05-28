from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.users import UserListResponse, UserDetailResponse
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["Users"])


class CreateSuperAdminRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class InviteSuperAdminRequest(BaseModel):
    email: EmailStr


@router.get(
    "",
    response_model=UserListResponse,
    summary="Lista e të gjithë përdoruesve",
    description="""
Kthen listën e paginuar të të gjithë përdoruesve në platformë.

**Kërkon rolin:** `SUPER_ADMIN`
""",
    responses={
        200: {"description": "Listë e paginuar e përdoruesve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
    },
)
def list_users(
    sortBy:  str = Query("created_at", description="created_at | email | first_name | last_name"),
    sortDir: str = Query("desc",       description="asc | desc"),
    page:    int = Query(1,  ge=1),
    size:    int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("users:read")),
):
    return users_service.get_users(db, sortBy, sortDir, page, size)


@router.post(
    "/super-admin",
    summary="Krijo Super Admin të ri",
    description="""
Krijon një llogari Super Admin të re direkt.

**Kërkon rolin:** `SUPER_ADMIN`
""",
    responses={
        200: {"description": "Super Admin i krijuar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        409: {"description": "Email ekziston tashmë"},
    },
)
def create_super_admin(data: CreateSuperAdminRequest, db: Session = Depends(get_db), _: dict = Depends(require_permission("users:assign_role"))):
    return users_service.create_super_admin(db, data)


@router.post(
    "/invite-super-admin",
    summary="Fto Super Admin të ri",
    description="""
Dërgon ftesë me email për Super Admin të ri.

**Kërkon rolin:** `SUPER_ADMIN`
""",
    responses={
        200: {"description": "Ftesë e dërguar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        409: {"description": "Email ekziston tashmë"},
    },
)
def invite_super_admin(data: InviteSuperAdminRequest, db: Session = Depends(get_db), current_user: dict = Depends(require_permission("users:assign_role"))):
    return users_service.invite_super_admin(db, data.email, current_user["user_id"])


@router.patch(
    "/{user_id}/toggle-active",
    summary="Aktivizo / deaktivizo përdorues",
    description="""
Ndryshon statusin `is_active` të një përdoruesi (aktivizo ose deaktivizo).

**Kërkon rolin:** `SUPER_ADMIN`

Përdoruesi i deaktivizuar nuk mund të kyçet dhe nuk mund të përdorë API-n.
""",
    responses={
        200: {"description": "Statusi i ndryshuar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        404: {"description": "Përdoruesi nuk u gjet"},
    },
)
def toggle_user_active(user_id: str, db: Session = Depends(get_db), current_user: dict = Depends(require_permission("users:deactivate"))):
    return users_service.toggle_user_active(db, user_id, current_user["user_id"])


@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Detajet e një përdoruesi",
    description="""
Kthen detajet e plotë të një përdoruesi sipas ID-së.

**Kërkon rolin:** `SUPER_ADMIN`
""",
    responses={
        200: {"description": "Detajet e përdoruesit"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        404: {"description": "Përdoruesi nuk u gjet"},
    },
)
def get_user(user_id: str, db: Session = Depends(get_db), _: dict = Depends(require_permission("users:read"))):
    return users_service.get_user(db, user_id)
