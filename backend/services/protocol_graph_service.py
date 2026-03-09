"""
Protocol Knowledge Graph Service — Extract entities and relationships from protocol documents.
Builds a queryable knowledge graph of techniques, reagents, equipment, and their relationships.
"""

import json
import logging
import os
from database.models import ProtocolEntity, ProtocolRelation, ProtocolCooccurrence, Document
from sqlalchemy import or_

logger = logging.getLogger(__name__)


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

    def build_cooccurrences_from_corpus(self, db, tenant_id=None):
        """
        Build co-occurrence table from existing protocol graph entities.
        Scans all documents with extracted entities and creates technique-target pairs.
        """
        from sqlalchemy import func

        # Get all documents that have entities
        doc_ids_query = db.query(ProtocolEntity.document_id).distinct()
        if tenant_id:
            doc_ids_query = doc_ids_query.filter(ProtocolEntity.tenant_id == tenant_id)
        doc_ids = [r[0] for r in doc_ids_query.all() if r[0]]

        logger.info(f"[ProtocolGraph] Building co-occurrences from {len(doc_ids)} documents")

        cooc_count = 0
        for doc_id in doc_ids:
            entities = db.query(ProtocolEntity).filter(
                ProtocolEntity.document_id == doc_id
            ).all()

            techniques = [e for e in entities if e.entity_type == 'technique']
            targets = [e for e in entities if e.entity_type != 'technique']

            for tech in techniques:
                for target in targets:
                    # Upsert co-occurrence
                    existing = db.query(ProtocolCooccurrence).filter(
                        ProtocolCooccurrence.technique_entity_id == tech.id,
                        ProtocolCooccurrence.target_entity_id == target.id,
                    ).first()

                    if existing:
                        existing.cooccurrence_count += 1
                        if existing.source_protocols is None:
                            existing.source_protocols = []
                        existing.source_protocols.append({"document_id": doc_id})
                        existing.confidence = min(1.0, existing.cooccurrence_count / 10.0)
                    else:
                        cooc = ProtocolCooccurrence(
                            tenant_id=tenant_id,
                            technique_entity_id=tech.id,
                            target_entity_id=target.id,
                            target_type=target.entity_type,
                            cooccurrence_count=1,
                            source_protocols=[{"document_id": doc_id}],
                            confidence=0.1,
                        )
                        db.add(cooc)
                        cooc_count += 1

            if cooc_count % 100 == 0 and cooc_count > 0:
                db.commit()

        db.commit()
        logger.info(f"[ProtocolGraph] Created {cooc_count} new co-occurrence records")
        return cooc_count

    def embed_entities_to_pinecone(self, db, vector_store, embedding_client, tenant_id=None):
        """
        Embed all protocol entities into Pinecone for semantic lookup.
        Namespace: protocol-entities
        """
        import hashlib
        deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

        query = db.query(ProtocolEntity)
        if tenant_id:
            query = query.filter(ProtocolEntity.tenant_id == tenant_id)
        entities = query.all()

        logger.info(f"[ProtocolGraph] Embedding {len(entities)} entities to Pinecone")

        vectors_batch = []
        embedded = 0

        for entity in entities:
            # Build text: name + type + attributes
            text = f"{entity.entity_type}: {entity.name}"
            if entity.attributes:
                attrs = entity.attributes if isinstance(entity.attributes, dict) else {}
                attr_text = ", ".join(f"{k}={v}" for k, v in attrs.items())
                if attr_text:
                    text += f" ({attr_text})"

            vec_id = hashlib.md5(f"pe-{entity.id}".encode()).hexdigest()

            try:
                resp = embedding_client.embeddings.create(
                    model=deployment,
                    input=text[:500],
                    dimensions=1536,
                )
                vectors_batch.append({
                    "id": vec_id,
                    "values": resp.data[0].embedding,
                    "metadata": {
                        "entity_id": entity.id,
                        "name": entity.name,
                        "normalized_name": entity.normalized_name,
                        "entity_type": entity.entity_type,
                        "text": text[:200],
                    }
                })
                embedded += 1

                if len(vectors_batch) >= 50:
                    vector_store.index.upsert(vectors=vectors_batch, namespace="protocol-entities")
                    vectors_batch = []
            except Exception as e:
                logger.debug(f"Entity embedding failed for {entity.name}: {e}")

        if vectors_batch:
            vector_store.index.upsert(vectors=vectors_batch, namespace="protocol-entities")

        logger.info(f"[ProtocolGraph] Embedded {embedded} entities")
        return embedded

    def build_cooccurrences_from_corpus_file(self, corpus_file: str, db, tenant_id=None):
        """
        Build co-occurrences directly from unified_corpus.jsonl without LLM extraction.
        Uses structured fields (steps, reagents, equipment) from the corpus.
        """
        from pathlib import Path

        corpus_path = Path(corpus_file)
        if not corpus_path.exists():
            logger.warning(f"[ProtocolGraph] Corpus file not found: {corpus_file}")
            return 0

        logger.info(f"[ProtocolGraph] Building co-occurrences from corpus: {corpus_file}")

        # First pass: collect all unique entities and normalize
        entity_cache = {}  # normalized_name -> ProtocolEntity

        def get_or_create_entity(name: str, entity_type: str) -> str:
            """Get or create a protocol entity, return its ID."""
            normalized = name.lower().strip()
            cache_key = f"{entity_type}:{normalized}"

            if cache_key in entity_cache:
                return entity_cache[cache_key]

            existing = db.query(ProtocolEntity).filter(
                ProtocolEntity.normalized_name == normalized,
                ProtocolEntity.entity_type == entity_type,
            ).first()

            if existing:
                entity_cache[cache_key] = existing
                return existing

            entity = ProtocolEntity(
                tenant_id=tenant_id,
                entity_type=entity_type,
                name=name.strip(),
                normalized_name=normalized,
            )
            db.add(entity)
            db.flush()
            entity_cache[cache_key] = entity
            return entity

        cooc_count = 0
        protocols_processed = 0

        with open(corpus_path, "r") as f:
            for line in f:
                try:
                    protocol = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Extract techniques from steps
                techniques = set()
                steps = protocol.get("steps", [])
                for step in steps:
                    verb = step.get("action_verb", "") if isinstance(step, dict) else ""
                    if verb:
                        techniques.add(verb.lower())

                reagents = protocol.get("reagents", [])
                equipment = protocol.get("equipment", [])

                if not techniques or (not reagents and not equipment):
                    continue

                # Create entities and co-occurrences
                for tech_name in techniques:
                    tech_entity = get_or_create_entity(tech_name, "technique")

                    for reagent_name in reagents[:10]:
                        if not reagent_name or len(reagent_name) < 2:
                            continue
                        target_entity = get_or_create_entity(reagent_name, "reagent")

                        existing = db.query(ProtocolCooccurrence).filter(
                            ProtocolCooccurrence.technique_entity_id == tech_entity.id,
                            ProtocolCooccurrence.target_entity_id == target_entity.id,
                        ).first()

                        if existing:
                            existing.cooccurrence_count += 1
                            existing.confidence = min(1.0, existing.cooccurrence_count / 10.0)
                        else:
                            db.add(ProtocolCooccurrence(
                                tenant_id=tenant_id,
                                technique_entity_id=tech_entity.id,
                                target_entity_id=target_entity.id,
                                target_type="reagent",
                                cooccurrence_count=1,
                                source_protocols=[{"source": protocol.get("source", ""), "title": protocol.get("title", "")}],
                                confidence=0.1,
                            ))
                            cooc_count += 1

                    for equip_name in equipment[:10]:
                        if not equip_name or len(equip_name) < 2:
                            continue
                        target_entity = get_or_create_entity(equip_name, "equipment")

                        existing = db.query(ProtocolCooccurrence).filter(
                            ProtocolCooccurrence.technique_entity_id == tech_entity.id,
                            ProtocolCooccurrence.target_entity_id == target_entity.id,
                        ).first()

                        if existing:
                            existing.cooccurrence_count += 1
                            existing.confidence = min(1.0, existing.cooccurrence_count / 10.0)
                        else:
                            db.add(ProtocolCooccurrence(
                                tenant_id=tenant_id,
                                technique_entity_id=tech_entity.id,
                                target_entity_id=target_entity.id,
                                target_type="equipment",
                                cooccurrence_count=1,
                                source_protocols=[{"source": protocol.get("source", ""), "title": protocol.get("title", "")}],
                                confidence=0.1,
                            ))
                            cooc_count += 1

                protocols_processed += 1
                if protocols_processed % 1000 == 0:
                    db.commit()
                    logger.info(f"[ProtocolGraph] Processed {protocols_processed} protocols, {cooc_count} co-occurrences")

        db.commit()
        logger.info(f"[ProtocolGraph] Corpus processing complete: {protocols_processed} protocols, {cooc_count} co-occurrences")
        return cooc_count
