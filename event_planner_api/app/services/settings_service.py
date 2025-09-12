"""
Service layer for application settings.

This module provides CRUD operations on key‑value settings stored in
the ``settings`` table.  Each setting has a ``key``, ``value`` and
``type`` to allow conversion from the stored string to the
appropriate Python type.  Use this service to centralize access to
configuration values that may be changed at runtime via the API.
"""

import logging
from typing import List, Optional, Any, Dict

from event_planner_api.app.core.db import get_connection


class SettingsService:
    """Service for managing application settings."""

    @classmethod
    async def list_settings(cls) -> List[Dict[str, Any]]:
        """Return all settings as a list of dictionaries."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT key, value, type FROM settings").fetchall()
            settings_list = []
            for row in rows:
                settings_list.append({"key": row["key"], "value": cls._deserialize(row["value"], row["type"]), "type": row["type"]})
            return settings_list
        finally:
            conn.close()

    @classmethod
    async def get_setting(cls, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single setting by key."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT key, value, type FROM settings WHERE key = ?", (key,)).fetchone()
            if not row:
                return None
            return {"key": row["key"], "value": cls._deserialize(row["value"], row["type"]), "type": row["type"]}
        finally:
            conn.close()

    @classmethod
    async def upsert_setting(cls, key: str, value: Any, type_str: str) -> Dict[str, Any]:
        """Insert or update a setting.

        If the key exists, its value and type are updated; otherwise a
        new record is inserted.  Returns the stored setting (with
        deserialized value).
        """
        logger = logging.getLogger(__name__)
        serialized = cls._serialize(value, type_str)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value, type) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value, type = excluded.type",
                (key, serialized, type_str),
            )
            conn.commit()
            logger.info("Setting %s updated", key)
            # Audit log for setting update
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="update",
                    object_type="setting",
                    object_id=None,
                    details={"key": key},
                )
            except Exception:
                pass
            return {"key": key, "value": value, "type": type_str}
        finally:
            conn.close()

    @classmethod
    async def delete_setting(cls, key: str) -> None:
        """Delete a setting by key.

        Removes the entry from the ``settings`` table.  If the key
        does not exist, silently returns.  Access control should be
        enforced in the API layer.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
            conn.commit()
            # Audit log for deletion
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="delete",
                    object_type="setting",
                    object_id=None,
                    details={"key": key},
                )
            except Exception:
                pass
        finally:
            conn.close()

    @staticmethod
    def _serialize(value: Any, type_str: str) -> str:
        """Serialize a Python value to a string based on type."""
        if type_str == "int":
            return str(int(value))
        if type_str == "float":
            return str(float(value))
        if type_str == "bool":
            return "1" if bool(value) else "0"
        # Default to string
        return str(value)

    @staticmethod
    def _deserialize(value: str, type_str: str) -> Any:
        """Deserialize a string back to a Python value based on type."""
        if type_str == "int":
            return int(value)
        if type_str == "float":
            return float(value)
        if type_str == "bool":
            return value not in {"0", "false", "False", ""}
        return value