# Protocol Feasibility Pipeline + Intelligent Chatbot Router

**Date:** 2026-03-08
**Status:** Approved

## Decisions

- **Intent routing:** LLM classifier (gpt-4o-mini) replaces keyword pattern matching
- **Knowledge graph storage:** PostgreSQL + Pinecone hybrid (structured queries in PG, semantic similarity in Pinecone)
- **BioProBench usage:** RAG over embedded instances now, swappable for fine-tuned model later (approach C)
- **Journal coverage:** 30 journals deep extraction (TEI XML), 10K+ journals abstract/metadata indexing, on-demand for rest

## Architecture

```
User Query → LLM Intent Classifier → Route to:
  - rag_search (existing)
  - experiment_suggestion → Model A (GPT-5) + Model B (Feasibility Checker v2)
  - protocol_feasibility → Co-occurrence graph + BioProBench RAG + LLM reasoning
  - journal_analysis (existing, enriched with 10K journal data)
  - methodology_analysis (existing)
  - knowledge_gap (existing)
  - literature_search (existing)
  - general (existing)
```

## New Components

### 1. Intent Classifier (`services/intent_classifier.py`)
- Single gpt-4o-mini call, ~50 tokens output
- Returns: {intent, confidence, sub_intents[], source_weights}
- Considers conversation history

### 2. Data Ingestion Pipeline
- BioProBench 27K protocols, 556K instances → Pinecone `protocol-corpus`
- protocols.io 50K+ → Postgres protocol graph + Pinecone
- OpenAlex 30 journals TEI XML → Postgres co-occurrences
- OpenAlex 10K+ journals abstracts → Pinecone `journal-abstracts`

### 3. Protocol Knowledge Graph v2
- New `ProtocolCooccurrence` table (technique-reagent-system edges with counts)
- Entity embeddings in Pinecone `protocol-entities` namespace
- Negative evidence tracking (never co-occurring pairs = incompatibility)

### 4. Feasibility Checker v2
- Extract technique-reagent-system triples from proposal
- Query co-occurrence graph (Postgres)
- RAG over BioProBench (Pinecone)
- LLM reasoning with evidence (GPT-5)
- Output: {score, issues, modifications, evidence}
- Behind `protocol_reasoning()` abstraction (swappable for fine-tuned model)

### 5. Two-Model Experiment Pipeline
- Model A: GPT-5 creative suggestions
- Model B: Feasibility Checker v2 validation
- Failed suggestions get modification notes

## Database Changes

```sql
CREATE TABLE protocol_cooccurrence (
  id UUID PRIMARY KEY,
  tenant_id UUID,
  technique_entity_id UUID REFERENCES protocol_entity(id),
  target_entity_id UUID REFERENCES protocol_entity(id),
  target_type VARCHAR(50),
  cooccurrence_count INTEGER DEFAULT 1,
  source_protocols JSONB,
  confidence FLOAT DEFAULT 0.0,
  first_seen TIMESTAMP,
  last_seen TIMESTAMP
);
```

## Pinecone Namespaces

| Namespace | Content | Est. Vectors |
|-----------|---------|-------------|
| (default) | User KB | existing |
| protocol-corpus | BioProBench + protocols.io | ~500K |
| protocol-entities | Entity embeddings | ~100K |
| journal-abstracts | 10K+ journal abstracts | ~1M+ |

## Build Order

1. Intent Classifier
2. Database models (ProtocolCooccurrence)
3. BioProBench embedding pipeline
4. Protocol Knowledge Graph v2 (co-occurrence extraction)
5. OpenAlex Tier 2 (10K journal abstracts)
6. OpenAlex Tier 1 (30 journal TEI XML methods)
7. Feasibility Checker v2
8. Experiment Suggestion upgrade (Model A → Model B)
9. Chatbot integration (SSE events, intent routing)
10. Frontend updates (feasibility display, protocol evidence)

## Files

| File | Action |
|------|--------|
| services/intent_classifier.py | NEW |
| services/feasibility_checker.py | NEW |
| services/protocol_reasoning.py | NEW |
| protocol_training/ingest_openalex_methods.py | NEW |
| protocol_training/ingest_bioprotocolbench_embeddings.py | NEW |
| protocol_training/ingest_journal_abstracts.py | NEW |
| database/models.py | MODIFY |
| services/protocol_graph_service.py | MODIFY |
| services/experiment_suggestion_service.py | MODIFY |
| app_v2.py | MODIFY |
| services/enhanced_search_service.py | MODIFY |
| tasks/protocol_training_tasks.py | MODIFY |
| frontend/components/co-work/CoWorkChat.tsx | MODIFY |
| frontend/components/co-work/CoWorkContext.tsx | MODIFY |
