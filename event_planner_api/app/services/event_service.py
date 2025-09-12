"""
Business logic for events.

The ``EventService`` uses in‑memory storage to demonstrate how
operations might work.  For production, replace the lists with
persistent storage and handle concurrency appropriately.
"""

import logging
from typing import List, Optional

from ..schemas.event import EventCreate, EventRead


class EventService:
    """Сервис для управления мероприятиями.

    Использует SQLite для хранения данных.  В дальнейшем методы
    следует расширить фильтрацией, пагинацией и проверкой прав
    доступа.  Для интеграции с листом ожидания и групповой записью
    потребуется более сложная бизнес‑логика и использование
    транзакций.
    """

    @classmethod
    async def create_event(cls, data: EventCreate, current_user: dict) -> EventRead:
        """Создать новое мероприятие в БД и вернуть его.

        Пользователь, инициировавший создание, передаётся для записи
        audit‑лога (пока не реализовано).  Поле ``created_by``
        устанавливается в ``NULL`` в данной реализации; в будущем следует
        записывать идентификатор текущего пользователя.
        """
        logger = logging.getLogger(__name__)
        logger.info("User %s is creating event '%s'", current_user.get("sub"), data.title)
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (title, description, start_time, duration_minutes, max_participants, is_paid)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    data.title,
                    data.description,
                    data.start_time,
                    data.duration_minutes,
                    data.max_participants,
                    int(data.is_paid),
                ),
            )
            event_id = cursor.lastrowid
            conn.commit()
            # Write audit log
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="create",
                    object_type="event",
                    object_id=event_id,
                    details={"title": data.title},
                )
            except Exception:
                # Logging failures should not prevent event creation
                pass
            return EventRead(id=event_id, **data.dict())
        finally:
            conn.close()

    @classmethod
    async def list_events(
        cls,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        order: str = "asc",
        is_paid: Optional[bool] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[EventRead]:
        """Вернуть список мероприятий с фильтрами, сортировкой и пагинацией.

        - ``limit`` и ``offset`` управляют пагинацией.
        - ``sort_by``: поле для сортировки (id, title, start_time, duration_minutes, max_participants).
        - ``order``: направление сортировки (asc или desc).
        - ``is_paid``: фильтр по платности (True/False) или None (без фильтра).
        - ``date_from`` и ``date_to``: диапазон дат начала (в формате ISO‑строки) для фильтрации.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT id, title, description, start_time, duration_minutes, max_participants, is_paid FROM events"
            params: list = []
            where_clauses: list[str] = []
            if is_paid is not None:
                where_clauses.append("is_paid = ?")
                params.append(1 if is_paid else 0)
            if date_from:
                where_clauses.append("start_time >= ?")
                params.append(date_from)
            if date_to:
                where_clauses.append("start_time <= ?")
                params.append(date_to)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            # Validate sort_by
            allowed_sorts = {"id", "title", "start_time", "duration_minutes", "max_participants"}
            if sort_by not in allowed_sorts:
                sort_by = "id"
            order = order.lower()
            if order not in {"asc", "desc"}:
                order = "asc"
            query += f" ORDER BY {sort_by} {order}"
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = cursor.execute(query, tuple(params)).fetchall()
            events: List[EventRead] = []
            for row in rows:
                events.append(
                    EventRead(
                        id=row["id"],
                        title=row["title"],
                        description=row["description"],
                        start_time=row["start_time"],
                        duration_minutes=row["duration_minutes"],
                        max_participants=row["max_participants"],
                        is_paid=bool(row["is_paid"]),
                    )
                )
            return events
        finally:
            conn.close()

    @classmethod
    async def delete_event(cls, event_id: int) -> None:
        """Удалить мероприятие.

        Удаляет запись из таблицы events.  В реальном
        приложении следует также удалять связанные бронирования,
        платежи, отзывы и элементы листа ожидания.  Если
        мероприятие не найдено, возбуждает ``ValueError``.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # First check event exists
            exists = cursor.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
            if not exists:
                raise ValueError(f"Event {event_id} not found")
            # Cascade delete dependent records
            cursor.execute("DELETE FROM bookings WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM waitlist WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM payments WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM reviews WHERE event_id = ?", (event_id,))
            # Remove the event itself
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()
            # Record audit log
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="delete",
                    object_type="event",
                    object_id=event_id,
                    details=None,
                )
            except Exception:
                pass
        finally:
            conn.close()

    @classmethod
    async def get_event(cls, event_id: int) -> EventRead:
        """Retrieve a single event by ID.

        Queries the database and returns the event details.  Raises
        ``ValueError`` if the event does not exist.  In future
        iterations this method should include related data (e.g.,
        number of bookings) and enforce authorization rules.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, title, description, start_time, duration_minutes, max_participants, is_paid, price FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Event {event_id} not found")
            return EventRead(
                id=row["id"],
                title=row["title"],
                description=row["description"],
                start_time=row["start_time"],
                duration_minutes=row["duration_minutes"],
                max_participants=row["max_participants"],
                is_paid=bool(row["is_paid"]),
            )
        finally:
            conn.close()

    @classmethod
    async def update_event(cls, event_id: int, updates: dict) -> EventRead:
        """Update fields of an existing event.

        Only fields provided in the ``updates`` dict will be set.  If
        the event does not exist, raises ``ValueError``.  Returns the
        updated event as ``EventRead``.  Use transactions in a real
        implementation to ensure atomicity.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Validate event exists
            row = cursor.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
            if not row:
                raise ValueError(f"Event {event_id} not found")
            # Build dynamic update
            if updates:
                fields = []
                values = []
                for key, value in updates.items():
                    fields.append(f"{key} = ?")
                    # For boolean fields, convert to int
                    if isinstance(value, bool):
                        values.append(1 if value else 0)
                    else:
                        values.append(value)
                values.append(event_id)
                sql = f"UPDATE events SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(sql, tuple(values))
                conn.commit()
            # Return updated event
            event_row = cursor.execute(
                "SELECT id, title, description, start_time, duration_minutes, max_participants, is_paid, price FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            # Record audit log for update
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="update",
                    object_type="event",
                    object_id=event_id,
                    details=updates,
                )
            except Exception:
                pass
            return EventRead(
                id=event_row["id"],
                title=event_row["title"],
                description=event_row["description"],
                start_time=event_row["start_time"],
                duration_minutes=event_row["duration_minutes"],
                max_participants=event_row["max_participants"],
                is_paid=bool(event_row["is_paid"]),
            )
        finally:
            conn.close()

    @classmethod
    async def duplicate_event(cls, event_id: int, new_start_time) -> EventRead:
        """Duplicate an existing event with a new start time.

        Copies all fields of the specified event except for the
        ``start_time`` (which is replaced by ``new_start_time``) and
        timestamps.  Returns the created event.  Raises ``ValueError``
        if the source event does not exist.  Future versions should
        handle duplication of related data (e.g., pricing options).
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT title, description, duration_minutes, max_participants, is_paid, price FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Event {event_id} not found")
            # Insert duplicate with new start time
            cursor.execute(
                """
                INSERT INTO events (title, description, start_time, duration_minutes, max_participants, is_paid, price, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    row["title"],
                    row["description"],
                    new_start_time,
                    row["duration_minutes"],
                    row["max_participants"],
                    row["is_paid"],
                    row["price"],
                ),
            )
            new_id = cursor.lastrowid
            conn.commit()
            # Return new event
            return EventRead(
                id=new_id,
                title=row["title"],
                description=row["description"],
                start_time=new_start_time,
                duration_minutes=row["duration_minutes"],
                max_participants=row["max_participants"],
                is_paid=bool(row["is_paid"]),
            )
        finally:
            conn.close()