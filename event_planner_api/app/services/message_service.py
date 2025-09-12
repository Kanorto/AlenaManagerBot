"""
Service layer for bot messages.

This module manages message templates stored in the ``bot_messages``
table.  Each message has a unique ``key``, a ``content`` string and
optional JSON‐encoded ``buttons`` describing interactive elements
(e.g. callback buttons).  The service supports listing all messages,
retrieving a single message and inserting/updating templates.  Use
these helpers to centralize the management of all user‑facing text.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from event_planner_api.app.core.db import get_connection


class MessageService:
    """Service for managing bot message templates."""

    @classmethod
    async def list_messages(cls) -> List[Dict[str, Any]]:
        """Return all bot messages as a list of dictionaries."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT id, key, content, buttons FROM bot_messages").fetchall()
            messages: List[Dict[str, Any]] = []
            for row in rows:
                messages.append(
                    {
                        "id": row["id"],
                        "key": row["key"],
                        "content": row["content"],
                        "buttons": json.loads(row["buttons"]) if row["buttons"] else None,
                    }
                )
            return messages
        finally:
            conn.close()

    @classmethod
    async def get_message(cls, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single message by its key."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id, key, content, buttons FROM bot_messages WHERE key = ?", (key,)).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "key": row["key"],
                "content": row["content"],
                "buttons": json.loads(row["buttons"]) if row["buttons"] else None,
            }
        finally:
            conn.close()

    @classmethod
    async def upsert_message(cls, key: str, content: str, buttons: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Insert or update a bot message template.

        The ``buttons`` list is stored as JSON.  If the key already
        exists, its content and buttons are replaced.
        """
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            buttons_json = json.dumps(buttons) if buttons is not None else None
            cursor.execute(
                "INSERT INTO bot_messages (key, content, buttons) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET content = excluded.content, buttons = excluded.buttons, updated_at = CURRENT_TIMESTAMP",
                (key, content, buttons_json),
            )
            conn.commit()
            logger.info("Bot message %s updated", key)
            # Audit log for message upsert
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="update",
                    object_type="bot_message",
                    object_id=None,
                    details={"key": key},
                )
            except Exception:
                pass
            return {"key": key, "content": content, "buttons": buttons}
        finally:
            conn.close()

    @classmethod
    async def delete_message(cls, key: str) -> None:
        """Удалить шаблон сообщения по ключу.

        Полностью удаляет запись из таблицы ``bot_messages``.
        Проверка прав должна быть осуществлена на уровне эндпоинта.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bot_messages WHERE key = ?", (key,))
            conn.commit()
            # Audit log for deletion
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="delete",
                    object_type="bot_message",
                    object_id=None,
                    details={"key": key},
                )
            except Exception:
                pass
        finally:
            conn.close()