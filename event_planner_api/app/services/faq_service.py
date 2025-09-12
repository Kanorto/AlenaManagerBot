"""
Service layer for Frequently Asked Questions (FAQ).

This module provides CRUD operations for the FAQ module.  Each FAQ
entry consists of a short question (for use in buttons or lists),
an optional full question, the answer text, optional attachments
(such as images or documents), and a position integer used to
control display ordering.  Attachments are stored as JSON in the
database.

Only administrators should be allowed to create, update or delete
FAQ entries; listing and retrieving entries is open to all users.

All queries use parameterized statements to avoid SQL injection
vulnerabilities.  Returned values are sanitized where appropriate
before being passed to the API layer.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import html
from typing import List, Optional

from event_planner_api.app.core.db import get_connection
from event_planner_api.app.schemas.faq import FAQCreate, FAQUpdate, FAQRead


class FAQService:
    """Service class for managing FAQ entries."""

    @classmethod
    async def create_faq(cls, data: FAQCreate) -> FAQRead:
        """Insert a new FAQ entry and return the created record.

        The ``attachments`` field is stored as a JSON string.  The
        ``position`` field defaults to 0 if not provided.
        """
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            attachments_json = json.dumps(data.attachments) if data.attachments is not None else None
            cursor.execute(
                """
                INSERT INTO faqs (question_short, question_full, answer, attachments, position)
                VALUES (?, ?, ?, ?, ?)
                """,
                (data.question_short, data.question_full, data.answer, attachments_json, data.position or 0),
            )
            faq_id = cursor.lastrowid
            conn.commit()
            logger.info("Created FAQ %s", faq_id)
            # Audit log for FAQ creation
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="create",
                    object_type="faq",
                    object_id=faq_id,
                    details={"question_short": data.question_short},
                )
            except Exception:
                pass
            row = cursor.execute(
                "SELECT * FROM faqs WHERE id = ?",
                (faq_id,),
            ).fetchone()
            return cls._row_to_faq_read(row)
        finally:
            conn.close()

    @classmethod
    async def list_faqs(
        cls,
        limit: int = 100,
        offset: int = 0,
        sort_by: str | None = None,
        order: str | None = None,
    ) -> List[FAQRead]:
        """Return a paginated list of FAQs with optional sorting.

        ``sort_by`` может быть ``position``, ``id``, ``question_short`` или
        ``created_at``; по умолчанию сортировка по ``position`` и ``id``.
        ``order`` может быть ``asc`` или ``desc`` (по умолчанию asc для
        ``position`` и ``question_short``).  Некорректные значения
        сортировки игнорируются.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if sort_by in {"id", "position", "question_short", "created_at"}:
                sort_field = sort_by
                sort_order = order.upper() if order and order.lower() in {"asc", "desc"} else ("ASC" if sort_by in {"position", "question_short"} else "DESC")
                query = f"SELECT * FROM faqs ORDER BY {sort_field} {sort_order} LIMIT ? OFFSET ?"
            else:
                # default sort by position then id
                query = "SELECT * FROM faqs ORDER BY position ASC, id ASC LIMIT ? OFFSET ?"
            rows = cursor.execute(query, (limit, offset)).fetchall()
            return [cls._row_to_faq_read(row) for row in rows]
        finally:
            conn.close()

    @classmethod
    async def get_faq(cls, faq_id: int) -> Optional[FAQRead]:
        """Retrieve a single FAQ entry by its ID."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT * FROM faqs WHERE id = ?",
                (faq_id,),
            ).fetchone()
            if not row:
                return None
            return cls._row_to_faq_read(row)
        finally:
            conn.close()

    @classmethod
    async def update_faq(cls, faq_id: int, data: FAQUpdate) -> Optional[FAQRead]:
        """Update an existing FAQ entry.

        Only fields provided in ``data`` will be updated.  Returns
        the updated FAQ or ``None`` if the record does not exist.
        """
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Fetch current record
            row = cursor.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,)).fetchone()
            if not row:
                return None
            current = dict(row)
            new_question_short = data.question_short if data.question_short is not None else current["question_short"]
            new_question_full = data.question_full if data.question_full is not None else current["question_full"]
            new_answer = data.answer if data.answer is not None else current["answer"]
            # attachments: if provided, convert to JSON; else keep existing text
            if data.attachments is not None:
                new_attachments = json.dumps(data.attachments)
            else:
                new_attachments = current["attachments"]
            new_position = data.position if data.position is not None else current["position"]
            cursor.execute(
                """
                UPDATE faqs
                SET question_short = ?, question_full = ?, answer = ?, attachments = ?, position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    new_question_short,
                    new_question_full,
                    new_answer,
                    new_attachments,
                    new_position,
                    faq_id,
                ),
            )
            conn.commit()
            logger.info("Updated FAQ %s", faq_id)
            # Audit log for FAQ update
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="update",
                    object_type="faq",
                    object_id=faq_id,
                    details={k: v for k, v in data.dict(exclude_unset=True).items()},
                )
            except Exception:
                pass
            row = cursor.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,)).fetchone()
            return cls._row_to_faq_read(row)
        finally:
            conn.close()

    @classmethod
    async def delete_faq(cls, faq_id: int) -> bool:
        """Delete an FAQ entry by ID.

        Returns ``True`` if a record was deleted, ``False`` otherwise.
        """
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
            affected = cursor.rowcount
            conn.commit()
            if affected:
                logger.info("Deleted FAQ %s", faq_id)
                # Audit log for deletion
                try:
                    from event_planner_api.app.services.audit_service import AuditService
                    await AuditService.log(
                        user_id=None,
                        action="delete",
                        object_type="faq",
                        object_id=faq_id,
                        details=None,
                    )
                except Exception:
                    pass
            return affected > 0
        finally:
            conn.close()

    @staticmethod
    def _row_to_faq_read(row: sqlite3.Row) -> FAQRead:
        """Convert a database row to an FAQRead schema instance."""
        attachments = None
        # row["attachments"] may be stored as JSON text or None
        if row["attachments"]:
            try:
                attachments = json.loads(row["attachments"])
            except (TypeError, json.JSONDecodeError):
                attachments = None
        # Escape text fields to prevent XSS when rendering in clients
        question_short = html.escape(row["question_short"]) if row["question_short"] is not None else None
        question_full = html.escape(row["question_full"]) if row["question_full"] is not None else None
        answer = html.escape(row["answer"]) if row["answer"] is not None else None
        return FAQRead(
            id=row["id"],
            question_short=question_short,
            question_full=question_full,
            answer=answer,
            attachments=attachments,
            position=row["position"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )