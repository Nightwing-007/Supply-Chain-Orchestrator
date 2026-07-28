"""
Supply Chain Orchestrator — Pydantic Models Package

Re-exports all domain models for convenient access:
    from models import Product, Warehouse, Vehicle, ...
"""

from models.warehouse import Warehouse, WarehouseCreate, WarehouseUpdate
from models.inventory import (
    Product, ProductCreate,
    InventoryItem, InventoryUpdate,
    InventoryTransaction, InventoryTransactionCreate,
)
from models.fleet import Vehicle, VehicleCreate, VehicleUpdate
from models.demand import DemandForecast, DemandForecastCreate
from models.route import Route, RouteCreate, RouteStop, RouteStopCreate
from models.notification import Notification, NotificationCreate

__all__ = [
    # Warehouse
    "Warehouse", "WarehouseCreate", "WarehouseUpdate",
    # Inventory
    "Product", "ProductCreate",
    "InventoryItem", "InventoryUpdate",
    "InventoryTransaction", "InventoryTransactionCreate",
    # Fleet
    "Vehicle", "VehicleCreate", "VehicleUpdate",
    # Demand
    "DemandForecast", "DemandForecastCreate",
    # Route
    "Route", "RouteCreate", "RouteStop", "RouteStopCreate",
    # Notification
    "Notification", "NotificationCreate",
]
