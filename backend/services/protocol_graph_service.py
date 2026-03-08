"""
Protocol Knowledge Graph Service — Extract entities and relationships from protocol documents.
Builds a queryable knowledge graph of techniques, reagents, equipment, and their relationships.
"""

import json
from database.models import ProtocolEntity, ProtocolRelation, Document
from sqlalchemy import or_


class ProtocolGraphService:
    """Extract and query protocol knowledge graphs."""

    ENTITY_TYPES = ['technique', 'reagent', 'equipment', 'parameter', 'organism', 'cell_line', 'buffer', 'assay']
    RELATION_TYPES = ['uses', 'requires', 'produces', 'follows', 'conflicts_with', 'alternative_to', 'measured_by']

    def __init__(self, llm_client, chat_deployment: str):
        self.llm_client = llm_client
        self.chat_deployment = chat_deployment

    def extract_entities_from_document(self, document, tenant_id: str, db) -> list:
        """Extract protocol entities and relationships from a document using LLM.

        Args:
            document: Document ORM object with .content
            tenant_id: Tenant ID for isolation
            db: Database session

        Returns:
            List of extracted entity dicts
        """
        content = (document.content or '')[:8000]  # Cap for LLM context
        if len(content) < 50:
            return []

        try:
            response = self.llm_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[{
                    'role': 'system',
                    'content': '''Extract protocol entities and relationships from this lab document.

Return JSON:
{
  "entities": [
    {"type": "technique|reagent|equipment|parameter|organism|cell_line|buffer|assay", "name": "...", "attributes": {}}
  ],
  "relations": [
    {"source": "entity_name", "target": "entity_name", "type": "uses|requires|produces|follows|conflicts_with|alternative_to|measured_by", "context": "brief description"}
  ]
}

Only extract entities clearly mentioned. Do not infer or guess. Keep attributes factual (concentrations, temperatures, volumes, etc.).'''
                }, {
                    'role': 'user',
                    'content': content
                }],
                temperature=0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[ProtocolGraph] LLM extraction failed: {e}")
            return []

        # Store entities
        entity_map = {}
        entities_created = []
        for ent in result.get('entities', []):
            ent_name = ent.get('name', '').strip()
            ent_type = ent.get('type', 'technique')
            if not ent_name or ent_type not in self.ENTITY_TYPES:
                continue

            entity = ProtocolEntity(
                tenant_id=tenant_id,
                document_id=document.id,
                entity_type=ent_type,
                name=ent_name,
                normalized_name=ent_name.lower().strip(),
                attributes=ent.get('attributes', {}),
            )
            db.add(entity)
            db.flush()
            entity_map[ent_name.lower()] = entity.id
            entities_created.append(entity.to_dict())

        # Store relations
        for rel in result.get('relations', []):
            src_name = (rel.get('source', '') or '').lower()
            tgt_name = (rel.get('target', '') or '').lower()
            rel_type = rel.get('type', 'uses')

            src_id = entity_map.get(src_name)
            tgt_id = entity_map.get(tgt_name)
            if src_id and tgt_id and rel_type in self.RELATION_TYPES:
                relation = ProtocolRelation(
                    tenant_id=tenant_id,
                    document_id=document.id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type=rel_type,
                    confidence=1.0,
                    context=rel.get('context', ''),
                )
                db.add(relation)

        try:
            db.commit()
            print(f"[ProtocolGraph] Extracted {len(entities_created)} entities from document {document.id}")
        except Exception as e:
            db.rollback()
            print(f"[ProtocolGraph] DB commit failed: {e}")
            return []

        return entities_created

    def query_graph(self, tenant_id: str, db, entity_name: str = None,
                    entity_type: str = None) -> dict:
        """Query the protocol knowledge graph.

        Args:
            tenant_id: Tenant ID for isolation
            db: Database session
            entity_name: Optional filter by entity name (partial match)
            entity_type: Optional filter by entity type

        Returns:
            Dict with entities and relations
        """
        query = db.query(ProtocolEntity).filter(ProtocolEntity.tenant_id == tenant_id)

        if entity_name:
            query = query.filter(ProtocolEntity.normalized_name.ilike(f'%{entity_name.lower()}%'))
        if entity_type:
            query = query.filter(ProtocolEntity.entity_type == entity_type)

        entities = query.limit(100).all()
        entity_ids = [e.id for e in entities]

        relations = []
        if entity_ids:
            relations = db.query(ProtocolRelation).filter(
                ProtocolRelation.tenant_id == tenant_id,
                or_(
                    ProtocolRelation.source_entity_id.in_(entity_ids),
                    ProtocolRelation.target_entity_id.in_(entity_ids),
                )
            ).limit(200).all()

        return {
            'entities': [e.to_dict() for e in entities],
            'relations': [r.to_dict() for r in relations],
            'entity_count': len(entities),
            'relation_count': len(relations),
        }
