-- Migration: Add ZOTERO connector type to PostgreSQL enum
-- Run this on your Render PostgreSQL database
--
-- IMPORTANT: SQLAlchemy Enum(PythonEnum) uses enum NAMES (uppercase),
-- not enum VALUES (lowercase). So we add 'ZOTERO' not 'zotero'.

-- Add new enum value to connectortype
ALTER TYPE connectortype ADD VALUE IF NOT EXISTS 'ZOTERO';

-- Verify the enum values
-- SELECT unnest(enum_range(NULL::connectortype));
