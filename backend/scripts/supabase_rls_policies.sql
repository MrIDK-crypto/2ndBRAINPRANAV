-- ============================================================================
-- 2nd Brain - Supabase Row Level Security (RLS) Policies
-- ============================================================================
--
-- Run this SQL in the Supabase SQL Editor after migration to enable
-- tenant isolation at the database level.
--
-- Go to: https://supabase.com/dashboard/project/bfsxwptbfuwhvazzyfbo/sql/new
-- ============================================================================

-- Create auth schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS auth;

-- ============================================================================
-- Helper Function: Get tenant_id from JWT or session
-- ============================================================================
-- This function extracts tenant_id from JWT claims or app settings
-- Your backend sets this via: SET app.tenant_id = 'xxx'

CREATE OR REPLACE FUNCTION auth.tenant_id() RETURNS TEXT AS $$
BEGIN
  -- Try to get from JWT claims first (Supabase Auth)
  BEGIN
    RETURN (current_setting('request.jwt.claims', true)::json->>'tenant_id');
  EXCEPTION WHEN OTHERS THEN
    -- Fall back to app setting (your JWT auth)
    BEGIN
      RETURN current_setting('app.tenant_id', true);
    EXCEPTION WHEN OTHERS THEN
      RETURN NULL;
    END;
  END;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ============================================================================
-- Enable RLS on all tables
-- ============================================================================

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

-- ============================================================================
-- Service Role Bypass Policy (for your backend)
-- ============================================================================
-- The postgres and service_role users bypass RLS by default.
-- Your backend uses the service_role key, so it has full access.

-- ============================================================================
-- TENANTS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS tenant_select ON tenants;
DROP POLICY IF EXISTS tenant_insert ON tenants;
DROP POLICY IF EXISTS tenant_update ON tenants;
DROP POLICY IF EXISTS tenant_delete ON tenants;

CREATE POLICY tenant_select ON tenants FOR SELECT
  USING (id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY tenant_insert ON tenants FOR INSERT
  WITH CHECK (true); -- Allow creating new tenants (signup)

CREATE POLICY tenant_update ON tenants FOR UPDATE
  USING (id = auth.tenant_id());

CREATE POLICY tenant_delete ON tenants FOR DELETE
  USING (id = auth.tenant_id());

-- ============================================================================
-- USERS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS users_select ON users;
DROP POLICY IF EXISTS users_insert ON users;
DROP POLICY IF EXISTS users_update ON users;
DROP POLICY IF EXISTS users_delete ON users;

CREATE POLICY users_select ON users FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY users_insert ON users FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY users_update ON users FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY users_delete ON users FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- USER_SESSIONS Table Policies (via user lookup)
-- ============================================================================

DROP POLICY IF EXISTS sessions_select ON user_sessions;
DROP POLICY IF EXISTS sessions_insert ON user_sessions;
DROP POLICY IF EXISTS sessions_delete ON user_sessions;

CREATE POLICY sessions_select ON user_sessions FOR SELECT
  USING (
    user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    OR auth.tenant_id() IS NULL
  );

CREATE POLICY sessions_insert ON user_sessions FOR INSERT
  WITH CHECK (
    user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    OR auth.tenant_id() IS NULL
  );

CREATE POLICY sessions_delete ON user_sessions FOR DELETE
  USING (
    user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    OR auth.tenant_id() IS NULL
  );

-- ============================================================================
-- CONNECTORS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS connectors_select ON connectors;
DROP POLICY IF EXISTS connectors_insert ON connectors;
DROP POLICY IF EXISTS connectors_update ON connectors;
DROP POLICY IF EXISTS connectors_delete ON connectors;

CREATE POLICY connectors_select ON connectors FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY connectors_insert ON connectors FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY connectors_update ON connectors FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY connectors_delete ON connectors FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- DOCUMENTS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS documents_select ON documents;
DROP POLICY IF EXISTS documents_insert ON documents;
DROP POLICY IF EXISTS documents_update ON documents;
DROP POLICY IF EXISTS documents_delete ON documents;

CREATE POLICY documents_select ON documents FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY documents_insert ON documents FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY documents_update ON documents FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY documents_delete ON documents FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- DOCUMENT_CHUNKS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS chunks_select ON document_chunks;
DROP POLICY IF EXISTS chunks_insert ON document_chunks;
DROP POLICY IF EXISTS chunks_update ON document_chunks;
DROP POLICY IF EXISTS chunks_delete ON document_chunks;

CREATE POLICY chunks_select ON document_chunks FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY chunks_insert ON document_chunks FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY chunks_update ON document_chunks FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY chunks_delete ON document_chunks FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- PROJECTS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS projects_select ON projects;
DROP POLICY IF EXISTS projects_insert ON projects;
DROP POLICY IF EXISTS projects_update ON projects;
DROP POLICY IF EXISTS projects_delete ON projects;

CREATE POLICY projects_select ON projects FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY projects_insert ON projects FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY projects_update ON projects FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY projects_delete ON projects FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- KNOWLEDGE_GAPS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS gaps_select ON knowledge_gaps;
DROP POLICY IF EXISTS gaps_insert ON knowledge_gaps;
DROP POLICY IF EXISTS gaps_update ON knowledge_gaps;
DROP POLICY IF EXISTS gaps_delete ON knowledge_gaps;

CREATE POLICY gaps_select ON knowledge_gaps FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY gaps_insert ON knowledge_gaps FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY gaps_update ON knowledge_gaps FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY gaps_delete ON knowledge_gaps FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- GAP_ANSWERS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS answers_select ON gap_answers;
DROP POLICY IF EXISTS answers_insert ON gap_answers;
DROP POLICY IF EXISTS answers_update ON gap_answers;
DROP POLICY IF EXISTS answers_delete ON gap_answers;

CREATE POLICY answers_select ON gap_answers FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY answers_insert ON gap_answers FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY answers_update ON gap_answers FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY answers_delete ON gap_answers FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- VIDEOS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS videos_select ON videos;
DROP POLICY IF EXISTS videos_insert ON videos;
DROP POLICY IF EXISTS videos_update ON videos;
DROP POLICY IF EXISTS videos_delete ON videos;

CREATE POLICY videos_select ON videos FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY videos_insert ON videos FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY videos_update ON videos FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY videos_delete ON videos FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- CHAT_CONVERSATIONS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS conversations_select ON chat_conversations;
DROP POLICY IF EXISTS conversations_insert ON chat_conversations;
DROP POLICY IF EXISTS conversations_update ON chat_conversations;
DROP POLICY IF EXISTS conversations_delete ON chat_conversations;

CREATE POLICY conversations_select ON chat_conversations FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY conversations_insert ON chat_conversations FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY conversations_update ON chat_conversations FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY conversations_delete ON chat_conversations FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- CHAT_MESSAGES Table Policies
-- ============================================================================

DROP POLICY IF EXISTS messages_select ON chat_messages;
DROP POLICY IF EXISTS messages_insert ON chat_messages;
DROP POLICY IF EXISTS messages_update ON chat_messages;
DROP POLICY IF EXISTS messages_delete ON chat_messages;

CREATE POLICY messages_select ON chat_messages FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY messages_insert ON chat_messages FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY messages_update ON chat_messages FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY messages_delete ON chat_messages FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- INVITATIONS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS invitations_select ON invitations;
DROP POLICY IF EXISTS invitations_insert ON invitations;
DROP POLICY IF EXISTS invitations_update ON invitations;
DROP POLICY IF EXISTS invitations_delete ON invitations;

CREATE POLICY invitations_select ON invitations FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY invitations_insert ON invitations FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY invitations_update ON invitations FOR UPDATE
  USING (tenant_id = auth.tenant_id());

CREATE POLICY invitations_delete ON invitations FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- SYNC_METRICS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS sync_select ON sync_metrics;
DROP POLICY IF EXISTS sync_insert ON sync_metrics;

CREATE POLICY sync_select ON sync_metrics FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY sync_insert ON sync_metrics FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

-- ============================================================================
-- AUDIT_LOGS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS audit_select ON audit_logs;
DROP POLICY IF EXISTS audit_insert ON audit_logs;

CREATE POLICY audit_select ON audit_logs FOR SELECT
  USING (tenant_id = auth.tenant_id() OR tenant_id IS NULL OR auth.tenant_id() IS NULL);

CREATE POLICY audit_insert ON audit_logs FOR INSERT
  WITH CHECK (true); -- Allow inserting audit logs for any action

-- ============================================================================
-- DELETED_DOCUMENTS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS deleted_select ON deleted_documents;
DROP POLICY IF EXISTS deleted_insert ON deleted_documents;
DROP POLICY IF EXISTS deleted_delete ON deleted_documents;

CREATE POLICY deleted_select ON deleted_documents FOR SELECT
  USING (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY deleted_insert ON deleted_documents FOR INSERT
  WITH CHECK (tenant_id = auth.tenant_id() OR auth.tenant_id() IS NULL);

CREATE POLICY deleted_delete ON deleted_documents FOR DELETE
  USING (tenant_id = auth.tenant_id());

-- ============================================================================
-- PASSWORD_RESET_TOKENS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS reset_select ON password_reset_tokens;
DROP POLICY IF EXISTS reset_insert ON password_reset_tokens;
DROP POLICY IF EXISTS reset_update ON password_reset_tokens;

CREATE POLICY reset_select ON password_reset_tokens FOR SELECT
  USING (
    user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    OR auth.tenant_id() IS NULL
  );

CREATE POLICY reset_insert ON password_reset_tokens FOR INSERT
  WITH CHECK (true); -- Allow password reset for anyone

CREATE POLICY reset_update ON password_reset_tokens FOR UPDATE
  USING (
    user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    OR auth.tenant_id() IS NULL
  );

-- ============================================================================
-- EMAIL_VERIFICATION_TOKENS Table Policies
-- ============================================================================

DROP POLICY IF EXISTS verify_select ON email_verification_tokens;
DROP POLICY IF EXISTS verify_insert ON email_verification_tokens;
DROP POLICY IF EXISTS verify_update ON email_verification_tokens;

CREATE POLICY verify_select ON email_verification_tokens FOR SELECT
  USING (
    user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    OR auth.tenant_id() IS NULL
  );

CREATE POLICY verify_insert ON email_verification_tokens FOR INSERT
  WITH CHECK (true); -- Allow email verification for anyone

CREATE POLICY verify_update ON email_verification_tokens FOR UPDATE
  USING (
    user_id IN (SELECT id FROM users WHERE tenant_id = auth.tenant_id())
    OR auth.tenant_id() IS NULL
  );

-- ============================================================================
-- Grant permissions
-- ============================================================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role;

-- Grant table permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- Grant sequence permissions (for auto-increment if any)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role;

-- ============================================================================
-- Done!
-- ============================================================================

DO $$
BEGIN
  RAISE NOTICE 'RLS policies applied successfully!';
  RAISE NOTICE 'Your backend uses service_role key which bypasses RLS.';
  RAISE NOTICE 'Frontend direct queries (if any) will be tenant-isolated.';
END $$;
