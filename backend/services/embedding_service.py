"""
Embedding Service - Centralized Document Embedding for Multi-tenant RAG

Handles:
- Document embedding to Pinecone during sync
- Document embedding during "Complete Process"
- Deduplication (skip already embedded documents)
- Tenant isolation

Updated 2025-12-09:
- Increased chunk size to 2000 chars (better context preservation)
- Increased overlap to 400 chars (better continuity between chunks)
- All document content is now fully embedded (no truncation)
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from database.models import Document, Tenant
from vector_stores.pinecone_store import get_vector_store, PineconeVectorStore

# Chunking configuration - 2000 chars with 400 overlap for optimal RAG
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 400


def utc_now():
    return datetime.now(timezone.utc)


class EmbeddingService:
    """
    Centralized service for embedding documents to Pinecone.

    Features:
    - Automatic chunking and embedding
    - Deduplication (tracks embedded_at timestamp)
    - Multi-tenant isolation via Pinecone namespaces
    - Progress callbacks for UI updates
    """

    def __init__(self, vector_store: Optional[PineconeVectorStore] = None):
        """
        Initialize embedding service.

        Args:
            vector_store: Optional PineconeVectorStore instance (creates one if not provided)
        """
        self._vector_store = vector_store
        self._init_error = None

    @property
    def vector_store(self) -> PineconeVectorStore:
        """Lazy initialization of vector store"""
        if self._vector_store is None:
            try:
                print("[EmbeddingService] Initializing Pinecone vector store...", flush=True)
                self._vector_store = get_vector_store()
                print("[EmbeddingService] Pinecone vector store initialized successfully", flush=True)
            except ValueError as e:
                self._init_error = str(e)
                print(f"[EmbeddingService] CRITICAL: Failed to initialize Pinecone: {e}", flush=True)
                raise
            except Exception as e:
                self._init_error = str(e)
                print(f"[EmbeddingService] CRITICAL: Unexpected error initializing Pinecone: {e}", flush=True)
                raise
        return self._vector_store

    def embed_documents(
        self,
        documents: List[Document],
        tenant_id: str,
        db: Session,
        force_reembed: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Embed documents to Pinecone one at a time with progress tracking.

        Args:
            documents: List of Document model instances
            tenant_id: Tenant ID for isolation
            db: Database session for updating embedded_at
            force_reembed: If True, re-embed even if already embedded
            progress_callback: Optional callback(current, total, doc_title) for progress updates

        Returns:
            Dict with embedding stats
        """
        print(f"[EmbeddingService] embed_documents called with {len(documents)} documents for tenant {tenant_id}", flush=True)

        if not documents:
            print("[EmbeddingService] No documents provided, returning early", flush=True)
            return {
                'success': True,
                'total': 0,
                'embedded': 0,
                'skipped': 0,
                'errors': []
            }

        total = len(documents)
        embedded_count = 0
        total_chunks = 0
        skipped = 0
        errors = []
        now = utc_now()
        embedding_model = os.getenv('AZURE_EMBEDDING_DEPLOYMENT', 'text-embedding-3-large')

        for i, doc in enumerate(documents):
            doc_title = doc.title[:50] if doc.title else f"Document {i+1}"

            # Report progress for every document (including skipped)
            if progress_callback:
                progress_callback(i + 1, total, f"Embedding: {doc_title}")

            # Skip if no content
            if not doc.content:
                skipped += 1
                continue

            # Skip if already embedded
            if not force_reembed and doc.embedded_at:
                skipped += 1
                continue

            # Prepare single document for Pinecone
            metadata = {
                'source_type': doc.source_type or '',
                'external_id': doc.external_id or '',
                'sender': doc.sender or '',
                'classification': doc.classification.value if doc.classification else 'unknown',
                'created_at': doc.source_created_at.isoformat() if doc.source_created_at else ''
            }

            # Add Slack-specific metadata for deep links
            if doc.source_type == 'slack' and doc.doc_metadata:
                doc_meta = doc.doc_metadata if isinstance(doc.doc_metadata, dict) else {}
                if doc_meta.get('channel_id'):
                    metadata['channel_id'] = doc_meta['channel_id']
                if doc_meta.get('message_ts'):
                    metadata['message_ts'] = doc_meta['message_ts']
                if doc_meta.get('team_domain'):
                    metadata['team_domain'] = doc_meta['team_domain']
                if doc_meta.get('team_id'):
                    metadata['team_id'] = doc_meta['team_id']

            pinecone_doc = {
                'id': str(doc.id),
                'content': doc.content,
                'title': doc.title or '',
                'metadata': metadata
            }

            try:
                result = self.vector_store.embed_and_upsert_documents(
                    documents=[pinecone_doc],
                    tenant_id=tenant_id,
                    chunk_size=CHUNK_SIZE,
                    chunk_overlap=CHUNK_OVERLAP,
                    show_progress=False
                )

                if result.get('success') or result.get('upserted', 0) > 0:
                    doc.embedded_at = now
                    doc.embedding_generated = True
                    doc.embedding_model = embedding_model
                    embedded_count += result.get('upserted', 0)
                    total_chunks += result.get('total_chunks', 0)
                    db.commit()
                else:
                    doc_errors = result.get('errors', [])
                    if doc_errors:
                        errors.extend(doc_errors)

            except Exception as e:
                print(f"[EmbeddingService] Error embedding doc {doc.id} ({doc_title}): {e}", flush=True)
                errors.append(f"Doc {doc_title}: {str(e)}")

        print(f"[EmbeddingService] Done: embedded={embedded_count} chunks, skipped={skipped}, errors={len(errors)}", flush=True)

        return {
            'success': len(errors) == 0,
            'total': total,
            'embedded': embedded_count,
            'chunks': total_chunks,
            'skipped': skipped,
            'errors': errors,
            'namespace': tenant_id
        }

    def embed_tenant_documents(
        self,
        tenant_id: str,
        db: Session,
        only_confirmed: bool = False,
        force_reembed: bool = False
    ) -> Dict:
        """
        Embed all documents for a tenant.

        Args:
            tenant_id: Tenant ID
            db: Database session
            only_confirmed: If True, only embed user-confirmed documents
            force_reembed: If True, re-embed all documents

        Returns:
            Dict with embedding stats
        """
        # Query documents
        query = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False,
            Document.content != None,
            Document.content != ''
        )

        if only_confirmed:
            query = query.filter(Document.user_confirmed == True)

        if not force_reembed:
            query = query.filter(Document.embedded_at == None)

        documents = query.all()

        print(f"[EmbeddingService] Found {len(documents)} documents to embed for tenant {tenant_id}")

        if not documents:
            return {
                'success': True,
                'total': 0,
                'embedded': 0,
                'skipped': 0,
                'errors': [],
                'message': 'No documents to embed'
            }

        return self.embed_documents(
            documents=documents,
            tenant_id=tenant_id,
            db=db,
            force_reembed=force_reembed
        )

    def delete_document_embeddings(
        self,
        document_ids: List[str],
        tenant_id: str,
        db: Session
    ) -> Dict:
        """
        Delete embeddings for specific documents.

        Args:
            document_ids: List of document IDs to delete
            tenant_id: Tenant ID
            db: Database session

        Returns:
            Dict with deletion stats
        """
        try:
            success = self.vector_store.delete_documents(
                doc_ids=document_ids,
                tenant_id=tenant_id
            )

            if success:
                # Update database to clear embedded_at
                db.query(Document).filter(
                    Document.id.in_(document_ids),
                    Document.tenant_id == tenant_id
                ).update({
                    'embedded_at': None,
                    'embedding_generated': False
                }, synchronize_session=False)
                db.commit()

            return {
                'success': success,
                'deleted': len(document_ids) if success else 0
            }

        except Exception as e:
            print(f"[EmbeddingService] Error deleting embeddings: {e}")
            return {
                'success': False,
                'deleted': 0,
                'error': str(e)
            }

    def delete_tenant_embeddings(self, tenant_id: str, db: Session) -> Dict:
        """
        Delete all embeddings for a tenant (for account deletion).

        Args:
            tenant_id: Tenant ID
            db: Database session

        Returns:
            Dict with deletion stats
        """
        try:
            success = self.vector_store.delete_tenant_data(tenant_id)

            if success:
                # Clear embedded_at for all tenant documents
                db.query(Document).filter(
                    Document.tenant_id == tenant_id
                ).update({
                    'embedded_at': None,
                    'embedding_generated': False
                }, synchronize_session=False)
                db.commit()

            return {
                'success': success,
                'tenant_id': tenant_id
            }

        except Exception as e:
            print(f"[EmbeddingService] Error deleting tenant embeddings: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_embedding_stats(self, tenant_id: str, db: Session) -> Dict:
        """
        Get embedding statistics for a tenant.

        Args:
            tenant_id: Tenant ID
            db: Database session

        Returns:
            Dict with stats
        """
        total_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False
        ).count()

        embedded_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False,
            Document.embedded_at != None
        ).count()

        pinecone_stats = self.vector_store.get_stats(tenant_id)

        return {
            'total_documents': total_docs,
            'embedded_documents': embedded_docs,
            'pending_documents': total_docs - embedded_docs,
            'pinecone_vectors': pinecone_stats.get('vector_count', 0),
            'namespace': tenant_id
        }


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create singleton EmbeddingService instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
