"""
API endpoints for support tickets and messages.

This router exposes a set of endpoints under ``/support`` that allow
users to open support tickets, view and reply to existing tickets,
and for administrators to change ticket statuses.  Access to each
operation is controlled by the current user's role, as provided by
the authentication dependency.

All responses include escaped message content to protect clients from
HTML injection.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from event_planner_api.app.core.security import get_current_user, require_roles
from event_planner_api.app.schemas.support import (
    SupportTicketCreate,
    SupportTicketRead,
    SupportTicketUpdate,
    SupportMessageCreate,
    SupportMessageRead,
    TicketWithMessages,
)
from event_planner_api.app.services.support_service import SupportService


router = APIRouter()


@router.post(
    "/tickets",
    response_model=SupportTicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new support ticket",
)
async def create_ticket(
    ticket_data: SupportTicketCreate,
    current_user: dict = Depends(get_current_user),
) -> SupportTicketRead:
    """Create a new support ticket.

    Accepts the subject and initial message content.  The user must
    be authenticated.  Returns the created ticket.
    """
    try:
        ticket = await SupportService.create_ticket(ticket_data, current_user)
        return ticket
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/tickets",
    response_model=List[SupportTicketRead],
    summary="List support tickets",
)
async def list_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: Optional[str] = Query(None, description="Sort by 'created_at', 'updated_at' or 'status'"),
    order: Optional[str] = Query(None, description="Sort order 'asc' or 'desc'"),
    current_user: dict = Depends(get_current_user),
) -> List[SupportTicketRead]:
    """Return a list of support tickets visible to the current user.

    Admin users can view all tickets; regular users see only their own.
    Supports optional filtering by status and pagination via ``limit``
    and ``offset`` query parameters.
    """
    tickets = await SupportService.list_tickets(
        current_user=current_user,
        status=status_filter,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order,
    )
    return tickets


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketWithMessages,
    summary="Get ticket details and messages",
)
async def get_ticket(
    ticket_id: int,
    current_user: dict = Depends(get_current_user),
) -> TicketWithMessages:
    """Retrieve a ticket and all of its messages.

    Users can access only their own tickets; admins can access any.
    Returns both the ticket details and the message thread.
    """
    try:
        ticket, messages = await SupportService.get_ticket(ticket_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TicketWithMessages(ticket=ticket, messages=messages)


@router.post(
    "/tickets/{ticket_id}/reply",
    response_model=SupportMessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Reply to a ticket",
)
async def reply_to_ticket(
    ticket_id: int,
    message: SupportMessageCreate,
    current_user: dict = Depends(get_current_user),
) -> SupportMessageRead:
    """Add a reply to an existing support ticket.

    The current user must be the ticket owner or an admin.
    Returns the created message.
    """
    try:
        reply = await SupportService.reply_to_ticket(ticket_id, message, current_user)
        return reply
    except ValueError as e:
        # Distinguish not found vs unauthorized
        detail = str(e)
        if "not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/tickets/{ticket_id}/status",
    response_model=SupportTicketRead,
    summary="Change ticket status",
)
async def update_ticket_status(
    ticket_id: int,
    update: SupportTicketUpdate,
    current_user: dict = Depends(require_roles(1, 2)),
) -> SupportTicketRead:
    """Update the status of a support ticket.

    Only administrators may update the status.  Valid statuses should
    be validated by the caller (e.g. 'open', 'in_progress', 'resolved',
    'closed').
    """
    try:
        ticket = await SupportService.update_ticket_status(ticket_id, update, current_user)
        return ticket
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        elif "Only administrators" in detail:
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/tickets/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a support ticket",
)
async def delete_ticket(
    ticket_id: int,
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Удалить тикет поддержки.

    Только администратор может удалять тикеты.  Удаляются также
    связанные сообщения.  Возвращает 204, если всё прошло успешно.
    """
    # Check admin
    if current_user.get("role_id") != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete tickets")
    try:
        await SupportService.delete_ticket(ticket_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return None
