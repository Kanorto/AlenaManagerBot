"""
Event endpoints for API v1.

These routes provide CRUD operations for events.  Only minimal
functionality is implemented here to demonstrate structure; you are
encouraged to expand upon these handlers by adding filtering,
validation, and integration with a real database.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime

from event_planner_api.app.schemas.event import EventCreate, EventRead, EventUpdate, EventDuplicate
from event_planner_api.app.schemas.booking import BookingRead
from event_planner_api.app.services.event_service import EventService
from event_planner_api.app.services.booking_service import BookingService
from event_planner_api.app.core.security import get_current_user, require_roles


router = APIRouter()


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    event: EventCreate,
    current_user: dict = Depends(require_roles(1, 2)),
) -> EventRead:
    """Create a new event.

    Requires an administrator (role_id 1 or 2).  Validates the
    authenticated user's role via the ``require_roles`` dependency.
    Future iterations should perform additional validation on the
    event payload.
    """
    return await EventService.create_event(event, current_user)


@router.get("/", response_model=List[EventRead])
async def list_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("id"),
    order: str = Query("asc"),
    is_paid: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> List[EventRead]:
    """Получить список мероприятий с фильтрами и сортировкой.

    - **limit**, **offset** — параметры пагинации.
    - **sort_by** — поле сортировки: `id`, `title`, `start_time`, `duration_minutes`, `max_participants`.
    - **order** — направление сортировки (`asc`/`desc`).
    - **is_paid** — фильтр по платности (true/false) или пропущено.
    - **date_from**, **date_to** — фильтры по дате начала (ISO‑строки).
    """
    return await EventService.list_events(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order,
        is_paid=is_paid,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{event_id}", response_model=EventRead)
async def get_event(event_id: int) -> EventRead:
    """Retrieve a single event by its ID.

    In the future, add authentication and permission checks (e.g.,
    private events visible only to certain users).  Raises 404 if
    the event is not found.
    """
    try:
        return await EventService.get_event(event_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.put("/{event_id}", response_model=EventRead)
async def update_event(
    event_id: int,
    updates: EventUpdate,
    current_user: dict = Depends(require_roles(1, 2)),
) -> EventRead:
    """Update an existing event.

    Only administrators (role_id 1 or 2) may modify events.  Partial
    updates are supported; any unspecified fields remain unchanged.
    """
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}
    try:
        return await EventService.update_event(event_id, update_dict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/{event_id}/duplicate", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def duplicate_event(
    event_id: int,
    duplication: EventDuplicate,
    current_user: dict = Depends(require_roles(1, 2)),
) -> EventRead:
    """Duplicate an event with a new start time.

    Requires administrator privileges (role_id 1 or 2).  The request
    body must contain the ``start_time`` for the new event.
    """
    try:
        return await EventService.duplicate_event(event_id, duplication.start_time)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Delete an event (admin only).

    When deleting an event, related records (bookings, payments, reviews) are
    removed as part of the ``EventService.delete_event`` implementation.
    Future versions should consider soft deletion or additional checks
    before removing events with dependencies.
    """
    try:
        await EventService.delete_event(event_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return None


@router.get("/{event_id}/participants", response_model=List[BookingRead])
async def list_event_participants(
    event_id: int,
    current_user: dict = Depends(require_roles(1, 2)),
) -> List[BookingRead]:
    """List all bookings (participants) for an event.

    Only administrators (role_id 1 or 2) can view the full participant list.
    Future versions may allow event organizers or the event creator to
    access this information.
    """
    return await BookingService.list_bookings(event_id)