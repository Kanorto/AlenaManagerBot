"""
API endpoints for mailings (mass messages).

These routes allow administrators to create mailings, list them,
view details, send messages to selected recipients and inspect
delivery logs.  Only users with administrative privileges may
perform these operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List

from event_planner_api.app.core.security import get_current_user, require_roles
from event_planner_api.app.schemas.mailing import (
    MailingCreate,
    MailingRead,
    MailingLogRead,
    MailingUpdate,
)
from event_planner_api.app.services.mailing_service import MailingService

router = APIRouter()


@router.post(
    "/",
    response_model=MailingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a mailing",
)
async def create_mailing(
    data: MailingCreate,
    current_user: dict = Depends(require_roles(1)),
) -> MailingRead:
    """Create a new mailing.

    Only super administrators may create mailings.  The ``filters`` field
    accepts a JSON object specifying criteria (e.g., event_id,
    is_paid, is_attended) to select recipients.  If
    ``scheduled_at`` is provided, the mailing may be scheduled for
    later execution by an external scheduler; immediate sending can
    be triggered via the send endpoint.
    """
    return await MailingService.create_mailing(data, current_user)


@router.get(
    "/",
    response_model=List[MailingRead],
    summary="List mailings",
)
async def list_mailings(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str | None = Query(None, description="Sort by 'created_at' or 'scheduled_at'"),
    order: str | None = Query(None, description="Sort order 'asc' or 'desc'"),
    current_user: dict = Depends(require_roles(1)),
) -> List[MailingRead]:
    """List mailings.

    Only super administrators may view the list.  Results are paginated.
    """
    return await MailingService.list_mailings(
        current_user,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order,
    )


@router.delete(
    "/{mailing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a mailing",
)
async def delete_mailing(
    mailing_id: int,
    current_user: dict = Depends(require_roles(1)),
) -> None:
    """Удалить рассылку.

    Only super administrators may delete mailings along with their logs.  Returns
    204 on success; raises 404 if the mailing does not exist.
    """
    try:
        await MailingService.delete_mailing(mailing_id, current_user)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        # Other ValueError messages denote lack of permission
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return None


@router.get(
    "/{mailing_id}",
    response_model=MailingRead,
    summary="Get mailing details",
)
async def get_mailing(
    mailing_id: int,
    current_user: dict = Depends(require_roles(1)),
) -> MailingRead:
    """Retrieve a mailing by ID.

    Only super administrators may view mailing details.  Raises 404 if the
    mailing does not exist.
    """
    try:
        return await MailingService.get_mailing(mailing_id, current_user)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@router.post(
    "/{mailing_id}/send",
    response_model=int,
    summary="Execute a mailing",
)
async def send_mailing(
    mailing_id: int,
    current_user: dict = Depends(require_roles(1)),
) -> int:
    """Send the mailing to all recipients matching its filters.

    Only super administrators may trigger sending.  Returns the number of
    recipients to whom the message was sent.
    """
    try:
        return await MailingService.send_mailing(mailing_id, current_user)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@router.get(
    "/{mailing_id}/logs",
    response_model=List[MailingLogRead],
    summary="Get mailing logs",
)
async def get_logs(
    mailing_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_roles(1)),
) -> List[MailingLogRead]:
    """Retrieve delivery logs for a mailing.

    Only super administrators may view logs.  Results are paginated.
    """
    try:
        return await MailingService.list_logs(mailing_id, current_user, limit=limit, offset=offset)
    except ValueError as e:
        detail = str(e)
        if "Only administrators" in detail:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# -----------------------------------------------------------------------------
# Update mailing
# -----------------------------------------------------------------------------
@router.put(
    "/{mailing_id}",
    response_model=MailingRead,
    summary="Update a mailing",
)
async def update_mailing(
    mailing_id: int,
    data: MailingUpdate,
    current_user: dict = Depends(require_roles(1)),
) -> MailingRead:
    """Update an existing mailing.

    Only super administrators may update mailings.  Any fields omitted from the
    request body will be left unchanged.  If the ``messengers`` list is
    provided, the existing messenger list will be replaced and associated
    tasks will be recreated with the new schedule and channels.
    """
    try:
        return await MailingService.update_mailing(mailing_id, data, current_user)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        # Other ValueError messages denote lack of permission
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
