# KnowledgeVault Project Detection - Key Files Reference

## Core Project Detection Files

### 1. Clustering Modules

**File:** `/clustering/employee_clustering.py`
- Purpose: Hard clustering by employee metadata
- Key Class: `EmployeeClusterer`
- Key Methods:
  - `cluster_by_employee()` - Group documents by employee
  - `get_employee_timeline()` - Timeline view for employee
  - `get_employee_metadata_summary()` - Metadata analysis

**File:** `/clustering/project_clustering.py`
- Purpose: Semantic project clustering using BERTopic or DistilBERT
- Key Class: `ProjectClusterer`
- Key Methods:
  - `cluster_employee_documents()` - Cluster single employee's docs
  - `cluster_all_employees()` - Batch clustering
  - `_classify_with_distilbert()` - Alternative classification method

### 2. Classification Modules

**File:** `/classification/project_classifier.py`
- Purpose: Supervised DistilBERT-based project classification
- Key Class: `DistilBERTProjectClassifier`
- Key Methods:
  - `train()` - Train on labeled documents
  - `predict()` - Predict project label
  - `classify_batch()` - Batch classification
  - `load_model()` / `save_model()` - Model persistence

**File:** `/classification/global_project_classifier.py`
- Purpose: Zero-shot classification across entire dataset
- Key Class: `GlobalProjectClassifier`
- Key Methods:
  - `auto_detect_project_categories()` - Auto-detect from keywords
  - `classify_document()` - Single document classification
  - `classify_all_documents()` - Batch classification
  - `create_project_employee_mapping()` - Build project-employee relationships
  - `create_employee_project_mapping()` - Build employee-project relationships

### 3. Stakeholder Graph

**File:** `/rag/stakeholder_graph.py` (400+ lines)
- Purpose: Extract people, expertise, and projects from documents
- Key Classes:
  - `Person` - Dataclass with roles, expertise, projects
  - `Project` - Dataclass with members, documents, topics
  - `StakeholderGraph` - Main graph builder
- Key Methods:
  - `process_document()` - Extract stakeholders from doc
  - `extract_project_from_doc()` - Extract project name
  - `extract_names()` - NER for people
  - `extract_roles()` - Role pattern matching
  - `extract_expertise()` - Expertise domain extraction
  - `answer_who_question()` - Query the graph
  - `get_project_team()` - Get team members
  - `get_experts()` - Find domain experts
  - `build_stakeholder_graph()` - Batch construction

### 4. Project Naming (Google Chat)

**File:** `/project_clusterer.py`
- Purpose: GPT-based project naming for Google Chat spaces
- Key Functions:
  - `generate_project_name()` - Generate name via GPT-4o-mini
  - `extract_sample_content()` - Sample messages/files
  - `cluster_projects_from_takeout()` - Process Google Chat takeout
  - `batch_rename_projects()` - Batch processing
  - `load_cache()` / `save_cache()` - Result caching

---

## Web Application & API

**File:** `/app_universal.py` (1200+ lines)
- Purpose: Flask web server with project detection APIs
- Key Functions:
  - `load_data()` - Load all indexes and graphs
  - `index()` - Home page with workflow
- Key API Endpoints:
  - `GET /api/spaces` - List all projects
  - `GET /api/questions?project=X` - Filter by project
  - `GET /api/stakeholders` - List people
  - `GET /api/stakeholders/projects` - Projects with teams
  - `POST /api/stakeholders/query` - "Who" questions
  - `POST /api/search` - Search with project detection
  - Stakeholder endpoints with project filtering

---

## Configuration & Utilities

**File:** `/config/config.py`
- Purpose: Centralized configuration
- Key Parameters:
  - `MIN_CLUSTER_SIZE = 5` - BERTopic parameter
  - `MIN_SAMPLES = 3` - BERTopic parameter
  - `UMAP_N_NEIGHBORS = 15` - BERTopic parameter
  - `EMBEDDING_MODEL` - MPNET for embeddings
  - `CLASSIFICATION_MODEL` - DistilBERT config

**File:** `/build_enhanced_knowledge_base.py`
- Purpose: Pipeline to build complete KB with project detection
- Demonstrates: End-to-end flow from documents to projects

---

## Data Files Generated

### Input/Output Structure

```
DATA_DIR/
├── project_clusters/
│   ├── project_clustering_summary.json
│   ├── {employee_name}/
│   │   ├── {project_name}.jsonl (documents)
│   │   ├── outliers.jsonl
│   │   └── metadata.json
│   └── ...

├── employee_clusters/
│   ├── employee_statistics.json
│   ├── {employee_name}.jsonl (all docs per employee)
│   └── ...

├── user_spaces.json (Google Chat spaces)
├── knowledge_base_metadata.json
├── stakeholder_graph.pkl (serialized graph)
└── project_names_cache.json (GPT results cache)

CLUB_DATA/
├── search_index.pkl
├── embedding_index.pkl
├── knowledge_gaps.json
├── user_spaces.json
├── project_clusters.json
└── project_names_cache.json
```

---

## Data Structure Reference

### Document Metadata
```python
metadata = {
    "subject": str,              # Email/doc title
    "file_name": str,            # Original filename
    "employee": str,             # Sender/owner
    "timestamp": str,            # ISO datetime
    "folder": str,               # Source folder
    "date": str,                 # Date extracted
    "file_path": str,            # File path
    "file_type": str,            # 'text', 'pdf', etc.
    "source": str,               # 'email', 'chat'
    "from": str,                 # Sender
    "project": str,              # Assigned project
    "project_category": str,     # Classification
    "project_confidence": float, # Confidence score
    "parser": str                # Parser type
}
```

### Project Cluster Output
```python
{
    "employee": str,
    "total_documents": int,
    "num_projects": int,
    "projects": {
        "project_name": {
            "cluster_id": "employee::project_N",
            "topic_id": int,
            "document_count": int,
            "documents": [...],
            "keywords": [str],
            "avg_confidence": float
        }
    },
    "outliers": [...]
}
```

### Stakeholder Graph (In-Memory)
```python
StakeholderGraph:
  .people[normalized_name] = Person {
      name, roles, expertise, projects, documents, mentions, email
  }
  .projects[normalized_name] = Project {
      name, members, documents, topics, status, client
  }
  .expertise_people[domain] = Set[person_names]
  .document_people[doc_id] = Set[person_names]
```

---

## Algorithm Parameters (config.py)

### Clustering
```python
MIN_CLUSTER_SIZE = 5              # HDBSCAN min cluster size
MIN_SAMPLES = 3                   # HDBSCAN density param
UMAP_N_NEIGHBORS = 15             # Preserve local structure
UMAP_N_COMPONENTS = 5             # Reduce to 5D
UMAP_METRIC = "cosine"            # Distance metric
```

### Classification
```python
WORK_CONFIDENCE_THRESHOLD = 0.85
PERSONAL_CONFIDENCE_THRESHOLD = 0.85
UNCERTAIN_LOWER_BOUND = 0.40
```

### Models
```python
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
CLASSIFICATION_MODEL = "distilbert-base-uncased"
LLM_MODEL = "gpt-4o-mini"  # For project naming
```

### RAG/Retrieval
```python
TOP_K_RETRIEVAL = 10
RERANK_TOP_K = 5
MAX_CONTEXT_LENGTH = 8000
```

---

## Key Imports & Dependencies

### Machine Learning
```python
from bertopic import BERTopic          # Topic modeling
from sentence_transformers import SentenceTransformer  # Embeddings
from umap import UMAP                  # Dimensionality reduction
from hdbscan import HDBSCAN            # Clustering
from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
```

### NLP & Extraction
```python
import re                              # Regex patterns
from pathlib import Path               # File handling
import json                            # JSON I/O
import pickle                          # Model serialization
```

### Web & API
```python
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS            # Cross-origin requests
from openai import OpenAI              # GPT-based naming
```

---

## Testing & Validation Files

**File:** `/test_club_classification.py`
- Tests global project classification

**File:** `/run_global_project_classification.py`
- Demonstrates global classification pipeline

**File:** `/run_simple_project_mapping.py`
- Simple project mapping example

---

## Integration with Other Components

### Inputs From
- `embedding_index` - Document embeddings and chunks
- `search_index` - Full-text searchable documents
- Document metadata (subject, employee, file_name, etc.)

### Outputs To
- `stakeholder_graph.pkl` - Person/project relationships
- `user_spaces.json` - Available projects/spaces
- API responses for `/api/spaces`, `/api/stakeholders/projects`
- Project-filtered search results

### Related Modules
- `rag/enhanced_rag.py` - Uses project info for better search
- `indexing/knowledge_graph.py` - May use project structure
- `gap_analysis/gap_analyzer.py` - Can filter gaps by project
- `content_generation/` - Projects used for content scoping

---

## Workflow Examples

### End-to-End Detection
```
1. Employee Clustering (employee_clustering.py)
   └─> Output: per-employee JSONL files

2. Project Clustering (project_clustering.py)
   └─> Input: per-employee files
   └─> Output: per-employee-per-project structure

3. Stakeholder Graph (stakeholder_graph.py)
   └─> Input: all documents
   └─> Output: person/project relationships

4. Global Classification (global_project_classifier.py)
   └─> Cross-dataset categorization
   └─> Project-employee mappings

5. API Exposure (app_universal.py)
   └─> /api/spaces, /api/stakeholders/projects
   └─> /api/search with project context
```

### For Google Chat
```
1. Read Takeout data
2. Extract samples (project_clusterer.py)
3. Query GPT-4o-mini for names
4. Cache results by space_id
5. Store in user_spaces.json
6. Expose via /api/spaces
```

---

## Performance Considerations

- **BERTopic:** Slow for large datasets, good accuracy
- **Zero-shot:** Fast, medium accuracy, no training needed
- **DistilBERT:** Faster than BERTopic, excellent accuracy, requires training data
- **GPT Naming:** Expensive (API calls), excellent UX
- **Stakeholder Graph:** One-time computation, fast queries

---

## Quick Reference: Which File For What

| Task | File |
|------|------|
| Cluster by employee | `/clustering/employee_clustering.py` |
| Cluster into projects (unsupervised) | `/clustering/project_clustering.py` |
| Classify projects (supervised) | `/classification/project_classifier.py` |
| Global zero-shot classification | `/classification/global_project_classifier.py` |
| Extract people & expertise | `/rag/stakeholder_graph.py` |
| Generate project names (chat) | `/project_clusterer.py` |
| API endpoints | `/app_universal.py` |
| Configuration | `/config/config.py` |
| Build full pipeline | `/build_enhanced_knowledge_base.py` |

