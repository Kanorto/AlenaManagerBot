"""
Role management endpoints for API v1.

These routes allow administrators to create, update, delete and list
roles, as well as assign roles to users.  Roles define sets of
permissions that control access to API functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path
from typing import List, Dict, Any, Optional

from event_planner_api.app.services.role_service import RoleService
from event_planner_api.app.core.security import get_current_user, require_roles


router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_roles(current_user: dict = Depends(require_roles(1))) -> List[Dict[str, Any]]:
    """List all roles.

    Only super administrators (role_id 1) may list roles.
    """
    return await RoleService.list_roles()


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_role(body: Dict[str, Any], current_user: dict = Depends(require_roles(1))) -> Dict[str, Any]:
    """Create a new role.

    Only super administrators may create new roles.  The request body must
    contain a ``name`` key and may include ``permissions`` (list of strings).
    """
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
    permissions = body.get("permissions", [])
    return await RoleService.create_role(name, permissions)


@router.put("/{role_id}", response_model=Dict[str, Any])
async def update_role(
    role_id: int,
    body: Dict[str, Any],
    current_user: dict = Depends(require_roles(1)),
) -> Dict[str, Any]:
    """Update an existing role.

    Only super administrators may modify roles.  The body may specify
    ``name`` and/or ``permissions``.
    """
    name: Optional[str] = body.get("name")
    permissions = body.get("permissions")
    try:
        return await RoleService.update_role(role_id, name, permissions)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: int, current_user: dict = Depends(require_roles(1))) -> None:
    """Delete a role.

    Only super administrators may delete roles.
    """
    await RoleService.delete_role(role_id)


@router.post("/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign_role(body: Dict[str, Any], current_user: dict = Depends(require_roles(1))) -> None:
    """Assign a role to a user.

    Only super administrators may assign roles to users.  The request body must
    include ``user_id`` and ``role_id``.
    """
    user_id = body.get("user_id")
    role_id = body.get("role_id")
    if user_id is None or role_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="user_id and role_id required")
    try:
        await RoleService.assign_role(int(user_id), int(role_id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))