CREATE INDEX IF NOT EXISTS idx_document_tenant_id ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_document_embedded_at ON documents(embedded_at) WHERE embedded_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_chat_message_conv_tenant ON chat_messages(conversation_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_document_chunk_doc_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_connector_tenant_id ON connectors(tenant_id);

-- Full-text search index for chat messages (replaces slow ILIKE)
CREATE INDEX IF NOT EXISTS idx_chat_message_content_trgm ON chat_messages USING gin (content gin_trgm_ops);

-- Full-text search index for documents (replaces slow ILIKE)
CREATE INDEX IF NOT EXISTS idx_document_title_trgm ON documents USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_document_content_trgm ON documents USING gin (content gin_trgm_ops);

-- Note: Requires pg_trgm extension: CREATE EXTENSION IF NOT EXISTS pg_trgm;
