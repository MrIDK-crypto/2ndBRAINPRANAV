# KnowledgeVault Backend - Project Detection & Clustering Research Summary

## Executive Overview

The KnowledgeVault backend uses a **multi-layered approach** to detect and cluster projects:

1. **Employee-based clustering** (metadata-based hard clustering)
2. **Project-based clustering** (semantic clustering with BERTopic or DistilBERT)
3. **Global project classification** (zero-shot classification across entire dataset)
4. **Stakeholder graph extraction** (person-project associations)
5. **GPT-based project naming** (for Google Chat spaces)

---

## 1. CURRENT PROJECT DETECTION APPROACHES

### 1.1 Employee Clustering (Metadata-Based)
**Location:** `/clustering/employee_clustering.py`

- **Method:** Hard clustering based on document metadata `employee` field
- **Data Structure:** `Dict[employee_name, List[documents]]`
- **Process:**
  - Extracts documents by employee from metadata
  - Groups all documents per employee
  - No semantic analysis - purely metadata-driven
  
**Output Structure:**
```python
{
  "employee_name": [
    {
      "doc_id": "...",
      "metadata": {
        "employee": "...",
        "timestamp": "...",
        "subject": "...",
        "folder": "...",
        ...
      },
      "content": "..."
    }
  ]
}
```

### 1.2 Project Clustering (Semantic + DistilBERT Hybrid)
**Location:** `/clustering/project_clustering.py`

- **Primary Method:** BERTopic (topic modeling with UMAP + HDBSCAN)
- **Secondary Method:** DistilBERT-based supervised classification (if model available)
- **Fallback:** Single cluster for employees with <10 documents

**BERTopic Configuration:**
```python
UMAP_N_NEIGHBORS = 15
UMAP_N_COMPONENTS = 5
UMAP_METRIC = "cosine"
MIN_CLUSTER_SIZE = 5
MIN_SAMPLES = 3
```

**Key Features:**
- Embedding Model: `sentence-transformers/all-mpnet-base-v2`
- Topic Extraction: Top 10 keywords per topic
- Probability Calculation: Disabled for speed
- Document enrichment: Doubles subject weight for clustering

**Data Structure:**
```python
{
  "employee": "...",
  "total_documents": int,
  "num_projects": int,
  "projects": {
    "project_name": {
      "cluster_id": "employee::project_N",
      "topic_id": int,
      "document_count": int,
      "documents": [...],
      "keywords": ["keyword1", "keyword2", ...],
      "avg_confidence": float  # if DistilBERT
    }
  },
  "outliers": [...]
}
```

**Document Enrichment (before clustering):**
```python
enriched_text = f"{subject} {subject} {content}"
# Subject is weighted 2x for better clustering
```

### 1.3 Global Project Classification
**Location:** `/classification/global_project_classifier.py`

- **Method:** Zero-shot classification using BART-large-MNLI
- **Categories:** Auto-detected from document keywords + default categories
- **Confidence:** Per-document confidence score

**Auto-Detection Process:**
1. Extract subjects from all documents
2. Identify frequent keywords (>3 chars, not common words)
3. Create category names from keywords
4. Add default categories
5. Classify each document against categories

**Default Categories:**
- General Communication
- Project Planning
- Technical Discussion
- Meeting Notes
- Status Update
- Client Communication

**Output Structure:**
```python
project_mapping = {
  "project_name": {
    "project_name": str,
    "total_documents": int,
    "num_employees": int,
    "employees": ["emp1", "emp2"],
    "employee_contributions": {"emp1": 5, "emp2": 3},
    "avg_confidence": float,
    "documents": [...]
  }
}

employee_mapping = {
  "employee": {
    "employee": str,
    "total_documents": int,
    "num_projects": int,
    "all_projects": {"proj1": 5, "proj2": 3},
    "primary_projects": {"proj1": 5},  # >10% of docs
    "documents": [...]
  }
}
```

### 1.4 DistilBERT Project Classification
**Location:** `/classification/project_classifier.py`

- **Model:** DistilBERT-base-uncased (fine-tuned)
- **Training Data:** From existing project clusters
- **Tokenization:** Max 512 tokens, padding/truncation enabled
- **Output:** `(predicted_label, confidence)` tuples

**Training Data Preparation:**
```python
# Load from project cluster directories:
# Data structure:
# project_clusters/
#   employee_1/
#     project_1.jsonl
#     project_2.jsonl
#     outliers.jsonl
#   employee_2/
#     ...
```

---

## 2. METADATA-BASED PROJECT EXTRACTION

### 2.1 Document Metadata Fields Used
**Standard Metadata Fields:**
```python
metadata = {
  "subject": str,           # Email subject or document title
  "file_name": str,         # Original file name
  "employee": str,          # Sender/owner
  "timestamp": str,         # ISO format datetime
  "folder": str,            # Email folder or source
  "date": str,              # Date extracted
  "file_path": str,         # Original file path
  "file_type": str,         # 'text', 'pdf', etc.
  "source": str,            # 'email', 'chat', etc.
  "from": str,              # Sender
  "project": str,           # Project name (if classified)
  "project_category": str,  # Classification category
  "project_confidence": float,  # Classification confidence
  "parser": str             # 'llamaparse', 'direct', etc.
}
```

### 2.2 Project Extraction from Documents
**Location:** `/rag/stakeholder_graph.py` - `extract_project_from_doc()`

**Extraction Order:**
1. Check `metadata.project_name` field
2. Search document content for pattern: `(?:Project|Case|Client):\s+([A-Z][A-Za-z0-9\s&]+)`
3. Search for pattern: `([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:Case Study|Analysis|Project)`
4. Fall back to file name (remove extension, normalize)

**Name Normalization:**
```python
def normalize_name(name: str) -> str:
    name = ' '.join(name.split())  # Remove extra whitespace
    return name.lower().strip()
```

---

## 3. PROJECT DATA STRUCTURES

### 3.1 Core Project Class (Stakeholder Graph)
**Location:** `/rag/stakeholder_graph.py`

```python
@dataclass
class Project:
    """Represents a project or initiative"""
    name: str                          # Display name
    normalized_name: str               # Lowercase, standardized
    members: Set[str]                  # Person names
    documents: Set[str]                # Doc IDs
    topics: Set[str]                   # Expertise domains
    status: Optional[str]              # Project status
    client: Optional[str]              # Client name
```

### 3.2 Person-Project Association (Stakeholder Graph)
**Location:** `/rag/stakeholder_graph.py`

```python
@dataclass
class Person:
    name: str                          # Display name
    normalized_name: str
    roles: Set[str]                    # Job titles
    expertise: Set[str]                # Domain expertise
    projects: Set[str]                 # Associated projects
    documents: Set[str]                # Doc IDs mentioned
    mentions: int                      # Frequency count
    email: Optional[str]
    department: Optional[str]
    relationships: Dict[str, str]      # person -> relationship_type
```

### 3.3 Project Cluster Metadata (File System)
**Location:** `/data/project_clusters/` directory

```
project_clusters/
  {employee_name}/
    {project_name}.jsonl              # JSONL with documents
    outliers.jsonl                    # Noise/outliers
    metadata.json
  {employee_name}/
    ...
  project_clustering_summary.json
```

**Metadata File Structure:**
```json
{
  "employee": "...",
  "total_documents": int,
  "num_projects": int,
  "projects": {
    "project_name": {
      "cluster_id": "employee::project_N",
      "document_count": int,
      "keywords": ["kw1", "kw2"]
    }
  },
  "outlier_count": int
}
```

### 3.4 Google Chat Space Metadata
**Location:** `/project_clusterer.py`

```python
{
  "space_id": str,
  "original_name": str,               # Original space name
  "generated_name": str,              # GPT-generated project name
  "message_count": int,
  "file_count": int,
  "members": [str],                   # Email addresses
  "confidence": float,                # Naming confidence
  "method": str                       # 'gpt', 'too_few_messages', etc.
}
```

### 3.5 User Spaces (Stored as JSON)
**Location:** `/club_data/user_spaces.json`

```json
[
  {
    "space_name": str,
    "space_id": str,
    "members": [str],
    "message_count": int,
    "file_count": int,
    "generated_project_name": str,
    "confidence": float
  }
]
```

---

## 4. CLUSTERING ALGORITHMS IN USE

### 4.1 BERTopic Clustering Pipeline
**Algorithm Chain:**
```
Documents
    ↓
Sentence Transformers (MPNET)
    ↓
UMAP (Dimensionality Reduction)
    ↓
HDBSCAN (Clustering)
    ↓
CountVectorizer (Topic Representation)
    ↓
Topic Labels + Keywords
```

**UMAP Parameters:**
- `n_neighbors=15` - Preserve local structure
- `n_components=5` - Reduce to 5 dimensions
- `metric="cosine"` - Cosine similarity for text

**HDBSCAN Parameters:**
- `min_cluster_size=5` - Minimum documents per cluster
- `min_samples=3` - Minimum samples for density
- `metric="euclidean"` - Euclidean distance
- `prediction_data=True` - Allow prediction on new data

**CountVectorizer:**
- `stop_words="english"` - Filter common words
- `min_df=2` - At least 2 documents
- `ngram_range=(1,2)` - Unigrams and bigrams

### 4.2 Zero-Shot Classification
**Algorithm:** Facebook BART-large-MNLI (Natural Language Inference)
- **Text Processing:**
  - Subject (first): Full weight
  - Content (next): First 500 chars
  - Format: `"{subject}. {content}"`
- **Classification:** Against candidate project categories
- **Output:** Top category + confidence score

### 4.3 DistilBERT Supervised Classification
**Algorithm:** Fine-tuned DistilBERT-base-uncased
- **Training:**
  - Data: Existing project cluster documents
  - Epochs: 3 (configurable)
  - Batch size: 8 (configurable)
  - Warmup: 100 steps
  - Weight decay: 0.01

### 4.4 GPT-Based Naming (Google Chat Spaces)
**Algorithm:** Temperature-controlled GPT-4o-mini
- **Input:**
  - Sample messages (sorted by length, top 10)
  - File names (up to 15)
  - Original space name
- **Process:**
  1. Extract content samples
  2. Create structured prompt
  3. Temperature: 0.3 (low randomness)
  4. Max tokens: 20
  5. Output: 2-5 word project name
- **Caching:** Result cached by `space_id_message_count`

**Prompt Structure:**
```
1. System: "You are a project naming assistant..."
2. User: Formatted content + original name + rules
3. Output: ONLY project name (no explanation)
4. Constraints: 2-5 words, title case, no punctuation
```

---

## 5. PROJECT-RELATED APIs (app_universal.py)

### 5.1 Project/Spaces Endpoints
```
GET  /api/spaces
     → Returns: {"spaces": user_spaces or []}
     
GET  /api/questions?project={project_name}
     → Filter knowledge gaps by project
     
GET  /api/stakeholders/projects
     → Returns: {"projects": project_list, "total": count}
     
POST /api/stakeholders/query
     → Answer "who worked on X?" questions
```

### 5.2 Stakeholder Graph Endpoints
```
GET  /api/stakeholders
     → All people with filtering (non-person term removal)
     → Fields: name, roles, expertise, projects, documents, mentions
     
GET  /api/stakeholders/expertise
     → Domains and people count
     
POST /api/search (with "who" question detection)
     → Routes to stakeholder_graph.answer_who_question()
```

### 5.3 Data Storage/Loading
**Location:** `app_universal.py` - `load_data()` function

**Files Loaded:**
```python
search_index = pickle.load("search_index.pkl")
embedding_index = pickle.load("embedding_index.pkl")
knowledge_gaps = json.load("knowledge_gaps.json")
user_spaces = json.load("user_spaces.json")
kb_metadata = json.load("knowledge_base_metadata.json")
stakeholder_graph = StakeholderGraph.load("stakeholder_graph.pkl")
```

**User Spaces Structure (from app_universal.py):**
```python
# Loaded from club_data/user_spaces.json
user_spaces = [
  {
    "name": str,
    "id": str,
    "members": [str],
    "document_count": int,
    ...
  }
]
```

---

## 6. PROJECT DETECTION WORKFLOW SUMMARY

```
1. INPUT DOCUMENTS
   ↓
2. EMPLOYEE CLUSTERING (metadata: 'employee' field)
   ↓ Each employee's documents saved to separate JSONL
   ↓
3. PROJECT CLUSTERING (per employee)
   ├─ Option A: BERTopic semantic clustering
   ├─ Option B: DistilBERT supervised classification
   └─ Generates keywords, topic IDs, confidence scores
   ↓
4. GLOBAL CLASSIFICATION (across dataset)
   ├─ Auto-detect project categories from keywords
   ├─ Zero-shot classify each document
   └─ Map documents → projects → employees
   ↓
5. STAKEHOLDER GRAPH EXTRACTION
   ├─ Extract project names from metadata/content
   ├─ Link people to projects
   ├─ Extract expertise domains
   └─ Create person-project associations
   ↓
6. API EXPOSURE
   ├─ /api/spaces - List projects
   ├─ /api/stakeholders/projects - Project teams
   ├─ /api/search - Query by project
   └─ /api/stakeholders/query - "Who worked on X?"
```

---

## 7. KEY CONFIGURATION PARAMETERS

**Location:** `config/config.py`

```python
# Clustering
MIN_CLUSTER_SIZE = 5
MIN_SAMPLES = 3
UMAP_N_NEIGHBORS = 15
UMAP_N_COMPONENTS = 5

# Classification
WORK_CONFIDENCE_THRESHOLD = 0.85
UNCERTAIN_LOWER_BOUND = 0.40

# Models
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
CLASSIFICATION_MODEL = "distilbert-base-uncased"
LLM_MODEL = "gpt-4o-mini"

# Retrieval
TOP_K_RETRIEVAL = 10
RERANK_TOP_K = 5
```

---

## 8. GAPS AND LIMITATIONS

**Current Approach Issues:**
1. **Hard clustering:** Employee field must exist in metadata
2. **BERTopic sensitivity:** Depends on number of documents and HDBSCAN parameters
3. **Project name consistency:** Multiple ways to extract/normalize
4. **Person extraction:** Heavy filtering needed to avoid false positives
5. **Cross-project relationships:** No explicit linking of related projects
6. **Temporal dynamics:** No time-aware clustering or project evolution tracking
7. **Confidence thresholds:** Hard-coded values may not fit all datasets

---

## 9. DATA FILES AND LOCATIONS

**Key Project-Related Files:**
```
/data/
  /project_clusters/
    {employee}/*.jsonl          # Per-employee project documents
    {employee}/metadata.json
    project_clustering_summary.json
  /employee_clusters/
    {employee}.jsonl            # All docs per employee
    employee_statistics.json
  user_spaces.json              # Google Chat spaces
  knowledge_base_metadata.json
  stakeholder_graph.pkl
  project_names_cache.json      # GPT-generated names cache

/club_data/
  user_spaces.json
  project_clusters.json
  search_index.pkl
  embedding_index.pkl
  knowledge_gaps.json
```

