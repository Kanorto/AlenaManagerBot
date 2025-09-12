"""
Pydantic schemas for mailing (mass messaging).

The mailing module allows administrators to send bulk messages to
selected audiences.  Mailings support arbitrary text content,
optional filters to select recipients and scheduling.  Logs track
delivery outcomes for each recipient.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime


class MailingCreate(BaseModel):
    """Schema for creating a new mailing."""

    title: str = Field(..., description="Title of the mailing for internal reference")
    content: str = Field(..., description="Message content to send to users")
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Criteria to select recipients, e.g. {\"event_id\": 1, \"is_paid\": true, \"is_attended\": true}",
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="When to schedule the mailing; if null, send immediately",
    )

    messengers: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of messenger channels to send this mailing to (e.g. ['telegram','vk','max']). "
            "If omitted, no tasks will be generated for bots and the mailing will only be stored for record keeping. "
            "Supported channels correspond to available bot integrations."
        ),
    )

    @validator('messengers', pre=True, always=True)
    def validate_messengers(cls, v):
        """
        Validate the messenger list:

        - If not provided (None) or empty, return None to indicate no tasks should be created.
        - Ensure each messenger value is one of the supported channels.
        - Remove duplicate values and preserve original order.

        Raises
        ------
        ValueError
            If any messenger is not supported.
        """
        if v is None or v == []:
            return None
        if isinstance(v, str):
            # Allow comma‑separated string instead of list
            v = [item.strip() for item in v.split(',') if item.strip()]
        if not isinstance(v, list):
            raise ValueError('messengers must be a list of strings')
        allowed = {'telegram', 'vk', 'max'}
        seen = set()
        filtered: List[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError('messengers must be strings')
            code = item.strip().lower()
            if code not in allowed:
                raise ValueError(f"Unsupported messenger '{item}'. Allowed: telegram, vk, max")
            if code not in seen:
                seen.add(code)
                filtered.append(code)
        return filtered


class MailingRead(BaseModel):
    """Schema for reading a mailing."""

    id: int
    created_by: int
    title: str
    content: str
    filters: Optional[Dict[str, Any]]
    scheduled_at: Optional[str]
    created_at: str
    # Return the list of messenger channels used for this mailing.  This
    # corresponds to the ``messengers`` column stored as JSON on the mailings
    # table.  When no messengers were selected, this field will be ``None``.
    messengers: Optional[List[str]]

    class Config:
        orm_mode = True


# Schema for updating an existing mailing.  All fields are optional; omitted
# values will not be modified.  The ``messengers`` field uses the same
# validation rules as on creation.  When the list is provided it will
# replace the previous messenger list on the mailing.
class MailingUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None
    messengers: Optional[List[str]] = None

    @validator('messengers', pre=True, always=False)
    def validate_messengers_update(cls, v):
        # Reuse the validation from MailingCreate for messenger lists.  Do not
        # return an empty list: treat empty or None as no change to the
        # messenger selection on update.
        if v is None or v == []:
            return None
        return MailingCreate.validate_messengers(v)



class MailingLogRead(BaseModel):
    """Schema for reading a single mailing log entry."""

    id: int
    mailing_id: int
    user_id: int
    status: str
    error_message: Optional[str]
    sent_at: str

    class Config:
        orm_mode = True