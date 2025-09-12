"""
Payment endpoints for API v1.

These routes expose minimal payment operations.  The implementation
uses an in‑memory list to simulate payment storage and does not
integrate with any external payment provider.  In a production
environment you would abstract payment processing behind a service
interface to support multiple providers and handle asynchronous
callbacks.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from typing import List

from event_planner_api.app.schemas.payment import PaymentCreate, PaymentRead
from event_planner_api.app.services.payment_service import PaymentService
from event_planner_api.app.core.security import get_current_user, require_roles


router = APIRouter()


@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(payment: PaymentCreate, current_user: dict = Depends(get_current_user)) -> PaymentRead:
    """Создать новый платёж.

    Требуется аутентификация.  В будущем будет реализована
    проверка валидности суммы, интеграция с платежными шлюзами
    (ЮKassa, Stripe и т.д.), обработка статусов транзакций и
    связка с конкретным мероприятием или пополнением баланса.
    """
    try:
        return await PaymentService.create_payment(payment, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[PaymentRead])
async def list_payments(
    event_id: int | None = None,
    provider: str | None = None,
    status_param: str | None = None,
    sort_by: str | None = None,
    order: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    current_user: dict = Depends(get_current_user),
) -> List[PaymentRead]:
    """Получить список платежей.

    Администратор видит все записи, обычный пользователь — только свои.
    Поддерживаются фильтры ``event_id``, ``provider`` (yookassa/support/cash), ``status``
    (pending/success), сортировка по ``created_at`` или ``amount`` и
    пагинация.
    """
    return await PaymentService.list_payments(
        current_user,
        event_id=event_id,
        provider=provider,
        status=status_param,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.post("/{payment_id}/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_payment(
    payment_id: int = Path(..., description="ID платежа"),
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Подтвердить платёж (администратор или супер‑администратор).

    Устанавливает статус ``success`` и отмечает подтверждающего.  Для
    платного мероприятия также помечает связанные брони как оплаченные.
    """
    try:
        await PaymentService.confirm_payment(payment_id, current_user.get("user_id"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: int = Path(..., description="ID платежа"),
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Удалить платёж.

    Удаление платежей доступно только супер‑администраторам и администраторам.  При
    необходимости следует запретить удаление подтверждённых платежей;
    текущая реализация удаляет любую запись.  Возвращает 204 при
    успешном удалении.
    """
    try:
        await PaymentService.delete_payment(payment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return None


@router.post("/yookassa/callback", status_code=status.HTTP_204_NO_CONTENT)
async def yookassa_callback(callback: dict = Body(...)) -> None:
    """Обработать callback от ЮKassa.

    В продуктивной среде ЮKassa отправляет уведомления о статусе
    платежа.  Здесь представлен только пример структуры: поле
    ``object.id`` должно содержать ``external_id`` платежа.  На
    основе этого id в базе обновляется статус платежа.  Отсутствие
    реальных HTTP‑запросов означает, что эта функция не будет
    вызываться автоматически в данной среде.
    """
    # Extract payment ID
    try:
        payment_obj = callback.get("object", {})
        external_id = payment_obj.get("id")
        status = payment_obj.get("status")
        # Find payment by external_id and update status if succeeded
        if not external_id:
            return
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id FROM payments WHERE external_id = ?", (external_id,)).fetchone()
            if not row:
                return
            payment_id = row["id"]
            if status == "succeeded":
                # Mark as confirmed by system (user_id None)
                await PaymentService.confirm_payment(payment_id, confirmer_user_id=None)
            elif status == "canceled":
                cursor.execute("UPDATE payments SET status = 'failed' WHERE id = ?", (payment_id,))
                conn.commit()
        finally:
            conn.close()
    except Exception:
        # Swallow exceptions to avoid returning error to Yookassa
        return