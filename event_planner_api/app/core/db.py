"""
SQLite database integration and simple migration system.

This module provides functions for obtaining a database connection
(``get_connection``), applying migrations on application start
(``init_db``) and a helper dependency for FastAPI routes.  It uses
SQLite as a lightweight embedded database; to switch to another DBMS
you would replace connection logic and adapt SQL syntax accordingly.

The migration mechanism stores applied migration versions in the
``migrations`` table and executes new migrations in order.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import settings


def get_database_path() -> str:
    """Compute the path to the SQLite database file.

    If ``settings.database_url`` is an absolute path, use it directly.
    Otherwise resolve it relative to the project root.
    """
    db_url = settings.database_url
    # If an absolute path is provided, return as is
    if os.path.isabs(db_url):
        return db_url
    # Otherwise resolve relative to the current file's parent (project root)
    base_dir = Path(__file__).resolve().parent.parent.parent  # event_planner_api/
    return str((base_dir / db_url).resolve())


def get_connection() -> sqlite3.Connection:
    """Create and return a new SQLite connection.

    The connection uses a row factory to access columns by name.  No
    type detection/parsing is enabled because some ISO timestamps (e.g.
    ``2025-09-01T09:00:00Z``) cannot be parsed by SQLite's built‑in
    converters.  All values will be returned as they are stored in the
    database (typically strings or numbers).
    """
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    # Return rows as dict‑like objects keyed by column name
    conn.row_factory = sqlite3.Row
    # Enable foreign key constraints for the lifetime of the connection.  In SQLite
    # foreign key support is disabled by default and must be turned on per
    # connection via PRAGMA.  Failure to enable this will silently bypass
    # REFERENCES clauses defined in ``init_db``.
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        # Ignore errors here; if this fails foreign key constraints will not
        # be enforced, which could lead to orphaned records.  See README for
        # more details on enabling FK enforcement in production.
        pass
    return conn


@contextmanager
def get_cursor() -> Iterator[sqlite3.Cursor]:
    """Context manager that yields a cursor and closes the connection on exit."""
    conn = get_connection()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialise the database and apply pending migrations.

    Creates the ``migrations`` table if it does not exist, checks the
    current schema version, and applies any new migrations defined in
    the ``MIGRATIONS`` list.  If you add a new migration, append it
    with an incremented version number.
    """
    migrations: list[tuple[int, str]] = [
        # Migration 1: Initial schema
        (
            1,
            """
            -- Base schema (version 1)
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                permissions TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                full_name TEXT,
                password TEXT,
                role_id INTEGER,
                balance REAL DEFAULT 0,
                disabled INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(role_id) REFERENCES roles(id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_time TIMESTAMP NOT NULL,
                duration_minutes INTEGER NOT NULL,
                max_participants INTEGER NOT NULL,
                is_paid INTEGER NOT NULL DEFAULT 0,
                price REAL,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'RUB',
                payment_method TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(event_id) REFERENCES events(id)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                group_size INTEGER DEFAULT 1,
                payment_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(event_id) REFERENCES events(id),
                FOREIGN KEY(payment_id) REFERENCES payments(id)
            );

            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES events(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                admin_id INTEGER,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(admin_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                approved INTEGER DEFAULT 0,
                moderated_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(event_id) REFERENCES events(id),
                FOREIGN KEY(moderated_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS mailings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_by INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                filters TEXT,
                scheduled_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                object_type TEXT,
                object_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """,
        ),
        # Migration 2: Additional tables for messages, FAQs, mailing logs and notifications
        (
            2,
            """
            CREATE TABLE IF NOT EXISTS bot_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                content TEXT NOT NULL,
                buttons TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS faqs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_short TEXT NOT NULL,
                question_full TEXT,
                answer TEXT NOT NULL,
                attachments TEXT,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mailing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mailing_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(mailing_id) REFERENCES mailings(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_id INTEGER,
                content TEXT NOT NULL,
                context TEXT,
                status TEXT NOT NULL DEFAULT 'sent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """,
        ),
        # Migration 3: Extend bookings table with payment and attendance flags
        (
            3,
            """
            -- Add columns to bookings to track payment and attendance status.
            -- These flags allow toggling payment and attendance independently of the
            -- general booking status string.  Values are 0 (false) or 1 (true).
            ALTER TABLE bookings ADD COLUMN is_paid INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE bookings ADD COLUMN is_attended INTEGER NOT NULL DEFAULT 0;
            """,
        ),
        # Migration 4: Extend payments table to support multiple providers and confirmation
        (
            4,
            """
            -- Add additional fields to payments for provider integration.
            ALTER TABLE payments ADD COLUMN provider TEXT;
            ALTER TABLE payments ADD COLUMN external_id TEXT;
            ALTER TABLE payments ADD COLUMN confirmed_by INTEGER;
            ALTER TABLE payments ADD COLUMN confirmed_at TIMESTAMP;
            ALTER TABLE payments ADD COLUMN notes TEXT;
            """,
        ),
        # Migration 5: Support tickets and additional message fields
        (
            5,
            """
            -- Table to group support conversations (tickets)
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            -- Add ticket_id and sender_role columns to support_messages to track conversations
            ALTER TABLE support_messages ADD COLUMN ticket_id INTEGER;
            ALTER TABLE support_messages ADD COLUMN sender_role TEXT;
            -- Create index for faster lookups by ticket
            CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages(ticket_id);
            """,
        ),
        # Migration 6: Add attachments to support messages
        (
            6,
            """
            -- Add attachments column to support_messages for file uploads
            ALTER TABLE support_messages ADD COLUMN attachments TEXT;
            """,
        ),
        # Migration 7: add social provider fields to users
        (
            7,
            """
            -- Add columns to support social login providers and IDs
            ALTER TABLE users ADD COLUMN social_provider TEXT DEFAULT 'internal';
            ALTER TABLE users ADD COLUMN social_id TEXT;
            """,
        ),
        # Migration 8: create indices on user_id columns for faster lookups
        (
            8,
            """
            -- Create indices on user-related foreign keys for performance
            CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);
            CREATE INDEX IF NOT EXISTS idx_waitlist_user_id ON waitlist(user_id);
            CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);
            CREATE INDEX IF NOT EXISTS idx_support_messages_user_id ON support_messages(user_id);
            CREATE INDEX IF NOT EXISTS idx_support_messages_admin_id ON support_messages(admin_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
            CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
            CREATE INDEX IF NOT EXISTS idx_mailing_logs_user_id ON mailing_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
            """,
        ),

        # Migration 9: create tasks table
        (
            9,
            """
            -- Create tasks table to track scheduled actions for messenger bots.  Each
            -- row represents a pending or completed task for a specific messenger
            -- and object (e.g. a mailing).  The scheduled_at column may be null to
            -- indicate immediate availability.  The status column uses values
            -- 'pending' and 'completed'.  If the table already exists, this
            -- statement is a no‑op.
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                object_id INTEGER NOT NULL,
                messenger TEXT NOT NULL,
                scheduled_at TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
        ),

        # Migration 10: add messengers column to mailings table
        (
            10,
            """
            -- Persist the selected messenger channels directly on the mailings table.  Prior to
            -- this migration the list of messengers was only represented via entries in the
            -- tasks table.  Adding a column allows storing the list as JSON text so that
            -- clients can retrieve it when listing or viewing mailings.
            ALTER TABLE mailings ADD COLUMN messengers TEXT;
            """,
        ),
    ]

    with get_cursor() as cursor:
        # Ensure migrations table exists
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS migrations (version INTEGER PRIMARY KEY)"
        )
        # Determine current version
        cursor.execute("SELECT MAX(version) as version FROM migrations")
        row = cursor.fetchone()
        current_version = row["version"] if row and row["version"] is not None else 0

        # Apply new migrations
        for version, sql in migrations:
            if version > current_version:
                cursor.executescript(sql)
                cursor.execute(
                    "INSERT INTO migrations (version) VALUES (?)", (version,)
                )
                current_version = version

        # Ensure default roles exist: super_admin (id=1), admin (2) and user (3)
        cursor.execute(
            "INSERT OR IGNORE INTO roles (id, name, permissions) VALUES (1, 'super_admin', '[]')"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO roles (id, name, permissions) VALUES (2, 'admin', '[]')"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO roles (id, name, permissions) VALUES (3, 'user', '[]')"
        )
