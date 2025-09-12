"""
Service layer for statistics and reporting.

This module provides aggregated metrics across the system.  It allows
administrators to query overall counts (users, events, bookings,
payments, reviews) as well as per‑event statistics such as number
of bookings, paid bookings, attended bookings and total revenue.

All queries are read‑only and rely on parameterized statements to
avoid SQL injection vulnerabilities.  Sorting and pagination of
event statistics are performed in Python to allow ordering by
computed columns that are not directly present in the database.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from event_planner_api.app.core.db import get_connection


class StatisticsService:
    """Service providing various aggregated statistics for administrators."""

    @classmethod
    async def overview(cls) -> Dict[str, Any]:
        """Return a dictionary with high‑level system metrics.

        Metrics include total active users, total events, total bookings,
        total successful payments and total reviews.  Disabled users are
        excluded from the user count.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Users (exclude disabled)
            users_count = cursor.execute("SELECT COUNT(*) FROM users WHERE disabled = 0").fetchone()[0]
            # Events
            events_count = cursor.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            # Bookings
            bookings_count = cursor.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
            # Successful payments
            payments_count = cursor.execute(
                "SELECT COUNT(*) FROM payments WHERE status = 'success'"
            ).fetchone()[0]
            # Reviews
            reviews_count = cursor.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            # Total revenue from successful payments
            total_revenue = cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'success'"
            ).fetchone()[0]
            # Support tickets
            tickets_total = cursor.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0]
            tickets_open = cursor.execute(
                "SELECT COUNT(*) FROM support_tickets WHERE status = 'open'"
            ).fetchone()[0]
            # Waitlist entries
            waitlist_count = cursor.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0]
            return {
                "users_count": users_count,
                "events_count": events_count,
                "bookings_count": bookings_count,
                "payments_count": payments_count,
                "reviews_count": reviews_count,
                "support_tickets_total": tickets_total,
                "support_tickets_open": tickets_open,
                "waitlist_count": waitlist_count,
                "total_revenue": total_revenue,
            }
        finally:
            conn.close()

    @classmethod
    async def events_statistics(
        cls,
        sort_by: str = "id",
        order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return per‑event statistics with pagination and sorting.

        Parameters:
          - sort_by: field to sort results by.  Allowed values are
            ``id``, ``title``, ``start_time``, ``total_bookings``, ``paid_bookings``,
            ``attended_bookings`` and ``revenue``.  Defaults to ``id``.
          - order: sort direction: ``asc`` or ``desc``.  Defaults to ``asc``.
          - limit: maximum number of records to return.  Defaults to 50.
          - offset: number of records to skip.  Defaults to 0.

        Returns a list of dictionaries, each containing the event's
        id, title, start_time, price, max_participants, and computed
        metrics: total_bookings, paid_bookings, attended_bookings and
        revenue.
        """
        # Validate sorting parameters
        allowed_sort_fields = {
            "id",
            "title",
            "start_time",
            "total_bookings",
            "paid_bookings",
            "attended_bookings",
            "waitlist_count",
            "available_seats",
            "revenue",
        }
        if sort_by not in allowed_sort_fields:
            sort_by = "id"
        order = order.lower()
        if order not in {"asc", "desc"}:
            order = "asc"

        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Retrieve base event info
            events_rows = cursor.execute(
                "SELECT id, title, start_time, price, max_participants FROM events"
            ).fetchall()
            stats: List[Dict[str, Any]] = []
            for ev in events_rows:
                event_id = ev["id"]
                # Compute metrics via separate queries
                total_bookings = cursor.execute(
                    "SELECT COUNT(*) FROM bookings WHERE event_id = ?",
                    (event_id,),
                ).fetchone()[0]
                paid_bookings = cursor.execute(
                    "SELECT COUNT(*) FROM bookings WHERE event_id = ? AND is_paid = 1",
                    (event_id,),
                ).fetchone()[0]
                attended_bookings = cursor.execute(
                    "SELECT COUNT(*) FROM bookings WHERE event_id = ? AND is_attended = 1",
                    (event_id,),
                ).fetchone()[0]
                revenue = cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE event_id = ? AND status = 'success'",
                    (event_id,),
                ).fetchone()[0]
                # Waitlist count and available seats
                waitlist_count_event = cursor.execute(
                    "SELECT COUNT(*) FROM waitlist WHERE event_id = ?",
                    (event_id,),
                ).fetchone()[0]
                available_seats = max(ev["max_participants"] - total_bookings, 0)
                stats.append(
                    {
                        "id": event_id,
                        "title": ev["title"],
                        "start_time": ev["start_time"],
                        "price": ev["price"],
                        "max_participants": ev["max_participants"],
                        "total_bookings": total_bookings,
                        "paid_bookings": paid_bookings,
                        "attended_bookings": attended_bookings,
                        "waitlist_count": waitlist_count_event,
                        "available_seats": available_seats,
                        "revenue": revenue,
                    }
                )
            # Sort the list by requested field
            reverse = order == "desc"
            stats.sort(key=lambda x: x[sort_by], reverse=reverse)
            # Apply pagination
            paginated = stats[offset : offset + limit]
            return paginated
        finally:
            conn.close()

    @classmethod
    async def payments_statistics(
        cls,
        start_date: str | None = None,
        end_date: str | None = None,
        group_by: str = "day",
    ) -> List[Dict[str, Any]]:
        """Return aggregated payment statistics.

        Parameters
        ----------
        start_date : str | None
            ISO‑formatted date (YYYY‑MM‑DD).  Only payments created at
            or after this date are included.  If ``None``, no lower
            bound is applied.
        end_date : str | None
            ISO‑formatted date (YYYY‑MM‑DD).  Only payments created
            before this date are included.  If ``None``, no upper
            bound is applied.
        group_by : str
            Aggregation key.  Allowed values:
              - ``day`` (default): group by calendar day (YYYY‑MM‑DD)
              - ``month``: group by calendar month (YYYY‑MM)
              - ``event``: group by event ID
              - ``provider``: group by payment provider
              - ``status``: group by payment status

        Returns
        -------
        List[Dict[str, Any]]
            A list of dictionaries with keys depending on ``group_by``:
             - For ``day`` and ``month``: ``period``, ``payments_count``, ``total_amount``
             - For ``event``: ``event_id``, ``payments_count``, ``total_amount``
             - For ``provider``: ``provider``, ``payments_count``, ``total_amount``
             - For ``status``: ``status``, ``payments_count``, ``total_amount``
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Build base query with optional date filters
            where_clauses: list[str] = []
            params: list[Any] = []
            if start_date:
                where_clauses.append("DATE(created_at) >= DATE(?)")
                params.append(start_date)
            if end_date:
                where_clauses.append("DATE(created_at) < DATE(?)")
                params.append(end_date)
            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            # Determine grouping and select clause
            group_field: str
            label_field: str
            if group_by == "month":
                group_field = "strftime('%Y-%m', created_at)"
                label_field = "period"
            elif group_by == "event":
                group_field = "event_id"
                label_field = "event_id"
            elif group_by == "provider":
                group_field = "provider"
                label_field = "provider"
            elif group_by == "status":
                group_field = "status"
                label_field = "status"
            else:
                # default group by day
                group_by = "day"
                group_field = "strftime('%Y-%m-%d', created_at)"
                label_field = "period"
            query = (
                f"SELECT {group_field} as {label_field}, COUNT(*) as payments_count, "
                "COALESCE(SUM(amount), 0) as total_amount FROM payments"
                f"{where_sql} GROUP BY {group_field} ORDER BY {group_field} ASC"
            )
            rows = cursor.execute(query, tuple(params)).fetchall()
            results: List[Dict[str, Any]] = []
            for row in rows:
                results.append({
                    label_field: row[label_field],
                    "payments_count": row["payments_count"],
                    "total_amount": row["total_amount"],
                })
            return results
        finally:
            conn.close()

    @classmethod
    async def bookings_statistics(
        cls,
        start_date: str | None = None,
        end_date: str | None = None,
        group_by: str = "day",
    ) -> List[Dict[str, Any]]:
        """Return aggregated booking statistics.

        Parameters
        ----------
        start_date : str | None
            ISO date (YYYY‑MM‑DD).  Only bookings created at or after this date
            are included.  If ``None``, no lower bound is applied.
        end_date : str | None
            ISO date (YYYY‑MM‑DD).  Only bookings created before this date are
            included.  If ``None``, no upper bound is applied.
        group_by : str
            Aggregation key.  Allowed values:
              - ``day`` (default): group by date of creation
              - ``month``: group by month of creation
              - ``event``: group by event ID
              - ``status``: group by booking status (`pending`, `confirmed`, etc.)
            Returns
        -------
        List[Dict[str, Any]]
            A list of dictionaries with keys depending on ``group_by``:
             - For ``day`` and ``month``: ``period``, ``bookings_count``
             - For ``event``: ``event_id``, ``bookings_count``
             - For ``status``: ``status``, ``bookings_count``
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            where_clauses: list[str] = []
            params: list[Any] = []
            if start_date:
                where_clauses.append("DATE(created_at) >= DATE(?)")
                params.append(start_date)
            if end_date:
                where_clauses.append("DATE(created_at) < DATE(?)")
                params.append(end_date)
            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            # Determine grouping
            group_field: str
            label_field: str
            if group_by == "month":
                group_field = "strftime('%Y-%m', created_at)"
                label_field = "period"
            elif group_by == "event":
                group_field = "event_id"
                label_field = "event_id"
            elif group_by == "status":
                group_field = "status"
                label_field = "status"
            else:
                # default group by day
                group_by = "day"
                group_field = "strftime('%Y-%m-%d', created_at)"
                label_field = "period"
            query = (
                f"SELECT {group_field} as {label_field}, COUNT(*) as bookings_count "
                "FROM bookings"
                f"{where_sql} GROUP BY {group_field} ORDER BY {group_field} ASC"
            )
            rows = cursor.execute(query, tuple(params)).fetchall()
            results: List[Dict[str, Any]] = []
            for row in rows:
                results.append({
                    label_field: row[label_field],
                    "bookings_count": row["bookings_count"],
                })
            return results
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Users statistics
    # ------------------------------------------------------------------
    @classmethod
    async def users_statistics(
        cls,
        start_date: str | None = None,
        end_date: str | None = None,
        group_by: str = "social_provider",
    ) -> List[Dict[str, Any]]:
        """Return aggregated user statistics.

        This endpoint helps administrators understand the composition
        and activity of their user base.  It can aggregate users by
        social provider (Telegram, VK, etc.), by role (super_admin,
        admin, user), or return overall counts of active and paying
        users.  Optional date filters may be applied to count only
        users who were active (e.g. made a booking or payment) in
        the specified period.

        Parameters
        ----------
        start_date : str | None
            ISO date (YYYY‑MM‑DD) to filter activity.  Only bookings
            or payments created on or after this date are considered
            when computing active/paying users.  If ``None``, no lower
            bound is applied.
        end_date : str | None
            ISO date (YYYY‑MM‑DD) to filter activity.  Only bookings
            or payments created before this date are considered when
            computing active/paying users.  If ``None``, no upper
            bound is applied.
        group_by : str
            Aggregation key.  Allowed values:
              - ``social_provider`` (default): group by ``social_provider`` in ``users``
              - ``role``: group by ``role_id`` in ``users``
              - ``none``: return overall metrics (active_users_count,
                paying_users_count)

        Returns
        -------
        List[Dict[str, Any]]
            A list of dictionaries, each containing counts depending on
            ``group_by``:
              - For ``social_provider``: ``social_provider``, ``users_count``
              - For ``role``: ``role_id``, ``users_count``
              - For ``none``: a single element with keys
                ``active_users_count``, ``paying_users_count``
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            results: List[Dict[str, Any]] = []
            # When grouping by provider or role, simply count users (disabled excluded)
            if group_by == "role":
                rows = cursor.execute(
                    "SELECT role_id, COUNT(*) as users_count FROM users WHERE disabled = 0 GROUP BY role_id"
                ).fetchall()
                for row in rows:
                    results.append({
                        "role_id": row["role_id"],
                        "users_count": row["users_count"],
                    })
                return results
            if group_by == "social_provider":
                rows = cursor.execute(
                    "SELECT COALESCE(social_provider, 'internal') as social_provider, COUNT(*) as users_count "
                    "FROM users WHERE disabled = 0 GROUP BY social_provider"
                ).fetchall()
                for row in rows:
                    results.append({
                        "social_provider": row["social_provider"],
                        "users_count": row["users_count"],
                    })
                return results
            # If group_by is anything else (e.g. "none"), compute overall metrics
            # Active users: distinct users who made a booking or payment in the given date range
            where_clauses: list[str] = []
            params: list[Any] = []
            if start_date:
                where_clauses.append("DATE(created_at) >= DATE(?)")
                params.append(start_date)
            if end_date:
                where_clauses.append("DATE(created_at) < DATE(?)")
                params.append(end_date)
            where_sql = " AND ".join(where_clauses)
            # Find distinct users from bookings or payments
            active_users = set()
            # Bookings
            if where_sql:
                query_bookings = f"SELECT DISTINCT user_id FROM bookings WHERE {where_sql}"
                for row in cursor.execute(query_bookings, tuple(params)).fetchall():
                    if row["user_id"]:
                        active_users.add(row["user_id"])
                # Payments created_at is in payments table
                query_payments = f"SELECT DISTINCT user_id FROM payments WHERE {where_sql}"
                for row in cursor.execute(query_payments, tuple(params)).fetchall():
                    if row["user_id"]:
                        active_users.add(row["user_id"])
            else:
                # No date filter: count all users with any booking or payment
                rows_b = cursor.execute("SELECT DISTINCT user_id FROM bookings").fetchall()
                rows_p = cursor.execute("SELECT DISTINCT user_id FROM payments").fetchall()
                for row in rows_b:
                    if row["user_id"]:
                        active_users.add(row["user_id"])
                for row in rows_p:
                    if row["user_id"]:
                        active_users.add(row["user_id"])
            active_users_count = len(active_users)
            # Paying users: users with at least one successful payment
            paying_users = set()
            if where_sql:
                query_paying = f"SELECT DISTINCT user_id FROM payments WHERE status = 'success' AND {where_sql}"
                for row in cursor.execute(query_paying, tuple(params)).fetchall():
                    if row["user_id"]:
                        paying_users.add(row["user_id"])
            else:
                rows_pay = cursor.execute(
                    "SELECT DISTINCT user_id FROM payments WHERE status = 'success'"
                ).fetchall()
                for row in rows_pay:
                    if row["user_id"]:
                        paying_users.add(row["user_id"])
            paying_users_count = len(paying_users)
            results.append({
                "active_users_count": active_users_count,
                "paying_users_count": paying_users_count,
            })
            return results
        finally:
            conn.close()