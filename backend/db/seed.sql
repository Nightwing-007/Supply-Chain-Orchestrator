-- ============================================================
-- Supply Chain Orchestrator — Crisis Scenario Seed Data
-- ============================================================
-- Designed for Live Hackathon Demonstrations:
-- Intentionally triggers threshold & anomaly logic across all 6 agents:
--   1. Inventory Agent : 4 high-value products in critical stock deficit
--   2. Warehouse Agent : WH-MUM-01 utilization at 89.0% (> 85% threshold)
--   3. Demand Agent    : 79x sudden demand spike on Bluetooth Headphones (7d vs 30d)
--   4. Route Agent     : 5 multi-stop delivery locations in Mumbai/Pune cluster
--   5. Fleet Agent     : Vehicle 2 (>14k km), Vehicle 3 (>115 days), Vehicle 4 (<10% fuel)
--   6. Notif Agent     : Queued customer notifications for delays & dispatch
-- ============================================================

SET search_path TO sco, public;

-- Clean existing seed data
TRUNCATE TABLE notifications, shipments, route_stops, routes, vehicles, order_items, orders, inventory_transactions, inventory, products, warehouses RESTART IDENTITY CASCADE;

-- ── 1. Warehouses (3) ────────────────────────────────────────

INSERT INTO warehouses (id, name, code, address, city, state, country, latitude, longitude, total_capacity, used_capacity, is_active) VALUES
    (1, 'Mumbai Central Hub',    'WH-MUM-01', '123 Dock Road, Nhava Sheva',     'Mumbai',    'Maharashtra', 'India', 19.0760, 72.8777, 50000, 44500, TRUE), -- 89.0% Utilisation (>85% ALERT!)
    (2, 'Delhi NCR Fulfillment', 'WH-DEL-01', '45 Logistics Park, Manesar',     'Gurugram',  'Haryana',     'India', 28.7041, 77.1025, 35000, 14200, TRUE),
    (3, 'Bangalore Tech Park',   'WH-BLR-01', '789 Electronic City Phase II',   'Bangalore', 'Karnataka',   'India', 12.9716, 77.5946, 28000, 11000, TRUE);

SELECT setval('warehouses_id_seq', 3, true);


-- ── 2. Products (10) ─────────────────────────────────────────

INSERT INTO products (id, sku, name, category, unit_weight_kg, unit_volume_m3, unit_price, is_active) VALUES
    (1,  'SKU-ELEC-001', 'Wireless Bluetooth Headphones',   'Electronics',   0.250, 0.001200,  2499.00, TRUE),
    (2,  'SKU-ELEC-002', '27" 4K Gaming Monitor',            'Electronics',  12.500, 0.085000, 32999.00, TRUE),
    (3,  'SKU-ELEC-003', 'USB-C Thunderbolt Docking Hub',   'Electronics',   0.850, 0.003500,  5999.00, TRUE),
    (4,  'SKU-HOME-001', 'Ergonomic Mesh Office Chair',      'Furniture',    18.000, 0.420000, 15999.00, TRUE),
    (5,  'SKU-HOME-002', 'Motorized Standing Desk Converter','Furniture',    14.500, 0.350000, 12499.00, TRUE),
    (6,  'SKU-GROC-001', 'Organic Green Tea (100 bags)',      'Grocery',       0.300, 0.002500,   599.00, TRUE),
    (7,  'SKU-GROC-002', 'Cold-Pressed Olive Oil 1L',        'Grocery',       1.100, 0.001100,   899.00, TRUE),
    (8,  'SKU-APRL-001', 'Men''s Pro Running Shoes (Size 10)','Apparel',      0.750, 0.008000,  4999.00, TRUE),
    (9,  'SKU-APRL-002', 'Women''s Flex Yoga Pants (M)',     'Apparel',       0.200, 0.002000,  1999.00, TRUE),
    (10, 'SKU-BOOK-001', 'Designing Data-Intensive Apps',    'Books',         0.900, 0.002800,   749.00, TRUE);

SELECT setval('products_id_seq', 10, true);


-- ── 3. Inventory (Stock Deficits to Trigger Agent 1) ──────────

INSERT INTO inventory (id, warehouse_id, product_id, quantity_on_hand, quantity_reserved, reorder_point, reorder_qty) VALUES
    -- Mumbai Hub (Crisis Deficits)
    (1,  1, 1,   5, 12, 100, 500),  -- Headphones: Stock 5 <= 100 (DEFICIT: 95)
    (2,  1, 2,   2,  3,  50, 100),  -- 4K Monitor: Stock 2 <= 50  (DEFICIT: 48 - High Value!)
    (3,  1, 3, 220,  5,  25, 100),  -- Normal
    (4,  1, 4,   0,  2,  30,  50),  -- Office Chair: Stock 0 <= 30 (CRITICAL OUT OF STOCK!)
    (5,  1, 5,   3,  4,  40,  60),  -- Standing Desk: Stock 3 <= 40 (DEFICIT: 37)
    (6,  1, 6, 1200,30, 100, 500),  -- Normal
    -- Delhi Fulfillment
    (7,  2, 1, 350,  8,  40, 150),
    (8,  2, 2,  60,  1,  10,  25),
    (9,  2, 5,  90,  4,  10,  40),
    (10, 2, 7, 800, 20,  80, 400),
    -- Bangalore Tech Park
    (11, 3, 1, 200,  5,  30, 100),
    (12, 3, 3, 180,  7,  20,  80),
    (13, 3, 4,  30,  0,   5,  15);

SELECT setval('inventory_id_seq', 13, true);


-- ── 4. Vehicles (Telemetry Anomalies to Trigger Agent 5) ─────

INSERT INTO vehicles (id, registration, type, status, capacity_kg, capacity_m3, current_lat, current_lon, home_warehouse, fuel_level_pct, mileage_km, last_maintenance, next_maintenance, is_active) VALUES
    -- Vehicle 1: Healthy Available
    (1, 'MH-04-AB-1234', 'truck',      'available',  8000.00, 40.00, 19.0760, 72.8777, 1, 85.00,  4500.00, NOW() - INTERVAL '30 days',  NOW() + INTERVAL '60 days', TRUE),
    -- Vehicle 2: Over Mileage (>10,000 km threshold!)
    (2, 'MH-04-CD-5678', 'van',        'in_transit', 2500.00, 12.00, 19.0760, 72.8777, 1, 60.00, 14250.00, NOW() - INTERVAL '40 days',  NOW() - INTERVAL '5 days',  TRUE),
    -- Vehicle 3: Over Days (>90 days since service threshold!)
    (3, 'DL-01-EF-9012', 'truck',      'available',  8000.00, 40.00, 28.7041, 77.1025, 2, 75.00,  3000.00, NOW() - INTERVAL '115 days', NOW() - INTERVAL '25 days', TRUE),
    -- Vehicle 4: Low Fuel Alert (<15% threshold!)
    (4, 'KA-01-GH-3456', 'van',        'available',  2500.00, 12.00, 12.9716, 77.5946, 3,  9.50,  2000.00, NOW() - INTERVAL '15 days',  NOW() + INTERVAL '75 days', TRUE),
    -- Vehicle 5: Healthy Delivery Bike
    (5, 'KA-01-IJ-7890', 'motorcycle', 'available',    50.00,  0.15, 12.9716, 77.5946, 3, 95.00,   890.00, NOW() - INTERVAL '10 days',  NOW() + INTERVAL '80 days', TRUE);

SELECT setval('vehicles_id_seq', 5, true);


-- ── 5. Orders (Multi-Location Cluster to Trigger Agent 4 & 6) ─

INSERT INTO orders (id, order_number, customer_name, customer_email, customer_phone, delivery_address, delivery_city, delivery_lat, delivery_lon, status, priority, total_amount, promised_at) VALUES
    -- Order 1: High Priority (Indiranagar Bangalore)
    (1, 'ORD-2026-00001', 'Arjun Mehta',   'arjun@example.com',  '+91-98765-43210', '12 MG Road, Indiranagar',        'Bangalore', 12.9784, 77.6408, 'confirmed', 2, 38498.00, NOW() + INTERVAL '1 day'),
    -- Order 2: Priority (Marine Drive Mumbai)
    (2, 'ORD-2026-00002', 'Rohan Kapoor',  'rohan@example.com',  '+91-87654-32109', '5 Marine Drive, Churchgate',      'Mumbai',    18.9440, 72.8237, 'picking',   2,  5999.00, NOW() + INTERVAL '1 day'),
    -- Order 3: Normal (Dadar West Mumbai)
    (3, 'ORD-2026-00003', 'Priya Sharma',  'priya@example.com',  '+91-91234-56789', '45 Dadar West Station Road',     'Mumbai',    19.0178, 72.8478, 'pending',   1, 15999.00, NOW() + INTERVAL '2 days'),
    -- Order 4: Normal (Bandra Kurla Complex)
    (4, 'ORD-2026-00004', 'Vikram Patel',  'vikram@example.com', '+91-99887-76655', 'G Block, BKC Complex',           'Mumbai',    19.0657, 72.8687, 'pending',   1,  2499.00, NOW() + INTERVAL '2 days'),
    -- Order 5: Inter-city Delivery (Pune Central)
    (5, 'ORD-2026-00005', 'Ananya Roy',    'ananya@example.com', '+91-95544-33221', 'FC Road, Deccan Gymkhana',       'Pune',      18.5204, 73.8567, 'pending',   0, 12499.00, NOW() + INTERVAL '3 days');

SELECT setval('orders_id_seq', 5, true);


-- ── 6. Order Items (Demand Volatility Spike for Agent 3) ──────

-- Historical orders in recent 7 days (Massive spike for Product 1)
INSERT INTO order_items (order_id, product_id, quantity, unit_price, fulfilled_from) VALUES
    (1, 2, 1, 32999.00, 3),
    (1, 1, 2,  2499.00, 3),
    (2, 3, 1,  5999.00, 1),
    (3, 4, 1, 15999.00, 1),
    (4, 1, 1,  2499.00, 1),
    (5, 5, 1, 12499.00, 1);

-- Insert artificial historical high-volume orders over last 7 days (Product 1 Demand Spike!)
INSERT INTO orders (id, order_number, customer_name, customer_email, delivery_address, delivery_city, status, total_amount, created_at, updated_at) VALUES
    (101, 'ORD-HIST-001', 'Bulk Buyer 1', 'bulk1@example.com', 'Warehouse District', 'Mumbai', 'delivered', 124950.00, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'),
    (102, 'ORD-HIST-002', 'Bulk Buyer 2', 'bulk2@example.com', 'Tech Park North',   'Mumbai', 'delivered', 149940.00, NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'),
    (103, 'ORD-HIST-003', 'Bulk Buyer 3', 'bulk3@example.com', 'Corporate Center', 'Mumbai', 'delivered',  99960.00, NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days');

INSERT INTO order_items (order_id, product_id, quantity, unit_price, fulfilled_from) VALUES
    (101, 1, 50, 2499.00, 1),  -- 50 units
    (102, 1, 60, 2499.00, 1),  -- 60 units
    (103, 1, 40, 2499.00, 1);  -- 40 units

-- Baseline older orders (days 15-30: low volume 2 units/day)
INSERT INTO orders (id, order_number, customer_name, customer_email, delivery_address, delivery_city, status, total_amount, created_at, updated_at) VALUES
    (104, 'ORD-HIST-004', 'Old Buyer 1', 'old1@example.com', 'Old Town', 'Mumbai', 'delivered', 4998.00, NOW() - INTERVAL '20 days', NOW() - INTERVAL '20 days'),
    (105, 'ORD-HIST-005', 'Old Buyer 2', 'old2@example.com', 'Old Town', 'Mumbai', 'delivered', 4998.00, NOW() - INTERVAL '25 days', NOW() - INTERVAL '25 days');

INSERT INTO order_items (order_id, product_id, quantity, unit_price, fulfilled_from) VALUES
    (104, 1, 2, 2499.00, 1),
    (105, 1, 2, 2499.00, 1);

SELECT setval('orders_id_seq', 105, true);


-- ── 7. Queued Notifications (Trigger Agent 6) ───────────────

INSERT INTO notifications (id, order_id, channel, recipient, subject, body, status, created_at) VALUES
    (1, 1, 'email', 'arjun@example.com', 'Order Confirmation #ORD-2026-00001', 'Your order is confirmed and being prepared at Bangalore Tech Park.', 'queued', NOW()),
    (2, 2, 'sms',   '+91-87654-32109',   NULL,                                   'Order #ORD-2026-00002 status is out for picking at Mumbai Hub.',     'queued', NOW()),
    (3, 5, 'email', 'ananya@example.com', 'Weather Alert: Potential Route Delay', 'Heavy monsoon downpour on Pune Expressway may add 45m to delivery.',   'queued', NOW());

SELECT setval('notifications_id_seq', 3, true);
