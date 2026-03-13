# Research Methodology System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve knowledge gaps, RAG (co-work) quality, and high-impact journal methodology with OpenAlex citation graphs, protocol knowledge graphs, experiment suggestions, and feasibility scoring.

**Architecture:** Extend existing infrastructure (OpenAlex in `journal_data_service.py`, PubMed in `pubmed_connector.py`, protocol patterns in `protocol_patterns.py`, gap detector in `intelligent_gap_detector.py`, co-researcher in `co_researcher_service.py`) rather than building from scratch. Add new services for citation graph analysis, protocol knowledge graph, experiment suggestion, and feasibility scoring. All changes are additive — no breaking modifications to existing endpoints or data flows.

**Tech Stack:** Flask, SQLAlchemy, PostgreSQL (RDS), Pinecone (knowledgevault index, 1536-dim), Azure OpenAI (GPT-5, text-embedding-3-large), OpenAlex API, CrossRef, spaCy, NetworkX, Next.js 14, SSE streaming

---

## Phase 1: Knowledge Gaps Improvements

### Task 1: Smarter Gap Prioritization with User Feedback Loop

**Files:**
- Modify: `backend/services/intelligent_gap_detector.py`
- Modify: `backend/api/knowledge_routes.py`
- Modify: `backend/database/models.py`

**Step 1: Add priority learning fields to KnowledgeGap model**

In `backend/database/models.py`, add to the `KnowledgeGap` class (after line ~1089):

```python
# Priority learning
auto_priority_score = Column(Float, default=0.0)  # ML-derived priority
priority_signals = Column(JSON, default=dict)  # {recency, frequency, cross_ref_count, user_boost}
```

**Step 2: Build priority scoring function**

In `backend/services/intelligent_gap_detector.py`, add a method that scores gaps based on:
- How many documents reference the gap topic (cross-reference density)
- Recency of related documents (fresher = higher priority)
- User feedback history (gaps marked "useful" in same category get boosted)
- Bus factor (knowledge held by single person = critical)

```python
def compute_auto_priority(self, gap_data: dict, all_docs: list, feedback_history: list) -> float:
    """Score 0-1 based on cross-ref density, recency, feedback, bus factor."""
    score = 0.0
    topic_terms = set(gap_data.get('title', '').lower().split())

    # Cross-reference density (0-0.3)
    ref_count = sum(1 for doc in all_docs if any(t in doc.get('content', '').lower() for t in topic_terms))
    score += min(0.3, ref_count / max(len(all_docs), 1) * 3)

    # Recency boost (0-0.2)
    related_docs = [d for d in all_docs if any(t in d.get('content', '').lower() for t in topic_terms)]
    if related_docs:
        from datetime import datetime, timedelta
        recent = sum(1 for d in related_docs if d.get('created_at') and
                     (datetime.utcnow() - d['created_at']).days < 30)
        score += min(0.2, recent / max(len(related_docs), 1) * 0.4)

    # Feedback boost (0-0.3) — same category gaps marked useful
    category = gap_data.get('category', '')
    useful_in_cat = sum(1 for f in feedback_history if f.get('category') == category and f.get('useful'))
    score += min(0.3, useful_in_cat * 0.1)

    # Bus factor (0-0.2) — single-person knowledge
    if gap_data.get('context', {}).get('bus_factor_person'):
        score += 0.2

    return round(min(1.0, score), 3)
```

**Step 3: Wire priority scoring into gap analysis endpoint**

In `backend/api/knowledge_routes.py`, after gaps are created in the `analyze` endpoint, call `compute_auto_priority` for each gap and store the result in `auto_priority_score` and `priority_signals`.

**Step 4: Add sort-by-priority option to GET /api/knowledge/gaps**

Add `?sort=priority` query param that orders by `auto_priority_score DESC` instead of `created_at DESC`.

**Step 5: Test manually**

Run: `curl -X POST http://localhost:5003/api/knowledge/analyze -H "Authorization: Bearer $TOKEN" -d '{"mode":"intelligent"}' | python3 -m json.tool`
Verify gaps have `auto_priority_score` values.

**Step 6: Commit**

```bash
git add backend/database/models.py backend/services/intelligent_gap_detector.py backend/api/knowledge_routes.py
git commit -m "feat: smart gap prioritization with feedback learning"
```

---

### Task 2: Gap Deduplication Across Runs with Merge

**Files:**
- Modify: `backend/services/intelligent_gap_detector.py`
- Modify: `backend/api/knowledge_routes.py`

**Step 1: Improve fingerprint to catch near-duplicates**

The current fingerprint is MD5 of (category + questions + evidence). Enhance it to also do fuzzy matching — if a new gap's title has >80% token overlap with an existing gap, merge them instead of creating a duplicate.

In `intelligent_gap_detector.py`, add:

```python
def _find_similar_existing_gap(self, new_gap: dict, existing_gaps: list) -> Optional[dict]:
    """Find existing gap with >80% title token overlap."""
    new_tokens = set(new_gap.get('title', '').lower().split())
    if len(new_tokens) < 3:
        return None
    for existing in existing_gaps:
        existing_tokens = set(existing.title.lower().split())
        if not existing_tokens:
            continue
        overlap = len(new_tokens & existing_tokens) / max(len(new_tokens | existing_tokens), 1)
        if overlap > 0.8:
            return existing
    return None
```

**Step 2: Merge logic — update existing gap instead of creating new**

When a near-duplicate is found:
- Append new questions that don't already exist
- Update priority if new score is higher
- Bump `updated_at`
- Don't create a new row

**Step 3: Add merge count display**

In the analyze response, include `{"merged": 3, "new": 7, "total": 10}` so the frontend can show "3 gaps updated, 7 new gaps found".

**Step 4: Test manually**

Run analysis twice on same documents. Second run should merge, not duplicate.

**Step 5: Commit**

```bash
git add backend/services/intelligent_gap_detector.py backend/api/knowledge_routes.py
git commit -m "feat: gap deduplication with fuzzy merge across runs"
```

---

### Task 3: Knowledge Gap Context Enrichment from RAG

**Files:**
- Modify: `backend/api/knowledge_routes.py`
- Modify: `backend/services/knowledge_service.py`

**Step 1: Add endpoint to enrich a gap with RAG context**

When a user views a gap, fetch relevant context from the knowledge base (Pinecone) and PubMed to show what's already known vs. what's missing.

```python
@knowledge_bp.route('/gaps/<int:gap_id>/enrich', methods=['POST'])
@jwt_required
def enrich_gap(gap_id):
    """Enrich a gap with RAG context showing known vs. missing info."""
    gap = KnowledgeGap.query.get_or_404(gap_id)

    # Search KB for related content
    from services.enhanced_search_service import EnhancedSearchService
    search = EnhancedSearchService()
    results = search.search(gap.title + ' ' + gap.description, tenant_id=gap.tenant_id, top_k=5)

    # Summarize what's known
    known_context = [r['content'][:500] for r in results.get('sources', [])]

    return jsonify({
        'gap_id': gap_id,
        'known_context': known_context,
        'known_count': len(known_context),
        'gap_questions': gap.questions,
    })
```

**Step 2: Test**

```bash
curl -X POST http://localhost:5003/api/knowledge/gaps/1/enrich -H "Authorization: Bearer $TOKEN"
```

**Step 3: Commit**

```bash
git add backend/api/knowledge_routes.py backend/services/knowledge_service.py
git commit -m "feat: gap context enrichment via RAG search"
```

---

## Phase 2: RAG (Co-Work) Quality Improvements

### Task 4: Multi-Step Query Decomposition

**Files:**
- Modify: `backend/services/enhanced_search_service.py`

**Step 1: Add query decomposition for complex questions**

Complex queries like "Compare the efficacy of Drug A vs Drug B in NICU patients over the last 5 years" should be decomposed into sub-queries, each searched independently, then results merged.

In `enhanced_search_service.py`, add:

```python
def _decompose_query(self, query: str) -> list[str]:
    """Break complex queries into searchable sub-queries using LLM."""
    # Only decompose if query looks complex (>15 words, contains comparison/temporal)
    words = query.split()
    if len(words) < 15 and not any(w in query.lower() for w in ['compare', 'versus', 'vs', 'difference', 'between', 'relationship']):
        return [query]

    response = self.llm_client.chat.completions.create(
        model=self.chat_deployment,
        messages=[{
            'role': 'system',
            'content': 'Break this research question into 2-4 simpler search queries. Return ONLY a JSON array of strings. Each sub-query should be self-contained and searchable.'
        }, {
            'role': 'user',
            'content': query
        }],
        temperature=0,
        max_tokens=300,
    )

    import json
    try:
        sub_queries = json.loads(response.choices[0].message.content)
        return sub_queries[:4] if isinstance(sub_queries, list) else [query]
    except:
        return [query]
```

**Step 2: Integrate decomposition into search pipeline**

In the main `search()` or `_stream_search()` method, call `_decompose_query()` before Pinecone search. For each sub-query, run a separate Pinecone search, then merge and deduplicate results by `doc_id` before reranking.

**Step 3: Add decomposition to SSE action events**

Emit an action event: `{"section": "Research", "text": "Decomposing complex query into sub-queries", "status": "in_progress"}` when decomposition happens.

**Step 4: Test with a complex query**

```bash
curl -X POST http://localhost:5003/api/search -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Compare outcomes of surfactant therapy versus CPAP in preterm infants under 28 weeks"}'
```

**Step 5: Commit**

```bash
git add backend/services/enhanced_search_service.py
git commit -m "feat: multi-step query decomposition for complex questions"
```

---

### Task 5: Adaptive Source Selection Based on Query Intent

**Files:**
- Modify: `backend/services/enhanced_search_service.py`
- Modify: `backend/app_v2.py`

**Step 1: Classify query intent to determine source mix**

Different queries need different source weightings:
- "What's in my files about X?" → 100% user KB, 0% CTSI/PubMed
- "What does the literature say about X?" → 20% user KB, 80% PubMed
- "How does our protocol compare to published methods?" → 50% user KB, 50% PubMed + journals

```python
def _classify_query_intent(self, query: str) -> dict:
    """Classify query to determine optimal source mix."""
    q_lower = query.lower()

    # Personal/internal queries
    if any(p in q_lower for p in ['my file', 'my data', 'our protocol', 'our lab', 'we have', 'i uploaded']):
        return {'user_kb': 1.0, 'ctsi': 0.0, 'pubmed': 0.0, 'journals': 0.0}

    # Literature queries
    if any(p in q_lower for p in ['literature', 'published', 'studies show', 'research says', 'evidence for']):
        return {'user_kb': 0.2, 'ctsi': 0.1, 'pubmed': 0.5, 'journals': 0.2}

    # Comparison queries
    if any(p in q_lower for p in ['compare', 'versus', 'vs', 'difference between', 'how does our']):
        return {'user_kb': 0.4, 'ctsi': 0.1, 'pubmed': 0.3, 'journals': 0.2}

    # Default balanced
    return {'user_kb': 0.5, 'ctsi': 0.15, 'pubmed': 0.2, 'journals': 0.15}
```

**Step 2: Use source weights to allocate top_k per source**

Instead of a fixed number of results per source, distribute the total `top_k` based on weights. E.g., if total is 10 and weights are {user_kb: 0.5, pubmed: 0.3, journals: 0.2}, allocate 5 from KB, 3 from PubMed, 2 from journals.

**Step 3: Report source allocation in SSE stream**

Emit: `{"section": "Research", "text": "Searching 5 KB sources, 3 PubMed, 2 journals", "status": "in_progress"}`

**Step 4: Test**

Verify "What's in my files?" returns only KB sources, and "What does the literature say?" returns mostly PubMed.

**Step 5: Commit**

```bash
git add backend/services/enhanced_search_service.py backend/app_v2.py
git commit -m "feat: adaptive source selection based on query intent classification"
```

---

### Task 6: Answer Quality Scoring and Confidence Display

**Files:**
- Modify: `backend/services/enhanced_search_service.py`
- Modify: `backend/app_v2.py`
- Modify: `frontend/components/co-work/CoWorkChat.tsx`

**Step 1: Add answer confidence scoring**

After generating the answer, score it based on:
- Source coverage (how many claims have citations)
- Source quality (reranker scores of used sources)
- Query-answer alignment (does the answer address the question?)

```python
def _score_answer_confidence(self, answer: str, sources: list, query: str) -> dict:
    """Score answer quality 0-1 with breakdown."""
    # Source coverage: ratio of paragraphs with citations
    paragraphs = [p for p in answer.split('\n\n') if len(p.strip()) > 50]
    cited = sum(1 for p in paragraphs if any(s['title'][:20].lower() in p.lower() for s in sources))
    coverage = cited / max(len(paragraphs), 1)

    # Source quality: average reranker score (normalized 0-1 via sigmoid)
    import math
    scores = [s.get('rerank_score', 0) for s in sources if s.get('rerank_score')]
    avg_quality = 1 / (1 + math.exp(-sum(scores) / max(len(scores), 1))) if scores else 0.5

    # Overall
    confidence = round(coverage * 0.6 + avg_quality * 0.4, 2)

    return {
        'confidence': confidence,
        'source_coverage': round(coverage, 2),
        'source_quality': round(avg_quality, 2),
        'sources_used': len(sources),
    }
```

**Step 2: Include confidence in SSE `done` event**

Add `confidence` field to the `done` event data so the frontend can display it.

**Step 3: Display confidence in frontend**

In `CoWorkChat.tsx`, show a small confidence indicator below the answer (e.g., "Confidence: High (87%)" or "Confidence: Low (34%) — limited sources found").

**Step 4: Test**

Ask a well-documented topic (should show high confidence) and an obscure topic (should show low confidence).

**Step 5: Commit**

```bash
git add backend/services/enhanced_search_service.py backend/app_v2.py frontend/components/co-work/CoWorkChat.tsx
git commit -m "feat: answer confidence scoring with source coverage metrics"
```

---

## Phase 3: Citation Graph & OpenAlex Deep Integration

### Task 7: OpenAlex Paper Search in Co-Work RAG

**Files:**
- Create: `backend/services/openalex_search_service.py`
- Modify: `backend/services/enhanced_search_service.py`
- Modify: `backend/app_v2.py`

**Step 1: Create OpenAlex search service**

The existing `journal_data_service.py` only fetches journal profiles. Create a new service for searching actual papers (works) via the OpenAlex API.

```python
# backend/services/openalex_search_service.py
import requests
import time
from typing import Optional

class OpenAlexSearchService:
    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str = "prmogathala@gmail.com"):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = f'2ndBrain/1.0 (mailto:{email})'
        self._last_request = 0

    def _rate_limit(self):
        """Respect OpenAlex polite pool: max 10 req/sec."""
        elapsed = time.time() - self._last_request
        if elapsed < 0.1:
            time.sleep(0.1 - elapsed)
        self._last_request = time.time()

    def search_works(self, query: str, max_results: int = 10,
                     from_year: Optional[int] = None,
                     min_citations: int = 0) -> list[dict]:
        """Search OpenAlex for academic papers matching query."""
        self._rate_limit()
        params = {
            'search': query,
            'per_page': min(max_results, 50),
            'sort': 'relevance_score:desc',
            'select': 'id,doi,title,publication_year,cited_by_count,authorships,primary_location,abstract_inverted_index,concepts,type',
        }
        if from_year:
            params['filter'] = f'publication_year:>{from_year}'
        if min_citations > 0:
            filt = params.get('filter', '')
            params['filter'] = (filt + ',' if filt else '') + f'cited_by_count:>{min_citations}'

        resp = self.session.get(f'{self.BASE_URL}/works', params=params, timeout=15)
        resp.raise_for_status()

        results = []
        for work in resp.json().get('results', []):
            # Reconstruct abstract from inverted index
            abstract = self._reconstruct_abstract(work.get('abstract_inverted_index'))

            authors = [a.get('author', {}).get('display_name', '')
                       for a in work.get('authorships', [])[:5]]

            journal = ''
            loc = work.get('primary_location', {})
            if loc and loc.get('source'):
                journal = loc['source'].get('display_name', '')

            results.append({
                'openalex_id': work.get('id', ''),
                'doi': work.get('doi', ''),
                'title': work.get('title', ''),
                'authors': authors,
                'year': work.get('publication_year'),
                'cited_by_count': work.get('cited_by_count', 0),
                'journal': journal,
                'abstract': abstract,
                'concepts': [c.get('display_name', '') for c in work.get('concepts', [])[:5]],
                'source_origin': 'openalex',
                'source_origin_label': 'OpenAlex',
            })

        return results

    def get_citations(self, openalex_id: str, max_results: int = 25) -> list[dict]:
        """Get papers that cite a given work."""
        self._rate_limit()
        work_id = openalex_id.replace('https://openalex.org/', '')
        params = {
            'filter': f'cites:{work_id}',
            'per_page': min(max_results, 50),
            'sort': 'cited_by_count:desc',
            'select': 'id,doi,title,publication_year,cited_by_count,authorships,primary_location',
        }
        resp = self.session.get(f'{self.BASE_URL}/works', params=params, timeout=15)
        resp.raise_for_status()

        return [{
            'openalex_id': w.get('id', ''),
            'doi': w.get('doi', ''),
            'title': w.get('title', ''),
            'year': w.get('publication_year'),
            'cited_by_count': w.get('cited_by_count', 0),
        } for w in resp.json().get('results', [])]

    def get_references(self, openalex_id: str) -> list[dict]:
        """Get papers referenced by a given work."""
        self._rate_limit()
        work_id = openalex_id.replace('https://openalex.org/', '')
        resp = self.session.get(f'{self.BASE_URL}/works/{work_id}',
                                params={'select': 'referenced_works'}, timeout=15)
        resp.raise_for_status()

        ref_ids = resp.json().get('referenced_works', [])
        if not ref_ids:
            return []

        # Batch fetch referenced works
        filter_str = '|'.join(r.replace('https://openalex.org/', '') for r in ref_ids[:25])
        self._rate_limit()
        resp2 = self.session.get(f'{self.BASE_URL}/works',
                                  params={'filter': f'openalex:{filter_str}',
                                          'per_page': 25,
                                          'select': 'id,doi,title,publication_year,cited_by_count'},
                                  timeout=15)
        resp2.raise_for_status()

        return [{
            'openalex_id': w.get('id', ''),
            'doi': w.get('doi', ''),
            'title': w.get('title', ''),
            'year': w.get('publication_year'),
            'cited_by_count': w.get('cited_by_count', 0),
        } for w in resp2.json().get('results', [])]

    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ''
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return ' '.join(w for _, w in word_positions)
```

**Step 2: Integrate OpenAlex into enhanced search pipeline**

In `enhanced_search_service.py`, when the query intent suggests literature search, also call `OpenAlexSearchService.search_works()` and merge results with PubMed results. Use abstract text as content for reranking.

**Step 3: Add OpenAlex source type to frontend**

In `CoWorkContext.tsx`, add `'OpenAlex': '#F59E0B'` (amber) to `SOURCE_BADGE_COLORS`. In `CoWorkChat.tsx`, handle `source_origin === 'openalex'` in the source routing.

**Step 4: Test**

Ask a research question in co-work. Verify OpenAlex papers appear alongside PubMed results with proper attribution.

**Step 5: Commit**

```bash
git add backend/services/openalex_search_service.py backend/services/enhanced_search_service.py backend/app_v2.py frontend/components/co-work/CoWorkChat.tsx frontend/components/co-work/CoWorkContext.tsx
git commit -m "feat: OpenAlex paper search integration in co-work RAG"
```

---

### Task 8: Citation Graph Traversal for Deep Research

**Files:**
- Modify: `backend/services/openalex_search_service.py`
- Create: `backend/services/citation_graph_service.py`
- Modify: `backend/services/co_researcher_service.py`

**Step 1: Create citation graph service**

Build a service that, given a seed paper, traverses its citation graph (both citing and cited-by) to find the most influential related papers.

```python
# backend/services/citation_graph_service.py
import networkx as nx
from services.openalex_search_service import OpenAlexSearchService

class CitationGraphService:
    def __init__(self):
        self.openalex = OpenAlexSearchService()

    def build_citation_graph(self, seed_openalex_id: str, depth: int = 1,
                              max_nodes: int = 50) -> dict:
        """Build citation graph around a seed paper.

        depth=1: seed + direct citations/references
        depth=2: seed + citations/references + their citations

        Returns: {nodes: [...], edges: [...], influential: [...]}
        """
        G = nx.DiGraph()
        visited = set()
        queue = [(seed_openalex_id, 0)]

        while queue and len(G.nodes) < max_nodes:
            current_id, current_depth = queue.pop(0)
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)

            # Get citations (papers that cite this one)
            try:
                citations = self.openalex.get_citations(current_id, max_results=15)
                for cit in citations:
                    cit_id = cit['openalex_id']
                    G.add_node(cit_id, **cit)
                    G.add_edge(cit_id, current_id)  # cit -> current (cit cites current)
                    if current_depth + 1 <= depth:
                        queue.append((cit_id, current_depth + 1))
            except Exception:
                pass

            # Get references (papers this one cites)
            try:
                references = self.openalex.get_references(current_id)
                for ref in references:
                    ref_id = ref['openalex_id']
                    G.add_node(ref_id, **ref)
                    G.add_edge(current_id, ref_id)  # current -> ref (current cites ref)
                    if current_depth + 1 <= depth:
                        queue.append((ref_id, current_depth + 1))
            except Exception:
                pass

        # Find most influential nodes (PageRank)
        try:
            pagerank = nx.pagerank(G, alpha=0.85)
        except:
            pagerank = {n: 1.0 / max(len(G.nodes), 1) for n in G.nodes}

        top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]

        nodes = []
        for node_id in G.nodes:
            data = G.nodes[node_id]
            nodes.append({
                'id': node_id,
                'title': data.get('title', ''),
                'year': data.get('year'),
                'cited_by_count': data.get('cited_by_count', 0),
                'pagerank': round(pagerank.get(node_id, 0), 4),
            })

        edges = [{'source': u, 'target': v} for u, v in G.edges]

        influential = [{
            'id': node_id,
            'title': G.nodes[node_id].get('title', ''),
            'year': G.nodes[node_id].get('year'),
            'cited_by_count': G.nodes[node_id].get('cited_by_count', 0),
            'pagerank': round(score, 4),
        } for node_id, score in top_nodes]

        return {
            'seed': seed_openalex_id,
            'node_count': len(nodes),
            'edge_count': len(edges),
            'nodes': nodes,
            'edges': edges,
            'influential': influential,
        }
```

**Step 2: Integrate citation graph into co-researcher**

In `co_researcher_service.py`, when the user asks about a specific paper or topic, offer citation graph traversal as a research action. When triggered, build the graph and present the most influential papers as additional context.

**Step 3: Add API endpoint for citation graph**

In `backend/app_v2.py` or a new route file, add:

```python
@app.route('/api/citations/graph', methods=['POST'])
@jwt_required
def get_citation_graph():
    data = request.get_json()
    openalex_id = data.get('openalex_id')
    depth = min(data.get('depth', 1), 2)  # Cap at 2

    service = CitationGraphService()
    graph = service.build_citation_graph(openalex_id, depth=depth)
    return jsonify(graph)
```

**Step 4: Test**

```bash
# Search for a paper first
curl -s "https://api.openalex.org/works?search=NICU+outcomes&per_page=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['results'][0]['id'])"
# Then build citation graph
curl -X POST http://localhost:5003/api/citations/graph -H "Authorization: Bearer $TOKEN" \
  -d '{"openalex_id": "https://openalex.org/W...", "depth": 1}'
```

**Step 5: Commit**

```bash
git add backend/services/citation_graph_service.py backend/services/openalex_search_service.py backend/services/co_researcher_service.py backend/app_v2.py
git commit -m "feat: citation graph traversal with PageRank for influential paper discovery"
```

---

## Phase 4: Protocol Knowledge Graph

### Task 9: Protocol Entity Extraction and Graph Building

**Files:**
- Create: `backend/services/protocol_graph_service.py`
- Modify: `backend/database/models.py`

**Step 1: Add protocol graph models**

```python
# In backend/database/models.py

class ProtocolEntity(db.Model):
    """Extracted entity from a protocol document."""
    __tablename__ = 'protocol_entities'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)

    entity_type = Column(String(50), nullable=False)  # technique, reagent, equipment, parameter, organism
    name = Column(String(500), nullable=False)
    normalized_name = Column(String(500))  # lowercase, canonical form
    attributes = Column(JSON, default=dict)  # {concentration: "10mM", temperature: "37°C", etc.}

    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('ix_protocol_entity_tenant_type', 'tenant_id', 'entity_type'),
        Index('ix_protocol_entity_name', 'normalized_name'),
    )

class ProtocolRelation(db.Model):
    """Relationship between two protocol entities."""
    __tablename__ = 'protocol_relations'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)

    source_entity_id = Column(Integer, ForeignKey('protocol_entities.id'), nullable=False)
    target_entity_id = Column(Integer, ForeignKey('protocol_entities.id'), nullable=False)
    relation_type = Column(String(100), nullable=False)  # uses, requires, produces, follows, conflicts_with
    confidence = Column(Float, default=1.0)
    context = Column(Text)  # surrounding text that describes this relationship

    created_at = Column(DateTime, default=func.now())

    source = relationship('ProtocolEntity', foreign_keys=[source_entity_id])
    target = relationship('ProtocolEntity', foreign_keys=[target_entity_id])
```

**Step 2: Create protocol graph service**

```python
# backend/services/protocol_graph_service.py
import json
from database.models import db, ProtocolEntity, ProtocolRelation, Document

class ProtocolGraphService:
    ENTITY_TYPES = ['technique', 'reagent', 'equipment', 'parameter', 'organism', 'cell_line', 'buffer', 'assay']
    RELATION_TYPES = ['uses', 'requires', 'produces', 'follows', 'conflicts_with', 'alternative_to', 'measured_by']

    def __init__(self, llm_client, chat_deployment: str):
        self.llm_client = llm_client
        self.chat_deployment = chat_deployment

    def extract_entities_from_document(self, document: Document, tenant_id: int) -> list[dict]:
        """Extract protocol entities and relationships from a document using LLM."""
        content = document.content[:8000]  # Cap for LLM context

        response = self.llm_client.chat.completions.create(
            model=self.chat_deployment,
            messages=[{
                'role': 'system',
                'content': f'''Extract protocol entities and relationships from this lab document.

Return JSON:
{{
  "entities": [
    {{"type": "technique|reagent|equipment|parameter|organism|cell_line|buffer|assay", "name": "...", "attributes": {{}}}}
  ],
  "relations": [
    {{"source": "entity_name", "target": "entity_name", "type": "uses|requires|produces|follows|conflicts_with|alternative_to|measured_by", "context": "brief description"}}
  ]
}}

Only extract entities clearly mentioned. Do not infer or guess.'''
            }, {
                'role': 'user',
                'content': content
            }],
            temperature=0,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response.choices[0].message.content)
        except:
            return []

        # Store entities
        entity_map = {}
        for ent in result.get('entities', []):
            entity = ProtocolEntity(
                tenant_id=tenant_id,
                document_id=document.id,
                entity_type=ent.get('type', 'technique'),
                name=ent.get('name', ''),
                normalized_name=ent.get('name', '').lower().strip(),
                attributes=ent.get('attributes', {}),
            )
            db.session.add(entity)
            db.session.flush()
            entity_map[ent['name'].lower()] = entity.id

        # Store relations
        for rel in result.get('relations', []):
            src_id = entity_map.get(rel.get('source', '').lower())
            tgt_id = entity_map.get(rel.get('target', '').lower())
            if src_id and tgt_id:
                relation = ProtocolRelation(
                    tenant_id=tenant_id,
                    document_id=document.id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type=rel.get('type', 'uses'),
                    confidence=1.0,
                    context=rel.get('context', ''),
                )
                db.session.add(relation)

        db.session.commit()
        return result.get('entities', [])

    def query_graph(self, tenant_id: int, entity_name: str = None,
                    entity_type: str = None) -> dict:
        """Query the protocol knowledge graph."""
        query = ProtocolEntity.query.filter_by(tenant_id=tenant_id)

        if entity_name:
            query = query.filter(ProtocolEntity.normalized_name.ilike(f'%{entity_name.lower()}%'))
        if entity_type:
            query = query.filter_by(entity_type=entity_type)

        entities = query.limit(100).all()
        entity_ids = [e.id for e in entities]

        relations = ProtocolRelation.query.filter(
            ProtocolRelation.tenant_id == tenant_id,
            db.or_(
                ProtocolRelation.source_entity_id.in_(entity_ids),
                ProtocolRelation.target_entity_id.in_(entity_ids),
            )
        ).limit(200).all()

        return {
            'entities': [{
                'id': e.id,
                'type': e.entity_type,
                'name': e.name,
                'attributes': e.attributes,
            } for e in entities],
            'relations': [{
                'source': r.source_entity_id,
                'target': r.target_entity_id,
                'type': r.relation_type,
                'context': r.context,
            } for r in relations],
        }
```

**Step 3: Add API endpoint for protocol graph**

```python
@app.route('/api/protocols/graph', methods=['GET'])
@jwt_required
def get_protocol_graph():
    tenant_id = g.current_user.tenant_id
    entity_name = request.args.get('entity')
    entity_type = request.args.get('type')

    service = ProtocolGraphService(llm_client, CHAT_DEPLOYMENT)
    graph = service.query_graph(tenant_id, entity_name, entity_type)
    return jsonify(graph)

@app.route('/api/protocols/extract', methods=['POST'])
@jwt_required
def extract_protocol_entities():
    """Extract entities from a specific document."""
    data = request.get_json()
    doc_id = data.get('document_id')
    doc = Document.query.get_or_404(doc_id)

    service = ProtocolGraphService(llm_client, CHAT_DEPLOYMENT)
    entities = service.extract_entities_from_document(doc, g.current_user.tenant_id)
    return jsonify({'entities_extracted': len(entities), 'entities': entities})
```

**Step 4: Wire protocol graph into RAG context**

In `enhanced_search_service.py`, when protocol content is detected in search results (using existing `is_protocol_content()` from `protocol_patterns.py`), also query the protocol graph for related entities and include them in the LLM context as structured knowledge.

**Step 5: Test**

Upload a protocol document, extract entities, then query the graph.

**Step 6: Commit**

```bash
git add backend/services/protocol_graph_service.py backend/database/models.py backend/app_v2.py backend/services/enhanced_search_service.py
git commit -m "feat: protocol knowledge graph with entity extraction and relationship mapping"
```

---

## Phase 5: Experiment Suggestion & Feasibility Scoring

### Task 10: Experiment Suggestion Engine

**Files:**
- Create: `backend/services/experiment_suggestion_service.py`
- Modify: `backend/app_v2.py`

**Step 1: Create experiment suggestion service**

Given a research question and available lab resources (from protocol graph), suggest experiments with methodology, expected outcomes, and required resources.

```python
# backend/services/experiment_suggestion_service.py
import json

class ExperimentSuggestionService:
    def __init__(self, llm_client, chat_deployment: str):
        self.llm_client = llm_client
        self.chat_deployment = chat_deployment

    def suggest_experiments(self, research_question: str,
                           available_resources: list[dict],
                           existing_results: list[dict] = None,
                           constraints: dict = None) -> list[dict]:
        """Suggest experiments based on research question and available resources.

        Args:
            research_question: The question to investigate
            available_resources: From protocol graph [{type, name, attributes}]
            existing_results: Previous experiment results to build on
            constraints: {budget_usd, timeline_weeks, personnel_count}

        Returns: List of experiment suggestions
        """
        resource_text = '\n'.join(
            f"- {r['type']}: {r['name']} ({json.dumps(r.get('attributes', {}))})"
            for r in available_resources[:30]
        )

        existing_text = ''
        if existing_results:
            existing_text = '\n\nPrevious results:\n' + '\n'.join(
                f"- {r.get('title', 'Experiment')}: {r.get('summary', 'No summary')}"
                for r in existing_results[:10]
            )

        constraint_text = ''
        if constraints:
            parts = []
            if constraints.get('budget_usd'):
                parts.append(f"Budget: ${constraints['budget_usd']}")
            if constraints.get('timeline_weeks'):
                parts.append(f"Timeline: {constraints['timeline_weeks']} weeks")
            if constraints.get('personnel_count'):
                parts.append(f"Personnel: {constraints['personnel_count']} people")
            constraint_text = f"\n\nConstraints: {', '.join(parts)}"

        response = self.llm_client.chat.completions.create(
            model=self.chat_deployment,
            messages=[{
                'role': 'system',
                'content': f'''You are a research methodology expert. Given a research question and available lab resources, suggest 2-4 experiments.

Available resources:
{resource_text}
{existing_text}
{constraint_text}

Return JSON:
{{
  "suggestions": [
    {{
      "title": "Experiment title",
      "hypothesis": "What this tests",
      "methodology": "Step-by-step approach",
      "required_resources": ["list of needed resources"],
      "missing_resources": ["resources needed but not available"],
      "expected_duration_weeks": 2,
      "expected_outcome": "What success looks like",
      "controls": ["Required controls"],
      "statistical_approach": "How to analyze results",
      "risk_level": "low|medium|high",
      "novelty": "incremental|moderate|high",
      "builds_on": "Which previous result this extends (if any)"
    }}
  ]
}}

Prioritize experiments that use available resources. Flag missing resources clearly.'''
            }, {
                'role': 'user',
                'content': research_question
            }],
            temperature=0.3,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response.choices[0].message.content)
            return result.get('suggestions', [])
        except:
            return []
```

**Step 2: Add API endpoint**

```python
@app.route('/api/experiments/suggest', methods=['POST'])
@jwt_required
def suggest_experiments():
    data = request.get_json()
    question = data.get('research_question', '')
    constraints = data.get('constraints', {})

    # Get available resources from protocol graph
    from services.protocol_graph_service import ProtocolGraphService
    graph_service = ProtocolGraphService(llm_client, CHAT_DEPLOYMENT)
    graph = graph_service.query_graph(g.current_user.tenant_id)
    resources = graph.get('entities', [])

    service = ExperimentSuggestionService(llm_client, CHAT_DEPLOYMENT)
    suggestions = service.suggest_experiments(question, resources, constraints=constraints)

    return jsonify({'suggestions': suggestions, 'resources_available': len(resources)})
```

**Step 3: Integrate into co-researcher**

In `co_researcher_service.py`, when the user asks "What experiments should I run?" or "How could I test this hypothesis?", trigger the experiment suggestion service and present results as structured research actions.

**Step 4: Test**

```bash
curl -X POST http://localhost:5003/api/experiments/suggest -H "Authorization: Bearer $TOKEN" \
  -d '{"research_question": "How does temperature affect cell viability in NICU incubators?", "constraints": {"timeline_weeks": 4}}'
```

**Step 5: Commit**

```bash
git add backend/services/experiment_suggestion_service.py backend/app_v2.py backend/services/co_researcher_service.py
git commit -m "feat: experiment suggestion engine with resource-aware methodology"
```

---

### Task 11: Feasibility Scoring for Experiments

**Files:**
- Create: `backend/services/feasibility_scorer.py`
- Modify: `backend/services/experiment_suggestion_service.py`

**Step 1: Create feasibility scorer**

Score each experiment suggestion on multiple dimensions: resource availability, timeline realism, statistical power, and novelty.

```python
# backend/services/feasibility_scorer.py

class FeasibilityScorer:
    def score(self, suggestion: dict, available_resources: list[dict],
              constraints: dict = None) -> dict:
        """Score experiment feasibility 0-1 across dimensions.

        Returns: {overall, resource_match, timeline, statistical_power, novelty, breakdown}
        """
        # Resource match (0-1): What fraction of required resources are available?
        required = set(r.lower() for r in suggestion.get('required_resources', []))
        available_names = set(r.get('name', '').lower() for r in available_resources)
        missing = set(r.lower() for r in suggestion.get('missing_resources', []))

        if required:
            matched = sum(1 for r in required if any(a in r or r in a for a in available_names))
            resource_score = matched / len(required)
        else:
            resource_score = 0.5  # Unknown

        # Penalize for missing resources
        if missing:
            resource_score *= max(0.3, 1 - len(missing) * 0.2)

        # Timeline feasibility (0-1)
        duration = suggestion.get('expected_duration_weeks', 4)
        max_weeks = (constraints or {}).get('timeline_weeks', 52)
        timeline_score = min(1.0, max_weeks / max(duration, 1)) if duration <= max_weeks else max(0.2, 1 - (duration - max_weeks) / max_weeks)

        # Statistical power (0-1): Based on presence of controls and statistical approach
        stat_score = 0.5
        if suggestion.get('controls'):
            stat_score += 0.2
        if suggestion.get('statistical_approach'):
            stat_score += 0.2
        if 'power analysis' in suggestion.get('statistical_approach', '').lower():
            stat_score += 0.1
        stat_score = min(1.0, stat_score)

        # Novelty (0-1)
        novelty_map = {'low': 0.2, 'incremental': 0.3, 'moderate': 0.6, 'high': 0.9}
        novelty_score = novelty_map.get(suggestion.get('novelty', 'moderate'), 0.5)

        # Risk penalty
        risk_map = {'low': 0.0, 'medium': 0.1, 'high': 0.25}
        risk_penalty = risk_map.get(suggestion.get('risk_level', 'medium'), 0.1)

        # Overall: weighted average minus risk
        overall = round(
            resource_score * 0.35 +
            timeline_score * 0.25 +
            stat_score * 0.20 +
            novelty_score * 0.20 -
            risk_penalty, 2
        )
        overall = max(0.0, min(1.0, overall))

        return {
            'overall': overall,
            'resource_match': round(resource_score, 2),
            'timeline': round(timeline_score, 2),
            'statistical_power': round(stat_score, 2),
            'novelty': round(novelty_score, 2),
            'risk_penalty': round(risk_penalty, 2),
            'feasibility_tier': 'high' if overall >= 0.7 else 'medium' if overall >= 0.4 else 'low',
        }
```

**Step 2: Integrate scoring into experiment suggestions**

In `experiment_suggestion_service.py`, after generating suggestions, score each one and sort by feasibility:

```python
def suggest_experiments_with_feasibility(self, research_question, available_resources,
                                         existing_results=None, constraints=None):
    suggestions = self.suggest_experiments(research_question, available_resources,
                                           existing_results, constraints)

    scorer = FeasibilityScorer()
    for suggestion in suggestions:
        suggestion['feasibility'] = scorer.score(suggestion, available_resources, constraints)

    # Sort by feasibility (highest first)
    suggestions.sort(key=lambda s: s.get('feasibility', {}).get('overall', 0), reverse=True)
    return suggestions
```

**Step 3: Update API endpoint to include feasibility**

Update `/api/experiments/suggest` to call `suggest_experiments_with_feasibility` instead.

**Step 4: Test**

Verify suggestions come back with feasibility scores and are sorted by overall score.

**Step 5: Commit**

```bash
git add backend/services/feasibility_scorer.py backend/services/experiment_suggestion_service.py backend/app_v2.py
git commit -m "feat: feasibility scoring for experiment suggestions with multi-dimension analysis"
```

---

## Phase 6: High-Impact Journal Methodology Improvements

### Task 12: Enhanced Manuscript Analysis with OpenAlex-Powered Journal Matching

**Files:**
- Modify: `backend/services/journal_scorer_service.py`
- Modify: `backend/services/journal_data_service.py`

**Step 1: Improve journal matching with citation context**

Currently journal matching uses OpenAlex journal profiles. Enhance it by also analyzing the manuscript's references to find journals that frequently publish in the same citation neighborhood.

In `journal_scorer_service.py`, add a method:

```python
def _find_citation_neighbor_journals(self, references: list[str], field: str) -> list[dict]:
    """Find journals that frequently publish papers cited by or citing the same works.

    Args:
        references: List of DOIs or titles from the manuscript
        field: Academic field

    Returns: Journal suggestions based on citation neighborhood
    """
    from services.openalex_search_service import OpenAlexSearchService
    openalex = OpenAlexSearchService()

    journal_counts = {}
    for ref in references[:15]:  # Cap at 15 references
        try:
            works = openalex.search_works(ref, max_results=3)
            for work in works:
                journal = work.get('journal', '')
                if journal:
                    journal_counts[journal] = journal_counts.get(journal, 0) + 1
        except:
            continue

    # Sort by frequency — journals appearing most often in the citation neighborhood
    neighbor_journals = sorted(journal_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return [{
        'journal_name': name,
        'citation_overlap': count,
        'match_reason': f'Found in {count} of your references\' citation neighborhoods'
    } for name, count in neighbor_journals]
```

**Step 2: Add citation neighborhood to manuscript analysis pipeline**

In the 10-step analysis pipeline (step 9: journal matching), after the current OpenAlex + local DB matching, also run `_find_citation_neighbor_journals()` and merge results, deduplicating by journal name.

**Step 3: Test**

Upload a manuscript PDF and verify the journal suggestions include citation-neighborhood-based matches.

**Step 4: Commit**

```bash
git add backend/services/journal_scorer_service.py backend/services/journal_data_service.py
git commit -m "feat: citation neighborhood journal matching for manuscript analysis"
```

---

### Task 13: Methodology Gap Detection in Manuscripts

**Files:**
- Modify: `backend/services/journal_scorer_service.py`

**Step 1: Add methodology gap detection step**

After scoring the manuscript, analyze it for common methodology gaps that reviewers flag:
- Missing sample size justification
- No mention of blinding/randomization
- Missing ethics approval statement
- No data availability statement
- Missing conflict of interest declaration
- Incomplete statistical methods description

```python
def _detect_methodology_gaps(self, text: str, field: str) -> list[dict]:
    """Detect common methodology gaps that reviewers will flag."""
    gaps = []
    text_lower = text.lower()

    checks = [
        {
            'name': 'Sample Size Justification',
            'keywords': ['sample size', 'power analysis', 'power calculation', 'n =', 'participants were'],
            'severity': 'high',
            'recommendation': 'Add a power analysis or sample size justification in the Methods section.',
        },
        {
            'name': 'Blinding/Randomization',
            'keywords': ['blind', 'randomiz', 'double-blind', 'single-blind', 'allocation conceal'],
            'severity': 'high' if field in ('biomedical', 'psychology', 'biology') else 'medium',
            'recommendation': 'Describe blinding and randomization procedures, or explain why they were not applicable.',
        },
        {
            'name': 'Ethics Statement',
            'keywords': ['ethics', 'irb', 'institutional review', 'informed consent', 'ethics committee', 'iacuc'],
            'severity': 'high' if field in ('biomedical', 'psychology', 'biology') else 'low',
            'recommendation': 'Include IRB/ethics committee approval number and informed consent details.',
        },
        {
            'name': 'Data Availability',
            'keywords': ['data availab', 'data sharing', 'openly available', 'repository', 'supplementary data', 'upon request'],
            'severity': 'medium',
            'recommendation': 'Add a Data Availability Statement specifying where data can be accessed.',
        },
        {
            'name': 'Conflict of Interest',
            'keywords': ['conflict of interest', 'competing interest', 'disclosure', 'no conflict'],
            'severity': 'medium',
            'recommendation': 'Include a Conflict of Interest / Competing Interests declaration.',
        },
        {
            'name': 'Statistical Methods',
            'keywords': ['t-test', 'anova', 'regression', 'chi-square', 'p-value', 'confidence interval', 'mann-whitney', 'statistical analys'],
            'severity': 'high',
            'recommendation': 'Describe statistical tests used, significance thresholds, and software/versions.',
        },
        {
            'name': 'Limitations',
            'keywords': ['limitation', 'caveat', 'shortcoming', 'weakness', 'future work should address'],
            'severity': 'medium',
            'recommendation': 'Add a Limitations section discussing study constraints and their impact.',
        },
    ]

    for check in checks:
        found = any(kw in text_lower for kw in check['keywords'])
        if not found:
            gaps.append({
                'gap': check['name'],
                'severity': check['severity'],
                'recommendation': check['recommendation'],
                'detected': False,
            })

    return gaps
```

**Step 2: Include methodology gaps in analysis output**

Add methodology gaps as a new section in the SSE stream output (between step 8 and step 9), so users see it as part of the analysis flow.

**Step 3: Test**

Upload a manuscript that's missing an ethics statement. Verify it appears in the methodology gaps section.

**Step 4: Commit**

```bash
git add backend/services/journal_scorer_service.py
git commit -m "feat: methodology gap detection for manuscript review preparation"
```

---

### Task 14: Build, Test, and Deploy All Changes

**Files:**
- Backend Dockerfile
- Frontend (if any frontend changes)

**Step 1: Run backend locally and verify all new endpoints**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python app_v2.py
```

Test each new endpoint:
- `POST /api/knowledge/gaps/<id>/enrich`
- `GET /api/knowledge/gaps?sort=priority`
- `POST /api/citations/graph`
- `GET /api/protocols/graph`
- `POST /api/protocols/extract`
- `POST /api/experiments/suggest`

**Step 2: Build backend Docker image**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
docker build -t secondbrain-backend:latest -f backend/Dockerfile backend/
```

**Step 3: Tag and push to ECR**

```bash
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 923028187100.dkr.ecr.us-east-2.amazonaws.com
docker tag secondbrain-backend:latest 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-backend:latest
docker push 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-backend:latest
```

**Step 4: Force new ECS deployment**

```bash
aws ecs update-service --cluster secondbrain-cluster --service secondbrain-backend --force-new-deployment --region us-east-2
```

**Step 5: Build and deploy frontend if changed**

```bash
docker build -t secondbrain-frontend:latest -f frontend/Dockerfile frontend/
docker tag secondbrain-frontend:latest 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-frontend:latest
docker push 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-frontend:latest
aws ecs update-service --cluster secondbrain-cluster --service secondbrain-frontend --force-new-deployment --region us-east-2
```

**Step 6: Verify deployment**

```bash
aws ecs describe-services --cluster secondbrain-cluster --services secondbrain-backend secondbrain-frontend --region us-east-2 --query 'services[].{name:serviceName,running:runningCount}'
```

**Step 7: Commit any remaining changes**

```bash
git add -A
git commit -m "chore: deployment config for research methodology system"
git push origin main
```

---

## Dependency Graph

```
Task 1 (Gap Priority) ─────────┐
Task 2 (Gap Dedup) ─────────────┤
Task 3 (Gap Enrich) ────────────┤── Phase 1: Independent, can parallelize
                                │
Task 4 (Query Decomposition) ───┤
Task 5 (Adaptive Sources) ──────┤── Phase 2: Independent
Task 6 (Confidence Scoring) ────┤
                                │
Task 7 (OpenAlex Search) ───────┤── Phase 3: Task 8 depends on Task 7
Task 8 (Citation Graph) ────────┤
                                │
Task 9 (Protocol Graph) ────────┤── Phase 4: Independent
                                │
Task 10 (Experiment Suggest) ───┤── Phase 5: Depends on Task 9 (protocol graph for resources)
Task 11 (Feasibility Score) ────┤── Depends on Task 10
                                │
Task 12 (Journal Citation Match)┤── Phase 6: Depends on Task 7 (OpenAlex service)
Task 13 (Methodology Gaps) ─────┤── Independent
                                │
Task 14 (Build & Deploy) ───────┘── Depends on all above
```

## Parallelization Strategy

- **Wave 1:** Tasks 1, 2, 3 (Phase 1 — all independent)
- **Wave 2:** Tasks 4, 5, 6, 7, 9 (Phase 2 + 3 start + Phase 4 — all independent)
- **Wave 3:** Tasks 8, 10, 12, 13 (depend on Wave 2 outputs)
- **Wave 4:** Task 11 (depends on Task 10)
- **Wave 5:** Task 14 (build & deploy — depends on all)
