"""
Business logic for users.

The ``UserService`` stores users in memory and provides basic
operations.  Password handling is not secure in this MVP; use a
strong hashing algorithm (e.g. bcrypt) in a production system.
"""

import logging
from typing import List, Optional

from ..schemas.user import UserCreate, UserRead


class UserService:
    """Сервис для работы с пользователями.

    Хранит пользователей в памяти и предоставляет базовые операции.
    В перспективе должен работать с реальной БД, поддерживать
    хеширование паролей, управление ролями, блокировку и восстановление
    аккаунтов.  Также следует добавить обработку уникальных e‑mail’ов
    и транзакционность операций.
    """

    # In a DB‑backed implementation, no in‑memory lists are used.  All
    # operations interact with the SQLite database defined in
    # ``core.db``.

    @classmethod
    async def create_user(cls, data: UserCreate) -> UserRead:
        """Create a new user in the database.

        Stores the email, full name and password (currently plain text;
        replace with hashed password in production) and returns the
        created user.  Logs the operation for audit purposes.
        """
        logger = logging.getLogger(__name__)
        logger.info("Registering user %s", data.email)
        from event_planner_api.app.core.db import get_connection
        from event_planner_api.app.core.security import hash_password
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Determine role and social fields.  First registered user becomes super_admin (role_id=1).
            row = cursor.execute("SELECT COUNT(*) AS count FROM users").fetchone()
            is_first = row["count"] == 0
            # If social_provider and social_id provided, treat as messenger user
            if data.social_provider and data.social_id:
                role_id = 3  # user
                social_provider = data.social_provider
                social_id = data.social_id
            else:
                social_provider = 'internal'
                social_id = None
                # Determine role for internal users
                if is_first:
                    role_id = 1  # super_admin
                else:
                    role_id = 2  # admin by default (can be adjusted later)
            # Password hashing: if provided, hash; else store None
            hashed = None
            if data.password:
                hashed = hash_password(data.password)
            # If no email provided (messenger user), generate surrogate email
            email_value = data.email
            if email_value is None:
                # Compose a unique placeholder using provider and ID
                email_value = f"{social_provider}:{social_id}"
            cursor.execute(
                "INSERT INTO users (email, full_name, password, role_id, social_provider, social_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    email_value,
                    data.full_name,
                    hashed,
                    role_id,
                    social_provider,
                    social_id,
                ),
            )
            user_id = cursor.lastrowid
            conn.commit()
            # Write audit log: record creation of user
            try:
                from event_planner_api.app.services.audit_service import AuditService
                # user_id is set to None because the creator may not yet be persisted or is a system action
                await AuditService.log(
                    user_id=None,
                    action="create",
                    object_type="user",
                    object_id=user_id,
                    details={"email": data.email},
                )
            except Exception:
                # Do not block user creation on audit failures
                pass
            # Return user with actual stored email (surrogate if generated)
            return UserRead(id=user_id, email=email_value, full_name=data.full_name, disabled=False)
        except Exception as e:
            conn.rollback()
            # Re‑raise with meaningful context if email uniqueness violated or other DB error
            raise e
        finally:
            conn.close()

    @classmethod
    async def list_users(cls) -> List[UserRead]:
        """Return the list of all users from the database."""
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, email, full_name, disabled FROM users"
            ).fetchall()
            return [UserRead(id=row["id"], email=row["email"], full_name=row["full_name"], disabled=bool(row["disabled"])) for row in rows]
        finally:
            conn.close()

    @classmethod
    async def authenticate(cls, email: str, password: str) -> Optional[UserRead]:
        """Authenticate a user by email and password.

        In this MVP the password is stored in plain text.  Replace
        this with password hashing (bcrypt/argon2) and constant time
        comparison for production.  Returns ``UserRead`` if
        credentials match, otherwise ``None``.
        """
        from event_planner_api.app.core.db import get_connection
        from event_planner_api.app.core.security import verify_password
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, email, full_name, password, disabled FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if not row:
                return None
            stored_hash = row["password"]
            if verify_password(password, stored_hash):
                return UserRead(
                    id=row["id"],
                    email=row["email"],
                    full_name=row["full_name"],
                    disabled=bool(row["disabled"]),
                )
            return None
        finally:
            conn.close()

    @classmethod
    async def update_user(cls, user_id: int, updates: dict) -> UserRead:
        """Update a user's profile, role or status.

        Accepts a dictionary of fields to update.  Only admins should
        call this method; role changes must be validated at the
        endpoint level.  Returns the updated user.  Raises ``ValueError``
        if the user does not exist.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError(f"User {user_id} not found")
            if updates:
                fields = []
                values = []
                for key, value in updates.items():
                    # When updating password, hash it
                    if key == "password":
                        from event_planner_api.app.core.security import hash_password
                        value = hash_password(value)
                    # Convert booleans to int for SQLite
                    if isinstance(value, bool):
                        values.append(1 if value else 0)
                    else:
                        values.append(value)
                    fields.append(f"{key} = ?")
                values.append(user_id)
                sql = f"UPDATE users SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(sql, tuple(values))
                conn.commit()
            # Return updated user
            updated = cursor.execute(
                "SELECT id, email, full_name, disabled FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            # Record audit log on update
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="update",
                    object_type="user",
                    object_id=user_id,
                    details=updates,
                )
            except Exception:
                pass
            return UserRead(
                id=updated["id"],
                email=updated["email"],
                full_name=updated["full_name"],
                disabled=bool(updated["disabled"]),
            )
        finally:
            conn.close()

    @classmethod
    async def get_user_by_id(cls, user_id: int) -> Optional[UserRead]:
        """Retrieve a user by ID."""
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, email, full_name, disabled FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row:
                return UserRead(
                    id=row["id"],
                    email=row["email"],
                    full_name=row["full_name"],
                    disabled=bool(row["disabled"]),
                )
            return None
        finally:
            conn.close()


    @classmethod
    async def delete_user(cls, user_id: int) -> None:
        """Удалить пользователя и связанные записи.

        Физически удаляет пользователя из базы и каскадно удаляет
        связанные бронирования, платежи, отзывы, тикеты и сообщения поддержки.
        Только администратор должен вызывать этот метод; проверка прав
        выполняется на уровне эндпоинта.  Если пользователь не найден,
        возбуждается ``ValueError``.
        """
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Проверяем существование
            row = cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError(f"User {user_id} not found")
            # Удаляем связанные записи
            cursor.execute("DELETE FROM support_messages WHERE user_id = ? OR admin_id = ?", (user_id, user_id))
            cursor.execute("DELETE FROM support_tickets WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM reviews WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM payments WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM waitlist WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
            # Наконец удаляем самого пользователя
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            # Record audit log for deletion
            try:
                from event_planner_api.app.services.audit_service import AuditService
                await AuditService.log(
                    user_id=None,
                    action="delete",
                    object_type="user",
                    object_id=user_id,
                    details=None,
                )
            except Exception:
                pass
        finally:
            conn.close()