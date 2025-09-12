"""
Business logic for mailings (mass messages).

The mailing service allows administrators to create mailing tasks,
list them, view details and send messages to recipients based on
filters.  Each mailing generates log entries per recipient to track
delivery status.  Actual sending of messages (e.g. via a bot) is
abstracted away; this service focuses on selecting recipients and
recording logs.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from ..schemas.mailing import MailingCreate, MailingRead, MailingLogRead, MailingUpdate


class MailingService:
    """Service for managing mailings."""

    @classmethod
    async def create_mailing(
        cls,
        data: MailingCreate,
        current_user: dict,
    ) -> MailingRead:
        """Create a new mailing entry.

        Only administrators may create mailings.  Filters are stored as
        JSON in the ``filters`` column.  The scheduled time is stored
        as ISO string if provided.
        """
        logger = logging.getLogger(__name__)
        # Only admin (role_id == 1)
        if current_user.get("role_id") != 1:
            raise ValueError("Only administrators can create mailings")
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            filters_json = json.dumps(data.filters) if data.filters is not None else None
            scheduled_at_iso = data.scheduled_at.isoformat() if data.scheduled_at else None
            # Persist the messenger list as JSON.  If no messengers were provided
            # (None), leave the column null to indicate no tasks should be created.
            messengers_json = json.dumps(data.messengers) if data.messengers is not None else None
            cursor.execute(
                """
                INSERT INTO mailings (created_by, title, content, filters, scheduled_at, messengers)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    current_user.get("user_id"),
                    data.title,
                    data.content,
                    filters_json,
                    scheduled_at_iso,
                    messengers_json,
                ),
            )
            mailing_id = cursor.lastrowid
            conn.commit()
            row = cursor.execute(
                "SELECT id, created_by, title, content, filters, scheduled_at, created_at, messengers FROM mailings WHERE id = ?",
                (mailing_id,),
            ).fetchone()
            logger.info(
                "Admin %s created mailing %s",
                current_user.get("user_id"),
                mailing_id,
            )
            # Audit log for mailing creation
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="create",
                    object_type="mailing",
                    object_id=row["id"],
                    details={"title": data.title},
                )
            except Exception:
                pass

            # If messenger channels are provided, create scheduled tasks for each messenger.
            # This ensures bots will be notified when the scheduled time arrives.
            if data.messengers:
                try:
                    from event_planner_api.app.services.task_service import TaskService
                    # Use the provided scheduled_at value or None if absent.  TaskService will
                    # treat None as immediate availability.
                    await TaskService.create_tasks_for_mailing(
                        mailing_id=row["id"],
                        messengers=data.messengers,
                        scheduled_at=row["scheduled_at"],
                    )
                except Exception as e:
                    logger.error("Failed to create tasks for mailing %s: %s", mailing_id, e)
            return MailingRead(
                id=row["id"],
                created_by=row["created_by"],
                title=row["title"],
                content=row["content"],
                filters=json.loads(row["filters"]) if row["filters"] else None,
                scheduled_at=row["scheduled_at"],
                created_at=row["created_at"],
                messengers=json.loads(row["messengers"]) if row["messengers"] else None,
            )
        finally:
            conn.close()

    @classmethod
    async def list_mailings(
        cls,
        current_user: dict,
        limit: int = 20,
        offset: int = 0,
        sort_by: str | None = None,
        order: str | None = None,
    ) -> List[MailingRead]:
        """List mailings with sorting and pagination.

        Only administrators may list mailings.  Поддерживает
        сортировку по ``created_at`` (по умолчанию) и ``scheduled_at``,
        а также направление ``asc``/``desc``.
        """
        if current_user.get("role_id") != 1:
            raise ValueError("Only administrators can view mailings")
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            sort_field = sort_by if sort_by in {"created_at", "scheduled_at"} else "created_at"
            sort_order = order.upper() if order and order.lower() in {"asc", "desc"} else "DESC"
            query = (
                "SELECT id, created_by, title, content, filters, scheduled_at, created_at, messengers "
                "FROM mailings "
                f"ORDER BY {sort_field} {sort_order} LIMIT ? OFFSET ?"
            )
            rows = cursor.execute(query, (limit, offset)).fetchall()
            results: List[MailingRead] = []
            for row in rows:
                results.append(
                    MailingRead(
                        id=row["id"],
                        created_by=row["created_by"],
                        title=row["title"],
                        content=row["content"],
                        filters=json.loads(row["filters"]) if row["filters"] else None,
                        scheduled_at=row["scheduled_at"],
                        created_at=row["created_at"],
                        messengers=json.loads(row["messengers"]) if row["messengers"] else None,
                    )
                )
            return results
        finally:
            conn.close()

    @classmethod
    async def delete_mailing(cls, mailing_id: int, current_user: dict) -> None:
        """Удалить рассылку и связанные логи.

        Допускается только для администраторов.  Удаляет запись из
        таблицы ``mailings`` и соответствующие записи из
        ``mailing_logs``.
        """
        if current_user.get("role_id") != 1:
            raise ValueError("Only administrators can delete mailings")
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id FROM mailings WHERE id = ?", (mailing_id,)).fetchone()
            if not row:
                raise ValueError(f"Mailing {mailing_id} not found")
            cursor.execute("DELETE FROM mailing_logs WHERE mailing_id = ?", (mailing_id,))
            # Remove any pending or completed tasks associated with this mailing so
            # that bots do not attempt to process an orphaned task.
            cursor.execute(
                "DELETE FROM tasks WHERE type = 'mailing' AND object_id = ?",
                (mailing_id,),
            )
            cursor.execute("DELETE FROM mailings WHERE id = ?", (mailing_id,))
            conn.commit()
            # Audit log for deletion
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="delete",
                    object_type="mailing",
                    object_id=mailing_id,
                    details=None,
                )
            except Exception:
                pass
        finally:
            conn.close()

    @classmethod
    async def get_mailing(
        cls,
        mailing_id: int,
        current_user: dict,
    ) -> MailingRead:
        """Retrieve a mailing by ID.

        Only administrators can view details.
        """
        if current_user.get("role_id") != 1:
            raise ValueError("Only administrators can view mailing details")
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, created_by, title, content, filters, scheduled_at, created_at, messengers FROM mailings WHERE id = ?",
                (mailing_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Mailing {mailing_id} not found")
            return MailingRead(
                id=row["id"],
                created_by=row["created_by"],
                title=row["title"],
                content=row["content"],
                filters=json.loads(row["filters"]) if row["filters"] else None,
                scheduled_at=row["scheduled_at"],
                created_at=row["created_at"],
                messengers=json.loads(row["messengers"]) if row["messengers"] else None,
            )
        finally:
            conn.close()

    @classmethod
    def _select_recipients(
        cls,
        cursor,
        filters: Optional[Dict[str, Any]],
    ) -> List[int]:
        """Select user IDs matching the given filters.

        Filters may include:

        * ``event_id``: restrict to users who have bookings for a specific event
        * ``is_paid`` (bool): restrict to bookings with the given payment status
        * ``is_attended`` (bool): restrict to bookings with the given attendance flag

        If no filters are provided, all users are selected.
        """
        # If no filters, select all distinct user IDs
        if not filters:
            rows = cursor.execute(
                "SELECT id FROM users WHERE disabled = 0",
            ).fetchall()
            return [row["id"] for row in rows]
        event_id = filters.get("event_id")
        is_paid = filters.get("is_paid")
        is_attended = filters.get("is_attended")
        user_ids: List[int] = []
        # Start building query
        query = "SELECT DISTINCT user_id FROM bookings"
        clauses = []
        params: List[Any] = []
        if event_id is not None:
            clauses.append("event_id = ?")
            params.append(event_id)
        if is_paid is not None:
            clauses.append("is_paid = ?")
            params.append(1 if is_paid else 0)
        if is_attended is not None:
            clauses.append("is_attended = ?")
            params.append(1 if is_attended else 0)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        rows = cursor.execute(query, tuple(params)).fetchall()
        user_ids = [row["user_id"] for row in rows]
        return user_ids

    @classmethod
    async def send_mailing(
        cls,
        mailing_id: int,
        current_user: dict,
    ) -> int:
        """Send the mailing to all matching recipients.

        This method selects recipients based on the stored filters,
        creates entries in ``mailing_logs`` for each, and returns
        the number of recipients.  Only administrators may send
        mailings.
        """
        if current_user.get("role_id") != 1:
            raise ValueError("Only administrators can send mailings")
        from event_planner_api.app.core.db import get_connection
        from event_planner_api.app.services.message_service import MessageService
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Load mailing
            row = cursor.execute(
                "SELECT id, filters, content FROM mailings WHERE id = ?",
                (mailing_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Mailing {mailing_id} not found")
            filters_json = row["filters"]
            content = row["content"]
            filters = json.loads(filters_json) if filters_json else None
            # Select recipients
            user_ids = cls._select_recipients(cursor, filters)
            if not user_ids:
                return 0
            # Insert log entries
            sent_count = 0
            now = datetime.utcnow().isoformat()
            for uid in user_ids:
                try:
                    # Here you would send the actual message via bot/email
                    # For this MVP we just record the log.
                    cursor.execute(
                        """
                        INSERT INTO mailing_logs (mailing_id, user_id, status, error_message, sent_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (mailing_id, uid, "sent", None, now),
                    )
                    sent_count += 1
                except Exception as e:
                    cursor.execute(
                        "INSERT INTO mailing_logs (mailing_id, user_id, status, error_message, sent_at) VALUES (?, ?, ?, ?, ?)",
                        (mailing_id, uid, "failed", str(e), now),
                    )
            conn.commit()
            logging.getLogger(__name__).info(
                "Mailing %s sent to %s recipients", mailing_id, sent_count
            )
            return sent_count
        finally:
            conn.close()

    @classmethod
    async def list_logs(
        cls,
        mailing_id: int,
        current_user: dict,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MailingLogRead]:
        """List logs for a given mailing.

        Only administrators may view logs.  Results are ordered by
        sent_at descending.
        """
        if current_user.get("role_id") != 1:
            raise ValueError("Only administrators can view mailing logs")
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                """
                SELECT id, mailing_id, user_id, status, error_message, sent_at
                FROM mailing_logs
                WHERE mailing_id = ?
                ORDER BY sent_at DESC
                LIMIT ? OFFSET ?
                """,
                (mailing_id, limit, offset),
            ).fetchall()
            results: List[MailingLogRead] = []
            for row in rows:
                results.append(
                    MailingLogRead(
                        id=row["id"],
                        mailing_id=row["mailing_id"],
                        user_id=row["user_id"],
                        status=row["status"],
                        error_message=row["error_message"],
                        sent_at=row["sent_at"],
                    )
                )
            return results
        finally:
            conn.close()

    @classmethod
    async def update_mailing(
        cls,
        mailing_id: int,
        data: "MailingUpdate",
        current_user: dict,
    ) -> MailingRead:
        """Update an existing mailing and optionally recreate messenger tasks.

        Only administrators may update mailings.  Fields provided in the
        ``data`` object will be updated; omitted fields remain unchanged.  If
        the messenger list or the scheduled time is changed, existing tasks
        associated with the mailing are removed and recreated with the new
        values.  If no messengers are specified (``None``), tasks will be
        cleared and not recreated.

        Raises
        ------
        ValueError
            If the mailing does not exist or the user does not have
            permission to update it.
        """
        from event_planner_api.app.core.db import get_connection
        from event_planner_api.app.services.task_service import TaskService
        # Ensure only super administrators can update
        if current_user.get("role_id") != 1:
            raise ValueError("Only administrators can update mailings")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Ensure the mailing exists and capture its current values
            row = cursor.execute(
                "SELECT id, messengers, scheduled_at FROM mailings WHERE id = ?",
                (mailing_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Mailing {mailing_id} not found")
            update_fields: List[str] = []
            params: List[Any] = []
            # Title
            if data.title is not None:
                update_fields.append("title = ?")
                params.append(data.title)
            # Content
            if data.content is not None:
                update_fields.append("content = ?")
                params.append(data.content)
            # Filters
            if data.filters is not None:
                update_fields.append("filters = ?")
                params.append(json.dumps(data.filters))
            # Scheduled at
            if data.scheduled_at is not None:
                update_fields.append("scheduled_at = ?")
                params.append(data.scheduled_at.isoformat())
            # Messengers
            if data.messengers is not None:
                update_fields.append("messengers = ?")
                params.append(json.dumps(data.messengers))
            # Perform update if there are fields to change
            if update_fields:
                query = f"UPDATE mailings SET {', '.join(update_fields)} WHERE id = ?"
                params.append(mailing_id)
                cursor.execute(query, tuple(params))
                conn.commit()
            # Determine if tasks need to be updated.  If messengers or scheduled_at
            # were supplied, or if the existing messengers list is null and the
            # new schedule/time should change tasks, we recreate tasks.
            if data.messengers is not None or data.scheduled_at is not None:
                # Remove existing tasks for this mailing
                cursor.execute(
                    "DELETE FROM tasks WHERE type = 'mailing' AND object_id = ?",
                    (mailing_id,),
                )
                conn.commit()
                # Recreate tasks only if a messenger list is provided and not empty
                if data.messengers:
                    # Determine the schedule to use: prefer the newly provided
                    # scheduled_at, otherwise the previously stored value (may be None)
                    schedule_for_tasks = (
                        data.scheduled_at.isoformat() if data.scheduled_at else row["scheduled_at"]
                    )
                    # Create new tasks asynchronously
                    await TaskService.create_tasks_for_mailing(
                        mailing_id=mailing_id,
                        messengers=data.messengers,
                        scheduled_at=schedule_for_tasks,
                    )
            # Return the updated mailing
            return await cls.get_mailing(mailing_id, current_user)
        finally:
            conn.close()
