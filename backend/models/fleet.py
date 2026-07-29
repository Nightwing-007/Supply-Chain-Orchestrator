"""
Pydantic models for the Fleet Management domain.

Maps to: sco.vehicles
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class VehicleStatus(str, Enum):
    AVAILABLE = "available"
    IN_TRANSIT = "in_transit"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"


class VehicleType(str, Enum):
    TRUCK = "truck"
    VAN = "van"
    MOTORCYCLE = "motorcycle"
    DRONE = "drone"


class VehicleBase(BaseModel):
    registration: str = Field(..., max_length=30, description="Unique vehicle registration number")
    type: VehicleType = VehicleType.TRUCK
    status: VehicleStatus = VehicleStatus.AVAILABLE
    capacity_kg: float = Field(0.0, ge=0)
    capacity_m3: float = Field(0.0, ge=0)
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    home_warehouse: Optional[int] = None
    fuel_level_pct: float = Field(100.0, ge=0, le=100)
    mileage_km: float = Field(0.0, ge=0)
    last_maintenance: Optional[datetime] = None
    next_maintenance: Optional[datetime] = None
    is_active: bool = True


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    """Partial update for a vehicle record."""
    status: Optional[VehicleStatus] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    fuel_level_pct: Optional[float] = None
    mileage_km: Optional[float] = None
    last_maintenance: Optional[datetime] = None
    next_maintenance: Optional[datetime] = None
    is_active: Optional[bool] = None


class Vehicle(VehicleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
