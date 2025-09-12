"""
Top‑level router for version 1 of the API.

This router aggregates domain‑specific routers (events, users, payments,
etc.) under a unified prefix.  When new endpoints are added or when
new domains are introduced, update this file to include their routers.
"""

from fastapi import APIRouter

from .endpoints import (
    events,
    users,
    payments,
    bookings,
    settings,
    messages,
    roles,
    support,
    reviews,
    mailings,
    faq,
    info,
    statistics,
    audit,
    tasks,
)

# Create a router for version 1 and include sub‑routers for each domain.
router = APIRouter()

router.include_router(events.router, prefix="/events", tags=["events"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(payments.router, prefix="/payments", tags=["payments"])
router.include_router(bookings.router, tags=["bookings"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(messages.router, prefix="/messages", tags=["messages"])
router.include_router(roles.router, prefix="/roles", tags=["roles"])
router.include_router(support.router, prefix="/support", tags=["support"])
router.include_router(reviews.router, tags=["reviews"])
router.include_router(mailings.router, prefix="/mailings", tags=["mailings"])
# NOTE: The FAQ endpoints are traditionally exposed under the plural prefix
# ``/faqs``.  However, the provided Postman collection and some clients
# referenced the singular form ``/faq``.  To maintain backward
# compatibility and avoid confusing 404 responses, we include the same
# FAQ router twice: once under the plural ``/faqs`` and once under the
# singular ``/faq``.  Both prefixes expose identical endpoints (e.g.,
# ``GET /faqs/`` and ``GET /faq/`` will list the available FAQ entries).
router.include_router(faq.router, prefix="/faqs", tags=["faqs"])
router.include_router(faq.router, prefix="/faq", tags=["faqs"])
router.include_router(info.router, prefix="/info", tags=["info"])
router.include_router(statistics.router, prefix="/statistics", tags=["statistics"])
router.include_router(audit.router, prefix="/audit", tags=["audit"])
# The tasks router defines its own "/tasks" path internally.  Do not
# specify a prefix here or the endpoint would appear under ``/tasks/tasks``.
router.include_router(tasks.router, tags=["tasks"])