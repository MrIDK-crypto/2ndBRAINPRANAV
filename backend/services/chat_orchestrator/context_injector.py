"""Context Injector — pulls RAG chunks + research profile for power services."""

import logging
from typing import Dict, Any, Optional, List

from services.research_profile_service import get_or_build_profile

logger = logging.getLogger(__name__)


def inject_context(
    tenant_id: str,
    message: str,
    source_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build the context package for power services.

    Args:
        tenant_id: The user's tenant ID
        message: The user's chat message (used as RAG query)
        source_types: Optional filter for document sources

    Returns:
        {
            "research_profile": {...} or None,
            "relevant_chunks": [...] list of text chunks from RAG,
            "profile_fields": [...] shorthand for SSE event,
            "chunks_found": int,
        }
    """
    # 1. Get or build research profile
    research_profile = None
    try:
        research_profile = get_or_build_profile(tenant_id)
    except Exception as e:
        logger.error(f"Failed to get research profile for tenant {tenant_id}: {e}", exc_info=True)

    # 2. RAG query for relevant chunks
    relevant_chunks = _query_rag(tenant_id, message, source_types)

    # Build context package
    profile_fields = []
    if research_profile:
        profile_fields = research_profile.get("primary_fields", [])

    return {
        "research_profile": research_profile,
        "relevant_chunks": relevant_chunks,
        "profile_fields": profile_fields,
        "chunks_found": len(relevant_chunks),
    }


def _query_rag(
    tenant_id: str,
    query: str,
    source_types: Optional[List[str]] = None,
    top_k: int = 15,
) -> List[Dict[str, Any]]:
    """Query the existing Pinecone RAG pipeline for relevant chunks."""
    try:
        from vector_stores.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore()
        results = store.search(
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
        )

        chunks = []
        for result in results:
            chunks.append({
                "text": result.get("text", result.get("content", "")),
                "score": result.get("score", 0),
                "source": result.get("metadata", {}).get("source_type", "unknown"),
                "document_id": result.get("metadata", {}).get("document_id"),
            })

        return chunks

    except Exception as e:
        logger.warning(f"RAG query failed for tenant {tenant_id}: {e}")
        return []
