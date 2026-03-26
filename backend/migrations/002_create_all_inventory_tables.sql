-- Migration: Create all inventory tables and add missing columns
-- Date: 2026-03-26
-- Description: Full inventory schema setup for PostgreSQL
-- Run this on production database

-- ============================================================================
-- 1. INVENTORY CATEGORIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_categories (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(7) DEFAULT '#C9A598',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE INDEX IF NOT EXISTS ix_inv_category_tenant ON inventory_categories(tenant_id);

-- ============================================================================
-- 2. INVENTORY LOCATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_locations (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    building VARCHAR(100),
    room VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE INDEX IF NOT EXISTS ix_inv_location_tenant ON inventory_locations(tenant_id);

-- ============================================================================
-- 3. INVENTORY VENDORS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_vendors (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255),
    contact_email VARCHAR(320),
    contact_phone VARCHAR(20),
    website VARCHAR(500),
    address TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE INDEX IF NOT EXISTS ix_inv_vendor_tenant ON inventory_vendors(tenant_id);

-- ============================================================================
-- 4. INVENTORY ITEMS TABLE (create if not exists)
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_items (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),

    -- Basic info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sku VARCHAR(100),
    barcode VARCHAR(100),

    -- Quantity tracking
    quantity INTEGER DEFAULT 0 NOT NULL,
    min_quantity INTEGER DEFAULT 0,
    unit VARCHAR(50) DEFAULT 'units',

    -- Pricing
    unit_price FLOAT,
    currency VARCHAR(3) DEFAULT 'USD',

    -- Foreign keys
    category_id VARCHAR(36) REFERENCES inventory_categories(id),
    location_id VARCHAR(36) REFERENCES inventory_locations(id),
    vendor_id VARCHAR(36) REFERENCES inventory_vendors(id),

    -- Purchase info
    purchase_date TIMESTAMP WITH TIME ZONE,
    purchase_price FLOAT,
    purchase_order_number VARCHAR(100),

    -- Warranty
    warranty_expiry TIMESTAMP WITH TIME ZONE,
    warranty_notes TEXT,

    -- Additional metadata
    serial_number VARCHAR(255),
    model_number VARCHAR(255),
    manufacturer VARCHAR(255),
    notes TEXT,
    image_url VARCHAR(500),

    -- Status
    is_active BOOLEAN DEFAULT TRUE NOT NULL,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(36) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_inventory_item_tenant ON inventory_items(tenant_id);
CREATE INDEX IF NOT EXISTS ix_inventory_item_barcode ON inventory_items(barcode);

-- ============================================================================
-- 5. ADD MISSING COLUMNS TO INVENTORY_ITEMS (if table already exists)
-- ============================================================================

-- Chemical Safety columns
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS hazard_class VARCHAR(100);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS sds_url VARCHAR(500);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS storage_temp VARCHAR(50);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS storage_conditions TEXT;

-- Calibration tracking columns
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS requires_calibration BOOLEAN DEFAULT FALSE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS calibration_interval_days INTEGER;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS last_calibration TIMESTAMP WITH TIME ZONE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS next_calibration TIMESTAMP WITH TIME ZONE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS calibration_notes TEXT;

-- Maintenance tracking columns
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS requires_maintenance BOOLEAN DEFAULT FALSE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS maintenance_interval_days INTEGER;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS last_maintenance TIMESTAMP WITH TIME ZONE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS next_maintenance TIMESTAMP WITH TIME ZONE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS maintenance_notes TEXT;

-- Usage tracking columns
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS last_used TIMESTAMP WITH TIME ZONE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS use_count INTEGER DEFAULT 0;

-- Checkout tracking columns
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS is_checked_out BOOLEAN DEFAULT FALSE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS checked_out_by VARCHAR(36);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS checked_out_at TIMESTAMP WITH TIME ZONE;

-- Additional indexes for inventory_items
CREATE INDEX IF NOT EXISTS ix_inventory_item_tenant_category ON inventory_items(tenant_id, category_id);
CREATE INDEX IF NOT EXISTS ix_inventory_item_tenant_location ON inventory_items(tenant_id, location_id);
CREATE INDEX IF NOT EXISTS ix_inventory_item_tenant_vendor ON inventory_items(tenant_id, vendor_id);
CREATE INDEX IF NOT EXISTS ix_inventory_item_low_stock ON inventory_items(tenant_id, quantity, min_quantity);
CREATE INDEX IF NOT EXISTS ix_inventory_item_warranty ON inventory_items(tenant_id, warranty_expiry);

-- ============================================================================
-- 6. INVENTORY TRANSACTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    item_id VARCHAR(36) NOT NULL REFERENCES inventory_items(id),
    user_id VARCHAR(36) REFERENCES users(id),

    transaction_type VARCHAR(50) NOT NULL,
    field_changed VARCHAR(100),
    old_value TEXT,
    new_value TEXT,

    quantity_change INTEGER,
    quantity_before INTEGER,
    quantity_after INTEGER,

    notes TEXT,
    reference VARCHAR(255),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_inv_transaction_item_date ON inventory_transactions(item_id, created_at);
CREATE INDEX IF NOT EXISTS ix_inv_transaction_tenant_date ON inventory_transactions(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_inv_transaction_type ON inventory_transactions(tenant_id, transaction_type);

-- ============================================================================
-- 7. INVENTORY BATCHES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_batches (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    item_id VARCHAR(36) NOT NULL REFERENCES inventory_items(id),

    lot_number VARCHAR(100) NOT NULL,
    batch_number VARCHAR(100),

    quantity INTEGER DEFAULT 0 NOT NULL,
    initial_quantity INTEGER,

    manufacture_date TIMESTAMP WITH TIME ZONE,
    expiry_date TIMESTAMP WITH TIME ZONE,
    received_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    coa_url VARCHAR(500),
    coa_notes TEXT,

    is_active BOOLEAN DEFAULT TRUE,
    is_expired BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(item_id, lot_number)
);

CREATE INDEX IF NOT EXISTS ix_inv_batch_item_lot ON inventory_batches(item_id, lot_number);
CREATE INDEX IF NOT EXISTS ix_inv_batch_expiry ON inventory_batches(tenant_id, expiry_date);

-- ============================================================================
-- 8. INVENTORY CHECKOUTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_checkouts (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    item_id VARCHAR(36) NOT NULL REFERENCES inventory_items(id),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),

    quantity INTEGER DEFAULT 1,
    purpose TEXT,
    project_reference VARCHAR(255),

    checked_out_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    expected_return TIMESTAMP WITH TIME ZONE,
    checked_in_at TIMESTAMP WITH TIME ZONE,

    status VARCHAR(20) DEFAULT 'ACTIVE',

    condition_out VARCHAR(50),
    condition_in VARCHAR(50),
    condition_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_inv_checkout_item_status ON inventory_checkouts(item_id, status);
CREATE INDEX IF NOT EXISTS ix_inv_checkout_user ON inventory_checkouts(user_id, status);
CREATE INDEX IF NOT EXISTS ix_inv_checkout_tenant_date ON inventory_checkouts(tenant_id, checked_out_at);

-- ============================================================================
-- 9. INVENTORY ALERTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_alerts (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    item_id VARCHAR(36) REFERENCES inventory_items(id),

    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'WARNING',

    message TEXT NOT NULL,
    threshold_value VARCHAR(100),
    current_value VARCHAR(100),

    is_active BOOLEAN DEFAULT TRUE,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(36) REFERENCES users(id),
    acknowledged_at TIMESTAMP WITH TIME ZONE,

    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP WITH TIME ZONE,
    email_recipients TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_inv_alert_tenant_active ON inventory_alerts(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS ix_inv_alert_type ON inventory_alerts(tenant_id, alert_type, is_active);

-- ============================================================================
-- 10. VERIFY SETUP
-- ============================================================================
SELECT 'Tables created/verified:' as status;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE 'inventory%'
ORDER BY table_name;

SELECT 'Columns in inventory_items:' as status;
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'inventory_items'
ORDER BY ordinal_position;
