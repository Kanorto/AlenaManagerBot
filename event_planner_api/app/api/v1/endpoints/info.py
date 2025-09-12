"""
Information endpoint for API v1.

This route returns the general information message together with a
list of FAQs.  The information text and its associated buttons are
retrieved from the bot messages table using the key ``info``.
Frequently asked questions are returned as a list of short
questions (with their IDs) so that clients can build interactive
menus.  Use the FAQ endpoints to retrieve full details of each
entry.

This endpoint is publicly accessible to all authenticated users.
"""

from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status

from event_planner_api.app.core.security import get_current_user
from event_planner_api.app.services.message_service import MessageService
from event_planner_api.app.services.faq_service import FAQService

router = APIRouter()


@router.get("/", response_model=Dict[str, Any])
async def get_info(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Return the information message and a list of FAQs.

    The info message is looked up by the key ``info`` in the
    ``bot_messages`` table.  The returned object contains the
    ``content`` and optional ``buttons`` of the info message, along
    with a list of FAQ short questions and their IDs.  If no info
    message is configured, a 404 error is returned.
    """
    # Retrieve the info message
    msg = await MessageService.get_message("info")
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Info message not configured")
    # Get FAQs; limit to e.g. 50 items for performance
    faqs = await FAQService.list_faqs(limit=50, offset=0)
    faqs_brief: List[Dict[str, Any]] = [
        {"id": faq.id, "question_short": faq.question_short, "position": faq.position} for faq in faqs
    ]
    return {"info": msg.get("content"), "buttons": msg.get("buttons"), "faqs": faqs_brief}