"""
Research Profile Service — lazy-built cached research profile per tenant.

Aggregates the user's documents' structured_summary fields into a concise
research profile used for context injection in the orchestrator.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from database.models import SessionLocal, Tenant, Document
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

logger = logging.getLogger(__name__)

PROFILE_STALE_HOURS = 24


def get_or_build_profile(tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the cached research profile for a tenant, rebuilding if stale.
    Returns None if the tenant has no documents or profile can't be built.
    Uses a building flag to prevent concurrent rebuilds.
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None

        # Check if profile is fresh enough
        if tenant.research_profile and tenant.profile_updated_at:
            age = datetime.now(timezone.utc) - tenant.profile_updated_at
            if age < timedelta(hours=PROFILE_STALE_HOURS):
                return tenant.research_profile

        # Check if another request is already building
        if tenant.profile_building:
            return tenant.research_profile  # Return stale profile rather than waiting

        # Mark as building
        tenant.profile_building = True
        db.commit()

        try:
            profile = _build_profile(tenant_id, db)
            if profile is not None:
                tenant.research_profile = profile
                tenant.profile_updated_at = datetime.now(timezone.utc)
            tenant.profile_building = False
            db.commit()
            return profile
        except Exception as e:
            logger.error(f"Failed to build research profile for {tenant_id}: {e}")
            tenant.profile_building = False
            db.commit()
            return tenant.research_profile  # Return stale if available

    finally:
        db.close()


def _build_profile(tenant_id: str, db) -> Dict[str, Any]:
    """
    Build a research profile by aggregating the tenant's recent documents.
    Uses structured_summary JSON from documents (already extracted during sync).
    """
    docs = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.structured_summary.isnot(None),
        )
        .order_by(Document.created_at.desc())
        .limit(20)
        .all()
    )

    if not docs:
        return None  # Caller must NOT update profile_updated_at when result is None

    summaries = []
    for doc in docs:
        summary = doc.structured_summary
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except json.JSONDecodeError:
                summary = {"text": summary}

        summaries.append({
            "title": doc.title or "Untitled",
            "source": getattr(doc, 'source_type', 'unknown') or "unknown",
            "summary": summary,
        })

    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "Analyze these document summaries from a researcher's knowledge base. "
                    "Extract a concise research profile as JSON with these fields:\n"
                    "- primary_fields: array of 1-3 research fields\n"
                    "- recent_topics: array of 3-5 specific topics they work on\n"
                    "- institution: their institution name (if detectable, else null)\n"
                    "- collaborators: array of collaborator names (if detectable, else [])\n"
                    "- recent_papers: array of their paper titles (if any, else [])\n"
                    "- methodology_preferences: array of methods they commonly use\n"
                    "Return ONLY valid JSON, no markdown."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(summaries[:20], default=str),
            },
        ],
        temperature=0.3,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()

    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        profile = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse research profile JSON: {raw[:200]}")
        profile = {
            "primary_fields": [],
            "recent_topics": [],
            "institution": None,
            "collaborators": [],
            "recent_papers": [],
            "methodology_preferences": [],
        }

    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    return profile
