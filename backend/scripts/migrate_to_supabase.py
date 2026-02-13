#!/usr/bin/env python3
"""
Supabase Migration Script
Migrates data from Render PostgreSQL to Supabase

Usage:
    1. Set environment variables:
       - RENDER_DATABASE_URL: Current Render PostgreSQL URL
       - SUPABASE_DATABASE_URL: New Supabase PostgreSQL URL

    2. Run: python scripts/migrate_to_supabase.py

The script will:
1. Export all data from Render
2. Create tables in Supabase
3. Import all data to Supabase
4. Apply Row Level Security (RLS) policies
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()


# Table order for export/import (respecting foreign key dependencies)
TABLE_ORDER = [
    'tenants',
    'users',
    'user_sessions',
    'password_reset_tokens',
    'email_verification_tokens',
    'invitations',
    'connectors',
    'sync_metrics',
    'projects',
    'documents',
    'document_chunks',
    'knowledge_gaps',
    'gap_answers',
    'videos',
    'audit_logs',
    'chat_conversations',
    'chat_messages',
    'deleted_documents',
]

# RLS policies for tenant isolation
RLS_POLICIES = """
-- Enable RLS on all tenant-scoped tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_verification_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE connectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_gaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE gap_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE deleted_documents ENABLE ROW LEVEL SECURITY;

-- Create a function to get current tenant_id from JWT claims
-- This works with your existing JWT auth (tenant_id is stored in JWT)
CREATE OR REPLACE FUNCTION auth.tenant_id() RETURNS TEXT AS $$
  SELECT COALESCE(
    current_setting('request.jwt.claims', true)::json->>'tenant_id',
    current_setting('app.tenant_id', true)
  );
$$ LANGUAGE SQL STABLE;

-- RLS Policies for tenants table
CREATE POLICY tenant_isolation_select ON tenants
    FOR SELECT USING (id = auth.tenant_id());
CREATE POLICY tenant_isolation_insert ON tenants
    FOR INSERT WITH CHECK (id = auth.tenant_id());
CREATE POLICY tenant_isolation_update ON tenants
    FOR UPDATE USING (id = auth.tenant_id());
CREATE POLICY tenant_isolation_delete ON tenants
    FOR DELETE USING (id = auth.tenant_id());

-- RLS Policies for users table
CREATE POLICY user_tenant_isolation_select ON users
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY user_tenant_isolation_insert ON users
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY user_tenant_isolation_update ON users
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY user_tenant_isolation_delete ON users
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for connectors table
CREATE POLICY connector_tenant_isolation_select ON connectors
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY connector_tenant_isolation_insert ON connectors
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY connector_tenant_isolation_update ON connectors
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY connector_tenant_isolation_delete ON connectors
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for documents table
CREATE POLICY document_tenant_isolation_select ON documents
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY document_tenant_isolation_insert ON documents
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY document_tenant_isolation_update ON documents
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY document_tenant_isolation_delete ON documents
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for document_chunks table
CREATE POLICY chunk_tenant_isolation_select ON document_chunks
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY chunk_tenant_isolation_insert ON document_chunks
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY chunk_tenant_isolation_update ON document_chunks
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY chunk_tenant_isolation_delete ON document_chunks
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for projects table
CREATE POLICY project_tenant_isolation_select ON projects
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY project_tenant_isolation_insert ON projects
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY project_tenant_isolation_update ON projects
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY project_tenant_isolation_delete ON projects
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for knowledge_gaps table
CREATE POLICY gap_tenant_isolation_select ON knowledge_gaps
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY gap_tenant_isolation_insert ON knowledge_gaps
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY gap_tenant_isolation_update ON knowledge_gaps
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY gap_tenant_isolation_delete ON knowledge_gaps
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for gap_answers table
CREATE POLICY answer_tenant_isolation_select ON gap_answers
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY answer_tenant_isolation_insert ON gap_answers
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY answer_tenant_isolation_update ON gap_answers
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY answer_tenant_isolation_delete ON gap_answers
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for videos table
CREATE POLICY video_tenant_isolation_select ON videos
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY video_tenant_isolation_insert ON videos
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY video_tenant_isolation_update ON videos
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY video_tenant_isolation_delete ON videos
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for chat_conversations table
CREATE POLICY chat_conv_tenant_isolation_select ON chat_conversations
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY chat_conv_tenant_isolation_insert ON chat_conversations
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY chat_conv_tenant_isolation_update ON chat_conversations
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY chat_conv_tenant_isolation_delete ON chat_conversations
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for chat_messages table
CREATE POLICY chat_msg_tenant_isolation_select ON chat_messages
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY chat_msg_tenant_isolation_insert ON chat_messages
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY chat_msg_tenant_isolation_update ON chat_messages
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY chat_msg_tenant_isolation_delete ON chat_messages
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for user_sessions (via user's tenant)
CREATE POLICY session_tenant_isolation_select ON user_sessions
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    );
CREATE POLICY session_tenant_isolation_insert ON user_sessions
    FOR INSERT WITH CHECK (
        user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    );
CREATE POLICY session_tenant_isolation_delete ON user_sessions
    FOR DELETE USING (
        user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    );

-- RLS Policies for invitations table
CREATE POLICY invitation_tenant_isolation_select ON invitations
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY invitation_tenant_isolation_insert ON invitations
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY invitation_tenant_isolation_update ON invitations
    FOR UPDATE USING (tenant_id = auth.tenant_id());
CREATE POLICY invitation_tenant_isolation_delete ON invitations
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for sync_metrics table
CREATE POLICY sync_tenant_isolation_select ON sync_metrics
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY sync_tenant_isolation_insert ON sync_metrics
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());

-- RLS Policies for audit_logs table
CREATE POLICY audit_tenant_isolation_select ON audit_logs
    FOR SELECT USING (tenant_id = auth.tenant_id() OR tenant_id IS NULL);
CREATE POLICY audit_tenant_isolation_insert ON audit_logs
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id() OR tenant_id IS NULL);

-- RLS Policies for deleted_documents table
CREATE POLICY deleted_doc_tenant_isolation_select ON deleted_documents
    FOR SELECT USING (tenant_id = auth.tenant_id());
CREATE POLICY deleted_doc_tenant_isolation_insert ON deleted_documents
    FOR INSERT WITH CHECK (tenant_id = auth.tenant_id());
CREATE POLICY deleted_doc_tenant_isolation_delete ON deleted_documents
    FOR DELETE USING (tenant_id = auth.tenant_id());

-- RLS Policies for password_reset_tokens (via user's tenant)
CREATE POLICY reset_tenant_isolation_select ON password_reset_tokens
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    );
CREATE POLICY reset_tenant_isolation_insert ON password_reset_tokens
    FOR INSERT WITH CHECK (
        user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    );

-- RLS Policies for email_verification_tokens (via user's tenant)
CREATE POLICY verify_tenant_isolation_select ON email_verification_tokens
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    );
CREATE POLICY verify_tenant_isolation_insert ON email_verification_tokens
    FOR INSERT WITH CHECK (
        user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    );

-- Service role bypass (for backend operations)
-- The service role key should bypass RLS
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE connectors FORCE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
ALTER TABLE knowledge_gaps FORCE ROW LEVEL SECURITY;
ALTER TABLE gap_answers FORCE ROW LEVEL SECURITY;
ALTER TABLE videos FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
"""


def get_render_url():
    """Get the Render database URL"""
    url = os.getenv('RENDER_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not url:
        print("ERROR: RENDER_DATABASE_URL or DATABASE_URL not set")
        print("\nTo find your Render database URL:")
        print("1. Go to https://dashboard.render.com")
        print("2. Click on your PostgreSQL database")
        print("3. Copy the 'Internal Database URL' or 'External Database URL'")
        sys.exit(1)
    return url


def get_supabase_url():
    """Get the Supabase database URL"""
    url = os.getenv('SUPABASE_DATABASE_URL')
    if not url:
        print("ERROR: SUPABASE_DATABASE_URL not set")
        print("\nTo find your Supabase database URL:")
        print("1. Go to https://supabase.com/dashboard/project/bfsxwptbfuwhvazzyfbo/settings/database")
        print("2. Scroll to 'Connection string'")
        print("3. Select 'URI' tab")
        print("4. Copy the connection string (starts with postgresql://)")
        print("5. Replace [YOUR-PASSWORD] with your database password")
        print("\nSet it as: export SUPABASE_DATABASE_URL='postgresql://postgres:PASSWORD@db.bfsxwptbfuwhvazzyfbo.supabase.co:5432/postgres'")
        sys.exit(1)
    return url


def export_table_data(engine, table_name):
    """Export all data from a table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {table_name}"))
            columns = result.keys()
            rows = []
            for row in result:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Handle special types
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif isinstance(value, bytes):
                        # Skip binary data (embeddings) for now
                        value = None
                    row_dict[col] = value
                rows.append(row_dict)
            return {'columns': list(columns), 'rows': rows}
    except Exception as e:
        print(f"  Warning: Could not export {table_name}: {e}")
        return {'columns': [], 'rows': []}


def import_table_data(engine, table_name, data):
    """Import data into a table"""
    if not data['rows']:
        print(f"  {table_name}: No data to import")
        return 0

    columns = data['columns']
    rows = data['rows']

    # Skip embedding column if present (binary data)
    if 'embedding' in columns:
        columns = [c for c in columns if c != 'embedding']

    # Build INSERT statement
    col_str = ', '.join([f'"{c}"' for c in columns])
    placeholders = ', '.join([f':{c}' for c in columns])

    insert_sql = f'INSERT INTO {table_name} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

    count = 0
    with engine.begin() as conn:
        for row in rows:
            # Filter row to only include columns we're inserting
            filtered_row = {k: v for k, v in row.items() if k in columns}
            try:
                conn.execute(text(insert_sql), filtered_row)
                count += 1
            except Exception as e:
                print(f"  Warning: Could not insert row in {table_name}: {e}")

    return count


def create_tables_in_supabase(supabase_engine):
    """Create all tables in Supabase using SQLAlchemy models"""
    print("\n2. Creating tables in Supabase...")

    # Import models to get Base
    from database.models import Base, engine as _

    # Create all tables
    Base.metadata.create_all(bind=supabase_engine)
    print("   Tables created successfully")


def apply_rls_policies(supabase_engine):
    """Apply Row Level Security policies"""
    print("\n4. Applying Row Level Security policies...")

    with supabase_engine.begin() as conn:
        # Split policies into individual statements
        statements = [s.strip() for s in RLS_POLICIES.split(';') if s.strip()]

        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                # Ignore errors for policies that already exist
                if 'already exists' not in str(e).lower():
                    print(f"   Warning: {e}")

    print("   RLS policies applied")


def main():
    print("=" * 60)
    print("2nd Brain - Supabase Migration Tool")
    print("=" * 60)

    # Get database URLs
    render_url = get_render_url()
    supabase_url = get_supabase_url()

    print(f"\nSource (Render): {render_url[:50]}...")
    print(f"Target (Supabase): {supabase_url[:50]}...")

    # Create engines
    render_engine = create_engine(render_url, pool_pre_ping=True)
    supabase_engine = create_engine(supabase_url, pool_pre_ping=True)

    # Step 1: Export data from Render
    print("\n1. Exporting data from Render...")
    export_data = {}

    for table in TABLE_ORDER:
        data = export_table_data(render_engine, table)
        export_data[table] = data
        print(f"   {table}: {len(data['rows'])} rows")

    # Save export to file (backup)
    backup_file = Path(__file__).parent / f"migration_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_file, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    print(f"\n   Backup saved to: {backup_file}")

    # Step 2: Create tables in Supabase
    create_tables_in_supabase(supabase_engine)

    # Step 3: Import data to Supabase
    print("\n3. Importing data to Supabase...")

    for table in TABLE_ORDER:
        data = export_data[table]
        count = import_table_data(supabase_engine, table, data)
        print(f"   {table}: {count} rows imported")

    # Step 4: Apply RLS policies
    apply_rls_policies(supabase_engine)

    # Done
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Update your Render environment variable:")
    print(f"   DATABASE_URL={supabase_url}")
    print("\n2. Add Supabase keys to Render:")
    print("   SUPABASE_URL=https://bfsxwptbfuwhvazzyfbo.supabase.co")
    print("   SUPABASE_ANON_KEY=<your anon key>")
    print("   SUPABASE_SERVICE_KEY=<your service role key>")
    print("\n3. Redeploy your application on Render")
    print("\n4. Test all functionality to ensure migration was successful")


if __name__ == '__main__':
    main()
