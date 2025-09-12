"""
Message endpoints for API v1.

These routes allow administrators to list, retrieve and update bot
message templates.  Each template defines the content and buttons
displayed to users.  Only administrators may modify messages.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any

from event_planner_api.app.services.message_service import MessageService
from event_planner_api.app.core.security import get_current_user, require_roles


router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_messages(current_user: dict = Depends(require_roles(1, 2))) -> List[Dict[str, Any]]:
    """List all bot message templates."""
    if current_user.get("role_id") != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return await MessageService.list_messages()


@router.get("/{key}", response_model=Dict[str, Any])
async def get_message(key: str, current_user: dict = Depends(require_roles(1, 2))) -> Dict[str, Any]:
    """Retrieve a single bot message template by key."""
    if current_user.get("role_id") != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    msg = await MessageService.get_message(key)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return msg


@router.post("/{key}", response_model=Dict[str, Any])
async def upsert_message(key: str, body: Dict[str, Any], current_user: dict = Depends(require_roles(1, 2))) -> Dict[str, Any]:
    """Insert or update a bot message template.

    The request body must contain ``content`` and may contain
    ``buttons`` (a list of objects).  The ``buttons`` structure
    should follow the format expected by the client (e.g. callback
    data for Telegram).
    """
    if current_user.get("role_id") != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if "content" not in body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Body must include 'content'")
    content = body["content"]
    buttons = body.get("buttons")
    return await MessageService.upsert_message(key, content, buttons)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(key: str, current_user: dict = Depends(require_roles(1, 2))) -> None:
    """Удалить шаблон сообщения.

    Только администратор может удалять сообщения.  Возвращает 204
    при успешном удалении.  Если ключ не найден, возвращается 404.
    """
    if current_user.get("role_id") != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    msg = await MessageService.get_message(key)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    await MessageService.delete_message(key)
    return None