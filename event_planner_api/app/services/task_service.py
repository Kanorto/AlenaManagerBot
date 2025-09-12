"""
Service for managing scheduled tasks for bots and other clients.

Tasks represent pending actions that a messenger bot should perform,
such as sending a mailing or notifying about some event.  Each task
is specific to a messenger (e.g. Telegram, VK, Max) and has a
scheduled time when it becomes available.  Bots poll the API to
retrieve tasks for their messenger and acknowledge completion via a
callback endpoint.

This service creates tasks on behalf of other services (for example,
when a mailing is scheduled) and provides methods for polling and
completing tasks.  Tasks are stored in a dedicated SQLite table.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any

from event_planner_api.app.schemas.task import TaskRead
from event_planner_api.app.core.db import get_connection


class TaskService:
    """Service for creating, listing and completing tasks for bots."""

    @staticmethod
    def _ensure_table_exists(cursor: sqlite3.Cursor) -> None:
        """Ensure that the tasks table exists.  Creates it if missing."""
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                object_id INTEGER NOT NULL,
                messenger TEXT NOT NULL,
                scheduled_at TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    # ------------------------------------------------------------------
    # Task creation methods
    # ------------------------------------------------------------------
    @classmethod
    async def create_tasks_for_mailing(
        cls,
        mailing_id: int,
        messengers: List[str],
        scheduled_at: Optional[str] = None,
    ) -> None:
        """Create tasks for a mailing for each specified messenger.

        This method is called by the MailingService after a mailing is
        created.  It inserts one task per messenger into the tasks
        table.  If ``scheduled_at`` is provided, it will be stored to
        delay availability of the task until the given time.

        Parameters
        ----------
        mailing_id : int
            ID of the mailing for which tasks should be created.
        messengers : List[str]
            List of messenger codes (e.g. ['telegram','vk','max']).  Each
            entry will result in a separate task.
        scheduled_at : Optional[str], optional
            ISO string for when the mailing is scheduled.  If None, the
            task is available immediately.
        """
        if not messengers:
            return
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Ensure tasks table
            cls._ensure_table_exists(cursor)
            for messenger in messengers:
                cursor.execute(
                    """
                    INSERT INTO tasks (type, object_id, messenger, scheduled_at, status)
                    VALUES (?, ?, ?, ?, 'pending')
                    """,
                    ("mailing", mailing_id, messenger, scheduled_at),
                )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Waitlist notification tasks
    # ------------------------------------------------------------------
    @classmethod
    async def create_waitlist_tasks(
        cls,
        entry_id: int,
        messengers: list[str],
        scheduled_at: Optional[str] = None,
    ) -> None:
        """Create notification tasks for a waitlist entry.

        Inserts one task per messenger for the given waitlist entry.  Each
        task has type ``waitlist`` and stores the entry ID in the
        ``object_id`` field.  If ``scheduled_at`` is provided, the
        notification will not be delivered until the specified time.

        Parameters
        ----------
        entry_id : int
            Identifier of the waitlist entry to notify.
        messengers : list[str]
            List of messenger codes (e.g. ['telegram','vk','max']).
        scheduled_at : Optional[str], optional
            ISO string for when to deliver the notification.  If None,
            the task is available immediately.
        """
        if not messengers:
            return
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cls._ensure_table_exists(cursor)
            for messenger in messengers:
                cursor.execute(
                    "INSERT INTO tasks (type, object_id, messenger, scheduled_at, status) VALUES (?, ?, ?, ?, 'pending')",
                    ("waitlist", entry_id, messenger, scheduled_at),
                )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    async def complete_waitlist_tasks(cls, entry_id: int) -> None:
        """Mark waitlist notification tasks as completed.

        This helper updates all tasks with type ``waitlist`` and the given
        ``object_id`` to ``status = 'completed'``.  It is invoked when a
        user claims their seat from the waitlist so that bots do not
        deliver redundant notifications.

        Parameters
        ----------
        entry_id : int
            Waitlist entry identifier whose tasks should be completed.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cls._ensure_table_exists(cursor)
            cursor.execute(
                "UPDATE tasks SET status = 'completed', updated_at = ? WHERE type = 'waitlist' AND object_id = ?",
                (datetime.utcnow().isoformat(), entry_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Task polling
    # ------------------------------------------------------------------
    @classmethod
    async def get_pending_tasks(
        cls,
        messenger: str,
        now: datetime | None = None,
    ) -> List[TaskRead]:
        """Return a list of pending tasks for a given messenger.

        Parameters
        ----------
        messenger : str
            Code of the messenger requesting tasks (e.g. 'telegram', 'vk', 'max').
        now : datetime, optional
            Current time used to check scheduled tasks.  Defaults to
            ``datetime.utcnow()`` if omitted.

        Returns
        -------
        List[TaskRead]
            A list of tasks ready for the caller.  Each task includes
            an identifier and contextual information (e.g., mailing title
            and content).
        """
        tasks: List[TaskRead] = []
        current_time = now or datetime.utcnow()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cls._ensure_table_exists(cursor)
            # Select tasks for the messenger that are pending and scheduled
            # no later than now (or with null scheduled_at).
            rows = cursor.execute(
                """
                SELECT id, type, object_id, messenger, scheduled_at
                FROM tasks
                WHERE messenger = ? AND status = 'pending' AND (scheduled_at IS NULL OR scheduled_at <= ?)
                """,
                (messenger, current_time.isoformat()),
            ).fetchall()
            for row in rows:
                task_type = row["type"]
                obj_id = row["object_id"]
                sched_at = row["scheduled_at"]
                scheduled_dt: Optional[datetime] = None
                if sched_at:
                    try:
                        scheduled_dt = datetime.fromisoformat(sched_at)
                    except Exception:
                        scheduled_dt = None
                # Fetch additional info based on task type
                if task_type == "mailing":
                    # Retrieve mailing title and content for context
                    m_cursor = conn.cursor()
                    m_row = m_cursor.execute(
                        "SELECT title, content FROM mailings WHERE id = ?",
                        (obj_id,),
                    ).fetchone()
                    title = m_row["title"] if m_row else None
                    description = m_row["content"] if m_row else None
                    tasks.append(
                        TaskRead(
                            id=row["id"],
                            type=task_type,
                            title=title,
                            description=description,
                            scheduled_at=scheduled_dt,
                        )
                    )
                elif task_type == "waitlist":
                    # Waitlist notification: include event title and
                    # descriptive text.  object_id stores the waitlist
                    # entry ID; fetch event info via the waitlist table.
                    w_cursor = conn.cursor()
                    w_row = w_cursor.execute(
                        "SELECT event_id, user_id FROM waitlist WHERE id = ?",
                        (obj_id,),
                    ).fetchone()
                    title = None
                    description = None
                    if w_row:
                        evt_row = w_cursor.execute(
                            "SELECT title FROM events WHERE id = ?",
                            (w_row["event_id"],),
                        ).fetchone()
                        event_title = evt_row["title"] if evt_row else "Event"
                        title = f"\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u043c\u0435\u0441\u0442\u043e: {event_title}"
                        description = (
                            f"\u0414\u043b\u044f \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f {event_title} "
                            "\u043e\u0441\u0432\u043e\u0431\u043e\u0434\u0438\u043b\u043e\u0441\u044c \u043c\u0435\u0441\u0442\u043e. "
                            "\u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 \"\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u044c\" \u0432 \u0447\u0430\u0442\u0435, \u0447\u0442\u043e\u0431\u044b \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u0441\u0432\u043e\u0435 \u0443\u0447\u0430\u0441\u0442\u0438\u0435."
                        )
                    tasks.append(
                        TaskRead(
                            id=row["id"],
                            type=task_type,
                            title=title,
                            description=description,
                            scheduled_at=scheduled_dt,
                        )
                    )
                else:
                    # Unknown task type: include minimal info
                    tasks.append(
                        TaskRead(
                            id=row["id"],
                            type=task_type,
                            title=None,
                            description=None,
                            scheduled_at=scheduled_dt,
                        )
                    )
            return tasks
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Task completion
    # ------------------------------------------------------------------
    @classmethod
    async def complete_task(cls, task_id: int) -> None:
        """Mark a task as completed.

        Parameters
        ----------
        task_id : int
            Identifier of the task to mark as completed.

        Raises
        ------
        ValueError
            If the task does not exist.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cls._ensure_table_exists(cursor)
            row = cursor.execute(
                "SELECT id FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Task {task_id} not found")
            cursor.execute(
                "UPDATE tasks SET status = 'completed', updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), task_id),
            )
            conn.commit()
        finally:
            conn.close()