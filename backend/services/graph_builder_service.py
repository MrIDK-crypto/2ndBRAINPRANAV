"""
Graph Builder Service for 2nd Brain

Builds a knowledge graph from documents using structured_summary entities.
All storage in PostgreSQL (no Neo4j dependency).
Includes simple community detection via connected components.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from collections import defaultdict

from database.models import (
    SessionLocal, Document, GraphEntity, GraphRelation, GraphCommunity,
    GraphEntityType, GraphRelationType,
    utc_now, generate_uuid,
)


# Map structured_summary entity types to graph entity types
ENTITY_TYPE_MAP = {
    "people": GraphEntityType.PERSON,
    "systems": GraphEntityType.SYSTEM,
    "organizations": GraphEntityType.ORG,
}


class GraphBuilderService:
    """Build knowledge graph from document structured summaries."""

    def build_graph(
        self,
        tenant_id: str,
        db,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Build/update the knowledge graph for a tenant.
        Extracts entities and relations from Document.structured_summary.

        Returns: {"entities_created": int, "relations_created": int, "communities": int}
        """
        # Load documents with structured summaries
        documents = (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.is_deleted == False,
                Document.structured_summary.isnot(None),
            )
            .all()
        )

        if not documents:
            return {"entities_created": 0, "relations_created": 0, "communities": 0}

        if force:
            # Clear existing graph data
            db.query(GraphRelation).filter(GraphRelation.tenant_id == tenant_id).delete()
            db.query(GraphEntity).filter(GraphEntity.tenant_id == tenant_id).delete()
            db.query(GraphCommunity).filter(GraphCommunity.tenant_id == tenant_id).delete()
            db.commit()

        # Phase 1: Extract entities
        entity_map = {}  # (name_lower, type) -> GraphEntity
        entities_created = 0

        for doc in documents:
            structured = doc.structured_summary or {}
            entities = structured.get("entities") or {}

            for entity_category, entity_type in ENTITY_TYPE_MAP.items():
                for name in (entities.get(entity_category) or []):
                    name = name.strip()
                    if not name or len(name) < 2:
                        continue

                    key = (name.lower(), entity_type.value)
                    if key in entity_map:
                        # Update existing entity
                        ent = entity_map[key]
                        ent.mention_count = (ent.mention_count or 0) + 1
                        doc_ids = ent.document_ids or []
                        if doc.id not in doc_ids:
                            doc_ids.append(doc.id)
                            ent.document_ids = doc_ids
                            ent.document_count = len(doc_ids)
                    else:
                        # Check DB for existing
                        existing = (
                            db.query(GraphEntity)
                            .filter(
                                GraphEntity.tenant_id == tenant_id,
                                GraphEntity.canonical_name == name,
                                GraphEntity.entity_type == entity_type,
                            )
                            .first()
                        )
                        if existing:
                            existing.mention_count = (existing.mention_count or 0) + 1
                            doc_ids = existing.document_ids or []
                            if doc.id not in doc_ids:
                                doc_ids.append(doc.id)
                                existing.document_ids = doc_ids
                                existing.document_count = len(doc_ids)
                            entity_map[key] = existing
                        else:
                            ent = GraphEntity(
                                id=generate_uuid(),
                                tenant_id=tenant_id,
                                canonical_name=name,
                                entity_type=entity_type,
                                document_ids=[doc.id],
                                mention_count=1,
                                document_count=1,
                            )
                            db.add(ent)
                            entity_map[key] = ent
                            entities_created += 1

            # Also add key_topics as TOPIC entities
            for topic in (structured.get("key_topics") or []):
                topic = topic.strip()
                if not topic or len(topic) < 3:
                    continue
                key = (topic.lower(), "topic")
                if key not in entity_map:
                    existing = (
                        db.query(GraphEntity)
                        .filter(
                            GraphEntity.tenant_id == tenant_id,
                            GraphEntity.canonical_name == topic,
                            GraphEntity.entity_type == GraphEntityType.TOPIC,
                        )
                        .first()
                    )
                    if existing:
                        existing.mention_count = (existing.mention_count or 0) + 1
                        entity_map[key] = existing
                    else:
                        ent = GraphEntity(
                            id=generate_uuid(),
                            tenant_id=tenant_id,
                            canonical_name=topic,
                            entity_type=GraphEntityType.TOPIC,
                            document_ids=[doc.id],
                            mention_count=1,
                            document_count=1,
                        )
                        db.add(ent)
                        entity_map[key] = ent
                        entities_created += 1

        db.flush()

        # Phase 2: Create relations (co-occurrence in same document)
        relations_created = 0
        doc_entity_map = defaultdict(list)  # doc_id -> [(entity_key, entity)]

        for (name_lower, etype), ent in entity_map.items():
            for doc_id in (ent.document_ids or []):
                doc_entity_map[doc_id].append(ent)

        existing_rels = set()
        if not force:
            existing = (
                db.query(GraphRelation.source_entity_id, GraphRelation.target_entity_id)
                .filter(GraphRelation.tenant_id == tenant_id)
                .all()
            )
            for s, t in existing:
                existing_rels.add((s, t))

        for doc_id, entities in doc_entity_map.items():
            # Create RELATED_TO relations between entities in same document
            for i, ent_a in enumerate(entities):
                for ent_b in entities[i + 1:]:
                    if ent_a.id == ent_b.id:
                        continue
                    pair = (ent_a.id, ent_b.id)
                    rev_pair = (ent_b.id, ent_a.id)
                    if pair in existing_rels or rev_pair in existing_rels:
                        continue

                    # Determine relation type
                    rel_type = GraphRelationType.RELATED_TO
                    if ent_a.entity_type == GraphEntityType.PERSON and ent_b.entity_type == GraphEntityType.SYSTEM:
                        rel_type = GraphRelationType.USES
                    elif ent_a.entity_type == GraphEntityType.PERSON and ent_b.entity_type == GraphEntityType.ORG:
                        rel_type = GraphRelationType.MANAGES

                    rel = GraphRelation(
                        id=generate_uuid(),
                        tenant_id=tenant_id,
                        source_entity_id=ent_a.id,
                        target_entity_id=ent_b.id,
                        relation_type=rel_type,
                        confidence=0.6,
                        evidence_doc_ids=[doc_id],
                    )
                    db.add(rel)
                    existing_rels.add(pair)
                    relations_created += 1

        db.flush()

        # Phase 3: Simple community detection (connected components)
        communities_created = self._detect_communities(tenant_id, db, entity_map)

        db.commit()

        print(f"[GraphBuilder] Tenant {tenant_id[:8]}: {entities_created} entities, {relations_created} relations, {communities_created} communities")

        return {
            "entities_created": entities_created,
            "relations_created": relations_created,
            "communities": communities_created,
        }

    def _detect_communities(self, tenant_id: str, db, entity_map: dict) -> int:
        """Simple community detection using connected components via Union-Find."""
        # Clear existing communities
        db.query(GraphCommunity).filter(GraphCommunity.tenant_id == tenant_id).delete()

        # Load all relations for this tenant
        relations = (
            db.query(GraphRelation)
            .filter(GraphRelation.tenant_id == tenant_id)
            .all()
        )

        if not relations:
            return 0

        # Union-Find
        parent = {}
        def find(x):
            if x not in parent:
                parent[x] = x
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Build connected components from relations
        all_entity_ids = set()
        for rel in relations:
            all_entity_ids.add(rel.source_entity_id)
            all_entity_ids.add(rel.target_entity_id)
            union(rel.source_entity_id, rel.target_entity_id)

        # Group by component
        components = defaultdict(list)
        for eid in all_entity_ids:
            components[find(eid)].append(eid)

        # Create community for each component with 2+ entities
        communities_created = 0
        for root_id, members in components.items():
            if len(members) < 2:
                continue

            # Get entity names for naming the community
            entities = (
                db.query(GraphEntity)
                .filter(GraphEntity.id.in_(members))
                .all()
            )

            top_entities = sorted(entities, key=lambda e: e.mention_count or 0, reverse=True)[:5]
            community_name = " & ".join([e.canonical_name for e in top_entities[:3]])

            community = GraphCommunity(
                id=generate_uuid(),
                tenant_id=tenant_id,
                name=community_name,
                level=0,
                entity_count=len(members),
                top_entities=[{"name": e.canonical_name, "type": e.entity_type.value} for e in top_entities],
            )
            db.add(community)
            db.flush()

            # Assign community to entities
            for entity in entities:
                entity.community_id = community.id

            communities_created += 1

        return communities_created

    def get_graph_stats(self, tenant_id: str, db) -> Dict[str, Any]:
        """Get graph statistics."""
        from sqlalchemy import func

        entity_count = db.query(func.count(GraphEntity.id)).filter(GraphEntity.tenant_id == tenant_id).scalar() or 0
        relation_count = db.query(func.count(GraphRelation.id)).filter(GraphRelation.tenant_id == tenant_id).scalar() or 0
        community_count = db.query(func.count(GraphCommunity.id)).filter(GraphCommunity.tenant_id == tenant_id).scalar() or 0

        type_counts = (
            db.query(GraphEntity.entity_type, func.count(GraphEntity.id))
            .filter(GraphEntity.tenant_id == tenant_id)
            .group_by(GraphEntity.entity_type)
            .all()
        )

        entity_types = {}
        for et, count in type_counts:
            entity_types[et.value if hasattr(et, 'value') else str(et)] = count

        return {
            "total_entities": entity_count,
            "total_relations": relation_count,
            "total_communities": community_count,
            "entity_types": entity_types,
        }
