"""
Pydantic models for the Route Optimization domain.

Maps to: sco.routes, sco.route_stops
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RouteStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ── Routes ───────────────────────────────────────────────────

class RouteBase(BaseModel):
    route_code: str = Field(..., max_length=50)
    vehicle_id: Optional[int] = None
    status: RouteStatus = RouteStatus.PLANNED
    origin_warehouse: Optional[int] = None
    total_distance_km: float = Field(0.0, ge=0)
    total_duration_min: int = Field(0, ge=0)
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None


class RouteCreate(RouteBase):
    pass


class Route(RouteBase):
    id: int
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Route Stops ──────────────────────────────────────────────

class RouteStopBase(BaseModel):
    route_id: int
    stop_order: int = Field(..., ge=1)
    stop_type: str = Field("delivery", description="delivery | pickup | warehouse")
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    warehouse_id: Optional[int] = None
    order_id: Optional[int] = None
    eta: Optional[datetime] = None


class RouteStopCreate(RouteStopBase):
    pass


class RouteStop(RouteStopBase):
    id: int
    arrived_at: Optional[datetime] = None
    departed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
