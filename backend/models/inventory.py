"""
Pydantic models for the Inventory Planning domain.

Maps to: sco.products, sco.inventory, sco.inventory_transactions
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────

class TransactionType(str, Enum):
    RECEIPT = "receipt"
    PICK = "pick"
    ADJUSTMENT = "adjustment"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    RETURN = "return"


# ── Products ─────────────────────────────────────────────────

class ProductBase(BaseModel):
    sku: str = Field(..., max_length=50, description="Unique stock-keeping unit")
    name: str = Field(..., max_length=300)
    category: Optional[str] = None
    unit_weight_kg: float = 0.0
    unit_volume_m3: float = 0.0
    unit_price: float = 0.0
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Inventory ────────────────────────────────────────────────

class InventoryBase(BaseModel):
    warehouse_id: int
    product_id: int
    quantity_on_hand: int = Field(0, ge=0)
    quantity_reserved: int = Field(0, ge=0)
    reorder_point: int = Field(10, ge=0)
    reorder_qty: int = Field(50, ge=0)


class InventoryUpdate(BaseModel):
    """Partial update for an inventory record."""
    quantity_on_hand: Optional[int] = None
    quantity_reserved: Optional[int] = None
    reorder_point: Optional[int] = None
    reorder_qty: Optional[int] = None


class InventoryItem(InventoryBase):
    id: int
    last_counted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Inventory Transactions ───────────────────────────────────

class InventoryTransactionCreate(BaseModel):
    """Schema for logging a new stock movement."""
    inventory_id: int
    txn_type: TransactionType
    quantity: int = Field(..., description="Positive = inbound, negative = outbound")
    reference_id: Optional[str] = Field(None, max_length=100, description="Order ID, PO number, etc.")
    notes: Optional[str] = None


class InventoryTransaction(InventoryTransactionCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
