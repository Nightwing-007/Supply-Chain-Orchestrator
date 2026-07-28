"""
Pydantic models for the Customer Notification domain.

Maps to: sco.notifications
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"


class NotificationStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class NotificationBase(BaseModel):
    order_id: Optional[int] = None
    channel: NotificationChannel = NotificationChannel.EMAIL
    recipient: str = Field(..., max_length=200)
    subject: Optional[str] = Field(None, max_length=500)
    body: str


class NotificationCreate(NotificationBase):
    pass


class Notification(NotificationBase):
    id: int
    status: NotificationStatus = NotificationStatus.QUEUED
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
