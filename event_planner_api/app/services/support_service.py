"""
Business logic for support tickets and messages.

This module implements the support workflow: creating tickets,
listing tickets, reading ticket details with messages, replying to
tickets and updating ticket status.  It uses SQLite via the
``get_connection`` helper and includes basic role‑based access
control.  All user‑supplied content is escaped on output to prevent
cross‑site scripting when consumed by clients.

The service relies on the current user's ID and role, which
should be provided by the authentication layer.  It logs all
operations for audit purposes.
"""

import logging
import html
from typing import List, Tuple, Optional

from ..schemas.support import (
    SupportTicketCreate,
    SupportTicketRead,
    SupportTicketUpdate,
    SupportMessageCreate,
    SupportMessageRead,
)


class SupportService:
    """Service for handling support tickets and messages."""

    @classmethod
    async def create_ticket(
        cls,
        data: SupportTicketCreate,
        current_user: dict,
    ) -> SupportTicketRead:
        """Create a new support ticket and initial message.

        Parameters
        ----------
        data : SupportTicketCreate
            Input data containing the subject and initial content.
        current_user : dict
            Authentication payload containing at least ``user_id``.

        Returns
        -------
        SupportTicketRead
            The created ticket.

        Raises
        ------
        ValueError
            If the database operation fails.
        """
        logger = logging.getLogger(__name__)
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Insert ticket
            cursor.execute(
                "INSERT INTO support_tickets (user_id, subject, status) VALUES (?, ?, 'open')",
                (current_user.get("user_id"), data.subject),
            )
            ticket_id = cursor.lastrowid
            # Insert first message
            # First message does not use attachments
            cursor.execute(
                """
                INSERT INTO support_messages (user_id, admin_id, content, ticket_id, sender_role, attachments)
                VALUES (?, NULL, ?, ?, 'user', NULL)
                """,
                (current_user.get("user_id"), data.content, ticket_id),
            )
            conn.commit()
            logger.info(
                "User %s opened support ticket %s",
                current_user.get("user_id"),
                ticket_id,
            )
            # Fetch created ticket fields
            row = cursor.execute(
                "SELECT id, user_id, subject, status, created_at, updated_at FROM support_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            # Audit log for ticket creation
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="create",
                    object_type="support_ticket",
                    object_id=row["id"],
                    details={"subject": data.subject},
                )
            except Exception:
                pass
            return SupportTicketRead(
                id=row["id"],
                user_id=row["user_id"],
                subject=row["subject"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        except Exception as e:
            conn.rollback()
            logger.error("Failed to create support ticket: %s", e)
            raise
        finally:
            conn.close()

    @classmethod
    async def list_tickets(
        cls,
        current_user: dict,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str | None = None,
        order: str | None = None,
    ) -> List[SupportTicketRead]:
        """List support tickets accessible to the current user.

        Admin users (role_id == 1) can view all tickets.  Regular users
        can only view their own tickets.  Supports optional status
        filter and pagination.

        Parameters
        ----------
        current_user : dict
            Authentication payload containing ``user_id`` and ``role_id``.
        status : Optional[str], optional
            Filter by ticket status (e.g. 'open', 'resolved'), by default None.
        limit : int, optional
            Maximum number of tickets to return, by default 20.
        offset : int, optional
            Number of tickets to skip for pagination, by default 0.

        Returns
        -------
        List[SupportTicketRead]
            A list of tickets.
        """
        logger = logging.getLogger(__name__)
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            params: list = []
            query = "SELECT id, user_id, subject, status, created_at, updated_at FROM support_tickets"
            where_clauses: list[str] = []
            # Non-admins (neither super‑administrator nor administrator) see only their tickets
            if current_user.get("role_id") not in (1, 2):
                where_clauses.append("user_id = ?")
                params.append(current_user.get("user_id"))
            # Status filter
            if status:
                where_clauses.append("status = ?")
                params.append(status)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            # Sorting
            sort_field = sort_by if sort_by in {"created_at", "updated_at", "status"} else "created_at"
            sort_order = order.upper() if order and order.lower() in {"asc", "desc"} else "DESC"
            query += f" ORDER BY {sort_field} {sort_order}"
            # Pagination
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = cursor.execute(query, tuple(params)).fetchall()
            tickets: List[SupportTicketRead] = []
            for row in rows:
                tickets.append(
                    SupportTicketRead(
                        id=row["id"],
                        user_id=row["user_id"],
                        subject=row["subject"],
                        status=row["status"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )
            logger.info(
                "User %s listed %s tickets", current_user.get("user_id"), len(tickets)
            )
            return tickets
        finally:
            conn.close()

    @classmethod
    async def delete_ticket(cls, ticket_id: int, current_user: dict) -> None:
        """Удалить тикет поддержки и все связанные сообщения.

        Только администратор может удалять тикеты.  Проверка прав
        выполняется в эндпоинте.  При удалении также удаляются
        сообщения из ``support_messages``.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Проверяем существование тикета
            row = cursor.execute(
                "SELECT id FROM support_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Ticket {ticket_id} not found")
            # Удаляем сообщения и сам тикет
            cursor.execute("DELETE FROM support_messages WHERE ticket_id = ?", (ticket_id,))
            cursor.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
            conn.commit()
            # Audit log for deletion of ticket
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="delete",
                    object_type="support_ticket",
                    object_id=ticket_id,
                    details=None,
                )
            except Exception:
                pass
        finally:
            conn.close()

    @classmethod
    async def get_ticket(
        cls,
        ticket_id: int,
        current_user: dict,
    ) -> Tuple[SupportTicketRead, List[SupportMessageRead]]:
        """Retrieve a support ticket and its messages.

        Ensures the current user has access to the ticket.  Admins can
        access any ticket; users can only access their own.

        Parameters
        ----------
        ticket_id : int
            ID of the ticket to retrieve.
        current_user : dict
            Authentication payload containing ``user_id`` and ``role_id``.

        Returns
        -------
        Tuple[SupportTicketRead, List[SupportMessageRead]]
            The ticket details and associated messages.

        Raises
        ------
        ValueError
            If the ticket does not exist or the user is not
            authorized to view it.
        """
        logger = logging.getLogger(__name__)
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            ticket_row = cursor.execute(
                "SELECT id, user_id, subject, status, created_at, updated_at FROM support_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if not ticket_row:
                raise ValueError(f"Support ticket {ticket_id} not found")
            # Check permissions: admin (super‑administrator or administrator) or ticket owner
            if current_user.get("role_id") not in (1, 2) and ticket_row["user_id"] != current_user.get("user_id"):
                raise ValueError("Not authorized to view this ticket")
            ticket = SupportTicketRead(
                id=ticket_row["id"],
                user_id=ticket_row["user_id"],
                subject=ticket_row["subject"],
                status=ticket_row["status"],
                created_at=ticket_row["created_at"],
                updated_at=ticket_row["updated_at"],
            )
            # Fetch messages
            msg_rows = cursor.execute(
                """
                SELECT id, ticket_id, user_id, admin_id, content, created_at, sender_role, attachments
                FROM support_messages
                WHERE ticket_id = ?
                ORDER BY created_at ASC
                """,
                (ticket_id,),
            ).fetchall()
            messages: List[SupportMessageRead] = []
            for mr in msg_rows:
                # Escape content for safety
                safe_content = html.escape(mr["content"]) if mr["content"] is not None else None
                # Deserialize attachments
                attachments = None
                if mr["attachments"]:
                    import json as _json
                    try:
                        attachments = _json.loads(mr["attachments"])
                    except Exception:
                        attachments = None
                messages.append(
                    SupportMessageRead(
                        id=mr["id"],
                        ticket_id=mr["ticket_id"],
                        content=safe_content,
                        created_at=mr["created_at"],
                        sender_role=mr["sender_role"],
                        user_id=mr["user_id"],
                        admin_id=mr["admin_id"],
                        attachments=attachments,
                    )
                )
            logger.info(
                "User %s retrieved ticket %s with %s messages",
                current_user.get("user_id"),
                ticket_id,
                len(messages),
            )
            return ticket, messages
        finally:
            conn.close()

    @classmethod
    async def reply_to_ticket(
        cls,
        ticket_id: int,
        data: SupportMessageCreate,
        current_user: dict,
    ) -> SupportMessageRead:
        """Add a reply to an existing support ticket.

        Determines the sender role (user or admin) based on the current
        user and ensures they have permission to reply to the ticket.
        The ticket's ``updated_at`` timestamp is refreshed.  The
        content is stored as provided but will be escaped upon
        retrieval.

        Parameters
        ----------
        ticket_id : int
            ID of the ticket to reply to.
        data : SupportMessageCreate
            The message content.
        current_user : dict
            Authentication payload containing ``user_id`` and ``role_id``.

        Returns
        -------
        SupportMessageRead
            The created message.

        Raises
        ------
        ValueError
            If the ticket does not exist or the user is not
            authorized to reply.
        """
        logger = logging.getLogger(__name__)
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Check ticket exists and permissions
            ticket_row = cursor.execute(
                "SELECT id, user_id FROM support_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if not ticket_row:
                raise ValueError(f"Support ticket {ticket_id} not found")
            ticket_owner = ticket_row["user_id"]
            user_role = current_user.get("role_id")
            # Only admins (super‑administrator or administrator) or ticket owner can reply
            if user_role not in (1, 2) and ticket_owner != current_user.get("user_id"):
                raise ValueError("Not authorized to reply to this ticket")
            # Determine sender_role and set user_id/admin_id accordingly
            sender_role = "admin" if user_role in (1, 2) else "user"
            # Determine columns: user_id refers to the ticket owner for admin messages
            if sender_role == "admin":
                # Admin response: user_id is the ticket owner, admin_id is the admin
                user_id_insert = ticket_owner
                admin_id_insert = current_user.get("user_id")
            else:
                # User response: user_id is current user, admin_id is NULL
                user_id_insert = current_user.get("user_id")
                admin_id_insert = None
            # Insert message
            # Serialize attachments as JSON if provided
            attachments_json = None
            if getattr(data, "attachments", None) is not None:
                import json as _json
                attachments_json = _json.dumps(data.attachments)
            cursor.execute(
                """
                INSERT INTO support_messages (user_id, admin_id, content, ticket_id, sender_role, attachments)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id_insert, admin_id_insert, data.content, ticket_id, sender_role, attachments_json),
            )
            message_id = cursor.lastrowid
            # Update ticket's updated_at timestamp
            cursor.execute(
                "UPDATE support_tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (ticket_id,),
            )
            conn.commit()
            # Fetch created message row
            msg_row = cursor.execute(
                "SELECT id, ticket_id, user_id, admin_id, content, created_at, sender_role, attachments FROM support_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            safe_content = html.escape(msg_row["content"])
            logger.info(
                "User %s replied to ticket %s as %s",
                current_user.get("user_id"),
                ticket_id,
                sender_role,
            )
            # Deserialize attachments
            attachments = None
            if msg_row["attachments"]:
                import json as _json
                try:
                    attachments = _json.loads(msg_row["attachments"])
                except Exception:
                    attachments = None
            # Audit log for reply
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="create",
                    object_type="support_message",
                    object_id=msg_row["id"],
                    details={"ticket_id": ticket_id, "sender_role": sender_role},
                )
            except Exception:
                pass
            return SupportMessageRead(
                id=msg_row["id"],
                ticket_id=msg_row["ticket_id"],
                content=safe_content,
                created_at=msg_row["created_at"],
                sender_role=msg_row["sender_role"],
                user_id=msg_row["user_id"],
                admin_id=msg_row["admin_id"],
                attachments=attachments,
            )
        except Exception as e:
            conn.rollback()
            logger.error(
                "Failed to reply to ticket %s by user %s: %s",
                ticket_id,
                current_user.get("user_id"),
                e,
            )
            raise
        finally:
            conn.close()

    @classmethod
    async def update_ticket_status(
        cls,
        ticket_id: int,
        update: SupportTicketUpdate,
        current_user: dict,
    ) -> SupportTicketRead:
        """Update the status of a support ticket.

        Only administrators (role_id == 1) may change the status.
        Supported statuses should be validated at the endpoint level.

        Parameters
        ----------
        ticket_id : int
            ID of the ticket to update.
        update : SupportTicketUpdate
            Object containing the new status.
        current_user : dict
            Authentication payload with ``user_id`` and ``role_id``.

        Returns
        -------
        SupportTicketRead
            The updated ticket.

        Raises
        ------
        ValueError
            If the ticket does not exist or the user is not an admin.
        """
        logger = logging.getLogger(__name__)
        # Allow super‑administrators and administrators to update ticket status
        if current_user.get("role_id") not in (1, 2):
            raise ValueError("Only administrators can update ticket status")
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Check existence
            ticket_row = cursor.execute(
                "SELECT id FROM support_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if not ticket_row:
                raise ValueError(f"Support ticket {ticket_id} not found")
            # Update status and timestamp
            cursor.execute(
                "UPDATE support_tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (update.status, ticket_id),
            )
            conn.commit()
            # Fetch updated ticket
            updated_row = cursor.execute(
                "SELECT id, user_id, subject, status, created_at, updated_at FROM support_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            logger.info(
                "Admin %s updated ticket %s status to %s",
                current_user.get("user_id"),
                ticket_id,
                update.status,
            )
            # Audit log for status update
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=current_user.get("user_id"),
                    action="update",
                    object_type="support_ticket",
                    object_id=ticket_id,
                    details={"status": update.status},
                )
            except Exception:
                pass
            return SupportTicketRead(
                id=updated_row["id"],
                user_id=updated_row["user_id"],
                subject=updated_row["subject"],
                status=updated_row["status"],
                created_at=updated_row["created_at"],
                updated_at=updated_row["updated_at"],
            )
        finally:
            conn.close()
