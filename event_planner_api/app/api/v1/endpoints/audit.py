"""
Audit log endpoints for API v1.

Provides access to system audit logs for super‑administrators.  Logs
capture create, update and delete actions across the system and
support filtering by user, object type, action and date range.  Only
administrators (role_id == 1) should be allowed to view audit logs.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from event_planner_api.app.core.security import get_current_user
from event_planner_api.app.services.audit_service import AuditService

router = APIRouter()


@router.get("/logs")
async def list_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by acting user ID"),
    object_type: Optional[str] = Query(None, description="Filter by object type (event, booking, payment, etc.)"),
    action: Optional[str] = Query(None, description="Filter by action (create, update, delete)"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format) for filtering"),
    end_date: Optional[str] = Query(None, description="End date (ISO format) for filtering"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    current_user: dict = Depends(get_current_user),
) -> List[dict]:
    """Retrieve audit logs with optional filters.

    Only users with role_id == 1 may access this endpoint.  Returns a
    list of audit records ordered by timestamp descending.
    """
    if current_user.get("role_id") != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return await AuditService.list_logs(
        user_id=user_id,
        object_type=object_type,
        action=action,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )