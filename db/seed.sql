-- ============================================================
-- Supply Chain Orchestrator — Seed Data
-- ============================================================
-- Run: psql -f db/seed.sql -d supply_chain
-- Prerequisite: schema.sql must be applied first.
-- ============================================================

SET search_path TO sco, public;

-- ── Warehouses (3) ──────────────────────────────────────────

INSERT INTO warehouses (name, code, address, city, state, country, latitude, longitude, total_capacity, used_capacity) VALUES
    ('Mumbai Central Hub',    'WH-MUM-01', '123 Dock Road, Nhava Sheva',     'Mumbai',    'Maharashtra', 'India', 19.0760, 72.8777, 50000, 18500),
    ('Delhi NCR Fulfillment', 'WH-DEL-01', '45 Logistics Park, Manesar',     'Gurugram',  'Haryana',     'India', 28.7041, 77.1025, 35000, 12000),
    ('Bangalore Tech Park',   'WH-BLR-01', '789 Electronic City Phase II',   'Bangalore', 'Karnataka',   'India', 12.9716, 77.5946, 28000,  9500);

-- ── Products (10) ───────────────────────────────────────────

INSERT INTO products (sku, name, category, unit_weight_kg, unit_volume_m3, unit_price) VALUES
    ('SKU-ELEC-001', 'Wireless Bluetooth Headphones',   'Electronics',   0.250, 0.001200, 2499.00),
    ('SKU-ELEC-002', '27" 4K Monitor',                  'Electronics',  12.500, 0.085000, 32999.00),
    ('SKU-ELEC-003', 'USB-C Docking Station',            'Electronics',   0.850, 0.003500,  5999.00),
    ('SKU-HOME-001', 'Ergonomic Office Chair',            'Furniture',    18.000, 0.420000, 15999.00),
    ('SKU-HOME-002', 'Standing Desk Converter',           'Furniture',    14.500, 0.350000, 12499.00),
    ('SKU-GROC-001', 'Organic Green Tea (100 bags)',      'Grocery',       0.300, 0.002500,   599.00),
    ('SKU-GROC-002', 'Cold-Pressed Olive Oil 1L',        'Grocery',       1.100, 0.001100,   899.00),
    ('SKU-APRL-001', 'Men''s Running Shoes (Size 10)',   'Apparel',       0.750, 0.008000,  4999.00),
    ('SKU-APRL-002', 'Women''s Yoga Pants (M)',          'Apparel',       0.200, 0.002000,  1999.00),
    ('SKU-BOOK-001', 'Data-Intensive Applications',       'Books',         0.900, 0.002800,   749.00);

-- ── Inventory (stock across warehouses) ─────────────────────

INSERT INTO inventory (warehouse_id, product_id, quantity_on_hand, quantity_reserved, reorder_point, reorder_qty) VALUES
    -- Mumbai warehouse
    (1, 1,  500, 12, 50, 200),
    (1, 2,   80,  3, 10,  30),
    (1, 3,  220,  5, 25, 100),
    (1, 4,   45,  2,  5,  20),
    (1, 6, 1200, 30, 100, 500),
    (1, 8,  300, 10, 30, 150),
    -- Delhi warehouse
    (2, 1,  350,  8, 40, 150),
    (2, 2,   60,  1, 10,  25),
    (2, 5,   90,  4, 10,  40),
    (2, 7,  800, 20, 80, 400),
    (2, 9,  450, 15, 50, 200),
    (2, 10, 600, 25, 60, 300),
    -- Bangalore warehouse
    (3, 1,  200,  5, 30, 100),
    (3, 3,  180,  7, 20,  80),
    (3, 4,   30,  0,  5,  15),
    (3, 6,  900, 40, 100, 400),
    (3, 8,  150,  3, 20,  80),
    (3, 10, 400, 10, 40, 200);

-- ── Vehicles (5) ────────────────────────────────────────────

INSERT INTO vehicles (registration, type, status, capacity_kg, capacity_m3, current_lat, current_lon, home_warehouse, fuel_level_pct, mileage_km) VALUES
    ('MH-04-AB-1234', 'truck', 'available',    8000.00, 40.00, 19.0760, 72.8777, 1, 85.00,  45230.50),
    ('MH-04-CD-5678', 'van',   'available',    2500.00, 12.00, 19.0760, 72.8777, 1, 92.00,  23100.00),
    ('DL-01-EF-9012', 'truck', 'in_transit',   8000.00, 40.00, 27.5000, 76.5000, 2, 55.00,  67840.75),
    ('KA-01-GH-3456', 'van',   'available',    2500.00, 12.00, 12.9716, 77.5946, 3, 78.00,  31200.25),
    ('KA-01-IJ-7890', 'motorcycle', 'available', 50.00,  0.15, 12.9716, 77.5946, 3, 95.00,   8900.00);

-- ── Sample Orders (3) ──────────────────────────────────────

INSERT INTO orders (order_number, customer_name, customer_email, customer_phone, delivery_address, delivery_city, delivery_lat, delivery_lon, status, priority, total_amount, promised_at) VALUES
    ('ORD-2026-00001', 'Arjun Mehta',   'arjun@example.com',  '+91-98765-43210', '12 MG Road, Indiranagar',        'Bangalore', 12.9784, 77.6408, 'confirmed', 1, 38498.00, NOW() + INTERVAL '2 days'),
    ('ORD-2026-00002', 'Priya Sharma',  'priya@example.com',  '+91-91234-56789', '88 Connaught Place',              'New Delhi', 28.6315, 77.2167, 'pending',   0,  1498.00, NOW() + INTERVAL '5 days'),
    ('ORD-2026-00003', 'Rohan Kapoor',  'rohan@example.com',  '+91-87654-32109', '5 Marine Drive, Churchgate',      'Mumbai',    18.9440, 72.8237, 'picking',   2,  5999.00, NOW() + INTERVAL '1 day');

INSERT INTO order_items (order_id, product_id, quantity, unit_price, fulfilled_from) VALUES
    (1, 2, 1, 32999.00, 3),   -- 4K Monitor from Bangalore
    (1, 1, 2,  2499.00, 3),   -- 2x Headphones from Bangalore
    (2, 6, 1,   599.00, 2),   -- Green Tea from Delhi
    (2, 7, 1,   899.00, 2),   -- Olive Oil from Delhi
    (3, 3, 1,  5999.00, 1);   -- Docking Station from Mumbai
