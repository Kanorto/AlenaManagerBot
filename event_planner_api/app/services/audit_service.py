"""
Audit service for recording and querying system actions.

This module provides a centralized API for writing audit events to the
``audit_logs`` table and retrieving them with filters and pagination.
Use this service to record significant actions (create, update,
delete) performed by users or the system.  Only administrators
should have access to read audit logs.
"""

from __future__ import annotations

import json
from typing import Optional, List, Dict, Any

from event_planner_api.app.core.db import get_connection


class AuditService:
    """Service class for writing and retrieving audit logs."""

    @classmethod
    async def log(
        cls,
        user_id: Optional[int],
        action: str,
        object_type: str,
        object_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Insert a new audit record.

        Parameters
        ----------
        user_id : Optional[int]
            ID of the user performing the action.  May be ``None`` for
            system‑initiated actions.
        action : str
            Short description of the action (e.g. "create", "update", "delete").
        object_type : str
            Type of object affected (e.g. "event", "booking", "payment").
        object_id : Optional[int]
            Primary key of the affected object, if applicable.
        details : Optional[dict]
            Additional structured data about the action, stored as JSON.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            details_json = json.dumps(details) if details else None
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, action, object_type, object_id, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, action, object_type, object_id, details_json),
            )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    async def list_logs(
        cls,
        user_id: Optional[int] = None,
        object_type: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit records with optional filters and pagination.

        Only super‑admins should call this method.  Filtering by
        user_id, object_type or action reduces the result set.  Date
        filters accept ISO date strings ("YYYY-MM-DD") and apply to
        the ``timestamp`` column.  Sorting is always by ``timestamp"
        descending.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            where_clauses: List[str] = []
            params: List[Any] = []
            if user_id is not None:
                where_clauses.append("user_id = ?")
                params.append(user_id)
            if object_type:
                where_clauses.append("object_type = ?")
                params.append(object_type)
            if action:
                where_clauses.append("action = ?")
                params.append(action)
            if start_date:
                where_clauses.append("timestamp >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("timestamp <= ?")
                params.append(end_date)
            query = "SELECT id, user_id, action, object_type, object_id, timestamp, details FROM audit_logs"
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = cursor.execute(query, tuple(params)).fetchall()
            logs = []
            for row in rows:
                details_data = None
                if row["details"]:
                    try:
                        details_data = json.loads(row["details"])
                    except json.JSONDecodeError:
                        details_data = row["details"]
                logs.append(
                    {
                        "id": row["id"],
                        "user_id": row["user_id"],
                        "action": row["action"],
                        "object_type": row["object_type"],
                        "object_id": row["object_id"],
                        "timestamp": row["timestamp"],
                        "details": details_data,
                    }
                )
            return logs
        finally:
            conn.close()