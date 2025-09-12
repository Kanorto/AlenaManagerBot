"""
Booking-related endpoints for API v1.

These routes handle creating bookings, listing bookings and waitlist
entries for events.  They rely on the ``BookingService`` to perform
database operations and apply necessary business logic (such as
capacity checks and waitlist placement).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status

from event_planner_api.app.schemas.booking import (
    BookingCreate,
    BookingRead,
    BookingUpdate,
    WaitlistUpdate,
)
from event_planner_api.app.services.booking_service import BookingService
from event_planner_api.app.core.security import get_current_user, require_roles


router = APIRouter()


@router.post(
    "/events/{event_id}/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    event_id: int = Path(..., description="ID of the event to book"),
    booking: BookingCreate = None,
    current_user: dict = Depends(get_current_user),
) -> BookingRead:
    """Создать бронь на мероприятие.

    Если свободных мест нет, пользователь будет помещён в лист ожидания,
    и возвращается HTTP 400 с описанием.  В противном случае
    возвращается созданная бронь со статусом ``pending``.
    """
    try:
        return await BookingService.create_booking(event_id, current_user.get("sub"), booking)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/events/{event_id}/bookings",
    response_model=List[BookingRead],
)
async def list_event_bookings(
    event_id: int = Path(..., description="ID of the event"),
    sort_by: str | None = None,
    order: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    current_user: dict = Depends(require_roles(1, 2)),
) -> List[BookingRead]:
    """Получить список бронирований для мероприятия.

    Поддерживает сортировку по ``created_at``, ``user_id``, ``is_paid`` или
    ``is_attended``, направление сортировки, а также пагинацию.
    Доступна только супер‑администраторам и администраторам.
    """
    return await BookingService.list_bookings(event_id, sort_by=sort_by, order=order, limit=limit, offset=offset)


@router.get(
    "/events/{event_id}/waitlist",
)
async def list_event_waitlist(
    event_id: int = Path(..., description="ID of the event"),
    current_user: dict = Depends(get_current_user),
):
    """Получить лист ожидания для мероприятия.

    Возвращается список объектов с полями ``id``, ``user_id``, ``position`` и ``created_at``.
    """
    return await BookingService.list_waitlist(event_id)


@router.get(
    "/bookings/{booking_id}",
    response_model=BookingRead,
    summary="Get a single booking",
)
async def get_booking_endpoint(
    booking_id: int = Path(..., description="ID of the booking"),
    current_user: dict = Depends(get_current_user),
) -> BookingRead:
    """Retrieve a single booking by its ID.

    Users may only access their own bookings unless they hold an
    administrative role (super‑administrator or administrator).  If the
    booking does not exist, a 404 error is returned.
    """
    try:
        booking = await BookingService.get_booking(booking_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # Authorization: allow admins (role_id in {1,2}) or owner
    role_id = current_user.get("role_id")
    user_id = current_user.get("user_id")
    if role_id not in (1, 2) and booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to view this booking")
    return booking


@router.put(
    "/bookings/{booking_id}",
    response_model=BookingRead,
    summary="Update an existing booking",
)
async def update_booking_endpoint(
    booking_id: int = Path(..., description="ID of the booking"),
    update: BookingUpdate | None = None,
    current_user: dict = Depends(get_current_user),
) -> BookingRead:
    """Modify certain attributes of an existing booking.

    Only ``group_size`` and ``group_names`` may be updated via this endpoint.
    Non‑administrative users can update only their own bookings.  Admins
    (role_id 1 or 2) may update any booking.  A 404 error is returned
    if the booking does not exist.  If no fields are provided in the
    request body, the booking is returned unchanged.
    """
    # Ensure update is not None
    update_dict: dict = update.dict() if update else {}
    # Check booking exists and determine owner
    try:
        booking = await BookingService.get_booking(booking_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    role_id = current_user.get("role_id")
    user_id = current_user.get("user_id")
    if role_id not in (1, 2) and booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to update this booking")
    try:
        updated_booking = await BookingService.update_booking(booking_id, update_dict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return updated_booking


@router.get(
    "/waitlist/{entry_id}",
    summary="Get a waitlist entry",
)
async def get_waitlist_entry_endpoint(
    entry_id: int = Path(..., description="ID of the waitlist entry"),
    current_user: dict = Depends(require_roles(1, 2)),
):
    """Retrieve a single waitlist entry by its ID.

    Only administrators (super‑administrators and administrators) may
    access detailed waitlist information.  A 404 error is returned if
    the entry does not exist.
    """
    try:
        return await BookingService.get_waitlist_entry(entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/waitlist/{entry_id}",
    summary="Update a waitlist entry",
)
async def update_waitlist_entry_endpoint(
    entry_id: int = Path(..., description="ID of the waitlist entry"),
    body: WaitlistUpdate = None,
    current_user: dict = Depends(require_roles(1, 2)),
):
    """Change the position of a waitlist entry.

    Accepts a JSON payload specifying the new ``position``.  Only
    administrators may modify the ordering of the waitlist.  Returns
    the updated entry on success.  A 404 error is returned if the
    entry does not exist.
    """
    if body is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Request body required")
    try:
        updated = await BookingService.update_waitlist_entry(entry_id, body.position)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return updated


@router.delete(
    "/waitlist/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a waitlist entry",
)
async def delete_waitlist_entry_endpoint(
    entry_id: int = Path(..., description="ID of the waitlist entry"),
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Remove a waitlist entry.

    Only administrators may remove users from the waitlist.  When an
    entry is deleted, the positions of remaining entries are compacted
    so that the ordering remains continuous.  A 404 error is returned
    if the entry does not exist.
    """
    try:
        await BookingService.delete_waitlist_entry(entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return None


@router.post(
    "/waitlist/{entry_id}/book",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Claim a seat from the waitlist",
)
async def claim_waitlist_seat(
    entry_id: int = Path(..., description="ID of the waitlist entry to claim"),
    current_user: dict = Depends(get_current_user),
) -> BookingRead:
    """Confirm a booking from a waitlist notification.

    When a user receives a notification that a seat has become available,
    they must call this endpoint to claim the seat.  The service
    validates that the entry exists, belongs to the current user and
    that there is at least one seat available.  On success, the
    waitlist entry is removed, a new booking is created, and the
    associated notification tasks are marked completed.  If no seats
    remain or the entry is invalid, an error is returned.
    """
    user_email = current_user.get("sub")
    if not user_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email not found in token")
    try:
        booking = await BookingService.confirm_waitlist(entry_id, user_email)
        return booking
    except ValueError as e:
        detail = str(e)
        # Distinguish different error conditions for clarity
        if "not found" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        elif "authorized" in detail:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        elif "No seats" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

@router.delete(
    "/bookings/{booking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_booking_endpoint(
    booking_id: int = Path(..., description="ID of the booking"),
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Удалить бронирование.

    Доступно только супер‑администраторам и администраторам.  При удалении брони система
    автоматически пытается заполнить освободившееся место пользователями
    из листа ожидания.  Возвращает статус ``204 No Content`` в случае
    успешного удаления.  Если бронирование не найдено, возвращается
    ошибка 404.
    """
    try:
        # Используем метод delete_booking без параметров – он вызывает
        # внутреннюю реализацию с автоматическим продвижением из waitlist
        await BookingService.delete_booking(booking_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/bookings/{booking_id}/toggle-payment",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def toggle_booking_payment(
    booking_id: int = Path(..., description="ID of the booking"),
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Toggle the payment status of a booking.

    Only супер‑администраторы и администраторы могут переключать статус оплаты.  The response
    returns no content on success.
    """
    try:
        await BookingService.toggle_payment(booking_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/bookings/{booking_id}/toggle-attendance",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def toggle_booking_attendance(
    booking_id: int = Path(..., description="ID of the booking"),
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Toggle the attendance status of a booking.

    Only супер‑администраторы и администраторы могут переключать статус посещения.  Returns no content.
    """
    try:
        await BookingService.toggle_attendance(booking_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e