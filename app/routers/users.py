from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.users import UserListResponse, UserDetailResponse
from app.services.users import UserService

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

**Filtrime të disponueshme:** rol, statusi i llogarisë
""",
    responses={
        200: {"description": "Listë e paginuar e përdoruesve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
    },
)
def list_users(
    role:      Optional[str]  = Query(None,  description="SUPER_ADMIN | ORG_ADMIN | COMMISSIONER | APPLICANT"),
    is_active: Optional[bool] = Query(None,  description="true | false"),
    sortBy:    str  = Query("created_at", description="created_at | email | first_name | last_name"),
    sortDir:   str  = Query("desc",       description="asc | desc"),
    page:      int  = Query(1,  ge=1),
    size:      int  = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    _: dict = Depends(require_permission("users:read")),
):
    return UserService(db).get_users(sortBy, sortDir, page, size, role, is_active)


@router.post(
    "/super-admin",
    response_model=dict,
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
    return UserService(db).create_super_admin(data)


@router.post(
    "/invite-super-admin",
    response_model=dict,
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
    return UserService(db).invite_super_admin(data.email, current_user["user_id"])


class UserActiveUpdate(BaseModel):
    is_active: bool


@router.patch(
    "/{user_id}",
    response_model=dict,
    summary="Përditëso statusin e përdoruesit",
    description="""
Aktivizon ose deaktivizon llogarinë e një përdoruesi.

**Kërkon rolin:** `SUPER_ADMIN`

Dërgo `{"is_active": true}` për aktivizim ose `{"is_active": false}` për deaktivizim.
""",
    responses={
        200: {"description": "Statusi i ndryshuar"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet SUPER_ADMIN"},
        404: {"description": "Përdoruesi nuk u gjet"},
    },
)
def update_user_active(
    user_id: str,
    data: UserActiveUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users:deactivate")),
):
    return UserService(db).toggle_user_active(user_id, current_user["user_id"])


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
    return UserService(db).get_user(user_id)
