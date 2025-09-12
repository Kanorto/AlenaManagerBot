"""
Pydantic models for event bookings.

These schemas define structures used to create and return bookings
associated with events.  Bookings allow multiple participants via the
``group_size`` field and track status for payment and attendance.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class BookingBase(BaseModel):
    group_size: int = Field(1, ge=1, example=1)
    # Optional list of participant names for group bookings.  A user can
    # specify names of group members when creating a booking.  This
    # field is not required and may be ``None`` or an empty list.
    group_names: list[str] | None = Field(default=None, description="Names of participants in the group")


class BookingCreate(BookingBase):
    """Schema for creating a booking."""
    pass


class BookingUpdate(BaseModel):
    """Schema for updating a booking.

    Only a subset of booking attributes may be modified by clients.  In
    particular, ``group_size`` and ``group_names`` can be changed to
    reflect changes in the size of a party or to provide updated
    participant names.  Other attributes such as the event identifier,
    payment status and attendance flags are managed via dedicated
    endpoints and may not be altered through this model.
    """

    # New group size for the booking.  If omitted, the existing
    # ``group_size`` will be retained.  Must be at least one when
    # supplied.
    group_size: int | None = Field(default=None, ge=1, description="Updated number of participants in the booking")
    # Optional list of participant names for group bookings.  A user can
    # specify names of group members when updating a booking.  This
    # field may be ``None`` or an empty list to clear previously
    # supplied names.
    group_names: list[str] | None = Field(default=None, description="Updated names of participants in the group")


class WaitlistUpdate(BaseModel):
    """Schema for updating a waitlist entry.

    Currently only the position on the waitlist can be modified.  When
    repositioning an entry, the service will adjust the positions of
    other entries for the same event to maintain a contiguous ordering.
    """

    position: int = Field(..., ge=1, description="New position for the waitlist entry (1‑based)")


class BookingRead(BaseModel):
    id: int
    user_id: int
    event_id: int
    group_size: int
    status: str
    created_at: datetime
    is_paid: bool | None = False
    is_attended: bool | None = False
    # Return the names of group members if provided.  This field is optional.
    group_names: list[str] | None = None

    model_config = {
        "from_attributes": True,
    }