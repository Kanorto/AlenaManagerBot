"""
Pydantic schemas for FAQ entries.

The FAQ module manages frequently asked questions and their answers.
Each entry includes a short question (used for button labels), an
optional full question, an answer and optional attachments (e.g.
images or documents).  An integer ``position`` field allows
ordering of FAQ items for display.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
import json


class FAQCreate(BaseModel):
    """Schema for creating a new FAQ entry."""

    question_short: str = Field(..., description="Short question text displayed on the FAQ button")
    question_full: Optional[str] = Field(None, description="Full question text")
    answer: str = Field(..., description="Answer text for the FAQ")
    attachments: Optional[List[str]] = Field(None, description="List of attachment URLs or identifiers")
    position: Optional[int] = Field(0, description="Ordering position for display; lower numbers appear first")

    @validator("attachments")
    def validate_attachments(cls, v):
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("Attachments must be a list of strings")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("Each attachment must be a string")
        return v


class FAQUpdate(BaseModel):
    """Schema for updating an existing FAQ entry.

    All fields are optional; only provided values will be updated.
    """

    question_short: Optional[str] = None
    question_full: Optional[str] = None
    answer: Optional[str] = None
    attachments: Optional[List[str]] = None
    position: Optional[int] = None


class FAQRead(BaseModel):
    """Schema for reading an FAQ entry."""

    id: int
    question_short: str
    question_full: Optional[str]
    answer: str
    attachments: Optional[List[str]]
    position: int
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True