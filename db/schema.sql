-- ============================================================
-- Supply Chain Orchestrator — PostgreSQL Schema
-- ============================================================
-- Run: psql -f db/schema.sql -d supply_chain
-- ============================================================

-- ── Cleanup (idempotent) ────────────────────────────────────

DROP SCHEMA IF EXISTS sco CASCADE;
CREATE SCHEMA sco;
SET search_path TO sco, public;

-- ── Enum Types ──────────────────────────────────────────────

CREATE TYPE order_status AS ENUM (
    'pending', 'confirmed', 'picking', 'packed',
    'shipped', 'in_transit', 'delivered', 'cancelled'
);

CREATE TYPE vehicle_status AS ENUM (
    'available', 'in_transit', 'maintenance', 'out_of_service'
);

CREATE TYPE vehicle_type AS ENUM (
    'truck', 'van', 'motorcycle', 'drone'
);

CREATE TYPE transaction_type AS ENUM (
    'receipt', 'pick', 'adjustment', 'transfer_in', 'transfer_out', 'return'
);

CREATE TYPE notification_channel AS ENUM (
    'email', 'sms', 'push', 'webhook'
);

CREATE TYPE notification_status AS ENUM (
    'queued', 'sent', 'delivered', 'failed'
);

CREATE TYPE route_status AS ENUM (
    'planned', 'in_progress', 'completed', 'cancelled'
);

CREATE TYPE shipment_status AS ENUM (
    'created', 'picked_up', 'in_transit', 'out_for_delivery',
    'delivered', 'failed_attempt', 'returned'
);

CREATE TYPE agent_name AS ENUM (
    'inventory_planning', 'warehouse_operations', 'demand_forecasting',
    'route_optimization', 'fleet_management', 'customer_notification',
    'supervisor'
);

-- ── 1. Warehouses ───────────────────────────────────────────

CREATE TABLE warehouses (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200)    NOT NULL,
    code            VARCHAR(20)     NOT NULL UNIQUE,
    address         TEXT,
    city            VARCHAR(100),
    state           VARCHAR(100),
    country         VARCHAR(100)    DEFAULT 'India',
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    total_capacity  INTEGER         NOT NULL DEFAULT 0,   -- cubic metres
    used_capacity   INTEGER         NOT NULL DEFAULT 0,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_warehouses_code ON warehouses (code);
CREATE INDEX idx_warehouses_active ON warehouses (is_active);

-- ── 2. Products ─────────────────────────────────────────────

CREATE TABLE products (
    id              BIGSERIAL PRIMARY KEY,
    sku             VARCHAR(50)     NOT NULL UNIQUE,
    name            VARCHAR(300)    NOT NULL,
    category        VARCHAR(100),
    unit_weight_kg  NUMERIC(10, 3)  DEFAULT 0,
    unit_volume_m3  NUMERIC(10, 6)  DEFAULT 0,
    unit_price      NUMERIC(12, 2)  DEFAULT 0,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_products_sku ON products (sku);
CREATE INDEX idx_products_category ON products (category);

-- ── 3. Inventory (per-warehouse stock) ──────────────────────

CREATE TABLE inventory (
    id              BIGSERIAL PRIMARY KEY,
    warehouse_id    BIGINT          NOT NULL REFERENCES warehouses(id),
    product_id      BIGINT          NOT NULL REFERENCES products(id),
    quantity_on_hand INTEGER        NOT NULL DEFAULT 0,
    quantity_reserved INTEGER       NOT NULL DEFAULT 0,
    reorder_point   INTEGER         NOT NULL DEFAULT 10,
    reorder_qty     INTEGER         NOT NULL DEFAULT 50,
    last_counted_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (warehouse_id, product_id)
);

CREATE INDEX idx_inventory_warehouse ON inventory (warehouse_id);
CREATE INDEX idx_inventory_product ON inventory (product_id);
CREATE INDEX idx_inventory_low_stock ON inventory (quantity_on_hand)
    WHERE quantity_on_hand <= 10;      -- partial index for low-stock alerts

-- ── 4. Inventory Transactions (audit log) ───────────────────

CREATE TABLE inventory_transactions (
    id              BIGSERIAL PRIMARY KEY,
    inventory_id    BIGINT          NOT NULL REFERENCES inventory(id),
    txn_type        transaction_type NOT NULL,
    quantity        INTEGER         NOT NULL,   -- positive = in, negative = out
    reference_id    VARCHAR(100),               -- e.g. order ID, PO number
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inv_txn_inventory ON inventory_transactions (inventory_id);
CREATE INDEX idx_inv_txn_type ON inventory_transactions (txn_type);
CREATE INDEX idx_inv_txn_created ON inventory_transactions (created_at);

-- ── 5. Demand Forecasts ─────────────────────────────────────

CREATE TABLE demand_forecasts (
    id              BIGSERIAL PRIMARY KEY,
    product_id      BIGINT          NOT NULL REFERENCES products(id),
    warehouse_id    BIGINT          REFERENCES warehouses(id),  -- NULL = global
    forecast_date   DATE            NOT NULL,
    period_days     INTEGER         NOT NULL DEFAULT 7,         -- forecast window
    predicted_qty   INTEGER         NOT NULL,
    confidence      NUMERIC(5, 4)   DEFAULT 0.0,               -- 0.0000–1.0000
    model_version   VARCHAR(50),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_forecast_product ON demand_forecasts (product_id);
CREATE INDEX idx_forecast_date ON demand_forecasts (forecast_date);

-- ── 6. Orders ───────────────────────────────────────────────

CREATE TABLE orders (
    id              BIGSERIAL PRIMARY KEY,
    order_number    VARCHAR(50)     NOT NULL UNIQUE,
    customer_name   VARCHAR(200)    NOT NULL,
    customer_email  VARCHAR(200),
    customer_phone  VARCHAR(30),
    delivery_address TEXT           NOT NULL,
    delivery_city   VARCHAR(100),
    delivery_lat    DOUBLE PRECISION,
    delivery_lon    DOUBLE PRECISION,
    status          order_status    NOT NULL DEFAULT 'pending',
    priority        INTEGER         NOT NULL DEFAULT 0,  -- higher = more urgent
    total_amount    NUMERIC(14, 2)  DEFAULT 0,
    placed_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    promised_at     TIMESTAMPTZ,                         -- SLA deadline
    delivered_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_status ON orders (status);
CREATE INDEX idx_orders_placed ON orders (placed_at);
CREATE INDEX idx_orders_number ON orders (order_number);

-- ── 7. Order Items ──────────────────────────────────────────

CREATE TABLE order_items (
    id              BIGSERIAL PRIMARY KEY,
    order_id        BIGINT          NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id      BIGINT          NOT NULL REFERENCES products(id),
    quantity        INTEGER         NOT NULL DEFAULT 1,
    unit_price      NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    fulfilled_from  BIGINT          REFERENCES warehouses(id),  -- assigned warehouse
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_order_items_order ON order_items (order_id);
CREATE INDEX idx_order_items_product ON order_items (product_id);

-- ── 8. Vehicles (Fleet) ─────────────────────────────────────

CREATE TABLE vehicles (
    id              BIGSERIAL PRIMARY KEY,
    registration    VARCHAR(30)     NOT NULL UNIQUE,
    type            vehicle_type    NOT NULL DEFAULT 'truck',
    status          vehicle_status  NOT NULL DEFAULT 'available',
    capacity_kg     NUMERIC(10, 2)  NOT NULL DEFAULT 0,
    capacity_m3     NUMERIC(10, 2)  NOT NULL DEFAULT 0,
    current_lat     DOUBLE PRECISION,
    current_lon     DOUBLE PRECISION,
    home_warehouse  BIGINT          REFERENCES warehouses(id),
    fuel_level_pct  NUMERIC(5, 2)   DEFAULT 100.00,
    mileage_km      NUMERIC(12, 2)  DEFAULT 0,
    last_maintenance TIMESTAMPTZ,
    next_maintenance TIMESTAMPTZ,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vehicles_status ON vehicles (status);
CREATE INDEX idx_vehicles_warehouse ON vehicles (home_warehouse);

-- ── 9. Routes ───────────────────────────────────────────────

CREATE TABLE routes (
    id              BIGSERIAL PRIMARY KEY,
    route_code      VARCHAR(50)     NOT NULL UNIQUE,
    vehicle_id      BIGINT          REFERENCES vehicles(id),
    status          route_status    NOT NULL DEFAULT 'planned',
    origin_warehouse BIGINT         REFERENCES warehouses(id),
    total_distance_km NUMERIC(10, 2) DEFAULT 0,
    total_duration_min INTEGER       DEFAULT 0,
    planned_start   TIMESTAMPTZ,
    planned_end     TIMESTAMPTZ,
    actual_start    TIMESTAMPTZ,
    actual_end      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_routes_vehicle ON routes (vehicle_id);
CREATE INDEX idx_routes_status ON routes (status);

-- ── 10. Route Stops ─────────────────────────────────────────

CREATE TABLE route_stops (
    id              BIGSERIAL PRIMARY KEY,
    route_id        BIGINT          NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    stop_order      INTEGER         NOT NULL,
    stop_type       VARCHAR(20)     NOT NULL DEFAULT 'delivery', -- delivery | pickup | warehouse
    address         TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    warehouse_id    BIGINT          REFERENCES warehouses(id),
    order_id        BIGINT          REFERENCES orders(id),
    eta             TIMESTAMPTZ,
    arrived_at      TIMESTAMPTZ,
    departed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_route_stops_route ON route_stops (route_id);
CREATE INDEX idx_route_stops_order ON route_stops (stop_order);

-- ── 11. Shipments ───────────────────────────────────────────

CREATE TABLE shipments (
    id              BIGSERIAL PRIMARY KEY,
    tracking_number VARCHAR(80)     NOT NULL UNIQUE,
    order_id        BIGINT          NOT NULL REFERENCES orders(id),
    route_id        BIGINT          REFERENCES routes(id),
    vehicle_id      BIGINT          REFERENCES vehicles(id),
    status          shipment_status NOT NULL DEFAULT 'created',
    weight_kg       NUMERIC(10, 2)  DEFAULT 0,
    volume_m3       NUMERIC(10, 4)  DEFAULT 0,
    picked_up_at    TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shipments_order ON shipments (order_id);
CREATE INDEX idx_shipments_route ON shipments (route_id);
CREATE INDEX idx_shipments_status ON shipments (status);

-- ── 12. Notifications ───────────────────────────────────────

CREATE TABLE notifications (
    id              BIGSERIAL PRIMARY KEY,
    order_id        BIGINT          REFERENCES orders(id),
    channel         notification_channel NOT NULL DEFAULT 'email',
    recipient       VARCHAR(200)    NOT NULL,
    subject         VARCHAR(500),
    body            TEXT            NOT NULL,
    status          notification_status NOT NULL DEFAULT 'queued',
    sent_at         TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_order ON notifications (order_id);
CREATE INDEX idx_notifications_status ON notifications (status);

-- ── 13. Agent Task Log ──────────────────────────────────────

CREATE TABLE agent_task_log (
    id              BIGSERIAL PRIMARY KEY,
    agent           agent_name      NOT NULL,
    task_type       VARCHAR(100)    NOT NULL,
    input_payload   JSONB           NOT NULL DEFAULT '{}',
    output_payload  JSONB           DEFAULT '{}',
    status          VARCHAR(20)     NOT NULL DEFAULT 'started',  -- started | completed | failed
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_agent_log_agent ON agent_task_log (agent);
CREATE INDEX idx_agent_log_status ON agent_task_log (status);
CREATE INDEX idx_agent_log_created ON agent_task_log (created_at);
