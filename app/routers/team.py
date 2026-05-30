from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission, get_tenant_db
from app.schemas.team import InviteRequest, TeamMemberResponse, PaginatedTeamResponse
from app.services.team import TeamService

router = APIRouter(tags=["Team"])


@router.post(
    "/invitations",
    status_code=202,
    response_model=TeamMemberResponse,
    summary="Dërgo ftesë anëtari të ri",
    description="""
Gjeneron një ftesë për COMMISSIONER ose ORG_ADMIN të ri.

**Kërkon rolin:** `ORG_ADMIN`

Nëse email-i është konfiguruar, ftesa dërgohet automatikisht. Përndryshe kthehet `invite_link` për ndarje manuale.
""",
    responses={
        202: {"description": "Ftesë e gjeneruar — kthen invite_link"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje — kërkohet ORG_ADMIN"},
        409: {"description": "Email ekziston tashmë në organizatë"},
        422: {"description": "Email i pavlefshëm ose rol i gabuar"},
    },
)
def invite_member(
    data: InviteRequest,
    current_user: dict = Depends(require_permission("invitations:send")),
    db: Session = Depends(get_tenant_db),
):
    return TeamService(db).send_invite(data, current_user)


@router.get(
    "/team",
    response_model=PaginatedTeamResponse,
    summary="Lista e anëtarëve të ekipit",
    description="""
Kthen listën e paginuar të anëtarëve të organizatës aktuale.

**Kërkon rolin:** `ORG_ADMIN` ose `COMMISSIONER`

Përfshin: ORG_ADMIN dhe COMMISSIONER. Aplikantët nuk shfaqen.
""",
    responses={
        200: {"description": "Listë e paginuar e anëtarëve"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje"},
    },
)
def get_team(
    sortBy:  str = Query("email", description="email | first_name | last_name | role"),
    sortDir: str = Query("asc",   description="asc | desc"),
    page:    int = Query(1,  ge=1),
    size:    int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_permission("team:read")),
    db: Session = Depends(get_tenant_db),
):
    return TeamService(db).get_team(current_user, sortBy, sortDir, page, size)


@router.delete(
    "/team/{member_id}",
    status_code=204,
    response_model=None,
    summary="Largo anëtar nga ekipi",
    description="""
Largon një anëtar nga organizata dhe e deaktivon llogarinë e tij.

**Kërkon rolin:** `ORG_ADMIN`

⚠️ Nuk mund të largosh veten tënde.
""",
    responses={
        204: {"description": "Anëtar i larguar me sukses"},
        401: {"description": "Token mungon ose i pavlefshëm"},
        403: {"description": "Nuk ke leje ose po provon të largosh veten"},
        404: {"description": "Anëtari nuk u gjet"},
    },
)
def remove_member(
    member_id: str,
    current_user: dict = Depends(require_permission("team:manage")),
    db: Session = Depends(get_tenant_db),
):
    TeamService(db).remove_member(member_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
