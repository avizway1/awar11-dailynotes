-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Aviz Academy — Product Catalog DB Setup                    ║
-- ║  Run this on your RDS MySQL instance                        ║
-- ╚══════════════════════════════════════════════════════════════╝

CREATE DATABASE IF NOT EXISTS productdb;
USE productdb;

-- Drop if re-running
DROP TABLE IF EXISTS products;

-- Product Catalog Table
CREATE TABLE products (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150)    NOT NULL,
    category    VARCHAR(80)     NOT NULL,
    price       DECIMAL(10, 2)  NOT NULL,
    stock       INT             DEFAULT 0,
    description TEXT,
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category)
);

-- ─────────────────────────────────────────────
-- Seed Data — 20 sample products
-- ─────────────────────────────────────────────
INSERT INTO products (name, category, price, stock, description) VALUES
-- Electronics
('AWS DeepRacer Car',         'Electronics',  399.99, 50,  'Autonomous 1/18th scale race car for machine learning'),
('Raspberry Pi 5',            'Electronics',   80.00, 200, '4GB RAM, Broadcom BCM2712 quad-core ARM Cortex-A76'),
('USB-C Hub 10-in-1',         'Electronics',   45.99, 300, 'HDMI 4K, SD card, 3x USB-A, Ethernet, PD charging'),
('Mechanical Keyboard',       'Electronics',  129.00, 150, 'TKL layout, Cherry MX Red switches, RGB backlight'),
('4K Webcam',                 'Electronics',   89.00, 120, '4K UHD, built-in noise cancelling mic, plug-and-play'),

-- Cloud Books & Learning
('AWS Solutions Architect Guide', 'Books',     49.99, 500, 'Study guide for SAA-C03 certification exam'),
('Docker Deep Dive',           'Books',        35.00, 400, 'Containerization fundamentals and advanced patterns'),
('Kubernetes in Action',       'Books',        55.00, 350, 'Practical guide to deploying and managing containers'),
('The Phoenix Project',        'Books',        28.00, 600, 'A novel about DevOps and IT transformation'),
('Clean Code',                 'Books',        42.00, 450, 'A handbook of agile software craftsmanship'),

-- DevOps Tools
('Yubikey 5 NFC',              'Security',     50.00, 200, 'Hardware authentication key, FIDO2/U2F support'),
('Ledger Nano S',              'Security',     79.00, 100, 'Hardware crypto wallet, USB-C, secure element'),
('Logitech MX Master 3S',      'Peripherals', 100.00, 250, 'Wireless ergonomic mouse, 8K DPI, USB-C charging'),
('Dell 27" 4K Monitor',        'Peripherals', 329.00,  80, 'IPS panel, USB-C 90W, 60Hz, HDR400'),
('Elgato Stream Deck',         'Peripherals',  99.00, 180, '15 LCD keys, customizable macros, plugin ecosystem'),

-- Cloud Merch / Fun
('Aviz Academy Hoodie',        'Apparel',      39.99, 100, 'Dark navy, orange logo, "Learn by Doing" printed'),
('AWS Hero T-Shirt',           'Apparel',      24.99, 300, '100% cotton, AWS logo front, community edition'),
('Docker Captain Cap',         'Apparel',      19.99, 200, 'Embroidered Docker whale logo, adjustable snap'),
('Standing Desk Converter',    'Furniture',   149.00,  60, 'Height adjustable, 36" wide, dual monitor support'),
('Cable Management Kit',       'Furniture',    22.99, 400, 'Velcro straps, cable clips, labels, desk grommet');

-- Verify
SELECT COUNT(*) AS total_products FROM products;
SELECT category, COUNT(*) AS count FROM products GROUP BY category ORDER BY category;
