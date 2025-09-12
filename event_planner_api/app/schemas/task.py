"""
Pydantic models for scheduled tasks exposed to bots.

These schemas define the structure of tasks that bots can poll from
the API.  A task represents an action that an external client (such
as a messaging bot) should perform, e.g. sending a mailing or
responding to a support ticket.  The schema is intentionally
generalized to support future extensions without breaking
compatibility.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskRead(BaseModel):
    """Schema for a task returned by the tasks API.

    A task represents some action that an external client (such as a
    messenger bot) should perform.  Supported types include:

    * ``"mailing"`` — send a mass mailing; the ``object_id`` points to a row
      in the ``mailings`` table, and the ``title``/``description`` provide
      context for the bot.
    * ``"waitlist"`` — notify a user that a seat is available; the
      ``object_id`` stores the waitlist entry ID.  Bots should send a
      message with a button "Записать" that triggers ``POST /api/v1/waitlist/{entry_id}/book``.
    * other types may be added in the future (e.g., support ticket alerts).

    The ``scheduled_at`` field is used for tasks that should not be
    executed until a particular time (for example, scheduled mailings).
    For waitlist notifications this value is typically ``None``.
    """

    id: int
    type: str
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }