# RAG Improvement Research for 2nd Brain
## State-of-the-Art Techniques (2025-2026)

**Date:** 2026-03-11
**Context:** 2nd Brain is a B2B SaaS knowledge management platform ingesting emails, documents, Slack messages, etc. This document evaluates advanced RAG techniques against the existing system.

### Current System Baseline

| Component | Implementation |
|-----------|---------------|
| Vector Store | Pinecone (serverless, cosine, `knowledgevault` index) |
| Embeddings | Azure OpenAI `text-embedding-3-large` (1536 dims) |
| Chunking | 2000 chars, 400 char overlap, sentence-aware splitting |
| Reranking | Cross-encoder `ms-marco-MiniLM-L-12-v2` |
| Diversity | MMR with adaptive lambda (0.7 default) |
| Query Expansion | 100+ acronym dictionary |
| Hallucination Detection | Claim extraction + verification |
| Freshness | Recency boost scoring |
| Hybrid Search | Dense + keyword boosting (basic) |
| Query Classification | 4 types: factual, exploratory, comparative, procedural |

---

## 1. Advanced Retrieval Techniques

### 1.1 Contextual Retrieval (Anthropic's Approach)

**What it is:** Before embedding each chunk, use an LLM to generate a short (50-100 token) context prefix that situates the chunk within the full document. This prefix is prepended to the chunk text before both embedding and BM25 indexing. For example, a chunk saying "Revenue grew 15% YoY" gets prepended with "This chunk is from Acme Corp's Q3 2025 earnings report, discussing financial performance in the North American market."

**Why it helps your system:** Your current chunking (2000 chars, 400 overlap) loses document-level context. An email thread chunk about "the budget" means nothing without knowing which project's budget. This is critical for 2nd Brain because emails and Slack messages are inherently context-dependent -- a message saying "approved" is meaningless without knowing what was approved.

**Implementation for 2nd Brain:**

```python
# In vector_stores/pinecone_store.py, modify _chunk_text() pipeline

async def _generate_chunk_context(self, chunk_text: str, full_document: str, doc_metadata: dict) -> str:
    """Generate contextual prefix for a chunk using cheap model."""
    prompt = f"""Given this document:
Title: {doc_metadata.get('title', 'Unknown')}
Source: {doc_metadata.get('source_type', 'Unknown')}
From: {doc_metadata.get('sender', 'Unknown')}
Date: {doc_metadata.get('date', 'Unknown')}

Full document (truncated):
{full_document[:8000]}

Generate a 1-2 sentence context prefix for this chunk that explains
what document it comes from and what topic area it covers:

Chunk: {chunk_text[:500]}

Context prefix:"""

    # Use gpt-4o-mini for cost efficiency (same as extraction_service.py)
    response = self.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.0
    )
    return response.choices[0].message.content.strip()

def _contextualize_and_embed(self, chunks: list, full_doc: str, metadata: dict) -> list:
    """Prepend context to each chunk before embedding."""
    contextualized = []
    for chunk in chunks:
        context = self._generate_chunk_context(chunk, full_doc, metadata)
        contextualized.append(f"{context}\n\n{chunk}")
    return contextualized
```

**Optimization -- use caching:** You already have `ExtractionService` that generates structured summaries during sync. Reuse those summaries as context prefixes instead of calling the LLM per-chunk:

```python
def _build_context_from_summary(self, doc_metadata: dict) -> str:
    """Build context prefix from pre-extracted structured summary."""
    summary = doc_metadata.get('structured_summary', {})
    parts = []
    if summary.get('summary'):
        parts.append(summary['summary'])
    if summary.get('key_topics'):
        parts.append(f"Topics: {', '.join(summary['key_topics'][:5])}")
    if doc_metadata.get('sender_email'):
        parts.append(f"From: {doc_metadata['sender_email']}")
    if doc_metadata.get('source_type'):
        parts.append(f"Source: {doc_metadata['source_type']}")
    return ' | '.join(parts)
```

This gives you 80% of the benefit at zero additional LLM cost by leveraging your existing extraction pipeline.

**Complexity:** Medium. Requires re-embedding all existing documents. The LLM-per-chunk approach costs ~$0.002 per chunk with gpt-4o-mini. The summary-reuse approach costs nothing extra.

**Expected improvement:** 35-49% reduction in failed retrievals (Anthropic's benchmarks). Combined with your existing reranking, up to 67% improvement.

**Priority: HIGH** -- This is the single highest-impact change you can make. Your email/Slack data suffers severely from decontextualization.

---

### 1.2 Late Interaction Models (ColBERT v2) vs Current Bi-encoder + Cross-encoder

**What it is:** ColBERT produces per-token embeddings for both queries and documents, then uses a "MaxSim" late interaction to compute relevance. Unlike bi-encoders (single vector per text) or cross-encoders (joint encoding, no precomputation), ColBERT precomputes document token embeddings and does lightweight interaction at query time.

**Architecture comparison relevant to your pipeline:**

| Approach | Your Current | ColBERT v2 |
|----------|-------------|------------|
| Index | 1 vector per chunk (1536d) | ~128 vectors per chunk (128d each) |
| Query | 1 vector, cosine search | ~32 vectors, MaxSim |
| Reranking | Separate cross-encoder pass | Built into retrieval |
| Storage | ~6KB per chunk | ~65KB per chunk (with 2-bit compression) |
| Latency | Fast retrieve + slow rerank | Medium retrieve, no rerank needed |

**Why it helps (and why it might not):** ColBERT v2 approaches cross-encoder quality at bi-encoder speed. However, your current pipeline already uses bi-encoder retrieval + cross-encoder reranking, which is the standard competitive approach. The marginal improvement of switching to ColBERT is modest (~2-5% on standard benchmarks) and comes with significant infrastructure cost.

**Implementation consideration for 2nd Brain:**

The practical blocker is Pinecone. Pinecone does not natively support multi-vector (late interaction) indexing. You would need to either:
1. Use a ColBERT-native store like Vespa, Weaviate, or Qdrant (migration)
2. Use Jina ColBERT v2 as a reranker only (replacing ms-marco-MiniLM), which is simpler

```python
# Option: Use jina-colbert-v2 as a reranker (drop-in replacement)
# In services/enhanced_search_service.py

from sentence_transformers import CrossEncoder

# Replace ms-marco-MiniLM-L-12-v2 with ColBERT-based reranker
# jina-reranker-v2-base-multilingual uses late interaction internally
reranker = CrossEncoder("jinaai/jina-reranker-v2-base-multilingual")
```

**Complexity:** Low if used as reranker replacement. Very High if replacing Pinecone with ColBERT-native store.

**Expected improvement:** 2-5% retrieval quality over current cross-encoder reranking. Not worth a full infrastructure change.

**Priority: LOW** -- Your current bi-encoder + cross-encoder pipeline is already strong. Upgrade the reranker model if you want marginal gains.

---

### 1.3 Hypothetical Document Embeddings (HyDE)

**What it is:** Instead of embedding the raw query, use an LLM to generate a hypothetical answer document, then embed that hypothetical document and use it for retrieval. The intuition: a query like "What is our vacation policy?" becomes a plausible answer "Employees are entitled to 15 days of paid vacation per year..." which is semantically closer to the actual policy document than the question itself.

**Why it helps your system:** 2nd Brain queries often have a query-document asymmetry problem. Users ask short questions ("What did John say about the budget?") but the relevant content is a long email thread. HyDE bridges this gap. It is particularly effective for:
- Factual queries where the answer format is predictable
- Domain-specific terminology (the hypothetical document will use domain terms)
- Cross-format retrieval (question vs. email vs. Slack message vs. document)

**Implementation for 2nd Brain:**

```python
# In services/enhanced_search_service.py

async def _generate_hypothetical_document(self, query: str, query_type: str) -> str:
    """Generate a hypothetical answer document for HyDE retrieval."""

    source_hint = ""
    if "email" in query.lower() or "said" in query.lower():
        source_hint = "Write it as if it were an email or message."
    elif "process" in query.lower() or "how" in query.lower():
        source_hint = "Write it as if it were a process document."

    prompt = f"""Write a short (100-200 word) document that would be a good answer
to this question. Write it as if it were a real internal document. {source_hint}
Do not say you are writing a hypothetical document. Just write the content directly.

Question: {query}

Document:"""

    response = self.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.7  # Some variation helps
    )
    return response.choices[0].message.content.strip()

async def enhanced_search(self, query: str, tenant_id: str, **kwargs):
    # Generate HyDE document
    hyde_doc = await self._generate_hypothetical_document(query, query_type)
    hyde_embedding = self._embed(hyde_doc)

    # Search with BOTH original query embedding AND HyDE embedding
    original_embedding = self._embed(expanded_query)

    # Combine results (weighted union)
    original_results = self.pinecone.query(vector=original_embedding, top_k=20)
    hyde_results = self.pinecone.query(vector=hyde_embedding, top_k=20)

    # Reciprocal Rank Fusion of both result sets
    combined = reciprocal_rank_fusion(
        [original_results, hyde_results],
        weights=[0.6, 0.4]  # Slightly favor original
    )

    # Then rerank combined set with cross-encoder as usual
    reranked = self._cross_encoder_rerank(query, combined[:30])
    return reranked[:top_k]
```

**Key trade-offs:**
- Adds one LLM call per query (~100-200ms with gpt-4o-mini, ~$0.0001 per query)
- Can hurt performance on simple keyword lookups ("meeting notes from March 5")
- Best combined with query classification: use HyDE only for `exploratory` and `comparative` query types, skip for `factual`

**Complexity:** Medium. One new function + query pipeline modification.

**Expected improvement:** 10-25% recall improvement on exploratory queries. Can degrade factual queries by 5-10% if applied blindly. Use conditionally based on your existing `QueryClassifier`.

**Priority: MEDIUM** -- Good improvement for complex queries, but must be gated by query type to avoid regressions.

---

### 1.4 Multi-Vector Retrieval

**What it is:** Instead of a single embedding per chunk, create multiple embeddings capturing different aspects: the factual content, the entities mentioned, the questions the chunk answers, and a summary. At query time, search across all vector types.

**Why it helps:** A single embedding compresses all information into one vector, losing nuance. Multi-vector lets you match on different dimensions -- a query about "John's opinion on React" can match the entity vector (John, React) and the opinion vector separately.

**Implementation for 2nd Brain:**

```python
# During indexing, create multiple vectors per chunk
def _multi_vector_embed(self, chunk_text: str, doc_metadata: dict) -> list:
    """Create multiple embedding perspectives for one chunk."""

    vectors = []
    chunk_id = self._generate_chunk_id(chunk_text)

    # Vector 1: Raw content embedding (current approach)
    vectors.append({
        "id": f"{chunk_id}_content",
        "values": self._embed(chunk_text),
        "metadata": {**doc_metadata, "vector_type": "content"}
    })

    # Vector 2: Summary/abstraction embedding
    summary = self._quick_summarize(chunk_text)  # 1-2 sentences
    vectors.append({
        "id": f"{chunk_id}_summary",
        "values": self._embed(summary),
        "metadata": {**doc_metadata, "vector_type": "summary"}
    })

    # Vector 3: Questions this chunk answers (synthetic)
    questions = self._generate_questions(chunk_text)  # 2-3 questions
    q_text = " ".join(questions)
    vectors.append({
        "id": f"{chunk_id}_questions",
        "values": self._embed(q_text),
        "metadata": {**doc_metadata, "vector_type": "questions"}
    })

    return vectors
```

**Practical consideration:** This triples your Pinecone storage and cost. For 2nd Brain's scale (enterprise knowledge bases can be 50K-500K chunks), this means 150K-1.5M vectors. At Pinecone's serverless pricing ($0.33/GB), this is manageable but not trivial.

**Complexity:** High. Triples storage, requires multi-query logic, needs LLM calls during indexing.

**Expected improvement:** 10-20% recall improvement, especially for question-style queries. The "questions" vector is the most impactful single addition.

**Priority: LOW-MEDIUM** -- The "questions" vector alone (generating what questions a chunk answers) gives most of the benefit at 2x storage instead of 3x. Consider implementing just that one.

---

### 1.5 Parent-Child Chunk Retrieval

**What it is:** Create a hierarchy: large "parent" chunks (2000-4000 chars) and small "child" chunks (200-500 chars) derived from them. Embed and search against child chunks (more precise matching), but return the parent chunk to the LLM (more context).

**Why it helps your system:** Your current 2000-char chunks are a compromise between precision and context. Parent-child lets you have both. For 2nd Brain, this is especially valuable for email threads (child = individual message, parent = full thread) and Slack conversations.

**Implementation for 2nd Brain:**

```python
# In vector_stores/pinecone_store.py

def _create_parent_child_chunks(self, text: str, doc_id: str) -> tuple:
    """Create hierarchical chunks."""
    PARENT_SIZE = 4000   # chars
    CHILD_SIZE = 500     # chars
    PARENT_OVERLAP = 800
    CHILD_OVERLAP = 100

    parents = self._chunk_text(text, PARENT_SIZE, PARENT_OVERLAP)

    all_children = []
    parent_map = {}  # child_id -> parent_text

    for p_idx, parent in enumerate(parents):
        parent_id = f"{doc_id}_p{p_idx}"
        children = self._chunk_text(parent, CHILD_SIZE, CHILD_OVERLAP)

        for c_idx, child in enumerate(children):
            child_id = f"{doc_id}_p{p_idx}_c{c_idx}"
            all_children.append({
                "id": child_id,
                "text": child,
                "parent_id": parent_id,
                "parent_text": parent  # Store in metadata or separate store
            })
            parent_map[child_id] = parent

    return all_children, parent_map

# At query time:
def search_with_parent_expansion(self, query_embedding, top_k=10):
    # Search against child chunks
    child_results = self.index.query(vector=query_embedding, top_k=top_k * 3)

    # Deduplicate by parent and return parent text
    seen_parents = set()
    expanded_results = []
    for match in child_results.matches:
        parent_id = match.metadata.get("parent_id")
        if parent_id not in seen_parents:
            seen_parents.add(parent_id)
            expanded_results.append({
                "text": match.metadata["parent_text"],  # Return parent
                "score": match.score,
                "child_text": match.metadata["text"],  # Keep child for citation
                "metadata": match.metadata
            })
        if len(expanded_results) >= top_k:
            break

    return expanded_results
```

**Storage strategy:** Store parent text in Pinecone metadata (up to 40KB per vector) or in a separate key-value store (Redis, DynamoDB). Given your current architecture with PostgreSQL/SQLite for document storage, you can store parent chunks in the `DocumentChunk` table and only embed children in Pinecone.

**Complexity:** Medium. Requires chunking refactor and parent text storage strategy.

**Expected improvement:** 15-25% improvement in answer quality (more context for LLM) with 5-10% improvement in retrieval precision (smaller child chunks match better).

**Priority: HIGH** -- Directly addresses the precision/context trade-off in your current system. Especially impactful for email/Slack content.

---

### 1.6 Agentic RAG

**What it is:** Instead of a fixed retrieve-then-generate pipeline, use an LLM agent that decides: (a) whether to retrieve at all, (b) what to retrieve, (c) from which sources, (d) whether the results are sufficient, and (e) whether to retrieve again with a refined query.

**Why it helps your system:** 2nd Brain ingests multiple source types (emails, documents, Slack, Box files). Different queries need different retrieval strategies. "What did marketing discuss last week?" should search Slack and emails. "What is our data retention policy?" should search documents. An agent can route intelligently.

**Implementation for 2nd Brain:**

```python
# New file: services/agentic_rag_service.py

class AgenticRAG:
    """Agent-based retrieval that decides strategy per query."""

    TOOLS = [
        {
            "name": "search_all",
            "description": "Search across all document types",
            "parameters": {"query": "str", "top_k": "int"}
        },
        {
            "name": "search_by_source",
            "description": "Search only specific sources (email, slack, box, gdrive)",
            "parameters": {"query": "str", "source_type": "str", "top_k": "int"}
        },
        {
            "name": "search_by_person",
            "description": "Search for content from/about a specific person",
            "parameters": {"query": "str", "person": "str", "top_k": "int"}
        },
        {
            "name": "search_by_date_range",
            "description": "Search within a date range",
            "parameters": {"query": "str", "start_date": "str", "end_date": "str"}
        },
        {
            "name": "answer_directly",
            "description": "Answer without retrieval (for greetings, meta-questions)",
            "parameters": {"response": "str"}
        }
    ]

    async def run(self, query: str, tenant_id: str, conversation_history: list = None):
        # Step 1: Agent decides retrieval strategy
        plan = await self._plan_retrieval(query, conversation_history)

        # Step 2: Execute retrieval tools
        all_results = []
        for tool_call in plan.tool_calls:
            results = await self._execute_tool(tool_call, tenant_id)
            all_results.extend(results)

        # Step 3: Evaluate sufficiency
        if not self._results_sufficient(query, all_results):
            # Refine and retrieve again
            refined_query = await self._refine_query(query, all_results)
            more_results = await self._execute_search(refined_query, tenant_id)
            all_results.extend(more_results)

        # Step 4: Generate answer with all gathered context
        return await self._generate_answer(query, all_results, conversation_history)

    async def _plan_retrieval(self, query: str, history: list) -> dict:
        """Use LLM to plan retrieval strategy."""
        response = self.client.chat.completions.create(
            model="gpt-5-chat",
            messages=[
                {"role": "system", "content": f"Plan retrieval using tools: {self.TOOLS}"},
                {"role": "user", "content": query}
            ],
            tools=self.TOOLS,
            tool_choice="auto"
        )
        return response.choices[0].message
```

**Complexity:** High. Requires building a tool-use agent, which adds latency (2-3 LLM calls per query) and complexity.

**Expected improvement:** 20-40% improvement on complex, multi-source queries. Marginal for simple factual lookups. The A-RAG framework (February 2026) reports 5-13% QA accuracy improvement over flat retrieval.

**Priority: MEDIUM** -- Implement after Contextual Retrieval and Parent-Child. The biggest win is source routing (email vs. doc vs. Slack), which you can approximate with simpler metadata filtering in your existing `QueryClassifier`.

---

## 2. User Context Integration

### 2.1 Personalized Embeddings (User Preference Vectors)

**What it is:** Maintain a per-user "preference vector" that evolves based on which documents they click, which answers they find useful, and their role/department. At query time, blend this preference vector with the query embedding to bias retrieval toward relevant content.

**Implementation for 2nd Brain:**

```python
# New: services/user_context_service.py

class UserContextService:
    """Tracks and applies user preferences to retrieval."""

    def __init__(self, db, embedding_service):
        self.db = db
        self.embedding_service = embedding_service

    def update_preference_vector(self, user_id: str, interaction: dict):
        """Update user's preference vector based on interaction."""
        # interaction = {"query": "...", "clicked_doc_ids": [...], "helpful": True/False}

        user = self.db.query(User).get(user_id)
        current_vector = np.array(user.preference_vector or np.zeros(1536))

        if interaction.get("helpful"):
            # Get embeddings of helpful documents
            for doc_id in interaction["clicked_doc_ids"]:
                doc_embedding = self._get_doc_embedding(doc_id)
                # Exponential moving average
                current_vector = 0.95 * current_vector + 0.05 * doc_embedding

        user.preference_vector = current_vector.tolist()
        self.db.commit()

    def personalize_query(self, query_embedding: list, user_id: str,
                          alpha: float = 0.1) -> list:
        """Blend query embedding with user preferences."""
        user = self.db.query(User).get(user_id)
        if not user.preference_vector:
            return query_embedding

        pref = np.array(user.preference_vector)
        query = np.array(query_embedding)

        # Light blending -- alpha too high biases toward past behavior
        blended = (1 - alpha) * query + alpha * pref
        # Re-normalize for cosine similarity
        blended = blended / np.linalg.norm(blended)
        return blended.tolist()
```

**Database addition:**
```python
# In database/models.py, add to User model:
preference_vector = Column(JSON, nullable=True)  # List[float], 1536 dims
preference_updated_at = Column(DateTime(timezone=True), nullable=True)
```

**Complexity:** Medium. Requires tracking interactions (clicks, thumbs up/down) and storing user vectors.

**Expected improvement:** 5-15% relevance improvement for repeat users. Minimal for new users (cold start problem).

**Priority: LOW** -- Only valuable once you have significant per-user interaction data. Implement feedback tracking first (section 2.4), then add personalized embeddings later.

---

### 2.2 Query Rewriting Based on User History and Role

**What it is:** Before retrieval, rewrite the user's query to include implicit context from their role, department, and recent queries. "What's the latest update?" becomes "What's the latest update on the NICU renovation project?" because the user is in Facilities and has been asking about NICU all week.

**Implementation for 2nd Brain:**

```python
# In services/enhanced_search_service.py

async def _rewrite_query_with_context(self, query: str, user: User,
                                       recent_queries: list) -> str:
    """Rewrite query with user context for better retrieval."""

    context_parts = []
    if user.role:
        context_parts.append(f"User role: {user.role}")
    if user.department:
        context_parts.append(f"Department: {user.department}")
    if recent_queries:
        context_parts.append(f"Recent queries: {'; '.join(recent_queries[-3:])}")

    if not context_parts:
        return query  # No context available

    prompt = f"""Rewrite this search query to be more specific based on the user context.
Only add specificity if the original query is ambiguous.
If the query is already specific, return it unchanged.

User context:
{chr(10).join(context_parts)}

Original query: {query}

Rewritten query (or original if already specific):"""

    response = self.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.0
    )
    rewritten = response.choices[0].message.content.strip()

    # Safety: if rewrite is drastically different, keep both
    if len(rewritten) > len(query) * 3:
        return query  # Rewrite went off the rails
    return rewritten
```

**Complexity:** Low-Medium. Requires storing recent queries per user (simple DB table or Redis).

**Expected improvement:** 10-20% improvement on ambiguous queries. No improvement on specific queries.

**Priority: MEDIUM** -- Especially valuable for 2nd Brain because internal queries are often vague ("any updates?", "what did we decide?").

---

### 2.3 Adaptive Retrieval (Different Strategies per Query Type)

**What it is:** Your `QueryClassifier` already classifies queries into 4 types with different parameters. Adaptive retrieval extends this by dynamically choosing the entire retrieval pipeline -- not just parameters but strategy.

**Implementation for 2nd Brain (extending existing QueryClassifier):**

```python
# In services/enhanced_search_service.py

ADAPTIVE_STRATEGIES = {
    'factual': {
        'use_hyde': False,          # Don't hallucinate, find the exact fact
        'use_parent_child': True,   # Precise child match, full parent context
        'top_k_initial': 12,
        'rerank': True,
        'max_context_chars': 10000,
        'system_prompt': 'Answer concisely with exact facts. Cite specific sources.'
    },
    'exploratory': {
        'use_hyde': True,           # HyDE helps find conceptually related docs
        'use_parent_child': True,
        'top_k_initial': 25,
        'rerank': True,
        'max_context_chars': 25000,
        'system_prompt': 'Provide a comprehensive overview. Cover multiple perspectives.'
    },
    'comparative': {
        'use_hyde': False,
        'use_parent_child': False,  # Need diverse chunks, not expanded parents
        'top_k_initial': 30,
        'rerank': True,
        'mmr_lambda': 0.4,         # High diversity for comparison
        'max_context_chars': 20000,
        'system_prompt': 'Compare and contrast. Use a structured format.'
    },
    'temporal': {                   # NEW query type
        'use_hyde': False,
        'use_parent_child': True,
        'top_k_initial': 20,
        'rerank': True,
        'sort_by': 'date',         # Override relevance sort
        'freshness_boost': 2.0,    # Strong recency bias
        'system_prompt': 'Focus on the most recent information. Note dates.'
    },
    'person_specific': {            # NEW query type
        'use_hyde': False,
        'use_parent_child': True,
        'top_k_initial': 20,
        'rerank': True,
        'metadata_filter': {'sender_email': '<extracted_person>'},
        'system_prompt': 'Focus on what this specific person said or wrote.'
    }
}
```

**Complexity:** Low. Extends your existing architecture with more strategies.

**Expected improvement:** 10-15% across all query types by eliminating one-size-fits-all parameter choices.

**Priority: HIGH** -- Low-effort, high-impact. You already have the `QueryClassifier` infrastructure; add more types and per-type strategy selection.

---

### 2.4 User Feedback Loops for Relevance Tuning

**What it is:** Collect explicit (thumbs up/down) and implicit (click-through, dwell time, copy/paste) signals from users, and use them to improve retrieval over time.

**Implementation for 2nd Brain:**

```python
# New table in database/models.py

class SearchFeedback(Base):
    __tablename__ = 'search_feedback'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    query = Column(Text, nullable=False)
    query_embedding = Column(JSON, nullable=True)  # Store for future fine-tuning
    result_doc_ids = Column(JSON, nullable=False)    # Ordered list of returned docs
    clicked_doc_ids = Column(JSON, nullable=True)    # Which docs user clicked/expanded
    feedback = Column(String(10), nullable=True)     # 'helpful' | 'not_helpful' | None
    feedback_text = Column(Text, nullable=True)
    answer_text = Column(Text, nullable=True)        # The generated answer
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# API endpoint in api/search_routes.py
@blueprint.route('/api/search/feedback', methods=['POST'])
@require_auth
def submit_search_feedback():
    data = request.json
    feedback = SearchFeedback(
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        query=data['query'],
        result_doc_ids=data['result_doc_ids'],
        clicked_doc_ids=data.get('clicked_doc_ids'),
        feedback=data['feedback'],
        feedback_text=data.get('feedback_text'),
        answer_text=data.get('answer_text')
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "recorded"})
```

**Usage for improvement:**
1. **Short-term:** Use negative feedback to suppress bad documents (add to a blocklist per query pattern)
2. **Medium-term:** Analyze feedback to identify weak query types and tune parameters
3. **Long-term:** Fine-tune embedding model or build a reward model for retrieval (Reward-RAG approach)

**Frontend addition:** Add a simple thumbs-up/thumbs-down below each answer in the Chat Interface.

**Complexity:** Low for collection, Medium for utilizing feedback in retrieval.

**Expected improvement:** 5-10% improvement after collecting 500+ feedback signals. Compounds over time.

**Priority: HIGH** -- Start collecting feedback immediately even if you do not use it yet. The data is invaluable.

---

### 2.5 Session-Aware Retrieval

**What it is:** Use the current conversation context to inform retrieval for follow-up queries. "What about the timeline?" should retrieve timeline-related content about whatever topic was just discussed.

**Your current state:** You already have basic conversational context ("last 2-3 Q&A pairs" per enhanced_rag_v2.py). This section extends it.

**Implementation for 2nd Brain:**

```python
# In services/enhanced_search_service.py

class SessionContext:
    """Manages conversation context for session-aware retrieval."""

    def __init__(self, max_turns: int = 5):
        self.max_turns = max_turns
        self.turns = []  # List of {"query": str, "answer": str, "doc_ids": list}
        self.active_topics = []  # Extracted topics from conversation
        self.mentioned_entities = set()  # People, projects, etc.

    def add_turn(self, query: str, answer: str, doc_ids: list, entities: list = None):
        self.turns.append({"query": query, "answer": answer, "doc_ids": doc_ids})
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)
        if entities:
            self.mentioned_entities.update(entities)

    def get_context_for_retrieval(self) -> dict:
        """Return context signals to enhance current retrieval."""
        return {
            "recent_queries": [t["query"] for t in self.turns[-3:]],
            "recent_doc_ids": list(set(
                doc_id for t in self.turns for doc_id in t.get("doc_ids", [])
            )),
            "entities": list(self.mentioned_entities),
            "turn_count": len(self.turns)
        }

# In the search endpoint:
async def enhanced_search(self, query: str, tenant_id: str, session: SessionContext):
    context = session.get_context_for_retrieval()

    # If this is a follow-up (short query + existing session), resolve coreferences
    if len(query.split()) < 6 and context["turn_count"] > 0:
        query = await self._resolve_coreferences(query, context["recent_queries"])

    # Boost documents related to entities already discussed
    if context["entities"]:
        metadata_filter = {"mentioned_entities": {"$in": context["entities"]}}
        # Add as soft boost, not hard filter

    # ... proceed with normal retrieval
```

**Complexity:** Low-Medium. Session management + coreference resolution for follow-ups.

**Expected improvement:** 20-30% improvement on follow-up queries (which are common in chat-based interfaces).

**Priority: MEDIUM** -- You already have basic context. The main upgrade is proper coreference resolution ("it", "that", "the timeline" -> what it refers to).

---

## 3. Hybrid Search Improvements

### 3.1 BM25 + Dense Retrieval with Reciprocal Rank Fusion (RRF)

**What it is:** Run BM25 (keyword) and dense (semantic) retrieval independently, then fuse results using RRF, a parameter-free algorithm that combines rankings:

```
RRF_score(d) = sum(1 / (k + rank_i(d))) for each retriever i
```

where `k` is a constant (typically 60).

**Your current state:** You have basic hybrid search in Pinecone with an `alpha` weighting parameter. This is Pinecone's built-in approach. The limitation is that Pinecone's hybrid search uses a single-index approach where sparse and dense scores are linearly combined, which requires tuning `alpha`.

**Upgrade path using Pinecone's native sparse vectors:**

```python
# In vector_stores/pinecone_store.py

from pinecone_text.sparse import BM25Encoder

class EnhancedPineconeStore(PineconeVectorStore):

    def __init__(self, config: PineconeConfig):
        super().__init__(config)
        # Initialize BM25 encoder
        self.bm25 = BM25Encoder.default()  # Pre-trained on MS MARCO
        # OR fit on your corpus:
        # self.bm25 = BM25Encoder()
        # self.bm25.fit(your_corpus_texts)

    def embed_and_upsert_with_sparse(self, doc_id: str, text: str,
                                      metadata: dict, tenant_id: str):
        """Upsert with both dense and sparse vectors."""
        chunks = self._chunk_text(text)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"

            # Dense embedding (existing)
            dense_vector = self._embed(chunk)

            # Sparse BM25 vector
            sparse_vector = self.bm25.encode_documents(chunk)

            self.index.upsert(
                vectors=[{
                    "id": chunk_id,
                    "values": dense_vector,
                    "sparse_values": sparse_vector,
                    "metadata": {**metadata, "text": chunk}
                }],
                namespace=tenant_id
            )

    def hybrid_search_rrf(self, query: str, tenant_id: str,
                          top_k: int = 15, k: int = 60) -> list:
        """True RRF hybrid search."""
        query_dense = self._embed(query)
        query_sparse = self.bm25.encode_queries(query)

        # Dense-only search
        dense_results = self.index.query(
            vector=query_dense,
            top_k=top_k * 2,
            namespace=tenant_id,
            include_metadata=True
        )

        # Sparse-only search
        sparse_results = self.index.query(
            sparse_vector=query_sparse,
            top_k=top_k * 2,
            namespace=tenant_id,
            include_metadata=True
        )

        # RRF fusion
        return self._reciprocal_rank_fusion(
            [dense_results.matches, sparse_results.matches],
            k=k,
            top_k=top_k
        )

    def _reciprocal_rank_fusion(self, result_lists: list, k: int = 60,
                                 top_k: int = 15) -> list:
        """Combine multiple ranked lists using RRF."""
        scores = defaultdict(float)
        doc_map = {}

        for results in result_lists:
            for rank, match in enumerate(results, 1):
                scores[match.id] += 1.0 / (k + rank)
                doc_map[match.id] = match

        # Sort by RRF score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return [doc_map[doc_id] for doc_id, score in ranked[:top_k]]
```

**Alternative -- Pinecone's built-in hybrid:** Pinecone now offers `pinecone-sparse-english-v0` as a managed sparse encoder. This produces better sparse vectors than local BM25 but requires sending text to Pinecone's API. Given that your data includes sensitive enterprise content, local BM25 encoding with `pinecone-text` is the safer choice.

**Complexity:** Medium. Requires re-indexing with sparse vectors and modifying search logic.

**Expected improvement:** 15-30% recall improvement over dense-only search. RRF specifically outperforms linear alpha-weighting because it is robust to score distribution mismatches between sparse and dense retrievers.

**Priority: HIGH** -- Your current hybrid search uses basic keyword boosting. True sparse-dense with RRF is a significant upgrade.

---

### 3.2 Sparse-Dense Hybrid with Learned Weights

**What it is:** Instead of fixed alpha=0.5 or parameter-free RRF, learn per-query-type weights for sparse vs. dense retrieval using your feedback data.

**Implementation:**

```python
# After collecting sufficient SearchFeedback data (section 2.4)

class LearnedHybridWeights:
    """Learn optimal sparse/dense weights per query type."""

    def __init__(self):
        # Initialize with sensible defaults
        self.weights = {
            'factual': {'dense': 0.5, 'sparse': 0.5},    # Keywords matter for facts
            'exploratory': {'dense': 0.8, 'sparse': 0.2}, # Semantics dominate
            'comparative': {'dense': 0.7, 'sparse': 0.3},
            'procedural': {'dense': 0.6, 'sparse': 0.4},
            'temporal': {'dense': 0.5, 'sparse': 0.5},
            'person_specific': {'dense': 0.4, 'sparse': 0.6},  # Names are keywords
        }

    def optimize_from_feedback(self, feedback_data: list):
        """Grid search optimal weights using clicked vs. not-clicked signals."""
        for query_type in self.weights:
            type_feedback = [f for f in feedback_data if f.query_type == query_type]
            if len(type_feedback) < 50:
                continue  # Not enough data

            best_score = 0
            best_weights = self.weights[query_type]

            for dense_w in np.arange(0.1, 1.0, 0.1):
                sparse_w = 1.0 - dense_w
                score = self._evaluate_weights(type_feedback, dense_w, sparse_w)
                if score > best_score:
                    best_score = score
                    best_weights = {'dense': dense_w, 'sparse': sparse_w}

            self.weights[query_type] = best_weights
```

**Complexity:** Medium. Requires sufficient feedback data (500+ queries per type).

**Expected improvement:** 5-10% over fixed weights, but only after collecting enough data.

**Priority: LOW** -- Implement after feedback collection is mature. RRF is good enough initially.

---

### 3.3 Keyword Extraction + Semantic Search Combination

**What it is:** Extract explicit keywords/entities from the query, use them for metadata filtering, then use semantic search within the filtered set.

**Implementation for 2nd Brain:**

```python
# In services/enhanced_search_service.py

def _extract_query_signals(self, query: str) -> dict:
    """Extract structured signals from query for targeted retrieval."""
    signals = {
        "person_names": [],
        "date_references": [],
        "source_types": [],
        "project_names": [],
        "keywords": []
    }

    # Person detection (simple patterns + spaCy if available)
    name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
    signals["person_names"] = re.findall(name_pattern, query)

    # Date references
    date_patterns = [
        r'(?:last|this|next)\s+(?:week|month|quarter|year)',
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
        r'\d{1,2}/\d{1,2}/\d{2,4}',
        r'(?:yesterday|today|recently)',
    ]
    for pattern in date_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        signals["date_references"].extend(matches)

    # Source type hints
    source_keywords = {
        'email': ['email', 'wrote', 'sent', 'replied', 'forwarded', 'inbox'],
        'slack': ['slack', 'channel', 'thread', 'posted', 'message'],
        'document': ['document', 'file', 'report', 'presentation', 'spreadsheet'],
    }
    for source, keywords in source_keywords.items():
        if any(kw in query.lower() for kw in keywords):
            signals["source_types"].append(source)

    return signals

def _build_metadata_filter(self, signals: dict) -> dict:
    """Convert extracted signals to Pinecone metadata filter."""
    filters = {}

    if signals["person_names"]:
        filters["sender_name"] = {"$in": signals["person_names"]}

    if signals["source_types"]:
        filters["source_type"] = {"$in": signals["source_types"]}

    if signals["date_references"]:
        date_range = self._parse_date_range(signals["date_references"])
        if date_range:
            filters["created_at"] = {
                "$gte": date_range[0].isoformat(),
                "$lte": date_range[1].isoformat()
            }

    return filters if filters else None
```

**Complexity:** Low. Pattern matching + metadata filtering using Pinecone's existing capabilities.

**Expected improvement:** 15-25% improvement on person/date/source-specific queries, which are extremely common in enterprise knowledge management.

**Priority: HIGH** -- Low effort, high impact for your use case. Enterprise users constantly ask "what did [person] say about [topic]" or "emails from last week about [topic]".

---

## 4. Answer Quality

### 4.1 Chain-of-Thought Retrieval

**What it is:** For complex queries, decompose them into sub-questions, retrieve for each sub-question separately, then synthesize. "Compare our Q3 and Q4 marketing strategies" becomes: (1) "What was our Q3 marketing strategy?" (2) "What was our Q4 marketing strategy?" (3) Synthesize comparison.

**Implementation for 2nd Brain:**

```python
# In services/enhanced_search_service.py

async def _decompose_and_retrieve(self, query: str, tenant_id: str) -> list:
    """Decompose complex query into sub-questions, retrieve for each."""

    # Step 1: Decompose
    decomp_prompt = f"""Break this question into 2-4 simpler sub-questions that,
when answered together, fully answer the original question.
Return as a JSON array of strings. If the question is already simple,
return just the original question in the array.

Question: {query}

Sub-questions (JSON array):"""

    response = self.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": decomp_prompt}],
        max_tokens=200,
        temperature=0.0
    )

    sub_questions = json.loads(response.choices[0].message.content)

    # Step 2: Retrieve for each sub-question
    all_results = []
    seen_ids = set()

    for sub_q in sub_questions:
        results = await self._basic_retrieve(sub_q, tenant_id, top_k=8)
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_results.append(r)

    # Step 3: Rerank combined results against original query
    reranked = self._cross_encoder_rerank(query, all_results)

    return reranked[:15]
```

**Integration with existing QueryClassifier:** Only trigger decomposition for `comparative` and `exploratory` query types. Skip for `factual` (single-fact lookup doesn't need decomposition).

**Complexity:** Low-Medium.

**Expected improvement:** 15-30% improvement on multi-hop and comparative queries. CoRAG (Chain-of-Retrieval) reports consistent improvement on complex reasoning tasks.

**Priority: MEDIUM** -- Your existing system handles simple queries well. This specifically targets the complex queries that currently fail.

---

### 4.2 Self-RAG (Model Decides When to Retrieve)

**What it is:** The model itself decides whether retrieval is needed, evaluates retrieved documents for relevance, and decides whether to use them or retrieve more. Uses special "reflection tokens" (ISREL, ISSUP, ISUSE) to self-evaluate.

**Practical implementation for 2nd Brain (simplified):**

```python
# In services/enhanced_search_service.py

async def self_rag_search(self, query: str, tenant_id: str) -> dict:
    """Self-RAG: model decides retrieval strategy and evaluates results."""

    # Step 1: Does this query need retrieval?
    needs_retrieval = await self._assess_retrieval_need(query)

    if not needs_retrieval:
        # Answer directly (greetings, meta-questions, simple math)
        return {"answer": await self._direct_answer(query), "sources": []}

    # Step 2: Retrieve
    results = await self.enhanced_search(query, tenant_id, top_k=15)

    # Step 3: Evaluate relevance of each result
    relevant_results = []
    for result in results:
        relevance = await self._evaluate_relevance(query, result)
        if relevance > 0.5:
            relevant_results.append(result)

    # Step 4: Generate answer
    answer = await self._generate_with_context(query, relevant_results)

    # Step 5: Self-critique -- is the answer supported?
    support_check = await self._check_support(answer, relevant_results)

    if support_check["score"] < 0.6:
        # Not well supported -- try different retrieval
        expanded_query = await self._expand_for_gaps(query, answer, relevant_results)
        more_results = await self.enhanced_search(expanded_query, tenant_id, top_k=10)
        relevant_results.extend(more_results)
        answer = await self._generate_with_context(query, relevant_results)

    return {
        "answer": answer,
        "sources": relevant_results,
        "support_score": support_check["score"],
        "retrieval_rounds": 2 if support_check["score"] < 0.6 else 1
    }

async def _assess_retrieval_need(self, query: str) -> bool:
    """Quick check: does this query need document retrieval?"""
    no_retrieval_patterns = [
        r'^(hi|hello|hey|thanks|thank you)',
        r'^(what can you|how do you|who are you)',
        r'^(summarize|rewrite|translate)\s+(?:this|the following)',
    ]
    for pattern in no_retrieval_patterns:
        if re.match(pattern, query.lower()):
            return False
    return True
```

**Complexity:** Medium-High. Multiple LLM calls per query (3-5), each adding latency.

**Expected improvement:** 10-20% improvement in answer quality, primarily by reducing hallucination (refusing to answer when evidence is weak) and improving coverage (retrieving more when initial results are insufficient).

**Priority: MEDIUM** -- Your existing hallucination detection partially covers this. The main new value is the "retrieve more if not supported" loop.

---

### 4.3 CRAG (Corrective RAG)

**What it is:** After retrieval, evaluate each document as Correct/Incorrect/Ambiguous. If results are Incorrect, trigger web search or expanded retrieval. If Ambiguous, decompose and retry. Only proceed to generation with verified-relevant documents.

**Implementation for 2nd Brain:**

```python
# In services/enhanced_search_service.py

async def corrective_rag(self, query: str, results: list) -> dict:
    """CRAG: evaluate, correct, then generate."""

    # Classify each result
    classifications = []
    for result in results:
        classification = await self._classify_relevance(query, result)
        classifications.append({
            "result": result,
            "label": classification,  # "correct" | "incorrect" | "ambiguous"
        })

    correct = [c["result"] for c in classifications if c["label"] == "correct"]
    ambiguous = [c["result"] for c in classifications if c["label"] == "ambiguous"]

    if len(correct) >= 3:
        # Enough good results -- proceed
        return {"results": correct, "action": "direct"}

    if len(correct) + len(ambiguous) < 3:
        # Not enough -- expand search
        expanded_query = await self._reformulate_query(query)
        new_results = await self.enhanced_search(expanded_query, tenant_id, top_k=20)
        # Re-classify new results
        for result in new_results:
            classification = await self._classify_relevance(query, result)
            if classification == "correct":
                correct.append(result)
        return {"results": correct, "action": "expanded"}

    # Use correct + ambiguous with lower confidence
    return {"results": correct + ambiguous, "action": "mixed"}

async def _classify_relevance(self, query: str, result: dict) -> str:
    """Classify if a retrieved document is relevant to the query."""
    prompt = f"""Is this document relevant to answering the query?

Query: {query}
Document: {result['text'][:1000]}

Answer with exactly one word: CORRECT, INCORRECT, or AMBIGUOUS"""

    response = self.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0.0
    )
    label = response.choices[0].message.content.strip().lower()
    if label not in ("correct", "incorrect", "ambiguous"):
        return "ambiguous"
    return label
```

**Cost consideration:** Classifying 15 results costs ~15 gpt-4o-mini calls per query (~$0.002 total). This is acceptable for a B2B SaaS product.

**Complexity:** Medium.

**Expected improvement:** 15-25% reduction in irrelevant context reaching the LLM, directly improving answer quality and reducing hallucination.

**Priority: HIGH** -- This is a natural extension of your existing hallucination detection. Instead of detecting hallucination after generation, prevent it by filtering bad retrieval results before generation.

---

### 4.4 Iterative Retrieval

**What it is:** Generate a partial answer, identify what information is still missing, retrieve specifically for those gaps, and repeat until the answer is complete or a max iteration limit is reached.

**Implementation for 2nd Brain:**

```python
# In services/enhanced_search_service.py

async def iterative_retrieval_answer(self, query: str, tenant_id: str,
                                      max_iterations: int = 3) -> dict:
    """Iteratively retrieve and generate until answer is complete."""

    all_context = []
    iteration_log = []

    for i in range(max_iterations):
        if i == 0:
            search_query = query
        else:
            # Identify what's missing from the partial answer
            search_query = await self._identify_gaps(query, partial_answer, all_context)
            if not search_query:
                break  # Answer is complete

        # Retrieve
        results = await self.enhanced_search(search_query, tenant_id, top_k=10)
        new_context = [r for r in results if r.id not in {c.id for c in all_context}]
        all_context.extend(new_context)

        # Generate (partial) answer
        partial_answer = await self._generate_with_context(query, all_context)

        iteration_log.append({
            "iteration": i + 1,
            "search_query": search_query,
            "new_docs_found": len(new_context),
            "total_context": len(all_context)
        })

        # Check completeness
        completeness = await self._assess_completeness(query, partial_answer)
        if completeness > 0.85:
            break

    return {
        "answer": partial_answer,
        "iterations": len(iteration_log),
        "iteration_log": iteration_log,
        "sources": all_context
    }

async def _identify_gaps(self, original_query: str, partial_answer: str,
                          existing_context: list) -> str:
    """Identify what information is still missing."""
    prompt = f"""Given this question and partial answer, what specific information
is still missing or needs more detail?

Question: {original_query}
Current answer: {partial_answer}

If the answer is complete, respond with "COMPLETE".
Otherwise, write a search query to find the missing information:"""

    response = self.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.0
    )
    result = response.choices[0].message.content.strip()
    return None if result == "COMPLETE" else result
```

**Complexity:** Medium-High. Multiple LLM calls and retrieval rounds per query.

**Expected improvement:** 20-35% improvement on complex, multi-faceted questions. Minimal improvement on simple factual queries.

**Priority: MEDIUM** -- Use for `exploratory` and `comparative` query types only. Gate behind query classification.

---

## 5. Evaluation and Monitoring

### 5.1 RAGAS Framework Integration

**What it is:** RAGAS provides four core metrics for evaluating RAG without ground-truth labels:
- **Faithfulness:** Is the answer grounded in the retrieved context? (0-1)
- **Answer Relevancy:** Does the answer address the query? (0-1)
- **Context Precision:** Are the retrieved documents relevant? (0-1)
- **Context Recall:** Did retrieval find all relevant documents? (requires ground truth)

**Implementation for 2nd Brain:**

```bash
pip install ragas
```

```python
# New file: services/rag_evaluator.py

from ragas.metrics import faithfulness, answer_relevancy, context_precision
from ragas import evaluate
from datasets import Dataset

class RAGEvaluator:
    """Evaluate RAG quality using RAGAS metrics."""

    def evaluate_single(self, query: str, answer: str, contexts: list) -> dict:
        """Evaluate a single RAG response."""
        dataset = Dataset.from_dict({
            "question": [query],
            "answer": [answer],
            "contexts": [contexts],  # List of retrieved text chunks
        })

        results = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
            llm=self._get_evaluator_llm(),  # Use gpt-4o-mini for cost
        )

        return {
            "faithfulness": float(results["faithfulness"]),
            "answer_relevancy": float(results["answer_relevancy"]),
            "context_precision": float(results["context_precision"]),
        }

    def batch_evaluate(self, evaluations: list) -> dict:
        """Evaluate a batch of RAG responses for monitoring."""
        dataset = Dataset.from_dict({
            "question": [e["query"] for e in evaluations],
            "answer": [e["answer"] for e in evaluations],
            "contexts": [e["contexts"] for e in evaluations],
        })

        results = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
            llm=self._get_evaluator_llm(),
        )

        return {
            "avg_faithfulness": float(results["faithfulness"]),
            "avg_answer_relevancy": float(results["answer_relevancy"]),
            "avg_context_precision": float(results["context_precision"]),
            "sample_count": len(evaluations),
        }

    async def evaluate_in_production(self, query: str, answer: str,
                                      contexts: list) -> dict:
        """Lightweight production evaluation (no RAGAS dependency)."""
        # Custom lightweight faithfulness check
        faithfulness_score = await self._check_faithfulness(answer, contexts)

        # Custom relevancy check
        relevancy_score = await self._check_relevancy(query, answer)

        return {
            "faithfulness": faithfulness_score,
            "relevancy": relevancy_score,
        }

    async def _check_faithfulness(self, answer: str, contexts: list) -> float:
        """Check if answer claims are supported by context."""
        # This overlaps with your existing hallucination detection
        # Reuse that logic and return a 0-1 score
        context_text = "\n---\n".join(contexts[:10])

        prompt = f"""Rate how well this answer is supported by the provided context.
Score from 0.0 (completely unsupported) to 1.0 (fully supported).

Context:
{context_text[:5000]}

Answer:
{answer}

Score (just the number):"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.0
        )
        try:
            return float(response.choices[0].message.content.strip())
        except ValueError:
            return 0.5
```

**Complexity:** Low for RAGAS integration. Medium for custom lightweight evaluator.

**Expected improvement:** Not a direct quality improvement, but enables data-driven optimization of all other techniques. Essential for measuring the impact of any RAG change.

**Priority: HIGH** -- You cannot improve what you do not measure. Implement evaluation before making other changes so you can measure their impact.

---

### 5.2 Production Monitoring Dashboard

**What it is:** Continuous monitoring of RAG quality metrics in production, with alerting on degradation.

**Implementation for 2nd Brain:**

```python
# New table in database/models.py

class RAGMetrics(Base):
    __tablename__ = 'rag_metrics'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False)
    query = Column(Text, nullable=False)
    query_type = Column(String(50), nullable=True)
    answer = Column(Text, nullable=False)

    # Quality metrics
    faithfulness = Column(Float, nullable=True)
    relevancy = Column(Float, nullable=True)
    context_precision = Column(Float, nullable=True)
    hallucination_score = Column(Float, nullable=True)
    citation_coverage = Column(Float, nullable=True)

    # Performance metrics
    retrieval_latency_ms = Column(Integer, nullable=True)
    reranking_latency_ms = Column(Integer, nullable=True)
    generation_latency_ms = Column(Integer, nullable=True)
    total_latency_ms = Column(Integer, nullable=True)

    # Retrieval stats
    chunks_retrieved = Column(Integer, nullable=True)
    chunks_after_rerank = Column(Integer, nullable=True)
    unique_documents = Column(Integer, nullable=True)

    # Cost
    embedding_tokens = Column(Integer, nullable=True)
    llm_input_tokens = Column(Integer, nullable=True)
    llm_output_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Monitoring API
@blueprint.route('/api/admin/rag-metrics', methods=['GET'])
@require_auth
@require_admin
def get_rag_metrics():
    """Dashboard data for RAG quality monitoring."""
    days = request.args.get('days', 7, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    metrics = db.session.query(
        func.avg(RAGMetrics.faithfulness).label('avg_faithfulness'),
        func.avg(RAGMetrics.relevancy).label('avg_relevancy'),
        func.avg(RAGMetrics.total_latency_ms).label('avg_latency'),
        func.avg(RAGMetrics.estimated_cost_usd).label('avg_cost'),
        func.count(RAGMetrics.id).label('total_queries'),
        func.avg(case(
            (RAGMetrics.faithfulness < 0.5, 1), else_=0
        )).label('low_faith_rate'),
    ).filter(
        RAGMetrics.tenant_id == g.tenant_id,
        RAGMetrics.created_at >= since
    ).first()

    return jsonify({
        "period_days": days,
        "avg_faithfulness": round(float(metrics.avg_faithfulness or 0), 3),
        "avg_relevancy": round(float(metrics.avg_relevancy or 0), 3),
        "avg_latency_ms": int(metrics.avg_latency or 0),
        "avg_cost_usd": round(float(metrics.avg_cost or 0), 4),
        "total_queries": metrics.total_queries,
        "low_faithfulness_rate": round(float(metrics.low_faith_rate or 0), 3),
    })
```

**Alerting:**
```python
# In services/rag_evaluator.py

async def check_and_alert(self, metrics: dict):
    """Alert if quality degrades below thresholds."""
    alerts = []

    if metrics["faithfulness"] < 0.6:
        alerts.append(f"Faithfulness dropped to {metrics['faithfulness']:.2f} (threshold: 0.6)")

    if metrics["relevancy"] < 0.5:
        alerts.append(f"Relevancy dropped to {metrics['relevancy']:.2f} (threshold: 0.5)")

    if metrics["total_latency_ms"] > 5000:
        alerts.append(f"Latency spiked to {metrics['total_latency_ms']}ms (threshold: 5000ms)")

    if alerts:
        # Send via existing email notification system
        await self._send_alert_email(alerts)
```

**Complexity:** Medium. Database table + recording logic + dashboard endpoint.

**Expected improvement:** Enables 10-20% quality improvement over time by identifying and fixing degradation patterns.

**Priority: HIGH** -- Essential infrastructure for all other improvements.

---

### 5.3 A/B Testing Framework

**What it is:** Run two RAG pipeline configurations simultaneously, randomly assign users to variants, and compare quality metrics.

**Implementation for 2nd Brain:**

```python
# New file: services/ab_test_service.py

import hashlib
import random

class ABTestService:
    """A/B testing for RAG pipeline configurations."""

    def __init__(self, db):
        self.db = db
        self.active_tests = {}  # test_id -> config

    def create_test(self, test_id: str, description: str,
                     control_config: dict, variant_config: dict,
                     traffic_split: float = 0.5):
        """Create a new A/B test."""
        self.active_tests[test_id] = {
            "description": description,
            "control": control_config,
            "variant": variant_config,
            "split": traffic_split,
            "created_at": datetime.utcnow().isoformat(),
        }

    def get_variant(self, test_id: str, user_id: str) -> tuple:
        """Deterministically assign user to control or variant."""
        test = self.active_tests.get(test_id)
        if not test:
            return "control", {}

        # Deterministic assignment based on user_id + test_id
        hash_input = f"{user_id}:{test_id}".encode()
        hash_val = int(hashlib.md5(hash_input).hexdigest(), 16) % 100

        if hash_val < test["split"] * 100:
            return "variant", test["variant"]
        else:
            return "control", test["control"]

    def get_test_results(self, test_id: str) -> dict:
        """Compare metrics between control and variant."""
        control_metrics = self.db.session.query(
            func.avg(RAGMetrics.faithfulness),
            func.avg(RAGMetrics.relevancy),
            func.avg(RAGMetrics.total_latency_ms),
            func.count(RAGMetrics.id),
        ).filter(
            RAGMetrics.ab_test_id == test_id,
            RAGMetrics.ab_variant == "control"
        ).first()

        variant_metrics = self.db.session.query(
            func.avg(RAGMetrics.faithfulness),
            func.avg(RAGMetrics.relevancy),
            func.avg(RAGMetrics.total_latency_ms),
            func.count(RAGMetrics.id),
        ).filter(
            RAGMetrics.ab_test_id == test_id,
            RAGMetrics.ab_variant == "variant"
        ).first()

        return {
            "test_id": test_id,
            "control": {
                "faithfulness": float(control_metrics[0] or 0),
                "relevancy": float(control_metrics[1] or 0),
                "latency_ms": int(control_metrics[2] or 0),
                "sample_size": control_metrics[3],
            },
            "variant": {
                "faithfulness": float(variant_metrics[0] or 0),
                "relevancy": float(variant_metrics[1] or 0),
                "latency_ms": int(variant_metrics[2] or 0),
                "sample_size": variant_metrics[3],
            },
            "significant": self._is_significant(control_metrics, variant_metrics),
        }
```

**Example A/B tests to run:**

| Test | Control | Variant | What you learn |
|------|---------|---------|----------------|
| Contextual Retrieval | Current chunks | Chunks with context prefix | Impact of contextual embedding |
| HyDE | Direct query embedding | HyDE + query embedding | HyDE value for your data |
| Reranker model | ms-marco-MiniLM-L-12 | jina-reranker-v2 | Better reranker? |
| RRF vs Alpha | alpha=0.5 blend | RRF fusion | Which hybrid approach wins |
| Parent-Child | 2000-char chunks | 500-char child / 4000-char parent | Hierarchical benefit |

**Complexity:** Medium. Requires RAGMetrics table + variant tracking + statistical testing.

**Expected improvement:** Not direct, but enables confident rollout of all other improvements.

**Priority: MEDIUM** -- Implement after RAGMetrics table is in place (section 5.2).

---

## Implementation Roadmap

### Phase 1: Foundation (1-2 weeks)
_Goal: Measure before you change_

| Task | Priority | Complexity | Files to modify |
|------|----------|------------|-----------------|
| RAGMetrics table + recording | HIGH | Medium | `database/models.py`, `services/enhanced_search_service.py` |
| SearchFeedback table + API | HIGH | Low | `database/models.py`, `api/search_routes.py` |
| Lightweight faithfulness scorer | HIGH | Low | `services/rag_evaluator.py` (new) |
| Thumbs up/down in frontend | HIGH | Low | `frontend/components/Chat.tsx` |

### Phase 2: High-Impact Retrieval (2-3 weeks)
_Goal: Biggest quality improvements_

| Task | Priority | Complexity | Expected Gain |
|------|----------|------------|---------------|
| Contextual Retrieval (summary-based) | HIGH | Medium | +35-49% recall |
| BM25 + Dense RRF hybrid search | HIGH | Medium | +15-30% recall |
| Keyword extraction + metadata filtering | HIGH | Low | +15-25% on entity queries |
| CRAG (Corrective RAG) | HIGH | Medium | +15-25% precision |
| Parent-Child chunk retrieval | HIGH | Medium | +15-25% answer quality |

### Phase 3: Query Intelligence (2-3 weeks)
_Goal: Smarter per-query behavior_

| Task | Priority | Complexity | Expected Gain |
|------|----------|------------|---------------|
| Expanded adaptive retrieval strategies | HIGH | Low | +10-15% |
| Query rewriting with user context | MEDIUM | Low-Medium | +10-20% on ambiguous queries |
| HyDE (for exploratory queries only) | MEDIUM | Medium | +10-25% on exploratory |
| Session-aware coreference resolution | MEDIUM | Medium | +20-30% on follow-ups |
| Chain-of-thought decomposition | MEDIUM | Medium | +15-30% on complex queries |

### Phase 4: Feedback Loop (2-3 weeks)
_Goal: Continuous improvement from usage_

| Task | Priority | Complexity | Expected Gain |
|------|----------|------------|---------------|
| A/B testing framework | MEDIUM | Medium | Enables confident rollout |
| Iterative retrieval | MEDIUM | Medium-High | +20-35% on complex queries |
| Self-RAG retrieval loop | MEDIUM | Medium-High | +10-20% answer quality |
| Personalized embeddings | LOW | Medium | +5-15% for repeat users |
| Learned hybrid weights | LOW | Medium | +5-10% after enough data |

### Phase 5: Infrastructure (as needed)
_Goal: Scale and efficiency_

| Task | Priority | Complexity | Expected Gain |
|------|----------|------------|---------------|
| Agentic RAG with source routing | MEDIUM | High | +20-40% multi-source queries |
| Multi-vector retrieval (questions only) | LOW-MEDIUM | High | +10-20% recall |
| ColBERT v2 reranker upgrade | LOW | Low | +2-5% reranking quality |
| RAGAS batch evaluation pipeline | MEDIUM | Low | Better measurement |

---

## Cost Estimates Per Query

| Component | Current | After Phase 2 | After Phase 3 |
|-----------|---------|---------------|---------------|
| Embedding (query) | $0.00001 | $0.00001 | $0.00002 (HyDE) |
| Retrieval (Pinecone) | $0.00001 | $0.00002 (dual search) | $0.00003 |
| Reranking (local) | $0.00 | $0.00 | $0.00 |
| CRAG classification | $0.00 | $0.002 (15 calls) | $0.002 |
| Query rewriting | $0.00 | $0.00 | $0.0001 |
| Generation (GPT-5) | $0.01 | $0.01 | $0.01 |
| Evaluation | $0.00 | $0.0001 | $0.0001 |
| **Total per query** | **~$0.01** | **~$0.012** | **~$0.014** |

The additional cost is approximately $0.002-0.004 per query (~20-40% increase), which is negligible for B2B SaaS pricing.

---

## Summary of Recommendations

**Do immediately (highest ROI):**
1. Start collecting feedback data (SearchFeedback table + thumbs up/down)
2. Add RAGMetrics recording to every query
3. Implement Contextual Retrieval using existing structured summaries (near-zero cost)
4. Upgrade to true BM25+dense RRF hybrid search
5. Add keyword/entity extraction for metadata filtering

**Do next (high impact, moderate effort):**
6. Parent-Child chunk retrieval
7. CRAG (Corrective RAG) post-retrieval filtering
8. Expanded adaptive retrieval strategies in QueryClassifier
9. Query rewriting with user context

**Do when ready (requires data or infrastructure):**
10. HyDE for exploratory queries
11. Session-aware coreference resolution
12. A/B testing framework
13. Chain-of-thought retrieval decomposition

**Do eventually (diminishing returns):**
14. Agentic RAG with source routing
15. Personalized embeddings
16. Multi-vector retrieval
17. Learned hybrid weights
