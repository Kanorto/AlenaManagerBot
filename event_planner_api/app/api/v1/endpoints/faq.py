"""
FAQ endpoints for API v1.

These routes expose a CRUD API for frequently asked questions.  The
FAQ list can be used by clients (e.g. bots or web apps) to build
interactive menus; individual FAQ entries include the full question
and answer, attachments and ordering position.  Administrators may
create, update and delete FAQ entries via the API, while regular
users may only list and retrieve entries.
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query, status, Depends

from event_planner_api.app.core.security import require_roles
from event_planner_api.app.schemas.faq import FAQCreate, FAQRead, FAQUpdate
from event_planner_api.app.services.faq_service import FAQService

router = APIRouter()


@router.get("/", response_model=List[FAQRead])
async def list_faqs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> List[FAQRead]:
    """Return a paginated list of FAQs.

    Ordered by ``position`` ascending then ``id`` ascending.  This
    endpoint is publicly accessible and does not require
    authentication.  Clients may call it without an Authorization
    header to retrieve the current FAQ entries.  Administrators
    should use the CRUD endpoints to manage FAQ content.
    """
    faqs = await FAQService.list_faqs(limit=limit, offset=offset)
    return faqs


@router.get("/{faq_id}", response_model=FAQRead)
async def get_faq(faq_id: int) -> FAQRead:
    """Retrieve a single FAQ by ID.

    Returns HTTP 404 if the entry is not found.  This endpoint is
    publicly accessible and does not require authentication.
    """
    faq = await FAQService.get_faq(faq_id)
    if faq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
    return faq


@router.post("/", response_model=FAQRead, status_code=status.HTTP_201_CREATED)
async def create_faq(
    faq_in: FAQCreate,
    current_user: dict = Depends(require_roles(1, 2)),
) -> FAQRead:
    """Create a new FAQ entry (admin only)."""
    # Создание FAQ доступно супер‑администратору и администратору
    faq = await FAQService.create_faq(faq_in)
    return faq


@router.put("/{faq_id}", response_model=FAQRead)
async def update_faq(
    faq_id: int,
    faq_in: FAQUpdate,
    current_user: dict = Depends(require_roles(1, 2)),
) -> FAQRead:
    """Update an existing FAQ entry (admin only)."""
    # Обновление FAQ доступно супер‑администратору и администратору
    faq = await FAQService.update_faq(faq_id, faq_in)
    if faq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
    return faq


@router.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: int,
    current_user: dict = Depends(require_roles(1, 2)),
) -> None:
    """Delete an FAQ entry (admin only)."""
    # Удаление FAQ доступно супер‑администратору и администратору
    deleted = await FAQService.delete_faq(faq_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
    return None