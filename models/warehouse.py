"""
Pydantic models for the Warehouse Operations domain.

Maps to the `sco.warehouses` table.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WarehouseBase(BaseModel):
    """Shared fields for warehouse representations."""
    name: str = Field(..., max_length=200, description="Human-readable warehouse name")
    code: str = Field(..., max_length=20, description="Unique warehouse code (e.g. WH-MUM-01)")
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_capacity: int = Field(0, ge=0, description="Total capacity in cubic metres")
    used_capacity: int = Field(0, ge=0, description="Currently used capacity in cubic metres")
    is_active: bool = True


class WarehouseCreate(WarehouseBase):
    """Schema for creating a new warehouse."""
    pass


class WarehouseUpdate(BaseModel):
    """Schema for partial warehouse updates."""
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    total_capacity: Optional[int] = None
    used_capacity: Optional[int] = None
    is_active: Optional[bool] = None


class Warehouse(WarehouseBase):
    """Full warehouse record as read from the database."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
