-- ============================================================================
-- Apex Logistics - B2B Freight Claim & Refund Decision Engine
-- Database Schema: schema.sql (SQLite)
-- ============================================================================

-- Enforce foreign key constraints in SQLite
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- Drop existing tables to allow idempotent execution
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS clients;

-- ----------------------------------------------------------------------------
-- Table: clients
-- Stores client profile metadata, relationship tier, and rolling refund metrics
-- ----------------------------------------------------------------------------
CREATE TABLE clients (
    client_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('ENTERPRISE_VIP', 'STANDARD')),
    refund_count_30d INTEGER NOT NULL DEFAULT 0 CHECK (refund_count_30d >= 0),
    account_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'SUSPENDED', 'UNDER_REVIEW')),
    contact_email TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- ----------------------------------------------------------------------------
-- Table: orders
-- Combines shipment records and claim evaluations with AI reasoning outputs
-- ----------------------------------------------------------------------------
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    tracking_number TEXT NOT NULL UNIQUE,
    client_id TEXT NOT NULL,
    declared_value REAL NOT NULL CHECK (declared_value >= 0),
    claim_amount REAL NOT NULL CHECK (claim_amount >= 0),
    delay_cause TEXT NOT NULL CHECK (
        delay_cause IN (
            'CARRIER_FAULT',
            'WEATHER_FORCE_MAJEURE',
            'CUSTOMS_HOLD'
        )
    ),
    claim_status TEXT NOT NULL DEFAULT 'FLAG_FOR_AUDIT' CHECK (
        claim_status IN (
            'AUTO_APPROVE',
            'FLAG_FOR_AUDIT',
            'REJECT'
        )
    ),
    ai_justification TEXT,
    claim_submitted_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    evaluated_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    CONSTRAINT fk_orders_client_id 
        FOREIGN KEY (client_id) 
        REFERENCES clients (client_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE
);

-- ----------------------------------------------------------------------------
-- Indexes for High-Performance Querying & Operational Dashboards
-- ----------------------------------------------------------------------------
CREATE INDEX idx_clients_tier ON clients(tier);
CREATE INDEX idx_orders_client_id ON orders(client_id);
CREATE INDEX idx_orders_claim_status ON orders(claim_status);
CREATE INDEX idx_orders_delay_cause ON orders(delay_cause);
CREATE INDEX idx_orders_submitted_at ON orders(claim_submitted_at DESC);
CREATE INDEX idx_orders_status_submitted ON orders(claim_status, claim_submitted_at DESC);

-- ----------------------------------------------------------------------------
-- Seed Data: clients (5 Realistic Sample Profiles)
-- ----------------------------------------------------------------------------
INSERT INTO clients (client_id, company_name, tier, refund_count_30d, account_status, contact_email, created_at, updated_at) VALUES
('CL-1001', 'Global Omni Retail Corp', 'ENTERPRISE_VIP', 1, 'ACTIVE', 'supply-chain@globalomni.com', '2026-01-15 08:30:00', '2026-10-01 10:00:00'),
('CL-1002', 'AeroTech Dynamics', 'ENTERPRISE_VIP', 0, 'ACTIVE', 'logistics@aerotech.io', '2026-02-10 09:15:00', '2026-10-02 11:20:00'),
('CL-1003', 'Apex Horizon Imports LLC', 'ENTERPRISE_VIP', 7, 'ACTIVE', 'claims@apexhorizon.com', '2026-03-01 14:00:00', '2026-10-05 16:45:00'),
('CL-1004', 'BlueWave Distributors', 'STANDARD', 2, 'ACTIVE', 'ops@bluewavedist.com', '2026-05-18 11:00:00', '2026-09-28 09:10:00'),
('CL-1005', 'Summit Industrial Tools', 'STANDARD', 8, 'UNDER_REVIEW', 'procurement@summitindustrial.net', '2026-06-22 13:40:00', '2026-10-08 12:00:00');

-- ----------------------------------------------------------------------------
-- Seed Data: orders (5 Sample Rows Representing All Test Scenarios)
-- ----------------------------------------------------------------------------
-- Case 1: AUTO_APPROVE (Enterprise VIP, Carrier Fault, Claim <= $2,500 threshold, Low historical frequency)
INSERT INTO orders (
    order_id,
    tracking_number,
    client_id,
    declared_value,
    claim_amount,
    delay_cause,
    claim_status,
    ai_justification,
    claim_submitted_at,
    evaluated_at,
    created_at,
    updated_at
) VALUES (
    'ORD-2026-8001',
    'APX-TRK-9810234',
    'CL-1001',
    12500.00,
    1450.00,
    'CARRIER_FAULT',
    'AUTO_APPROVE',
    'Claim amount ($1,450.00) is well below the instant approval threshold ($2,500.00). Client holds ENTERPRISE_VIP status with clean 30-day claim velocity (1 prior claim). Delay was verified as CARRIER_FAULT (hub sorting mechanical failure). SLA contract auto-approved.',
    '2026-10-09 10:15:00',
    '2026-10-09 10:15:04',
    '2026-10-09 10:15:00',
    '2026-10-09 10:15:04'
);

-- Case 2: AUTO_APPROVE (Standard Tier, Carrier Fault, Low Claim <= $2,500, Low historical refund count)
INSERT INTO orders (
    order_id,
    tracking_number,
    client_id,
    declared_value,
    claim_amount,
    delay_cause,
    claim_status,
    ai_justification,
    claim_submitted_at,
    evaluated_at,
    created_at,
    updated_at
) VALUES (
    'ORD-2026-8002',
    'APX-TRK-9810235',
    'CL-1004',
    4200.00,
    620.00,
    'CARRIER_FAULT',
    'AUTO_APPROVE',
    'Direct carrier delay verified (driver missed dispatch window). Claim amount of $620.00 is below the $2,500.00 instant threshold, and 30-day refund count is within acceptable standard bounds (2 claims). Approved automatically per standard SLA terms.',
    '2026-10-09 11:00:00',
    '2026-10-09 11:00:03',
    '2026-10-09 11:00:00',
    '2026-10-09 11:00:03'
);

-- Case 3: FLAG_FOR_AUDIT (Enterprise VIP, High Value > $2,500 threshold requiring manual sign-off despite carrier fault)
INSERT INTO orders (
    order_id,
    tracking_number,
    client_id,
    declared_value,
    claim_amount,
    delay_cause,
    claim_status,
    ai_justification,
    claim_submitted_at,
    evaluated_at,
    created_at,
    updated_at
) VALUES (
    'ORD-2026-8003',
    'APX-TRK-9810236',
    'CL-1002',
    48000.00,
    6800.00,
    'CARRIER_FAULT',
    'FLAG_FOR_AUDIT',
    'Claim amount ($6,800.00) exceeds the $2,500.00 instant approval threshold despite ENTERPRISE_VIP tier and CARRIER_FAULT status. Escalated to senior claims specialist for cargo damage inspection review and final authorization.',
    '2026-10-09 13:20:00',
    '2026-10-09 13:20:05',
    '2026-10-09 13:20:00',
    '2026-10-09 13:20:05'
);

-- Case 4: FLAG_FOR_AUDIT (High refund velocity / anomaly detection: VIP with 7 refunds in 30 days)
INSERT INTO orders (
    order_id,
    tracking_number,
    client_id,
    declared_value,
    claim_amount,
    delay_cause,
    claim_status,
    ai_justification,
    claim_submitted_at,
    evaluated_at,
    created_at,
    updated_at
) VALUES (
    'ORD-2026-8004',
    'APX-TRK-9810237',
    'CL-1003',
    9500.00,
    2100.00,
    'CUSTOMS_HOLD',
    'FLAG_FOR_AUDIT',
    'Underlying delay is CUSTOMS_HOLD (documentation mismatch at border) and client exhibits elevated 30-day refund frequency (7 refunds). Flagged for compliance review to confirm tariff liability before processing.',
    '2026-10-09 14:05:00',
    '2026-10-09 14:05:06',
    '2026-10-09 14:05:00',
    '2026-10-09 14:05:06'
);

-- Case 5: REJECT (Standard tier, Weather / Force Majeure event exempt under Apex Logistics Terms of Carriage)
INSERT INTO orders (
    order_id,
    tracking_number,
    client_id,
    declared_value,
    claim_amount,
    delay_cause,
    claim_status,
    ai_justification,
    claim_submitted_at,
    evaluated_at,
    created_at,
    updated_at
) VALUES (
    'ORD-2026-8005',
    'APX-TRK-9810238',
    'CL-1005',
    18000.00,
    3400.00,
    'WEATHER_FORCE_MAJEURE',
    'REJECT',
    'Delay attributed to severe winter storm grounding flights at Chicago O''Hare hub (WEATHER_FORCE_MAJEURE). Standard contract section 4.2 explicitly waives carrier liability for certified acts of nature without supplemental weather insurance.',
    '2026-10-09 15:45:00',
    '2026-10-09 15:45:03',
    '2026-10-09 15:45:00',
    '2026-10-09 15:45:03'
);
