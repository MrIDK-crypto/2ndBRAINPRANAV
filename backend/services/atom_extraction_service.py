"""
Atom Extraction Service for 2nd Brain

Extracts Knowledge Atoms from documents using structured_summary data.
Maps extraction fields to atom types:
  - decisions[]    → DECISION atoms
  - processes[]    → PROCESS atoms
  - key_topics[]   → CONCEPT atoms
  - action_items[] → INSIGHT atoms
  - entities       → FACT atoms (people/systems as named facts)

Link discovery via entity co-occurrence across atoms.
"""

import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from collections import defaultdict

from database.models import (
    SessionLocal, Document, KnowledgeAtom, AtomLink,
    AtomType, AtomLinkType, utc_now, generate_uuid,
)


class AtomExtractionService:
    """Extract Knowledge Atoms from document structured summaries."""

    def extract_from_document(
        self,
        document: Document,
        tenant_id: str,
        db,
    ) -> List[KnowledgeAtom]:
        """
        Extract atoms from a single document's structured_summary.
        Returns list of created KnowledgeAtom instances (already added to db session).
        """
        structured = document.structured_summary
        if not structured:
            return []

        atoms = []

        # DECISION atoms
        for decision in (structured.get("decisions") or []):
            if not decision or len(decision.strip()) < 10:
                continue
            atom = KnowledgeAtom(
                id=generate_uuid(),
                tenant_id=tenant_id,
                title=self._make_title(decision, "Decision"),
                content=decision,
                atom_type=AtomType.DECISION,
                source_document_id=document.id,
                project_id=document.project_id,
                extraction_confidence=0.7,
                extraction_metadata={"source_field": "decisions"},
            )
            db.add(atom)
            atoms.append(atom)

        # PROCESS atoms
        for process in (structured.get("processes") or []):
            if not process or len(process.strip()) < 10:
                continue
            atom = KnowledgeAtom(
                id=generate_uuid(),
                tenant_id=tenant_id,
                title=self._make_title(process, "Process"),
                content=process,
                atom_type=AtomType.PROCESS,
                source_document_id=document.id,
                project_id=document.project_id,
                extraction_confidence=0.7,
                extraction_metadata={"source_field": "processes"},
            )
            db.add(atom)
            atoms.append(atom)

        # CONCEPT atoms from key topics
        for topic in (structured.get("key_topics") or []):
            if not topic or len(topic.strip()) < 3:
                continue
            # Build content from summary context
            summary = structured.get("summary", "")
            content = f"Key topic: {topic}"
            if summary:
                content += f"\n\nContext: {summary}"
            atom = KnowledgeAtom(
                id=generate_uuid(),
                tenant_id=tenant_id,
                title=topic,
                content=content,
                atom_type=AtomType.CONCEPT,
                source_document_id=document.id,
                project_id=document.project_id,
                extraction_confidence=0.6,
                extraction_metadata={"source_field": "key_topics"},
            )
            db.add(atom)
            atoms.append(atom)

        # INSIGHT atoms from action items
        for item in (structured.get("action_items") or []):
            if not item or len(item.strip()) < 10:
                continue
            atom = KnowledgeAtom(
                id=generate_uuid(),
                tenant_id=tenant_id,
                title=self._make_title(item, "Action"),
                content=item,
                atom_type=AtomType.INSIGHT,
                source_document_id=document.id,
                project_id=document.project_id,
                extraction_confidence=0.65,
                extraction_metadata={"source_field": "action_items"},
            )
            db.add(atom)
            atoms.append(atom)

        # FACT atoms from key entities (people, systems)
        entities = structured.get("entities") or {}
        for person in (entities.get("people") or [])[:5]:
            if not person or len(person.strip()) < 2:
                continue
            atom = KnowledgeAtom(
                id=generate_uuid(),
                tenant_id=tenant_id,
                title=person,
                content=f"Person mentioned in: {document.title or 'Untitled'}",
                atom_type=AtomType.FACT,
                source_document_id=document.id,
                project_id=document.project_id,
                extraction_confidence=0.5,
                extraction_metadata={"source_field": "entities.people", "entity_type": "person"},
            )
            db.add(atom)
            atoms.append(atom)

        for system in (entities.get("systems") or [])[:5]:
            if not system or len(system.strip()) < 2:
                continue
            atom = KnowledgeAtom(
                id=generate_uuid(),
                tenant_id=tenant_id,
                title=system,
                content=f"System/tool referenced in: {document.title or 'Untitled'}",
                atom_type=AtomType.FACT,
                source_document_id=document.id,
                project_id=document.project_id,
                extraction_confidence=0.5,
                extraction_metadata={"source_field": "entities.systems", "entity_type": "system"},
            )
            db.add(atom)
            atoms.append(atom)

        return atoms

    def _make_title(self, text: str, prefix: str) -> str:
        """Create a concise title from content text."""
        clean = text.strip()
        if len(clean) <= 80:
            return clean
        # Truncate at word boundary
        truncated = clean[:77]
        last_space = truncated.rfind(' ')
        if last_space > 40:
            truncated = truncated[:last_space]
        return truncated + "..."

    def discover_links(
        self,
        tenant_id: str,
        db,
        max_atoms: int = 500,
    ) -> int:
        """
        Discover links between atoms based on:
        1. Same source document → RELATED
        2. Title/content overlap → RELATED
        3. Same entity name across documents → ELABORATES

        Returns count of new links created.
        """
        atoms = (
            db.query(KnowledgeAtom)
            .filter(
                KnowledgeAtom.tenant_id == tenant_id,
                KnowledgeAtom.is_deleted == False,
            )
            .order_by(KnowledgeAtom.created_at.desc())
            .limit(max_atoms)
            .all()
        )

        if len(atoms) < 2:
            return 0

        # Group by source document
        doc_atoms = defaultdict(list)
        for atom in atoms:
            if atom.source_document_id:
                doc_atoms[atom.source_document_id].append(atom)

        # Group by normalized title (for entity co-occurrence)
        title_atoms = defaultdict(list)
        for atom in atoms:
            key = atom.title.strip().lower()
            title_atoms[key].append(atom)

        # Existing links (to avoid duplicates)
        existing_links = set()
        existing = (
            db.query(AtomLink.source_atom_id, AtomLink.target_atom_id, AtomLink.link_type)
            .filter(AtomLink.tenant_id == tenant_id)
            .all()
        )
        for src, tgt, lt in existing:
            existing_links.add((src, tgt, lt.value if hasattr(lt, 'value') else lt))

        links_created = 0

        # 1. Same document → RELATED (cross-type only, to avoid noise)
        for doc_id, group in doc_atoms.items():
            for i, a in enumerate(group):
                for b in group[i + 1:]:
                    if a.atom_type == b.atom_type:
                        continue  # Skip same-type from same doc
                    key = (a.id, b.id, "related")
                    rev_key = (b.id, a.id, "related")
                    if key in existing_links or rev_key in existing_links:
                        continue
                    link = AtomLink(
                        id=generate_uuid(),
                        tenant_id=tenant_id,
                        source_atom_id=a.id,
                        target_atom_id=b.id,
                        link_type=AtomLinkType.RELATED,
                        confidence=0.6,
                        reason="Co-occur in same document",
                    )
                    db.add(link)
                    existing_links.add(key)
                    links_created += 1

        # 2. Same entity title across documents → ELABORATES
        for title_key, group in title_atoms.items():
            if len(group) < 2:
                continue
            # Link first to subsequent (not all pairs, to limit explosion)
            anchor = group[0]
            for other in group[1:]:
                if anchor.source_document_id == other.source_document_id:
                    continue
                key = (anchor.id, other.id, "elaborates")
                rev_key = (other.id, anchor.id, "elaborates")
                if key in existing_links or rev_key in existing_links:
                    continue
                link = AtomLink(
                    id=generate_uuid(),
                    tenant_id=tenant_id,
                    source_atom_id=other.id,
                    target_atom_id=anchor.id,
                    link_type=AtomLinkType.ELABORATES,
                    confidence=0.7,
                    reason=f"Same entity '{title_key}' across documents",
                )
                db.add(link)
                existing_links.add(key)
                links_created += 1

        if links_created > 0:
            db.commit()
            print(f"[AtomExtraction] Created {links_created} links for tenant {tenant_id[:8]}")

        return links_created

    def extract_for_tenant(
        self,
        tenant_id: str,
        db,
        force: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Extract atoms from all documents for a tenant.
        Skips documents that already have atoms extracted (unless force=True).

        Returns: {"documents_processed": int, "atoms_created": int, "links_created": int}
        """
        from sqlalchemy import func

        # Find documents with structured summaries
        query = (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.is_deleted == False,
                Document.structured_summary.isnot(None),
            )
        )

        if not force:
            # Skip documents that already have atoms
            docs_with_atoms = (
                db.query(KnowledgeAtom.source_document_id)
                .filter(
                    KnowledgeAtom.tenant_id == tenant_id,
                    KnowledgeAtom.is_deleted == False,
                )
                .distinct()
                .subquery()
            )
            query = query.filter(~Document.id.in_(db.query(docs_with_atoms)))

        documents = query.order_by(Document.created_at.desc()).limit(limit).all()

        total_atoms = 0
        docs_processed = 0

        for doc in documents:
            atoms = self.extract_from_document(doc, tenant_id, db)
            total_atoms += len(atoms)
            docs_processed += 1

        if total_atoms > 0:
            db.commit()

        # Discover links
        links_created = self.discover_links(tenant_id, db)

        print(f"[AtomExtraction] Tenant {tenant_id[:8]}: {docs_processed} docs, {total_atoms} atoms, {links_created} links")

        return {
            "documents_processed": docs_processed,
            "atoms_created": total_atoms,
            "links_created": links_created,
        }
