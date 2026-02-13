# KnowledgeVault Project Detection Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES                            │
├─────────────────────────────────────────────────────────────────┤
│  • Email (Gmail/IMAP)  • Chat (Google Chat)  • Documents (PDF)  │
│  • Metadata: subject, employee, timestamp, folder               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Employee    │  │  Project     │  │  Stakeholder │
│  Clustering  │  │  Clustering  │  │  Graph       │
│              │  │              │  │              │
│ Hard cluster │  │ Semantic     │  │ Extract:     │
│ by metadata  │  │ clustering   │  │ • People     │
│ 'employee'   │  │ (BERTopic)   │  │ • Expertise  │
│              │  │              │  │ • Projects   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ▼                 ▼                 ▼
    [JSONL]          [JSONL +         [Pickle +
   per emp        Keywords]        Knowledge]
       │                 │                 │
       └──────────────────┼─────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────────┐ ┌────────────────┐ ┌────────────────┐
│ Global Project   │ │ DistilBERT     │ │ GPT Naming     │
│ Classification   │ │ Classification │ │ (Chat spaces)  │
│                  │ │                │ │                │
│ Zero-shot with   │ │ Supervised     │ │ Cache results  │
│ BART-MNLI        │ │ fine-tuned     │ │ by space_id    │
└──────┬───────────┘ └────────┬───────┘ └────────┬───────┘
       │                      │                  │
       └──────────────────────┼──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Normalized     │
                    │ Project Metadata │
                    │                  │
                    │ • Project name   │
                    │ • Members        │
                    │ • Topics         │
                    │ • Confidence     │
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
            ┌──────────────┐  ┌──────────────┐
            │  JSON Files  │  │  Pickle      │
            │              │  │  Serialized  │
            │ project_     │  │              │
            │ mapping.json │  │ stakeholder_ │
            │ user_spaces  │  │ graph.pkl    │
            │ metadata     │  │              │
            └──────────────┘  └──────────────┘
                    │                 │
                    └────────┬────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    Flask API     │
                    │                  │
                    │ /api/spaces      │
                    │ /api/questions   │
                    │ /api/stakeholders│
                    │ /api/search      │
                    └──────────────────┘
```

---

## Data Flow: Document to Project

```
DOCUMENT
  ├─ metadata.subject
  ├─ metadata.employee
  ├─ metadata.timestamp
  ├─ metadata.project (optional)
  └─ content

       │
       ├─────────────────────────────────────┐
       │                                     │
       ▼                                     ▼
   METADATA PATH                      CONTENT PATH
   (Quick)                            (Semantic)
   
   Extract from:                      Extract from:
   ├─ metadata.project                ├─ Content patterns
   ├─ metadata.subject                │  (Project: X, Case: Y)
   ├─ metadata.file_name              ├─ Document keywords
   └─ metadata.folder                 └─ Topic modeling
   
       │                                     │
       ▼                                     ▼
   [Metadata Extracted]              [Semantic Features]
   [Normalized Name]                 [Topic Clusters]
       │                                     │
       └─────────────────┬───────────────────┘
                         │
                         ▼
                 ┌──────────────┐
                 │ Project Name │
                 │ (Normalized) │
                 └─────────────┘
                         │
             ┌───────────┼───────────┐
             │           │           │
             ▼           ▼           ▼
       [Link to]    [Link to]   [Link to]
       Employee     Expert      Client
         Team       (via NER)
```

---

## Clustering Algorithm Details

### BERTopic Pipeline (Primary Method)

```
DOCUMENTS
(with subject, content)
     │
     ▼
┌─────────────────────────────────┐
│ Embedding Layer                 │
├─────────────────────────────────┤
│ Model: all-mpnet-base-v2        │
│ Input: enriched_text            │
│        = subject + subject +    │
│          content                │
│ Output: 768-dim vectors         │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ UMAP Dimensionality Reduction   │
├─────────────────────────────────┤
│ Input: 768-dim vectors          │
│ Parameters:                     │
│ • n_neighbors: 15               │
│ • n_components: 5               │
│ • metric: cosine                │
│ Output: 5-dim vectors           │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ HDBSCAN Clustering              │
├─────────────────────────────────┤
│ Input: 5-dim vectors            │
│ Parameters:                     │
│ • min_cluster_size: 5           │
│ • min_samples: 3                │
│ • metric: euclidean             │
│ Output: Cluster assignments     │
│         (topic IDs)             │
│ Special: -1 = outliers          │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ CountVectorizer (Topic Repr.)   │
├─────────────────────────────────┤
│ Input: Docs in each cluster     │
│ Parameters:                     │
│ • stop_words: english           │
│ • min_df: 2                     │
│ • ngram_range: (1,2)            │
│ Output: Topic keywords          │
│         (top 10 words)          │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ OUTPUT: Projects                │
├─────────────────────────────────┤
│ For each topic:                 │
│ • topic_id (cluster ID)         │
│ • label (keyword-based name)    │
│ • keywords (top words)          │
│ • documents (assigned docs)     │
│ • document_count                │
└─────────────────────────────────┘
```

---

## Data Structures in Memory

```python
# StakeholderGraph main structures
class StakeholderGraph:
    people: Dict[str, Person] = {
        "normalized_name": {
            .name: str
            .roles: Set[str]
            .expertise: Set[str]
            .projects: Set[str]
            .documents: Set[str]
            .mentions: int
            .email: str
        }
    }
    
    projects: Dict[str, Project] = {
        "normalized_name": {
            .name: str
            .members: Set[str]          # person names
            .documents: Set[str]        # doc IDs
            .topics: Set[str]           # expertise domains
            .status: str
            .client: str
        }
    }
    
    expertise_people: Dict[str, Set[str]] = {
        "domain": {"person1", "person2", ...}
    }
    
    document_people: Dict[str, Set[str]] = {
        "doc_id": {"person1", "person2", ...}
    }
```

---

## File Organization

```
PROJECT_CLUSTERS/
├─ Project Clustering Summary
│  └─ project_clustering_summary.json
│     {
│       "total_employees": int,
│       "total_projects": int,
│       "total_documents": int,
│       "employees": {
│         "emp_name": {
│           "total_documents": int,
│           "num_projects": int,
│           "outlier_count": int
│         }
│       }
│     }
│
├─ [EMPLOYEE_1]/
│  ├─ project_1.jsonl     ← JSONL: documents in this project
│  ├─ project_2.jsonl
│  ├─ outliers.jsonl      ← JSONL: noise/outliers
│  └─ metadata.json       ← Per-employee metadata
│     {
│       "employee": str,
│       "total_documents": int,
│       "num_projects": int,
│       "projects": {
│         "proj_name": {
│           "cluster_id": str,
│           "document_count": int,
│           "keywords": [str]
│         }
│       },
│       "outlier_count": int
│     }
│
├─ [EMPLOYEE_2]/
│  └─ ...
│
└─ [EMPLOYEE_N]/
   └─ ...
```

---

## API Endpoints & Response Flow

```
CLIENT REQUEST
    │
    ▼
┌────────────────────────────┐
│ Flask Route Handler        │
│ (/api/spaces, /api/search) │
└────────────────┬───────────┘
                 │
                 ▼
         ┌──────────────────┐
         │ Check Query Type │
         ├──────────────────┤
         │ • Space filter?  │
         │ • "Who" query?   │
         │ • Project name?  │
         └────┬───┬───┬─────┘
             │   │   │
    ┌────────┘   │   └────────┐
    │            │            │
    ▼            ▼            ▼
 SPACES      WHO QUERY    GENERIC
 FILTER      (Graph API)  SEARCH
    │            │          │
    │      StakeholderGraph  │
    │      answer_who_query()│
    │            │          │
    └────────┬───┘          │
             │              │
             ▼              ▼
       ┌──────────────┐ ┌──────────────┐
       │ Format       │ │ Enhanced RAG │
       │ Results      │ │ .query()     │
       └──────┬───────┘ └──────┬───────┘
              │                │
              └────────┬───────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ JSON Response        │
            ├──────────────────────┤
            │ {                    │
            │   "answer": str,     │
            │   "sources": [...],  │
            │   "projects": [...], │
            │   "people": [...]    │
            │ }                    │
            └──────────────────────┘
                       │
                       ▼
                   CLIENT
```

---

## Key Algorithms Comparison

| Aspect | BERTopic | Zero-Shot | DistilBERT | GPT Naming |
|--------|----------|-----------|-----------|-----------|
| **Type** | Unsupervised | Zero-shot | Supervised | LLM |
| **Training** | None | None | Fine-tuned | Prompt-based |
| **Speed** | Slow | Fast | Medium | Slow (API) |
| **Accuracy** | Good | Medium | Excellent | Excellent |
| **Interpretability** | Keywords | Scores | Confidence | Human-readable |
| **Requirements** | Min 10 docs | Categories | Labeled data | API key + cache |
| **Use Case** | Auto-discovery | Quick sort | Production | Human names |

---

## Project Detection Confidence Levels

```
CONFIDENCE SCORING:

1. Metadata-based (HIGHEST)
   ✓ Explicit project field
   ✓ Derived from known patterns
   Confidence: 0.95+

2. Semantic clustering (HIGH)
   ✓ BERTopic with >50 docs
   ✓ Clear topic keywords
   Confidence: 0.85-0.95

3. Zero-shot classification (MEDIUM)
   ✓ Document matches category
   Confidence: 0.7-0.85

4. Content pattern matching (MEDIUM)
   ✓ "Project X:" pattern found
   Confidence: 0.75-0.85

5. File name extraction (LOW)
   ✓ Fallback only
   Confidence: 0.5-0.7

6. Single cluster (FALLBACK)
   ✓ <10 documents/employee
   Confidence: 0.3-0.5
```

---

## Extension Points

```
CURRENT SYSTEM
├─ Metadata extraction
├─ Employee clustering
├─ Project clustering (BERTopic)
├─ Global classification (Zero-shot)
├─ Stakeholder graph (NER + patterns)
└─ API exposure (Flask)

POTENTIAL EXTENSIONS
├─ Temporal project evolution tracking
├─ Cross-project relationship detection
├─ Dynamic threshold adjustment
├─ Multi-language support
├─ Real-time re-clustering
├─ Active learning for DistilBERT
├─ Hierarchical project organization
├─ Project metadata enrichment
├─ Integration with external project mgmt
└─ ML-based confidence scoring
```

