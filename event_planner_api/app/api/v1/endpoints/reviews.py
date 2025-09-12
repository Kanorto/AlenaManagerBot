"""
API endpoints for event reviews.

These endpoints allow users to submit reviews for events they have
attended and view their own reviews.  Administrators can list,
moderate and inspect reviews across all users.  Comments are
escaped when returned to protect clients from XSS.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from event_planner_api.app.core.security import get_current_user, require_roles
from event_planner_api.app.schemas.review import (
    ReviewCreate,
    ReviewRead,
    ReviewModerate,
)
from event_planner_api.app.services.review_service import ReviewService


router = APIRouter()


@router.post(
    "/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review",
)
async def create_review(
    data: ReviewCreate,
    current_user: dict = Depends(get_current_user),
) -> ReviewRead:
    """Create a new review for an event.

    The current user must have attended the event.  Returns the
    created review with ``approved`` set to ``False``.
    """
    try:
        return await ReviewService.create_review(data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/reviews",
    response_model=List[ReviewRead],
    summary="List reviews",
)
async def list_reviews(
    event_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    approved: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: Optional[str] = Query(None, description="Sort by 'created_at' or 'rating'"),
    order: Optional[str] = Query(None, description="Sort order 'asc' or 'desc'"),
    current_user: dict = Depends(get_current_user),
) -> List[ReviewRead]:
    """List reviews with optional filters.

    Regular users see only their own reviews; administrators can
    filter by event, user or approval status.  Results are
    paginated.
    """
    try:
        return await ReviewService.list_reviews(
            current_user=current_user,
            event_id=event_id,
            user_id=user_id,
            approved=approved,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewRead,
    summary="Get a single review",
)
async def get_review(
    review_id: int,
    current_user: dict = Depends(get_current_user),
) -> ReviewRead:
    """Retrieve a single review by its ID.

    Non-admin users can only access their own reviews.
    """
    try:
        return await ReviewService.get_review(review_id, current_user)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/reviews/{review_id}/moderate",
    response_model=ReviewRead,
    summary="Moderate a review",
)
async def moderate_review(
    review_id: int,
    data: ReviewModerate,
    current_user: dict = Depends(require_roles(1, 2)),
) -> ReviewRead:
    """Approve or reject a review.

    Only administrators (super‑administrators and administrators) can call this endpoint.
    """
    try:
        return await ReviewService.moderate_review(review_id, data, current_user)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        elif "Only administrators" in detail:
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a review",
)
async def delete_review(
    review_id: int,
    current_user: dict = Depends(get_current_user),
) -> None:
    """Удалить отзыв.

    Только администраторы могут удалить любой отзыв, а обычный
    пользователь может удалить только свой отзыв.  При отсутствии
    записи возвращается 404.
    """
    # Check access rights: admins can delete any; users can delete own
    try:
        review = await ReviewService.get_review(review_id, current_user)
    except ValueError as e:
        detail = str(e)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=status_code, detail=detail)
    # Non-admin (neither super‑administrator nor administrator) cannot delete others' reviews
    if current_user.get("role_id") not in (1, 2) and review.user_id != current_user.get("user_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    # Delete
    try:
        await ReviewService.delete_review(review_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return None
