-- Migration: Add lab-specific columns to inventory_items table
-- Date: 2026-03-26
-- Description: Adds hazard_class, calibration, maintenance, and checkout tracking columns

-- Check if columns exist before adding (PostgreSQL)
-- Run this on production database

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

-- Add foreign key constraint for checked_out_by (if users table exists)
-- Note: This may fail if the constraint already exists, which is fine
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_inventory_checked_out_by_user'
    ) THEN
        ALTER TABLE inventory_items
        ADD CONSTRAINT fk_inventory_checked_out_by_user
        FOREIGN KEY (checked_out_by) REFERENCES users(id);
    END IF;
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'Foreign key constraint may already exist or users table not found';
END $$;

-- Verify columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'inventory_items'
AND column_name IN (
    'hazard_class', 'sds_url', 'storage_temp', 'storage_conditions',
    'requires_calibration', 'calibration_interval_days', 'last_calibration',
    'next_calibration', 'calibration_notes',
    'requires_maintenance', 'maintenance_interval_days', 'last_maintenance',
    'next_maintenance', 'maintenance_notes',
    'last_used', 'use_count',
    'is_checked_out', 'checked_out_by', 'checked_out_at'
)
ORDER BY column_name;
