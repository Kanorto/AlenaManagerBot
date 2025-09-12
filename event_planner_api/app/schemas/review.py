"""
Pydantic schemas for event reviews.

The review module allows users to submit feedback for events they
attended.  Reviews may be moderated by administrators before being
published.  These schemas define the payloads and response shapes
used in the API.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional


class ReviewCreate(BaseModel):
    """Schema for creating a new review."""

    event_id: int = Field(..., description="Identifier of the event being reviewed")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, description="Optional textual comment")

    @validator("comment")
    def sanitize_comment(cls, v: Optional[str]) -> Optional[str]:
        """Trim whitespace from the comment and enforce a maximum length."""
        if v is None:
            return None
        v = v.strip()
        if len(v) > 1000:
            raise ValueError("Comment must be 1000 characters or fewer")
        return v


class ReviewModerate(BaseModel):
    """Schema for moderating a review."""

    approved: bool = Field(..., description="Whether to approve the review")


class ReviewRead(BaseModel):
    """Schema for reading a review from the API."""

    id: int
    user_id: int
    event_id: int
    rating: int
    comment: Optional[str]
    approved: bool
    moderated_by: Optional[int]
    created_at: str

    class Config:
        orm_mode = True