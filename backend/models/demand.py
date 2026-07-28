"""
Pydantic models for the Demand Forecasting domain.

Maps to: sco.demand_forecasts
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class DemandForecastBase(BaseModel):
    product_id: int
    warehouse_id: Optional[int] = Field(None, description="NULL means global forecast")
    forecast_date: date
    period_days: int = Field(7, ge=1, description="Forecast window in days")
    predicted_qty: int = Field(..., ge=0)
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Model confidence 0–1")
    model_version: Optional[str] = Field(None, max_length=50)


class DemandForecastCreate(DemandForecastBase):
    pass


class DemandForecast(DemandForecastBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
