"""
GraphRAG Search Service for 2nd Brain

Hybrid search: Pinecone vector search + PostgreSQL knowledge graph traversal.
Adds graph context (entity neighborhood, community summaries) to RAG answers.
Falls back to pure vector search if graph is empty.
"""

from typing import Dict, List, Optional, Any
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.models import (
    GraphEntity, GraphRelation, GraphCommunity,
    GraphEntityType, GraphRelationType,
)


class GraphRAGSearchService:
    """Hybrid vector + graph search for enriched RAG answers."""

    def get_graph_context(
        self,
        query: str,
        tenant_id: str,
        db: Session,
        max_depth: int = 2,
        max_entities: int = 10,
    ) -> Dict[str, Any]:
        """
        Extract entities from query, traverse graph, return enriched context.

        Returns:
            {
                "entities": [...],
                "relations": [...],
                "communities": [...],
                "context_text": "...",  # Pre-formatted text for LLM context
            }
        """
        # Step 1: Find matching entities in the graph
        matched_entities = self._match_query_entities(query, tenant_id, db, max_entities)

        if not matched_entities:
            return {"entities": [], "relations": [], "communities": [], "context_text": ""}

        # Step 2: Graph traversal (1-2 hops)
        entity_ids = [e.id for e in matched_entities]
        neighborhood = self._traverse_graph(entity_ids, tenant_id, db, max_depth)

        # Step 3: Get community summaries
        community_ids = set()
        for ent in matched_entities:
            if ent.community_id:
                community_ids.add(ent.community_id)
        for ent in neighborhood["entities"]:
            if ent.get("community_id"):
                community_ids.add(ent["community_id"])

        communities = []
        if community_ids:
            community_objs = (
                db.query(GraphCommunity)
                .filter(
                    GraphCommunity.id.in_(list(community_ids)),
                    GraphCommunity.tenant_id == tenant_id,
                )
                .all()
            )
            communities = [c.to_dict() for c in community_objs]

        # Step 4: Build context text for LLM
        context_text = self._build_context_text(
            matched_entities, neighborhood, communities
        )

        return {
            "entities": [e.to_dict() for e in matched_entities],
            "relations": neighborhood["relations"],
            "communities": communities,
            "context_text": context_text,
        }

    def _match_query_entities(
        self,
        query: str,
        tenant_id: str,
        db: Session,
        max_entities: int = 10,
    ) -> List[GraphEntity]:
        """
        Find graph entities matching the query.
        Uses simple keyword matching against canonical_name and aliases.
        """
        # Tokenize query into meaningful words
        import re
        words = re.findall(r'\b[a-zA-Z]{3,}\b', query)
        if not words:
            return []

        # Search by ILIKE for each significant word
        matched = set()
        results = []

        for word in words[:10]:
            entities = (
                db.query(GraphEntity)
                .filter(
                    GraphEntity.tenant_id == tenant_id,
                    GraphEntity.canonical_name.ilike(f"%{word}%"),
                )
                .order_by(GraphEntity.mention_count.desc())
                .limit(5)
                .all()
            )
            for ent in entities:
                if ent.id not in matched:
                    matched.add(ent.id)
                    results.append(ent)

        # Sort by mention count (most referenced first)
        results.sort(key=lambda e: e.mention_count or 0, reverse=True)
        return results[:max_entities]

    def _traverse_graph(
        self,
        start_entity_ids: List[str],
        tenant_id: str,
        db: Session,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """
        BFS traversal from start entities up to max_depth hops.
        Uses recursive CTE in PostgreSQL for efficient traversal.
        """
        if not start_entity_ids:
            return {"entities": [], "relations": []}

        # Simple BFS using SQLAlchemy queries (works with both SQLite and PostgreSQL)
        visited_entities = set(start_entity_ids)
        all_relations = []
        frontier = set(start_entity_ids)

        for depth in range(max_depth):
            if not frontier:
                break

            # Find relations from frontier
            relations = (
                db.query(GraphRelation)
                .filter(
                    GraphRelation.tenant_id == tenant_id,
                    (
                        GraphRelation.source_entity_id.in_(list(frontier)) |
                        GraphRelation.target_entity_id.in_(list(frontier))
                    ),
                )
                .limit(50)
                .all()
            )

            next_frontier = set()
            for rel in relations:
                all_relations.append(rel.to_dict())
                # Add newly discovered entities
                for eid in [rel.source_entity_id, rel.target_entity_id]:
                    if eid not in visited_entities:
                        visited_entities.add(eid)
                        next_frontier.add(eid)

            frontier = next_frontier

        # Load all visited entities
        neighbor_entities = []
        if visited_entities - set(start_entity_ids):
            neighbors = (
                db.query(GraphEntity)
                .filter(GraphEntity.id.in_(list(visited_entities - set(start_entity_ids))))
                .all()
            )
            neighbor_entities = [e.to_dict() for e in neighbors]

        return {
            "entities": neighbor_entities,
            "relations": all_relations,
        }

    def _build_context_text(
        self,
        matched_entities: List[GraphEntity],
        neighborhood: Dict[str, Any],
        communities: List[Dict],
    ) -> str:
        """Build a structured text block for LLM context injection."""
        parts = []

        if matched_entities:
            entity_lines = []
            for ent in matched_entities[:8]:
                etype = ent.entity_type.value if hasattr(ent.entity_type, 'value') else str(ent.entity_type)
                entity_lines.append(
                    f"- {ent.canonical_name} ({etype}, mentioned {ent.mention_count}x across {ent.document_count} docs)"
                )
            parts.append("Relevant entities:\n" + "\n".join(entity_lines))

        if neighborhood.get("relations"):
            rel_lines = []
            seen = set()
            for rel in neighborhood["relations"][:12]:
                src = rel.get("source_name", "?")
                tgt = rel.get("target_name", "?")
                rtype = rel.get("relation_type", "related_to")
                key = f"{src}-{rtype}-{tgt}"
                if key not in seen:
                    seen.add(key)
                    rel_lines.append(f"- {src} --[{rtype}]--> {tgt}")
            if rel_lines:
                parts.append("Knowledge graph connections:\n" + "\n".join(rel_lines))

        if communities:
            comm_lines = []
            for comm in communities[:3]:
                summary = comm.get("summary") or f"Cluster of {comm.get('entity_count', 0)} entities"
                top = ", ".join([e["name"] for e in (comm.get("top_entities") or [])[:4]])
                comm_lines.append(f"- {comm['name']}: {summary}" + (f" (includes: {top})" if top else ""))
            if comm_lines:
                parts.append("Topic communities:\n" + "\n".join(comm_lines))

        return "\n\n".join(parts) if parts else ""
