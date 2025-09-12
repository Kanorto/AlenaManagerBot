"""
Service layer for role management.

Roles define the permissions granted to users.  This module
provides operations to create, read, update and delete roles, as
well as assign roles to users.  Permissions are stored as a JSON
string in the ``permissions`` column; the application logic should
interpret these permissions accordingly.  The initial roles (admin
and user) are created via migrations.
"""

import json
import logging
from typing import List, Dict, Any

from event_planner_api.app.core.db import get_connection


class RoleService:
    """Service for managing roles and assignments."""

    @classmethod
    async def list_roles(cls) -> List[Dict[str, Any]]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT id, name, permissions FROM roles").fetchall()
            roles: List[Dict[str, Any]] = []
            for row in rows:
                roles.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "permissions": json.loads(row["permissions"]) if row["permissions"] else [],
                    }
                )
            return roles
        finally:
            conn.close()

    @classmethod
    async def create_role(cls, name: str, permissions: List[str]) -> Dict[str, Any]:
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO roles (name, permissions) VALUES (?, ?)",
                (name, json.dumps(permissions)),
            )
            role_id = cursor.lastrowid
            conn.commit()
            logger.info("Role %s created", name)
            return {"id": role_id, "name": name, "permissions": permissions}
        finally:
            conn.close()

    @classmethod
    async def update_role(cls, role_id: int, name: str | None = None, permissions: List[str] | None = None) -> Dict[str, Any]:
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id FROM roles WHERE id = ?", (role_id,)).fetchone()
            if not row:
                raise ValueError(f"Role {role_id} not found")
            updates = []
            values = []
            if name is not None:
                updates.append("name = ?")
                values.append(name)
            if permissions is not None:
                updates.append("permissions = ?")
                values.append(json.dumps(permissions))
            values.append(role_id)
            if updates:
                sql = f"UPDATE roles SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(sql, tuple(values))
                conn.commit()
                logger.info("Role %s updated", role_id)
            # Return updated role
            role_row = cursor.execute("SELECT id, name, permissions FROM roles WHERE id = ?", (role_id,)).fetchone()
            return {
                "id": role_row["id"],
                "name": role_row["name"],
                "permissions": json.loads(role_row["permissions"]) if role_row["permissions"] else [],
            }
        finally:
            conn.close()

    @classmethod
    async def delete_role(cls, role_id: int) -> None:
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            conn.commit()
            logger.info("Role %s deleted", role_id)
        finally:
            conn.close()

    @classmethod
    async def assign_role(cls, user_id: int, role_id: int) -> None:
        """Assign a role to a user."""
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Ensure role exists
            role_row = cursor.execute("SELECT id FROM roles WHERE id = ?", (role_id,)).fetchone()
            if not role_row:
                raise ValueError(f"Role {role_id} does not exist")
            # Ensure user exists
            user_row = cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user_row:
                raise ValueError(f"User {user_id} does not exist")
            cursor.execute("UPDATE users SET role_id = ? WHERE id = ?", (role_id, user_id))
            conn.commit()
            logger.info("Assigned role %s to user %s", role_id, user_id)
        finally:
            conn.close()