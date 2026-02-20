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

    def _prepare_pinecone_doc(self, doc: 'Document') -> Optional[Dict]:
        """Prepare a Document model instance for Pinecone ingestion."""
        if not doc.content:
            return None

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
            for key in ('channel_id', 'message_ts', 'team_domain', 'team_id'):
                if doc_meta.get(key):
                    metadata[key] = doc_meta[key]

        return {
            'id': str(doc.id),
            'content': doc.content,
            'title': doc.title or '',
            'metadata': metadata
        }

    def embed_documents(
        self,
        documents: List[Document],
        tenant_id: str,
        db: Session,
        force_reembed: bool = False,
        progress_callback: Optional[callable] = None,
        batch_size: int = 20
    ) -> Dict:
        """
        Embed documents to Pinecone in batches for speed.

        Sends batch_size documents at a time to the vector store instead of
        one at a time. The vector store handles chunking and embedding internally.

        Args:
            documents: List of Document model instances
            tenant_id: Tenant ID for isolation
            db: Database session for updating embedded_at
            force_reembed: If True, re-embed even if already embedded
            progress_callback: Optional callback(current, total, doc_title) for progress updates
            batch_size: Number of documents to embed per Pinecone call (default 20)

        Returns:
            Dict with embedding stats
        """
        import time as _time
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
        start_time = _time.time()

        # Filter and prepare docs
        docs_to_embed = []
        for doc in documents:
            if not doc.content:
                skipped += 1
                continue
            if not force_reembed and doc.embedded_at:
                skipped += 1
                continue
            pinecone_doc = self._prepare_pinecone_doc(doc)
            if pinecone_doc:
                docs_to_embed.append((doc, pinecone_doc))
            else:
                skipped += 1

        if not docs_to_embed:
            return {'success': True, 'total': total, 'embedded': 0, 'skipped': skipped, 'errors': []}

        print(f"[EmbeddingService] Embedding {len(docs_to_embed)} documents in batches of {batch_size}", flush=True)

        # Process in batches
        for batch_start in range(0, len(docs_to_embed), batch_size):
            batch = docs_to_embed[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(docs_to_embed) + batch_size - 1) // batch_size
            pinecone_docs = [pd for _, pd in batch]
            db_docs = [d for d, _ in batch]

            if progress_callback:
                progress_callback(skipped + batch_start + len(batch), total,
                                  f"Embedding batch {batch_num}/{total_batches} ({len(batch)} docs)")

            try:
                result = self.vector_store.embed_and_upsert_documents(
                    documents=pinecone_docs,
                    tenant_id=tenant_id,
                    chunk_size=CHUNK_SIZE,
                    chunk_overlap=CHUNK_OVERLAP,
                    show_progress=False
                )

                if result.get('success') or result.get('upserted', 0) > 0:
                    for doc in db_docs:
                        doc.embedded_at = now
                        doc.embedding_generated = True
                        doc.embedding_model = embedding_model
                    embedded_count += result.get('upserted', 0)
                    total_chunks += result.get('total_chunks', 0)
                    db.commit()
                    print(f"[EmbeddingService] Batch {batch_num}/{total_batches}: {result.get('upserted', 0)} chunks upserted", flush=True)
                else:
                    doc_errors = result.get('errors', [])
                    if doc_errors:
                        errors.extend(doc_errors)
                        print(f"[EmbeddingService] Batch {batch_num} had errors: {doc_errors}", flush=True)

            except Exception as e:
                print(f"[EmbeddingService] Error in batch {batch_num}: {e}", flush=True)
                errors.append(f"Batch {batch_num}: {str(e)}")

        elapsed = _time.time() - start_time
        rate = len(docs_to_embed) / elapsed if elapsed > 0 else 0
        print(f"[EmbeddingService] Done: {embedded_count} chunks from {len(docs_to_embed)} docs, "
              f"skipped={skipped}, errors={len(errors)}, {elapsed:.1f}s ({rate:.1f} docs/sec)", flush=True)

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
