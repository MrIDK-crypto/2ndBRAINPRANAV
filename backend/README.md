# KnowledgeVault Backend

A comprehensive enterprise knowledge management system that captures, organizes, and makes searchable tacit and explicit knowledge from employee documents.

## Overview

KnowledgeVault is a hierarchical RAG (Retrieval-Augmented Generation) framework designed for enterprise knowledge continuity. It processes unstructured employee data (emails, documents) through multiple stages:

1. **Data Unclustering** - Flattens organized data into a single corpus
2. **Employee Clustering** - Groups documents by employee
3. **Project Clustering** - Uses BERTopic to semantically cluster into projects
4. **Work/Personal Classification** - Uses GPT-4o-mini to filter personal content
5. **Gap Analysis** - Identifies missing knowledge and information gaps
6. **Question Generation** - Creates targeted questions to extract tacit knowledge
7. **Knowledge Graph** - Builds Neo4j graph of relationships
8. **Vector Database** - Creates ChromaDB embeddings for semantic search
9. **Hierarchical RAG** - Combines graph + vector search for intelligent querying
10. **Content Generation** - Creates PowerPoint presentations and training videos

## Architecture

```
┌─────────────────┐
│  Raw Documents  │
│  (Enron Emails) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Unclustered   │  ◄── Flatten into single corpus
│      Data       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Employee     │  ◄── Metadata-based clustering
│   Clustering    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Project      │  ◄── BERTopic semantic clustering
│   Clustering    │
└────────┬────────┘
         │
         ├─────────────────────┬──────────────────┐
         ▼                     ▼                  ▼
┌──────────────┐      ┌─────────────┐    ┌──────────────┐
│ Knowledge    │      │   Vector    │    │ Gap Analysis │
│ Graph (Neo4j)│      │ DB (Chroma) │    │  & Questions │
└──────┬───────┘      └──────┬──────┘    └──────┬───────┘
       │                     │                   │
       └──────────┬──────────┘                   │
                  ▼                               ▼
         ┌────────────────┐            ┌─────────────────┐
         │ Hierarchical   │            │    Content      │
         │  RAG Engine    │            │   Generation    │
         └────────────────┘            └─────────────────┘
                  │                             │
                  ▼                             ▼
         ┌────────────────┐            ┌─────────────────┐
         │    Chatbot     │            │  PowerPoints &  │
         │    Queries     │            │     Videos      │
         └────────────────┘            └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.8+
- Neo4j (optional, for knowledge graph)
- FFmpeg (for video generation)

### Setup

1. **Clone/Download the project**

```bash
cd /Users/rishitjain/Downloads/knowledgevault_backend
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure environment**

```bash
cp .env.template .env
# Edit .env and add your API keys
```

Required environment variables:
- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `ENRON_MAILDIR` - Path to Enron dataset (default: /Users/rishitjain/Downloads/maildir)
- `NEO4J_URI` - Neo4j connection URI (optional)
- `NEO4J_USER` - Neo4j username (optional)
- `NEO4J_PASSWORD` - Neo4j password (optional)

4. **Install FFmpeg** (for video generation)

```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt-get install ffmpeg
```

## Usage

### Full Pipeline

Run the complete pipeline:

```bash
python main.py
```

### Pipeline Options

```bash
# Test with limited data (e.g., 1000 documents)
python main.py --limit 1000

# Skip work/personal classification (saves API costs)
python main.py --skip-classification

# Skip video generation (faster processing)
python main.py --skip-videos

# Run with interactive RAG chatbot after completion
python main.py --interactive-rag

# Combine options
python main.py --limit 500 --skip-videos --interactive-rag
```

### Individual Components

Run components separately:

```bash
# 1. Uncluster data
python -m data_processing.enron_parser

# 2. Employee clustering
python -m clustering.employee_clustering

# 3. Project clustering
python -m clustering.project_clustering

# 4. Work/Personal classification
python -m classification.work_personal_classifier

# 5. Gap analysis
python -m gap_analysis.gap_analyzer

# 6. Question generation
python -m gap_analysis.question_generator

# 7. Build knowledge graph
python -m indexing.knowledge_graph

# 8. Build vector database
python -m indexing.vector_database

# 9. Test RAG system
python -m rag.hierarchical_rag

# 10. Generate PowerPoints
python -m content_generation.powerpoint_generator

# 11. Generate videos
python -m content_generation.video_generator
```

## Project Structure

```
knowledgevault_backend/
├── config/
│   └── config.py                 # Configuration management
├── data_processing/
│   └── enron_parser.py          # Email parsing and unclustering
├── clustering/
│   ├── employee_clustering.py   # Employee-based clustering
│   └── project_clustering.py    # BERTopic project clustering
├── classification/
│   └── work_personal_classifier.py  # Work vs personal classifier
├── gap_analysis/
│   ├── gap_analyzer.py          # Knowledge gap detection
│   └── question_generator.py    # Question generation
├── indexing/
│   ├── knowledge_graph.py       # Neo4j graph builder
│   └── vector_database.py       # ChromaDB vector indexer
├── rag/
│   └── hierarchical_rag.py      # Hierarchical RAG engine
├── content_generation/
│   ├── powerpoint_generator.py  # PowerPoint creation
│   └── video_generator.py       # Video generation
├── data/                        # Generated data (created at runtime)
├── output/                      # Generated outputs (created at runtime)
├── main.py                      # Master orchestration script
├── requirements.txt             # Python dependencies
├── .env.template               # Environment template
└── README.md                   # This file
```

## Technology Stack

### Core ML/NLP
- **BERTopic** - Advanced topic modeling with HDBSCAN clustering
- **Sentence Transformers** - Document embeddings (all-mpnet-base-v2)
- **OpenAI GPT-4o-mini** - Classification, gap analysis, question generation, RAG

### Databases
- **ChromaDB** - Vector database for semantic search
- **Neo4j** - Graph database for knowledge relationships (optional)

### Content Generation
- **python-pptx** - PowerPoint generation
- **gTTS** - Text-to-speech for narration
- **MoviePy** - Video assembly and rendering

## Key Features

### 1. BERTopic Clustering
- Automatically discovers project clusters without predefined categories
- Uses UMAP for dimensionality reduction
- HDBSCAN for density-based clustering
- Generates interpretable topic labels

### 2. Hierarchical RAG
- **Entity Extraction** - Identifies employees, projects, topics from queries
- **Graph Traversal** - Finds relevant clusters via knowledge graph
- **Scoped Retrieval** - Searches only within relevant clusters
- **Context-Aware Generation** - Synthesizes answers with citations

### 3. Gap Analysis
- Identifies missing document types
- Detects knowledge gaps and context gaps
- Generates targeted questions to fill gaps
- Creates employee questionnaires

### 4. Privacy-First Classification
- Distinguishes work from personal content
- Confidence-based filtering (>0.85 threshold)
- Flags uncertain content for human review
- Removes personal data before indexing

## Output Artifacts

After running the pipeline, you'll find:

### Data Outputs (`/data`)
- `unclustered/` - Flattened JSONL documents
- `employee_clusters/` - Documents grouped by employee
- `project_clusters/` - Documents clustered by project
- `classified/` - Work vs personal classification results
- `chroma_db/` - Vector database files

### Analysis Outputs (`/output`)
- `gap_analysis/` - Knowledge gap reports (JSON)
- `questionnaires/` - Employee questionnaires (JSON + TXT)
- `powerpoints/` - Training presentations (PPTX)
- `videos/` - Training videos (MP4)
- `reports/` - Various statistics and summaries
- `neo4j_queries.cypher` - Graph database queries

## API Costs

Approximate OpenAI API costs (GPT-4o-mini):

- **Classification** (50 docs): ~$0.05
- **Gap Analysis** (10 projects): ~$0.10
- **Question Generation** (10 projects): ~$0.10
- **RAG Queries** (10 queries): ~$0.05

Total estimated cost for 1000 documents: **~$0.50 - $1.00**

Use `--skip-classification` and `--limit` flags to reduce costs during testing.

## Interactive RAG Chatbot

After running the pipeline with `--interactive-rag`, you can query the knowledge base:

```
Your question: What were the main projects for employee beck-s?

ANSWER:
Based on the documents, beck-s worked on several projects including...
[Detailed answer with citations]

SOURCES (5):
1. Project Phoenix - Q2 Update
   Employee: beck-s
   Date: 2001-05-15
   Relevance: 94.2%
...
```

## Troubleshooting

### Neo4j Connection Failed
If Neo4j is not installed or not running, the system will continue without graph functionality. Graph queries will be saved to `output/neo4j_queries.cypher` for manual execution.

### FFmpeg Not Found
Video generation requires FFmpeg. Install it or use `--skip-videos` flag.

### Out of Memory
For large datasets, use the `--limit` flag to process fewer documents.

### API Rate Limits
Add delays or use smaller batches if hitting OpenAI rate limits.

## Future Enhancements

- [ ] Add support for more document types (PDF, DOCX, etc.)
- [ ] Implement cross-encoder re-ranking for better retrieval
- [ ] Add streaming RAG responses
- [ ] Build frontend UI for querying and visualization
- [ ] Add multi-modal support (images, diagrams)
- [ ] Implement feedback loop for improving classifications
- [ ] Add support for incremental updates
- [ ] Build employee onboarding workflows

## License

This project is for educational and research purposes.

## Acknowledgments

- Enron Email Dataset for testing and validation
- BERTopic for advanced topic modeling
- OpenAI for GPT-4o-mini API
- ChromaDB and Neo4j communities

---

Built with KnowledgeVault - Enterprise Knowledge Continuity Platform
