"""
Pydantic models for event data.

These schemas define the structure of event data exchanged via the
API.  The ``EventBase`` class contains shared fields; ``EventCreate``
extends it for requests, and ``EventRead`` extends it with an ``id``
for responses.  Additional fields can be added as the domain
requirements evolve.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventBase(BaseModel):
    title: str = Field(..., example="Yoga Class")
    description: Optional[str] = Field(None, example="A relaxing yoga session")
    start_time: datetime = Field(..., example="2025-09-01T10:00:00Z")
    duration_minutes: int = Field(..., example=60)
    max_participants: int = Field(..., example=15)
    is_paid: bool = Field(False, example=False)


class EventCreate(EventBase):
    """Schema for creating an event."""
    pass


class EventRead(EventBase):
    """Schema for reading an event from the API."""

    id: int
    # For pydantic v2, enable constructing from ORM models
    model_config = {
        "from_attributes": True,
    }


class EventUpdate(BaseModel):
    """Schema for updating an event.

    All fields are optional; only provided fields will be updated.
    """
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    duration_minutes: int | None = None
    max_participants: int | None = None
    is_paid: bool | None = None
    price: float | None = None

    model_config = {
        "from_attributes": True,
    }


class EventDuplicate(BaseModel):
    """Schema for duplicating an event.

    Requires a new start time for the duplicated event.  Other fields
    will be copied from the source event.
    """
    start_time: datetime = Field(..., example="2025-09-15T10:00:00Z")