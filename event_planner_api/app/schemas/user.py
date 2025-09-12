"""
Pydantic models for user data.

Defines schemas for creating users, authenticating and reading user
information.  In a real application you would not return passwords
through the API.  To support future extensions (e.g. roles), fields
can be added to these schemas and corresponding service logic.
"""

from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    # Email может отсутствовать для пользователей из мессенджеров.  Для
    # администратора обязательно указание email.  При отсутствии email
    # для клиента будет сгенерирован surrogate-адрес вида
    # ``telegram:12345`` (см. UserService.create_user).
    email: Optional[str] = Field(None, example="user@example.com")
    full_name: Optional[str] = Field(None, example="Иван Иванов")
    disabled: bool = Field(False, example=False)


class UserCreate(UserBase):
    """Schema for registering a user.

    There are two ways to create a user:

    * Администратор: требуется ``email`` и ``password``.  ``social_provider`` и
      ``social_id`` остаются по умолчанию.
    * Пользователь из мессенджера: передаются ``social_provider`` и ``social_id``.
      ``password`` может быть опущен.

    Хотя поле ``password`` остаётся необязательным, рекомендуется не отправлять
    его для пользователей Telegram/соцсетей.  Валидация осуществляется на
    уровне сервисов.
    """

    password: Optional[str] = Field(None, example="strongpassword")
    social_provider: Optional[str] = Field(None, example="telegram", description="Краткий код социальной сети (telegram, vk, etc.)")
    social_id: Optional[str] = Field(None, example="123456789", description="Идентификатор пользователя в социальной сети")


class UserRead(UserBase):
    """Schema for reading a user from the API."""

    id: int
    
    # For pydantic v2, set from_attributes to True so models can be
    # constructed from ORM objects.  For v1 this will be ignored.
    model_config = {
        "from_attributes": True,
    }