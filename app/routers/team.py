from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission, get_tenant_db
from app.schemas.team import InviteRequest, TeamMemberResponse, PaginatedTeamResponse
from app.services import team as team_service

router = APIRouter(tags=["Team"])


@router.post("/invitations", status_code=202)
def invite_member(
    data: InviteRequest,
    current_user: dict = Depends(require_permission("invitations:send")),
    db: Session = Depends(get_tenant_db),
):
    return team_service.send_invite(data, current_user, db)


@router.get("/team", response_model=PaginatedTeamResponse)
def get_team(
    sortBy:  str = Query("email", description="email | first_name | last_name | role"),
    sortDir: str = Query("asc",   description="asc | desc"),
    page:    int = Query(1,  ge=1),
    size:    int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_permission("team:read")),
    db: Session = Depends(get_tenant_db),
):
    return team_service.get_team(current_user, db, sortBy, sortDir, page, size)


@router.delete("/team/{member_id}", status_code=204)
def remove_member(
    member_id: str,
    current_user: dict = Depends(require_permission("team:manage")),
    db: Session = Depends(get_tenant_db),
):
    team_service.remove_member(member_id, current_user, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
