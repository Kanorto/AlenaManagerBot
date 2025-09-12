"""
Pydantic schemas for support tickets and messages.

These schemas define the request and response bodies for the support
module.  A ticket groups one or more messages exchanged between a
user and support staff.  Each message records who sent it and when.

Fields that are returned from the database (e.g. timestamps) are
represented as ``str`` because SQLite returns ISO timestamp strings.
In a more advanced implementation you might convert these to
``datetime`` objects.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class SupportMessageCreate(BaseModel):
    """Schema for creating or replying to a support message.

    Messages may include text and optional attachments.  Attachments
    should be provided as a list of strings (e.g. file URLs or IDs);
    they are stored as JSON in the database.
    """

    content: str = Field(..., description="Text content of the message")
    attachments: Optional[List[str]] = Field(None, description="Optional list of attachment identifiers")


class SupportMessageRead(BaseModel):
    """Schema for reading a support message from the API.

    Includes the ID, associated ticket, sender role and creation
    timestamp.  Optionally includes the IDs of the user and admin
    who sent the message.  The ``content`` field contains the
    message text with HTML characters escaped to prevent
    cross‑site scripting.
    """

    id: int
    ticket_id: int
    content: str
    created_at: str
    sender_role: str
    user_id: Optional[int] = None
    admin_id: Optional[int] = None

    attachments: Optional[List[str]] = None

    class Config:
        orm_mode = True


class SupportTicketCreate(BaseModel):
    """Schema for creating a new support ticket.

    The client provides a subject and the initial message content.
    Additional metadata can be added later (e.g. attachments).
    """

    subject: str = Field(..., description="Subject or title of the support request")
    content: str = Field(..., description="Initial message content")


class SupportTicketUpdate(BaseModel):
    """Schema for updating the status of an existing support ticket.

    Only the ``status`` field may be updated.  Valid statuses include
    ``open``, ``in_progress``, ``resolved`` and ``closed``.  Validation
    of allowed values should be performed at the service or endpoint
    level.
    """

    status: str = Field(..., description="New status for the ticket")


class SupportTicketRead(BaseModel):
    """Schema for reading a support ticket.

    This schema represents a ticket without its messages.  When
    retrieving a ticket with messages, the API may return a separate
    structure containing ``ticket`` and ``messages`` lists.
    """

    id: int
    user_id: int
    subject: Optional[str]
    status: str
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True


class TicketWithMessages(BaseModel):
    """Composite schema for returning a ticket along with its messages."""

    ticket: SupportTicketRead
    messages: List[SupportMessageRead]
