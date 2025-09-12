"""
User endpoints for API v1.

Provide registration, login and listing of users.  Password handling
in this MVP is intentionally simplified; use a secure password hashing
algorithm and proper authentication in production.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from event_planner_api.app.schemas.user import UserCreate, UserRead
from event_planner_api.app.services.user_service import UserService
from event_planner_api.app.core.security import create_access_token, get_current_user, require_roles
from fastapi import Body
from pydantic import BaseModel
from typing import Optional as OptionalType


router = APIRouter()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate) -> UserRead:
    """Зарегистрировать нового пользователя.

    Принимает данные пользователя и возвращает созданную запись.  В
    будущем здесь будет реализована проверка уникальности e‑mail,
    хеширование пароля (bcrypt/argon2), подтверждение почты и
    присвоение роли по умолчанию.  Сейчас данные хранятся в памяти.
    """
    return await UserService.create_user(user)


@router.post("/login")
async def login_user(user: UserCreate) -> dict:
    """Аутентифицировать пользователя и вернуть токен.

    На входе ожидаются e‑mail и пароль.  В дальнейшем рекомендуется
    выделить отдельную схему ``UserLogin`` и добавить refresh‑токены
    для долгосрочной сессии.  Метод будет проверять хешированный
    пароль и, возможно, блокировать учётные записи после нескольких
    неудачных попыток.
    """
    db_user = await UserService.authenticate(user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Social login endpoint for users authenticated via external services.
# ---------------------------------------------------------------------------

class SocialLogin(BaseModel):
    """Payload for social login.

    Clients should provide the external service identifier (e.g. 'telegram',
    'vk') and the unique user identifier within that service.  Optionally
    a full name may be supplied to populate the user record on first login.
    """
    social_provider: str
    social_id: str
    full_name: OptionalType[str] = None


@router.post("/social-login")
async def social_login(payload: SocialLogin) -> dict:
    """Authenticate or register a user via social provider and return a token.

    This endpoint allows bots or messenger integrations to obtain a JWT
    without requiring an email/password.  If a user with the given
    ``social_provider`` and ``social_id`` exists, a new access token is issued.
    Otherwise a new user is created with role ``user`` (role_id=3) and a
    token is returned.  The optional ``full_name`` is used only when creating
    a new user.
    """
    # Look up the user by social provider/id
    from event_planner_api.app.core.db import get_connection
    from event_planner_api.app.services.user_service import UserService
    from event_planner_api.app.core.security import create_access_token
    from fastapi import HTTPException
    conn = get_connection()
    try:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id, email, full_name, disabled FROM users WHERE social_provider = ? AND social_id = ?",
            (payload.social_provider, payload.social_id),
        ).fetchone()
        if row:
            if row["disabled"]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account disabled")
            email = row["email"]
            # Issue new token
            token = create_access_token({"sub": email})
            return {"access_token": token, "token_type": "bearer"}
    finally:
        conn.close()
    # If user does not exist, register a new one
    new_user = await UserService.create_user(
        UserCreate(
            email=None,
            full_name=payload.full_name,
            password=None,
            social_provider=payload.social_provider,
            social_id=payload.social_id,
        )
    )
    token = create_access_token({"sub": new_user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/", response_model=List[UserRead])
async def list_users(current_user: dict = Depends(require_roles(1, 2))) -> List[UserRead]:
    """Получить список всех пользователей.

    Доступно только супер‑администраторам и администраторам.  В дальнейшем
    будет добавлена пагинация и фильтрация (по активности, статусу блокировки и т.п.).
    """
    return await UserService.list_users()


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
) -> UserRead:
    """Update a user's profile, status or password.

    Only administrators may update other users.  The body may
    contain ``full_name``, ``disabled``, ``password``, or ``role_id``.
    ``role_id`` changes the user's role via RoleService.
    """
    # Check permission: admin (super‑administrator or administrator) can update; user can update self (except role)
    is_admin = current_user.get("role_id") in (1, 2)
    if not is_admin and current_user.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    updates = {}
    from event_planner_api.app.services.role_service import RoleService
    # Allowed fields
    for field in ("full_name", "disabled", "password"):
        if field in body:
            updates[field] = body[field]
    # Role assignment can only be done by super‑administrator (role_id == 1)
    if "role_id" in body:
        # Only super‑administrator may change roles
        if current_user.get("role_id") != 1:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the super administrator can change roles")
        try:
            await RoleService.assign_role(user_id, int(body["role_id"]))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # If there are other fields to update
    if updates:
        try:
            return await UserService.update_user(user_id, updates)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # If only role changed, return the user
    user = await UserService.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(
    user_id: int,
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Удалить пользователя по ID.

    Только супер‑администратор или администратор может удалять пользователей и не может удалить
    самого себя.  Удаление первого созданного пользователя (главного
    администратора) также запрещено.  После удаления пользователя
    связанные записи (сообщения, тикеты, бронирования, платежи) будут
    удалены каскадно.
    """
    # Prevent deleting self
    if current_user.get("user_id") == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    # Prevent deleting first user (super admin)
    from event_planner_api.app.core.db import get_connection
    conn = get_connection()
    try:
        cursor = conn.cursor()
        row = cursor.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
        first_id = row["id"] if row else None
        if user_id == first_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the primary administrator")
    finally:
        conn.close()
    try:
        await UserService.delete_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return None
