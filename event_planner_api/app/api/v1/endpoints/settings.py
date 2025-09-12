"""
Settings endpoints for API v1.

These routes allow administrators to view and modify configuration
settings at runtime.  Each setting is stored as a key/value pair
with an associated type to aid proper deserialization.  Only users
with admin privileges may change settings.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any

from event_planner_api.app.services.settings_service import SettingsService
from event_planner_api.app.core.security import get_current_user, require_roles


router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_settings(current_user: dict = Depends(require_roles(1, 2))) -> List[Dict[str, Any]]:
    """List all settings.

    Only super administrators may read settings.  Future versions may
    scope settings by namespace and restrict access further.
    """
    return await SettingsService.list_settings()


@router.get("/{key}", response_model=Dict[str, Any])
async def get_setting(key: str, current_user: dict = Depends(require_roles(1, 2))) -> Dict[str, Any]:
    """Retrieve a single setting by key.

    Only super administrators may access individual settings.
    """
    setting = await SettingsService.get_setting(key)
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return setting


@router.post("/{key}", response_model=Dict[str, Any])
async def upsert_setting(key: str, body: Dict[str, Any], current_user: dict = Depends(require_roles(1, 2))) -> Dict[str, Any]:
    """Insert or update a setting.

    Only super administrators may change settings.  The request body must
    include ``value`` and ``type`` keys.  Supported types are
    ``string``, ``int``, ``float`` and ``bool``.
    """
    if "value" not in body or "type" not in body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Body must include 'value' and 'type'")
    value = body["value"]
    type_str = body["type"]
    return await SettingsService.upsert_setting(key, value, type_str)