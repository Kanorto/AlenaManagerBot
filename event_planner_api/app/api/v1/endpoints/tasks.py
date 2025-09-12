"""
API endpoints for scheduled tasks.

These routes allow administrator clients and bots to poll the system
for tasks that need to be executed.  A task may correspond to a
scheduled mailing that is ready to be sent or an open support ticket
that requires a response.  Clients should call this endpoint
periodically to discover new work items instead of exposing a reverse
callback interface.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from event_planner_api.app.schemas.task import TaskRead
from event_planner_api.app.services.task_service import TaskService
from event_planner_api.app.core.security import get_current_user, require_roles


router = APIRouter()


@router.get(
    "/tasks",
    response_model=List[TaskRead],
    summary="Get pending tasks for a messenger",
    tags=["tasks"],
)
async def get_pending_tasks(
    messenger: str = Query(
        ...,  # required parameter
        description=(
            "Code of the messenger requesting tasks. Supported values: 'telegram', 'vk', 'max'. "
            "Only tasks for this messenger will be returned."
        ),
        regex="^(telegram|vk|max)$",
    ),
    until: Optional[str] = Query(
        None,
        description=(
            "Optional ISO date/time up to which tasks should be returned. "
            "Tasks scheduled after this time are excluded. If omitted, the current server time is used."
        ),
    ),
    current_user: dict = Depends(require_roles(1, 2)),
) -> List[TaskRead]:
    """Return pending tasks for a specific messenger.

    Bots should poll this endpoint regularly (e.g. every minute) to discover
    new work items.  Each task corresponds to a scheduled action (currently
    mailings) and is created separately for each messenger.  When a bot
    completes a task, it must call the completion endpoint with the task's
    ID so that the task is not returned again.  Only administrators and
    bots with an administrator role can access tasks.

    Parameters
    ----------
    messenger : str
        Short code of the messenger requesting tasks (e.g. ``telegram``,
        ``vk``, ``max``).  Tasks for other messengers are not returned.
    until : Optional[str]
        ISO‑formatted timestamp limiting the maximum ``scheduled_at`` of
        tasks returned.  Tasks scheduled after this time are excluded.
        If omitted, the current server time is used.

    Returns
    -------
    List[TaskRead]
        A list of pending tasks for the given messenger.
    """
    # Determine the cutoff time.  If an invalid value is provided, fall back
    # to None so TaskService will use the current time.
    now_dt: Optional[datetime] = None
    if until:
        try:
            now_dt = datetime.fromisoformat(until)
        except Exception:
            now_dt = None
    tasks = await TaskService.get_pending_tasks(messenger=messenger, now=now_dt)
    return tasks


@router.post(
    "/tasks/{task_id}/complete",
    status_code=204,
    summary="Mark a task as completed",
    tags=["tasks"],
)
async def complete_task(
    task_id: int,
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Mark the specified task as completed.

    Bots must call this endpoint after successfully processing a task returned
    by ``GET /tasks``.  Once a task is marked as completed it will no
    longer be returned to any messenger, ensuring that each task is
    executed at most once per messenger.

    Parameters
    ----------
    task_id : int
        Identifier of the task to complete.  This ID is returned by the
        ``GET /tasks`` endpoint.

    Returns
    -------
    None
        Responds with HTTP 204 No Content on success.
    """
    await TaskService.complete_task(task_id=task_id)