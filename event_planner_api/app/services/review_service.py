"""
Business logic for reviews.

This service manages user reviews for events, including creation,
listing, retrieval and moderation.  Reviews are stored in the
``reviews`` table.  Only users who attended an event may submit a
review for that event.  Administrators can approve or reject
reviews.
"""

import logging
import html
from typing import List, Optional

from ..schemas.review import ReviewCreate, ReviewRead, ReviewModerate


class ReviewService:
    """Service for handling event reviews."""

    @classmethod
    async def create_review(
        cls,
        data: ReviewCreate,
        current_user: dict,
    ) -> ReviewRead:
        """Create a new review for an event.

        Validates that the event exists and the current user has
        attended the event (i.e. has a booking with ``is_attended`` set
        to 1).  If validation passes, inserts a new review with
        ``approved = 0`` and returns the created object.
        """
        logger = logging.getLogger(__name__)
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            user_id = current_user.get("user_id")
            # Check that event exists
            event = cursor.execute(
                "SELECT id FROM events WHERE id = ?",
                (data.event_id,),
            ).fetchone()
            if not event:
                raise ValueError(f"Event {data.event_id} does not exist")
            # Check that user has attended the event (booking exists and attended)
            booking = cursor.execute(
                "SELECT id, is_attended FROM bookings WHERE user_id = ? AND event_id = ?",
                (user_id, data.event_id),
            ).fetchone()
            if not booking or booking["is_attended"] != 1:
                raise ValueError("User must attend the event before leaving a review")
            # Insert review
            cursor.execute(
                """
                INSERT INTO reviews (user_id, event_id, rating, comment, approved)
                VALUES (?, ?, ?, ?, 0)
                """,
                (user_id, data.event_id, data.rating, data.comment),
            )
            review_id = cursor.lastrowid
            conn.commit()
            # Fetch row
            row = cursor.execute(
                "SELECT id, user_id, event_id, rating, comment, approved, moderated_by, created_at FROM reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            logger.info(
                "User %s submitted review %s for event %s", user_id, review_id, data.event_id
            )
            # Escape comment when returning
            comment = html.escape(row["comment"]) if row["comment"] is not None else None
            # Audit log for review creation
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="create",
                    object_type="review",
                    object_id=row["id"],
                    details={"event_id": data.event_id, "rating": data.rating},
                )
            except Exception:
                pass
            return ReviewRead(
                id=row["id"],
                user_id=row["user_id"],
                event_id=row["event_id"],
                rating=row["rating"],
                comment=comment,
                approved=bool(row["approved"]),
                moderated_by=row["moderated_by"],
                created_at=row["created_at"],
            )
        except Exception as e:
            conn.rollback()
            logger.error("Failed to create review: %s", e)
            raise
        finally:
            conn.close()

    @classmethod
    async def list_reviews(
        cls,
        current_user: dict,
        event_id: Optional[int] = None,
        user_id: Optional[int] = None,
        approved: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str | None = None,
        order: str | None = None,
    ) -> List[ReviewRead]:
        """List reviews with optional filters and sorting.

        Administrators могут просматривать отзывы других пользователей и
        фильтровать по мероприятию, пользователю и статусу одобрения.
        Обычные пользователи видят только свои отзывы.  Допустима
        сортировка по ``created_at`` (по умолчанию) и ``rating`` в
        направлениях ``asc`` или ``desc``.  Поддерживается пагинация.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            params: list = []
            query = (
                "SELECT id, user_id, event_id, rating, comment, approved, moderated_by, created_at "
                "FROM reviews"
            )
            where_clauses = []
            # Non-admin (neither super‑administrator nor administrator): restrict to current user's reviews
            if current_user.get("role_id") not in (1, 2):
                where_clauses.append("user_id = ?")
                params.append(current_user.get("user_id"))
            else:
                # Admin filters for super‑administrators and administrators
                if user_id is not None:
                    where_clauses.append("user_id = ?")
                    params.append(user_id)
                if event_id is not None:
                    where_clauses.append("event_id = ?")
                    params.append(event_id)
                if approved is not None:
                    where_clauses.append("approved = ?")
                    params.append(1 if approved else 0)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            # Sorting
            sort_field = sort_by if sort_by in {"created_at", "rating"} else "created_at"
            sort_order = order.upper() if order and order.lower() in {"asc", "desc"} else "DESC"
            query += f" ORDER BY {sort_field} {sort_order}"
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = cursor.execute(query, tuple(params)).fetchall()
            results: List[ReviewRead] = []
            for row in rows:
                comment = html.escape(row["comment"]) if row["comment"] is not None else None
                results.append(
                    ReviewRead(
                        id=row["id"],
                        user_id=row["user_id"],
                        event_id=row["event_id"],
                        rating=row["rating"],
                        comment=comment,
                        approved=bool(row["approved"]),
                        moderated_by=row["moderated_by"],
                        created_at=row["created_at"],
                    )
                )
            return results
        finally:
            conn.close()

    @classmethod
    async def delete_review(cls, review_id: int) -> None:
        """Удалить отзыв.

        Удаляет запись из таблицы ``reviews``.  Проверка прав
        выполняется в эндпоинте.  При отсутствии отзыва возбуждает
        ``ValueError``.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
            if not row:
                raise ValueError(f"Review {review_id} not found")
            cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
            conn.commit()
            # Audit log for deletion
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="delete",
                    object_type="review",
                    object_id=review_id,
                    details=None,
                )
            except Exception:
                pass
        finally:
            conn.close()

    @classmethod
    async def get_review(
        cls,
        review_id: int,
        current_user: dict,
    ) -> ReviewRead:
        """Retrieve a single review by ID.

        Non-admins can only access their own reviews.  The comment
        content is escaped before returning.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, user_id, event_id, rating, comment, approved, moderated_by, created_at FROM reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Review {review_id} not found")
            # Check access
            if current_user.get("role_id") != 1 and row["user_id"] != current_user.get("user_id"):
                raise ValueError("Not authorized to view this review")
            comment = html.escape(row["comment"]) if row["comment"] is not None else None
            return ReviewRead(
                id=row["id"],
                user_id=row["user_id"],
                event_id=row["event_id"],
                rating=row["rating"],
                comment=comment,
                approved=bool(row["approved"]),
                moderated_by=row["moderated_by"],
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    @classmethod
    async def moderate_review(
        cls,
        review_id: int,
        data: ReviewModerate,
        current_user: dict,
    ) -> ReviewRead:
        """Approve or reject a review.

        Only administrators may call this method.  The ``approved``
        flag is set accordingly, and ``moderated_by`` records the
        admin's user ID.  Returns the updated review.
        """
        # Allow both super‑administrators (role 1) and administrators (role 2) to moderate reviews
        if current_user.get("role_id") not in (1, 2):
            raise ValueError("Only administrators can moderate reviews")
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Ensure review exists
            row = cursor.execute(
                "SELECT id FROM reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Review {review_id} not found")
            # Update
            cursor.execute(
                "UPDATE reviews SET approved = ?, moderated_by = ? WHERE id = ?",
                (1 if data.approved else 0, current_user.get("user_id"), review_id),
            )
            conn.commit()
            # Return updated review
            updated = cursor.execute(
                "SELECT id, user_id, event_id, rating, comment, approved, moderated_by, created_at FROM reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            comment = html.escape(updated["comment"]) if updated["comment"] is not None else None
            # Audit log for moderation
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="update",
                    object_type="review",
                    object_id=review_id,
                    details={"approved": data.approved},
                )
            except Exception:
                pass
            return ReviewRead(
                id=updated["id"],
                user_id=updated["user_id"],
                event_id=updated["event_id"],
                rating=updated["rating"],
                comment=comment,
                approved=bool(updated["approved"]),
                moderated_by=updated["moderated_by"],
                created_at=updated["created_at"],
            )
        finally:
            conn.close()
