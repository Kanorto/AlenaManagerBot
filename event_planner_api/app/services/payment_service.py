"""
Business logic for payments.

Stores payments in memory and provides minimal creation and listing
operations.  This service should be extended to integrate with
external payment providers and to associate payments with users and
events.
"""

import logging
import sqlite3
from datetime import datetime
from typing import List

from ..schemas.payment import PaymentCreate, PaymentRead


class PaymentService:
    """Сервис для обработки платежей.

    Использует SQLite для хранения платежей.  Поддерживает
    минимальные операции создания и чтения.  В дальнейшем необходимо
    интегрировать внешние платёжные системы, реализовать статусы
    транзакций и связывать платежи с пользователями и мероприятиями.
    """

    @classmethod
    async def create_payment(cls, data: PaymentCreate, current_user: dict) -> PaymentRead:
        """Создать новый платёж.

        В зависимости от указанного или подразумеваемого поставщика
        (``provider``) выполняет разные сценарии:

        * ``yookassa`` – создаёт запись о платеже со статусом
          ``pending`` и инициирует платёж через API ЮKassa (см.
          ``_initiate_yookassa_payment``).  Возвращает объект с
          внешним ID и ссылкой на оплату.
        * ``support`` – создаёт платёж со статусом ``pending`` и
          ожидает подтверждения оператором.  Пользователь получает
          реквизиты оплаты (например, из настроек).
        * ``cash`` – создаёт платёж со статусом ``pending`` для
          пост‑оплаты наличными; подтверждение производится в админке.

        ``event_id`` определяет, связан ли платёж с конкретным
        мероприятием.  Если ``provider`` не указан, для платных
        мероприятий по умолчанию используется ``yookassa``.
        """
        logger = logging.getLogger(__name__)
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Resolve user id
            user_id = cls._get_user_id_by_email(cursor, current_user.get("sub"))

            # Determine provider
            provider = data.provider
            # If not specified and event_id provided, infer from event
            if provider is None and data.event_id:
                # Fetch event to check if paid
                event_row = cursor.execute(
                    "SELECT is_paid, price FROM events WHERE id = ?",
                    (data.event_id,),
                ).fetchone()
                if not event_row:
                    raise ValueError(f"Event {data.event_id} does not exist")
                if event_row["is_paid"]:
                    provider = "yookassa"
                else:
                    provider = "free"
            # Default to user balance (support) for non‑event payments
            provider = provider or "support"

            external_id = None
            status = "pending"
            notes = None
            # Amount must be positive
            if data.amount <= 0:
                raise ValueError("Payment amount must be positive")

            # Initiate provider‑specific processing
            if provider == "yookassa":
                # Initiate payment with Yookassa
                try:
                    response = cls._initiate_yookassa_payment(amount=data.amount, currency=data.currency, description=data.description or "Payment")
                    external_id = response.get("id")
                    # Optionally store confirmation URL in notes
                    notes = response.get("confirmation_url")
                except Exception as e:
                    logger.error("Failed to initiate Yookassa payment: %s", e)
                    raise
            elif provider == "support":
                # Payment will be handled manually by support.  Provide instructions via bot message.
                notes = "Awaiting offline payment via support"
            elif provider == "cash":
                notes = "Cash payment to be collected at event"
            elif provider == "free":
                status = "success"  # no payment required for free events
            else:
                raise ValueError(f"Unsupported payment provider: {provider}")

            # Insert payment record
            cursor.execute(
                """
                INSERT INTO payments (user_id, event_id, amount, currency, payment_method, status, description, provider, external_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    data.event_id,
                    data.amount,
                    data.currency,
                    provider,
                    status,
                    data.description,
                    provider,
                    external_id,
                    notes,
                ),
            )
            payment_id = cursor.lastrowid
            conn.commit()
            created_at_row = cursor.execute(
                "SELECT created_at FROM payments WHERE id = ?",
                (payment_id,),
            ).fetchone()
            created_at = created_at_row["created_at"] if created_at_row else datetime.utcnow().isoformat()
            # Write audit log
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="create",
                    object_type="payment",
                    object_id=payment_id,
                    details={"amount": data.amount, "provider": provider, "status": status},
                )
            except Exception:
                pass
            return PaymentRead(
                id=payment_id,
                amount=data.amount,
                currency=data.currency,
                description=data.description,
                created_at=created_at,
                event_id=data.event_id,
                provider=provider,
                status=status,
                external_id=external_id,
            )
        finally:
            conn.close()

    @staticmethod
    def _get_user_id_by_email(cursor: sqlite3.Cursor, email: str) -> int:
        """Resolve a user ID by email.  Raises ValueError if not found."""
        row = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            raise ValueError(f"User with email {email} not found")
        return row["id"]

    @classmethod
    async def list_payments(
        cls,
        current_user: dict,
        event_id: int | None = None,
        provider: str | None = None,
        status: str | None = None,
        sort_by: str | None = None,
        order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> List[PaymentRead]:
        """List payments with optional filtering and sorting.

        - ``event_id`` – фильтр по мероприятию.
        - ``provider`` – фильтр по провайдеру (``yookassa``, ``support``, ``cash``).
        - ``status`` – фильтр по статусу платежа (``pending``, ``success``).
        - ``sort_by`` – поле сортировки (``created_at``, ``amount``); по умолчанию ``created_at``.
        - ``order`` – направление (``asc`` или ``desc``); по умолчанию ``desc``.
        - ``limit`` и ``offset`` – пагинация.

        Администраторы видят все платежи; пользователи — только свои.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            params: list = []
            query = "SELECT id, amount, currency, description, created_at, event_id, provider, status, external_id, confirmed_by, confirmed_at FROM payments"
            where_clauses: list[str] = []
            # Filter by user unless admin
            if current_user.get("role_id") != 1:
                where_clauses.append("user_id = ?")
                params.append(current_user.get("user_id"))
            if event_id:
                where_clauses.append("event_id = ?")
                params.append(event_id)
            if provider:
                where_clauses.append("provider = ?")
                params.append(provider)
            if status:
                where_clauses.append("status = ?")
                params.append(status)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            # Sorting
            sort_field = sort_by if sort_by in {"created_at", "amount"} else "created_at"
            sort_order = order.upper() if order and order.lower() in {"asc", "desc"} else "DESC"
            query += f" ORDER BY {sort_field} {sort_order}"
            # Pagination
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
                if offset is not None:
                    query += " OFFSET ?"
                    params.append(offset)
            rows = cursor.execute(query, tuple(params)).fetchall()
            results: List[PaymentRead] = []
            for row in rows:
                results.append(
                    PaymentRead(
                        id=row["id"],
                        amount=row["amount"],
                        currency=row["currency"],
                        description=row["description"],
                        created_at=row["created_at"],
                        event_id=row["event_id"],
                        provider=row["provider"],
                        status=row["status"],
                        external_id=row["external_id"],
                        confirmed_by=row["confirmed_by"],
                        confirmed_at=row["confirmed_at"],
                    )
                )
            return results
        finally:
            conn.close()

    @classmethod
    async def delete_payment(cls, payment_id: int) -> None:
        """Удалить платёж.

        Удаляет запись из таблицы ``payments``.  Проверка прав
        выполняется в эндпоинте.  Платёж со статусом ``success`` также
        удаляется; при необходимости можно изменить этот метод, чтобы
        запрещать удаление подтверждённых транзакций.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Fetch payment details to determine if we need to update bookings
            payment = cursor.execute(
                "SELECT id, user_id, event_id, status FROM payments WHERE id = ?",
                (payment_id,),
            ).fetchone()
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
            # If the payment was marked as successful and linked to an event,
            # reset the 'is_paid' flag on all bookings for this user and event
            if payment["status"] == "success" and payment["event_id"]:
                cursor.execute(
                    "UPDATE bookings SET is_paid = 0 WHERE user_id = ? AND event_id = ?",
                    (payment["user_id"], payment["event_id"]),
                )
            # Delete the payment record
            cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            conn.commit()
        finally:
            conn.close()
        # Audit log
        try:
            from event_planner_api.app.services.audit_service import AuditService
            await AuditService.log(
                user_id=None,
                action="delete",
                object_type="payment",
                object_id=payment_id,
                details=None,
            )
        except Exception:
            pass

    @classmethod
    async def confirm_payment(cls, payment_id: int, confirmer_user_id: int) -> None:
        """Mark a payment as successfully confirmed.

        Sets the status to ``success``, records who confirmed it and when.
        If the payment is associated with an event, the corresponding
        booking is marked as paid via the BookingService.
        """
        from event_planner_api.app.core.db import get_connection
        from event_planner_api.app.services.booking_service import BookingService
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id, user_id, event_id, status FROM payments WHERE id = ?", (payment_id,)).fetchone()
            if not row:
                raise ValueError(f"Payment {payment_id} not found")
            if row["status"] == "success":
                return
            # Update payment
            cursor.execute(
                "UPDATE payments SET status = 'success', confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (confirmer_user_id, payment_id),
            )
            conn.commit()
            # If linked to an event, update booking status (toggle payment)
            event_id = row["event_id"]
            if event_id:
                # Mark all bookings for this user and event as paid
                user_id = row["user_id"]
                # Find bookings for user+event
                bookings = cursor.execute(
                    "SELECT id FROM bookings WHERE user_id = ? AND event_id = ?",
                    (user_id, event_id),
                ).fetchall()
                for b in bookings:
                    await BookingService.toggle_payment(b["id"])
        finally:
            conn.close()
        # Audit log
        try:
            from event_planner_api.app.services.audit_service import AuditService
            await AuditService.log(
                user_id=confirmer_user_id,
                action="update",
                object_type="payment",
                object_id=payment_id,
                details={"status": "success"},
            )
        except Exception:
            pass

    @classmethod
    def _initiate_yookassa_payment(cls, amount: float, currency: str, description: str) -> dict:
        """Call the Yookassa API to create a payment.

        Reads the Yookassa shop ID and secret key from the settings table
        (keys ``yookassa_shop_id`` and ``yookassa_secret_key``).  If either
        setting is missing, raises a ``RuntimeError``.  Sends an HTTPS
        request to Yookassa's payment creation endpoint using HTTP Basic
        authentication.  Returns a dictionary containing the external
        payment ID and confirmation URL.

        Network errors and API failures will propagate to the caller.
        """
        import base64
        import httpx
        import os

        # Fetch credentials from settings table
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            shop_id_row = cursor.execute(
                "SELECT value FROM settings WHERE key = 'yookassa_shop_id'",
            ).fetchone()
            secret_row = cursor.execute(
                "SELECT value FROM settings WHERE key = 'yookassa_secret_key'",
            ).fetchone()
            if not shop_id_row or not secret_row:
                raise RuntimeError("Yookassa shop_id and secret_key must be configured in settings")
            shop_id = shop_id_row["value"]
            secret_key = secret_row["value"]
        finally:
            conn.close()
        # Construct basic auth header
        auth_token = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json",
            # Idempotence-Key ensures that repeated calls with the same key will not create multiple payments
            "Idempotence-Key": base64.b64encode(os.urandom(32)).decode(),
        }
        # Prepare request body according to Yookassa specification
        payload = {
            "amount": {"value": f"{amount:.2f}", "currency": currency},
            "description": description,
            "confirmation": {
                "type": "redirect",
                # In a real deployment this URL should point back to your service or bot
                "return_url": "https://example.com/payment-success",
            },
        }
        url = "https://api.yookassa.ru/v3/payments"
        # Send request to Yookassa
        response = httpx.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        # Extract external payment ID and confirmation URL
        external_id = data.get("id")
        confirmation_url = None
        confirmation_info = data.get("confirmation") or {}
        # Yookassa may return confirmation_url or url field depending on API version
        confirmation_url = confirmation_info.get("confirmation_url") or confirmation_info.get("url")
        return {
            "id": external_id,
            "confirmation_url": confirmation_url,
        }