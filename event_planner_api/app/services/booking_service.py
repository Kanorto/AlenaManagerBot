"""
Business logic for bookings and waitlist management.

The ``BookingService`` encapsulates operations for creating bookings,
listing bookings for an event, and handling waitlists when events are
fully booked.  It also provides methods for marking payment and
attendance status on a booking.  In a production system, these
operations should run within database transactions to ensure
consistency when multiple users attempt to book simultaneously.
"""

import logging
import sqlite3
from datetime import datetime
from typing import List, Optional

from event_planner_api.app.schemas.booking import BookingCreate, BookingRead
from event_planner_api.app.core.db import get_connection


class BookingService:
    """Service for managing bookings and waitlists."""

    @classmethod
    async def create_booking(cls, event_id: int, user_email: str, booking: BookingCreate) -> BookingRead:
        """Create a booking for a given event.

        If the event has available slots (``max_participants`` greater
        than the sum of existing confirmed bookings), a new booking is
        inserted with status ``pending``.  Otherwise, the user is
        placed on the waitlist.  Returns the created booking or raises
        an exception if the user is already booked or waitlisted.
        """
        logger = logging.getLogger(__name__)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Resolve user ID
            user_row = cursor.execute(
                "SELECT id FROM users WHERE email = ?",
                (user_email,),
            ).fetchone()
            if not user_row:
                raise ValueError(f"User {user_email} does not exist")
            user_id = user_row["id"]

            # Unlike earlier versions of the service, we no longer prevent a
            # single user from creating multiple bookings for the same event.
            # This allows a user to book several groups of seats, for
            # example when they want to pay separately for different
            # participants.  Therefore, we intentionally do not check
            # existing bookings or waitlist entries for this user/event pair.

            # Get event capacity and current bookings (confirmed or pending count as occupying spots)
            event = cursor.execute(
                "SELECT max_participants FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if not event:
                raise ValueError(f"Event {event_id} does not exist")
            capacity = event["max_participants"]
            count_row = cursor.execute(
                "SELECT COALESCE(SUM(group_size), 0) as total FROM bookings WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            current_booked = count_row["total"] if count_row else 0

            if current_booked + booking.group_size <= capacity:
                # Insert booking with status pending (awaiting payment/confirmation).
                # Ensure the "group_names" column exists.  When deploying to an existing
                # database, the column may not be present.  If missing, add it
                # dynamically on first use.  SQLite prior to version 3.35 does not
                # support "ALTER TABLE ... ADD COLUMN IF NOT EXISTS", so we check
                # via PRAGMA.
                import json
                # Check for group_names column
                try:
                    cols = cursor.execute("PRAGMA table_info(bookings)").fetchall()
                    if not any(col[1] == "group_names" for col in cols):
                        # Column does not exist; attempt to add it
                        try:
                            cursor.execute("ALTER TABLE bookings ADD COLUMN group_names TEXT")
                        except Exception:
                            # If another process added it concurrently, ignore error
                            pass
                except Exception:
                    # PRAGMA or ALTER may fail if database is busy; we ignore
                    pass
                group_names_json = json.dumps(booking.group_names) if booking.group_names else None
                cursor.execute(
                    """
                    INSERT INTO bookings (user_id, event_id, group_size, status, group_names)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, event_id, booking.group_size, "pending", group_names_json),
                )
                booking_id = cursor.lastrowid
                conn.commit()
                created_at = datetime.utcnow().isoformat()
                # Record audit log for booking creation
                try:
                    from event_planner_api.app.services.audit_service import AuditService
                    details = {"event_id": event_id, "group_size": booking.group_size}
                    if booking.group_names:
                        details["group_names"] = booking.group_names
                    await AuditService.log(
                        user_id=user_id,
                        action="create",
                        object_type="booking",
                        object_id=booking_id,
                        details=details,
                    )
                except Exception:
                    pass
                return BookingRead(
                    id=booking_id,
                    user_id=user_id,
                    event_id=event_id,
                    group_size=booking.group_size,
                    status="pending",
                    created_at=created_at,
                    group_names=booking.group_names,
                )
            else:
                # Add user to waitlist
                # Determine next position
                pos_row = cursor.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 as next_pos FROM waitlist WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                position = pos_row["next_pos"] if pos_row else 1
                cursor.execute(
                    "INSERT INTO waitlist (event_id, user_id, position) VALUES (?, ?, ?)",
                    (event_id, user_id, position),
                )
                conn.commit()
                logger.info(
                    "User %s added to waitlist for event %s at position %s", user_email, event_id, position
                )
                raise ValueError("Event is full. You have been added to the waitlist.")
        finally:
            conn.close()

    @classmethod
    async def list_bookings(
        cls,
        event_id: int,
        sort_by: str | None = None,
        order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> List[BookingRead]:
        """List bookings for a given event with optional sorting and pagination.

        Параметр ``sort_by`` может быть одним из ``created_at`` (по умолчанию),
        ``user_id``, ``is_paid`` или ``is_attended``.  ``order`` может быть
        ``asc`` или ``desc`` (по умолчанию desc).  ``limit`` и ``offset``
        управляют пагинацией.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            params: list = [event_id]
            # Determine whether the "group_names" column exists.  If it does not,
            # exclude it from the SELECT clause.  Otherwise include it.  This
            # dynamic check allows the service to operate on databases created
            # prior to the addition of the column.
            include_group_names = True
            try:
                col_rows = cursor.execute("PRAGMA table_info(bookings)").fetchall()
                include_group_names = any(col[1] == "group_names" for col in col_rows)
            except Exception:
                include_group_names = False

            if include_group_names:
                query = (
                    "SELECT id, user_id, event_id, group_size, status, created_at, is_paid, is_attended, group_names "
                    "FROM bookings WHERE event_id = ?"
                )
            else:
                query = (
                    "SELECT id, user_id, event_id, group_size, status, created_at, is_paid, is_attended "
                    "FROM bookings WHERE event_id = ?"
                )

            # Sorting
            sort_field = sort_by if sort_by in {"created_at", "user_id", "is_paid", "is_attended"} else "created_at"
            sort_order = order.upper() if order and order.lower() in {"asc", "desc"} else "DESC"
            query += f" ORDER BY {sort_field} {sort_order}"
            # Pagination
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
                if offset is not None:
                    query += " OFFSET ?"
                    params.append(offset)

            rows = cursor.execute(query, tuple(params)).fetchall()
            bookings: List[BookingRead] = []
            import json
            for row in rows:
                # Deserialize group_names JSON if the column is present
                group_names_list = None
                if include_group_names:
                    group_names_raw = row["group_names"]
                    if group_names_raw:
                        try:
                            group_names_list = json.loads(group_names_raw)
                        except Exception:
                            group_names_list = None
                bookings.append(
                    BookingRead(
                        id=row["id"],
                        user_id=row["user_id"],
                        event_id=row["event_id"],
                        group_size=row["group_size"],
                        status=row["status"],
                        created_at=row["created_at"],
                        is_paid=bool(row["is_paid"]),
                        is_attended=bool(row["is_attended"]),
                        group_names=group_names_list,
                    )
                )
            return bookings
        finally:
            conn.close()

    @classmethod
    async def list_waitlist(cls, event_id: int) -> List[dict]:
        """List waitlist entries for a given event in order."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, user_id, position, created_at FROM waitlist WHERE event_id = ? ORDER BY position ASC",
                (event_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @classmethod
    async def mark_booking_status(cls, booking_id: int, status: str) -> None:
        """Update the status of a booking (e.g., to 'paid' or 'attended')."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE bookings SET status = ? WHERE id = ?",
                (status, booking_id),
            )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    async def toggle_payment(cls, booking_id: int) -> None:
        """Toggle the payment flag for a booking.

        Retrieves the current ``is_paid`` value, flips it and
        persists the update.  In a production system this should be
        wrapped in a transaction to avoid race conditions.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT is_paid FROM bookings WHERE id = ?",
                (booking_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            current = row["is_paid"] or 0
            new_value = 0 if current else 1
            cursor.execute(
                "UPDATE bookings SET is_paid = ? WHERE id = ?",
                (new_value, booking_id),
            )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    async def toggle_attendance(cls, booking_id: int) -> None:
        """Toggle the attendance flag for a booking.

        Retrieves the current ``is_attended`` value, flips it and
        persists the update.  Use database transactions in a real
        implementation to guarantee consistency.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT is_attended FROM bookings WHERE id = ?",
                (booking_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            current = row["is_attended"] or 0
            new_value = 0 if current else 1
            cursor.execute(
                "UPDATE bookings SET is_attended = ? WHERE id = ?",
                (new_value, booking_id),
            )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    async def delete_booking_with_promotion(cls, booking_id: int, promote_waitlist: bool = True) -> None:
        """Delete a booking and optionally promote users from the waitlist.

        Parameters
        ----------
        booking_id : int
            Identifier of the booking to delete.
        promote_waitlist : bool, optional
            If True, the service will check for available seats after deletion
            and promote users from the waitlist until all available seats are
            filled.  Defaults to True.

        Raises
        ------
        ValueError
            If the booking does not exist.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Determine event_id before deletion
            row = cursor.execute(
                "SELECT event_id FROM bookings WHERE id = ?",
                (booking_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            event_id = row["event_id"]
            # Delete booking
            cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            conn.commit()
            # Promote from waitlist if required
            if promote_waitlist:
                # Determine promotion mode from settings.  By default
                # the system will automatically promote users from the
                # waitlist to fill vacancies.  Administrators can
                # override this behaviour via a runtime setting
                # ``waitlist_auto_promote`` (bool).  When set to
                # False, the service instead creates notification
                # tasks for each waitlist entry and relies on the
                # messenger bots to allow users to confirm their
                # booking.
                try:
                    from event_planner_api.app.services.settings_service import SettingsService
                    setting = await SettingsService.get_setting("waitlist_auto_promote")
                    auto = setting["value"] if setting else True
                except Exception:
                    auto = True
                if auto:
                    await cls._promote_from_waitlist(event_id)
                else:
                    await cls.notify_waitlist_users(event_id)
        finally:
            conn.close()
        # Write audit log outside of transaction
        try:
            from event_planner_api.app.services.audit_service import AuditService
            await AuditService.log(
                user_id=None,
                action="delete",
                object_type="booking",
                object_id=booking_id,
                details={"event_id": event_id},
            )
        except Exception:
            pass

    @classmethod
    async def _promote_from_waitlist(cls, event_id: int) -> None:
        """Internal helper to promote waitlisted users to bookings.

        Calculates available seats for the event and iteratively moves
        users from the waitlist to the bookings table until места
        закончатся или waitlist опустеет.  Each promoted user gets a
        booking with ``group_size = 1`` and ``status = 'pending'``.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Fetch event capacity
            evt = cursor.execute(
                "SELECT max_participants FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if not evt:
                return
            capacity = evt["max_participants"]
            # Count seats already booked
            seats = cursor.execute(
                "SELECT COALESCE(SUM(group_size),0) as total FROM bookings WHERE event_id = ?",
                (event_id,),
            ).fetchone()["total"]
            # Move users while there is space
            while seats < capacity:
                wait_row = cursor.execute(
                    "SELECT id, user_id FROM waitlist WHERE event_id = ? ORDER BY position ASC LIMIT 1",
                    (event_id,),
                ).fetchone()
                if not wait_row:
                    break
                wid = wait_row["id"]
                uid = wait_row["user_id"]
                # Remove from waitlist
                cursor.execute("DELETE FROM waitlist WHERE id = ?", (wid,))
                # Create new booking
                cursor.execute(
                    "INSERT INTO bookings (user_id, event_id, group_size, status) VALUES (?, ?, 1, 'pending')",
                    (uid, event_id),
                )
                seats += 1
            conn.commit()
        finally:
            conn.close()

    # To maintain backwards compatibility, provide a ``delete_booking`` alias
    # that automatically promotes users from the waitlist.  Endpoints should
    # call this method when deleting a booking so that any freed seat is
    # immediately filled by the first user on the waitlist.  Without this
    # alias, attempting to call ``delete_booking`` directly would result in
    # an infinite recursion.
    @classmethod
    async def delete_booking(cls, booking_id: int) -> None:
        await cls.delete_booking_with_promotion(booking_id, promote_waitlist=True)

    # ------------------------------------------------------------------
    # Waitlist notification and confirmation
    # ------------------------------------------------------------------

    @classmethod
    async def notify_waitlist_users(cls, event_id: int) -> None:
        """Create tasks to notify waitlisted users that a seat is available.

        Instead of automatically promoting users from the waitlist, this method
        generates a task for each waitlist entry associated with the given
        event.  Messenger bots can then deliver a notification to the user
        containing a button to confirm the booking.  If the tasks table
        does not exist it is created on demand via ``TaskService``.

        Parameters
        ----------
        event_id : int
            Identifier of the event for which a seat has become available.
        """
        try:
            from event_planner_api.app.services.task_service import TaskService
        except Exception:
            return
        # Fetch all waitlist entries for the event
        entries = await cls.list_waitlist(event_id)
        if not entries:
            return
        # Create a task for each waitlist entry.  Each task references
        # the waitlist entry ID as the ``object_id`` and uses type
        # ``waitlist``.  We generate a separate task for each supported
        # messenger (telegram, vk, max) so that bots can deliver the
        # notification to their respective platforms.
        messengers = ["telegram", "vk", "max"]
        for entry in entries:
            entry_id = entry.get("id")
            # Use TaskService to insert tasks.  It is idempotent and
            # ensures the tasks table exists.
            await TaskService.create_waitlist_tasks(entry_id=entry_id, messengers=messengers)

    @classmethod
    async def confirm_waitlist(cls, entry_id: int, user_email: str) -> BookingRead:
        """Confirm a booking for a waitlisted user.

        When a user receives a notification that a seat has become
        available, they can call this method to claim the seat.  The
        method validates that the waitlist entry exists and belongs
        to the user, checks that there is at least one free seat
        remaining for the associated event, and creates a new booking
        with group_size=1.  If no seats are available, a ``ValueError``
        is raised.  On success, the waitlist entry is removed and
        associated tasks are marked as completed.

        Parameters
        ----------
        entry_id : int
            Identifier of the waitlist entry being claimed.
        user_email : str
            Email of the user attempting to claim the booking.

        Returns
        -------
        BookingRead
            The created booking.

        Raises
        ------
        ValueError
            If the entry does not exist, does not belong to the
            authenticated user or if no seats are available.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Fetch waitlist entry
            wl = cursor.execute(
                "SELECT id, event_id, user_id, position FROM waitlist WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if not wl:
                raise ValueError(f"Waitlist entry {entry_id} not found")
            event_id = wl["event_id"]
            user_id = wl["user_id"]
            # Verify that the email corresponds to the user_id
            user_row = cursor.execute(
                "SELECT id FROM users WHERE email = ?",
                (user_email,),
            ).fetchone()
            if not user_row or user_row["id"] != user_id:
                raise ValueError("You are not authorized to claim this waitlist entry")
            # Determine capacity and current bookings
            event_row = cursor.execute(
                "SELECT max_participants FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if not event_row:
                raise ValueError(f"Event {event_id} does not exist")
            capacity = event_row["max_participants"]
            count_row = cursor.execute(
                "SELECT COALESCE(SUM(group_size),0) AS total FROM bookings WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            booked = count_row["total"] if count_row else 0
            if booked >= capacity:
                raise ValueError("No seats are currently available for this event")
            # Remove from waitlist
            cursor.execute("DELETE FROM waitlist WHERE id = ?", (entry_id,))
            # Compact positions for remaining entries by shifting down those below
            cursor.execute(
                "UPDATE waitlist SET position = position - 1 WHERE event_id = ? AND position > ?",
                (event_id, wl["position"]),
            )
            # Ensure group_names column exists for bookings
            try:
                cols = cursor.execute("PRAGMA table_info(bookings)").fetchall()
                if not any(col[1] == "group_names" for col in cols):
                    try:
                        cursor.execute("ALTER TABLE bookings ADD COLUMN group_names TEXT")
                    except Exception:
                        pass
            except Exception:
                pass
            # Insert booking with group_size=1, status pending
            cursor.execute(
                "INSERT INTO bookings (user_id, event_id, group_size, status) VALUES (?, ?, 1, 'pending')",
                (user_id, event_id),
            )
            booking_id = cursor.lastrowid
            conn.commit()
            # Mark associated tasks as completed
            try:
                from event_planner_api.app.services.task_service import TaskService
                await TaskService.complete_waitlist_tasks(entry_id)
            except Exception:
                pass
            # Audit log
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=user_id,
                    action="create",
                    object_type="booking",
                    object_id=booking_id,
                    details={"event_id": event_id, "from_waitlist": entry_id},
                )
            except Exception:
                pass
            # Build and return booking
            created_at = datetime.utcnow().isoformat()
            return BookingRead(
                id=booking_id,
                user_id=user_id,
                event_id=event_id,
                group_size=1,
                status="pending",
                created_at=created_at,
                is_paid=False,
                is_attended=False,
                group_names=None,
            )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Additional CRUD operations
    # ------------------------------------------------------------------

    @classmethod
    async def get_booking(cls, booking_id: int) -> BookingRead:
        """Retrieve a single booking by its identifier.

        Parameters
        ----------
        booking_id : int
            Identifier of the booking to fetch.

        Returns
        -------
        BookingRead
            A Pydantic model representing the booking.

        Raises
        ------
        ValueError
            If the booking does not exist.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Check if group_names column exists
            include_group_names = True
            try:
                cols = cursor.execute("PRAGMA table_info(bookings)").fetchall()
                include_group_names = any(col[1] == "group_names" for col in cols)
            except Exception:
                include_group_names = False
            if include_group_names:
                row = cursor.execute(
                    "SELECT id, user_id, event_id, group_size, status, created_at, is_paid, is_attended, group_names"
                    " FROM bookings WHERE id = ?",
                    (booking_id,),
                ).fetchone()
            else:
                row = cursor.execute(
                    "SELECT id, user_id, event_id, group_size, status, created_at, is_paid, is_attended"
                    " FROM bookings WHERE id = ?",
                    (booking_id,),
                ).fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            # Deserialize group_names
            import json
            group_names_list = None
            if include_group_names:
                raw = row[8]  # group_names column
                if raw:
                    try:
                        group_names_list = json.loads(raw)
                    except Exception:
                        group_names_list = None
            return BookingRead(
                id=row[0],
                user_id=row[1],
                event_id=row[2],
                group_size=row[3],
                status=row[4],
                created_at=row[5],
                is_paid=bool(row[6]),
                is_attended=bool(row[7]),
                group_names=group_names_list,
            )
        finally:
            conn.close()

    @classmethod
    async def update_booking(cls, booking_id: int, updates: dict) -> BookingRead:
        """Update an existing booking.

        Only ``group_size`` and ``group_names`` may be modified.  Other
        attributes, such as payment status and attendance, should be
        altered using their dedicated endpoints.  If the booking does
        not exist, a ValueError is raised.

        Parameters
        ----------
        booking_id : int
            Identifier of the booking to update.
        updates : dict
            Keys and values to update.  Supported keys are
            ``group_size`` and ``group_names``.

        Returns
        -------
        BookingRead
            The updated booking.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Ensure booking exists
            row = cursor.execute("SELECT id FROM bookings WHERE id = ?", (booking_id,)).fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            # Determine columns to update
            set_clauses = []
            params: list = []
            # Update group_size
            if "group_size" in updates and updates["group_size"] is not None:
                set_clauses.append("group_size = ?")
                params.append(int(updates["group_size"]))
            # Update group_names (ensure column exists)
            if "group_names" in updates:
                # Convert list to JSON or set NULL
                import json
                names = updates["group_names"]
                if names:
                    group_names_json = json.dumps(names)
                else:
                    group_names_json = None
                # Ensure column exists by attempting to add if missing
                try:
                    cols = cursor.execute("PRAGMA table_info(bookings)").fetchall()
                    if not any(col[1] == "group_names" for col in cols):
                        try:
                            cursor.execute("ALTER TABLE bookings ADD COLUMN group_names TEXT")
                        except Exception:
                            pass
                except Exception:
                    # Unable to check or add column; proceed
                    pass
                set_clauses.append("group_names = ?")
                params.append(group_names_json)
            # If nothing to update, return existing booking
            if not set_clauses:
                return await cls.get_booking(booking_id)
            # Compose update statement
            set_stmt = ", ".join(set_clauses)
            params.append(booking_id)
            cursor.execute(f"UPDATE bookings SET {set_stmt} WHERE id = ?", tuple(params))
            conn.commit()
            # Audit log
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="update",
                    object_type="booking",
                    object_id=booking_id,
                    details=updates,
                )
            except Exception:
                pass
            # Return updated booking
            return await cls.get_booking(booking_id)
        finally:
            conn.close()

    @classmethod
    async def get_waitlist_entry(cls, entry_id: int) -> dict:
        """Retrieve a single waitlist entry by its identifier.

        Parameters
        ----------
        entry_id : int
            Identifier of the waitlist entry.

        Returns
        -------
        dict
            A dictionary with keys ``id``, ``event_id``, ``user_id``,
            ``position`` and ``created_at``.

        Raises
        ------
        ValueError
            If the entry does not exist.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, event_id, user_id, position, created_at FROM waitlist WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Waitlist entry {entry_id} not found")
            return dict(row)
        finally:
            conn.close()

    @classmethod
    async def update_waitlist_entry(cls, entry_id: int, new_position: int) -> dict:
        """Change the position of a waitlist entry.

        When repositioning, the method adjusts other entries for the
        same event to maintain a contiguous sequence starting at 1.
        If the requested position is less than 1 or greater than the
        maximum number of entries for the event, it will be clamped.

        Parameters
        ----------
        entry_id : int
            Identifier of the waitlist entry to reposition.
        new_position : int
            Desired 1‑based position in the waitlist.

        Returns
        -------
        dict
            The updated waitlist entry.

        Raises
        ------
        ValueError
            If the entry does not exist.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Fetch current entry and event
            current = cursor.execute(
                "SELECT event_id, position FROM waitlist WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if not current:
                raise ValueError(f"Waitlist entry {entry_id} not found")
            event_id, cur_pos = current["event_id"], current["position"]
            # Determine bounds
            total_row = cursor.execute(
                "SELECT COUNT(*) AS total FROM waitlist WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            max_pos = total_row["total"] if total_row else 1
            # Clamp new_position
            if new_position < 1:
                new_position = 1
            if new_position > max_pos:
                new_position = max_pos
            # Adjust other entries
            if new_position < cur_pos:
                # Move up: shift down intervening entries
                cursor.execute(
                    "UPDATE waitlist SET position = position + 1 WHERE event_id = ? AND position >= ? AND position < ?",
                    (event_id, new_position, cur_pos),
                )
            elif new_position > cur_pos:
                # Move down: shift up intervening entries
                cursor.execute(
                    "UPDATE waitlist SET position = position - 1 WHERE event_id = ? AND position <= ? AND position > ?",
                    (event_id, new_position, cur_pos),
                )
            # Update entry
            cursor.execute(
                "UPDATE waitlist SET position = ? WHERE id = ?",
                (new_position, entry_id),
            )
            conn.commit()
            # Return updated entry
            row = cursor.execute(
                "SELECT id, event_id, user_id, position, created_at FROM waitlist WHERE id = ?",
                (entry_id,),
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    @classmethod
    async def delete_waitlist_entry(cls, entry_id: int) -> None:
        """Remove a waitlist entry.

        After deletion, the positions of remaining entries for the same
        event are compacted so that there are no gaps.  If the entry
        does not exist, a ValueError is raised.

        Parameters
        ----------
        entry_id : int
            Identifier of the waitlist entry to remove.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Fetch entry to get event and position
            current = cursor.execute(
                "SELECT event_id, position FROM waitlist WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if not current:
                raise ValueError(f"Waitlist entry {entry_id} not found")
            event_id, cur_pos = current["event_id"], current["position"]
            # Delete entry
            cursor.execute("DELETE FROM waitlist WHERE id = ?", (entry_id,))
            # Update positions of remaining entries (compact)
            cursor.execute(
                "UPDATE waitlist SET position = position - 1 WHERE event_id = ? AND position > ?",
                (event_id, cur_pos),
            )
            conn.commit()
        finally:
            conn.close()