"""
PARA Classification Service for 2nd Brain
AI-powered classification of projects into PARA taxonomy:
  - Projects: Time-bound deliverables with deadlines
  - Areas: Ongoing responsibilities and standards
  - Resources: Reference material, frameworks, templates
  - Archives: Completed or inactive items
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

from database.models import SessionLocal, Project, Document, utc_now


VALID_PARA_CATEGORIES = {"projects", "areas", "resources", "archives"}

PARA_SYSTEM_PROMPT = """You are a knowledge organization expert. Classify the given project into exactly ONE of these four categories:

1. **projects** - Time-bound deliverables with a clear goal and deadline. Examples: "Q4 Product Launch", "Client Proposal for Acme Corp", "Database Migration Sprint". These have a start, an end, and a measurable outcome.

2. **areas** - Ongoing responsibilities that require continuous maintenance with no end date. Examples: "Customer Support Operations", "Security Compliance", "Team Hiring Pipeline", "Quality Assurance". These represent standards to be maintained.

3. **resources** - Reference material, frameworks, templates, and knowledge for future use. Examples: "Python Best Practices", "Industry Research Notes", "Onboarding Templates", "Meeting Notes Archive". These are consulted but not actively worked on.

4. **archives** - Completed projects, outdated resources, or inactive areas. Examples: "2023 Annual Report (Complete)", "Legacy System Docs", "Previous Client Work".

Respond with ONLY a JSON object:
{"category": "projects|areas|resources|archives", "confidence": 0.0-1.0, "reason": "brief explanation"}"""


class PARAClassificationService:
    """AI-powered PARA classification for projects."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-load Azure OpenAI client."""
        if self._client is None:
            try:
                from services.openai_client import get_openai_client
                self._client = get_openai_client()
            except Exception as e:
                print(f"[PARA] Could not initialize OpenAI client: {e}")
        return self._client

    def classify_project(
        self,
        name: str,
        description: str = "",
        topic_words: list = None,
        doc_summaries: list = None,
    ) -> Dict[str, Any]:
        """
        Classify a project into a PARA category using AI.

        Returns: {"category": str, "confidence": float, "reason": str}
        """
        client = self._get_client()
        if not client:
            return {
                "category": "resources",
                "confidence": 0.5,
                "reason": "AI unavailable, defaulting to resources"
            }

        # Build context for classification
        context_parts = [f"Project name: {name}"]
        if description:
            context_parts.append(f"Description: {description}")
        if topic_words:
            context_parts.append(f"Key topics: {', '.join(topic_words[:10])}")
        if doc_summaries:
            summaries_text = "\n".join(
                f"- {s[:200]}" for s in doc_summaries[:5]
            )
            context_parts.append(f"Sample document summaries:\n{summaries_text}")

        user_message = "\n".join(context_parts)

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": PARA_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=150,
                response_format={"type": "json_object"},
            )

            import json
            result = json.loads(response.choices[0].message.content)

            category = result.get("category", "resources").lower()
            if category not in VALID_PARA_CATEGORIES:
                category = "resources"

            return {
                "category": category,
                "confidence": min(max(float(result.get("confidence", 0.5)), 0.0), 1.0),
                "reason": result.get("reason", ""),
            }

        except Exception as e:
            print(f"[PARA] Classification error: {e}")
            return {
                "category": "resources",
                "confidence": 0.3,
                "reason": f"Classification failed: {str(e)[:100]}"
            }

    def classify_project_heuristic(
        self,
        name: str,
        description: str = "",
        topic_words: list = None,
        last_document_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Fast heuristic classification (no AI call).
        Used as fallback or for bulk operations.
        """
        name_lower = (name or "").lower()
        desc_lower = (description or "").lower()
        combined = f"{name_lower} {desc_lower}"

        # Archive signals
        archive_signals = ["archive", "legacy", "deprecated", "old", "previous", "former", "completed"]
        if any(s in combined for s in archive_signals):
            return {"category": "archives", "confidence": 0.7, "reason": "Name/description contains archive signals"}

        # Check staleness (no documents in 90+ days)
        if last_document_date:
            days_since = (datetime.now(timezone.utc) - last_document_date).days
            if days_since > 90:
                return {"category": "archives", "confidence": 0.6, "reason": f"No new documents in {days_since} days"}

        # Project signals (time-bound deliverables)
        project_signals = [
            "launch", "sprint", "milestone", "deadline", "q1", "q2", "q3", "q4",
            "release", "migration", "proposal", "implementation", "phase",
            "deliverable", "pilot", "mvp", "prototype", "rollout"
        ]
        if any(s in combined for s in project_signals):
            return {"category": "projects", "confidence": 0.7, "reason": "Name/description contains project signals"}

        # Area signals (ongoing responsibilities)
        area_signals = [
            "operations", "maintenance", "compliance", "support", "hiring",
            "onboarding", "pipeline", "continuous", "monitoring", "standards",
            "quality", "security", "governance", "management"
        ]
        if any(s in combined for s in area_signals):
            return {"category": "areas", "confidence": 0.6, "reason": "Name/description contains area signals"}

        # Default to resources
        return {"category": "resources", "confidence": 0.5, "reason": "Default classification"}

    def auto_archive_stale_projects(
        self,
        tenant_id: str,
        db,
        stale_days: int = 90,
    ) -> List[Dict[str, Any]]:
        """
        Move projects with no new documents in stale_days to archives.
        Only affects category="projects" (time-bound deliverables).
        Respects user overrides.

        Returns list of archived project summaries.
        """
        from sqlalchemy import func

        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        archived = []

        try:
            # Find active projects (category=projects) with no recent documents
            projects = (
                db.query(Project)
                .filter(
                    Project.tenant_id == tenant_id,
                    Project.para_category == "projects",
                    Project.user_override_category == False,
                    Project.is_archived == False,
                )
                .all()
            )

            for project in projects:
                # Check most recent document date
                latest_doc = (
                    db.query(func.max(Document.created_at))
                    .filter(
                        Document.project_id == project.id,
                        Document.tenant_id == tenant_id,
                    )
                    .scalar()
                )

                if latest_doc is None or latest_doc < cutoff:
                    project.para_category = "archives"
                    project.is_archived = True
                    project.para_metadata = {
                        **(project.para_metadata or {}),
                        "archived_reason": f"No new documents in {stale_days}+ days",
                        "original_category": "projects",
                        "archived_at": datetime.now(timezone.utc).isoformat(),
                    }
                    project.updated_at = utc_now()
                    archived.append({
                        "id": project.id,
                        "name": project.name,
                        "last_document": latest_doc.isoformat() if latest_doc else None,
                    })

            if archived:
                db.commit()
                print(f"[PARA] Auto-archived {len(archived)} stale projects for tenant {tenant_id[:8]}")

        except Exception as e:
            db.rollback()
            print(f"[PARA] Error auto-archiving: {e}")

        return archived

    def bulk_classify_projects(
        self,
        tenant_id: str,
        db,
        use_ai: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Classify all projects for a tenant.
        Skips projects with user_override_category=True unless force=True.

        Returns: {"classified": int, "skipped": int, "results": [...]}
        """
        from sqlalchemy import func

        query = db.query(Project).filter(Project.tenant_id == tenant_id)
        if not force:
            query = query.filter(Project.user_override_category == False)

        projects = query.all()
        results = []
        classified = 0
        skipped = 0

        for project in projects:
            # Skip if already classified with high confidence (unless forced)
            if (not force
                    and project.ai_classification_confidence
                    and project.ai_classification_confidence > 0.7
                    and project.para_category):
                skipped += 1
                continue

            # Get doc summaries for context
            doc_summaries = []
            docs = (
                db.query(Document.summary)
                .filter(
                    Document.project_id == project.id,
                    Document.tenant_id == tenant_id,
                    Document.summary.isnot(None),
                )
                .limit(5)
                .all()
            )
            doc_summaries = [d[0] for d in docs if d[0]]

            # Get last document date for staleness check
            latest_doc_date = (
                db.query(func.max(Document.created_at))
                .filter(
                    Document.project_id == project.id,
                    Document.tenant_id == tenant_id,
                )
                .scalar()
            )

            if use_ai:
                result = self.classify_project(
                    name=project.name,
                    description=project.description or "",
                    topic_words=project.topic_words or [],
                    doc_summaries=doc_summaries,
                )
            else:
                result = self.classify_project_heuristic(
                    name=project.name,
                    description=project.description or "",
                    topic_words=project.topic_words or [],
                    last_document_date=latest_doc_date,
                )

            project.para_category = result["category"]
            project.ai_classification_confidence = result["confidence"]
            project.ai_classification_reason = result["reason"]
            if result["category"] == "archives":
                project.is_archived = True
            project.updated_at = utc_now()

            classified += 1
            results.append({
                "id": project.id,
                "name": project.name,
                "category": result["category"],
                "confidence": result["confidence"],
            })

        db.commit()

        return {
            "classified": classified,
            "skipped": skipped,
            "results": results,
        }
