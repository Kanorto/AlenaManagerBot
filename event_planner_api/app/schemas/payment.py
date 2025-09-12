"""
Pydantic models for payment data.

These schemas model the minimal information required to create and
represent a payment.  In a real implementation you would include
additional metadata (transaction IDs, payment status, user ID, etc.).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentBase(BaseModel):
    amount: float = Field(..., example=1000.0)
    currency: str = Field("RUB", example="RUB")
    description: Optional[str] = Field(None, example="Оплата участия в мероприятии")
    event_id: Optional[int] = Field(None, example=1, description="ID мероприятия, если платеж связан с событием")
    provider: Optional[str] = Field(None, example="yookassa", description="Источник платежа: yookassa, support или cash")


class PaymentCreate(PaymentBase):
    """Schema for creating a payment."""
    pass


class PaymentRead(PaymentBase):
    """Schema for reading a payment."""

    id: int
    created_at: datetime
    status: Optional[str] = Field(None, example="pending")
    external_id: Optional[str] = Field(None, example="2bcd42fa")
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True,
    }