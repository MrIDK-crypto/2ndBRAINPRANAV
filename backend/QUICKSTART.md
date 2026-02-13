# KnowledgeVault Quick Start Guide

Get up and running with KnowledgeVault in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- OpenAI API key
- Enron email dataset (already at `/Users/rishitjain/Downloads/maildir`)

## Step 1: Setup Environment

```bash
cd /Users/rishitjain/Downloads/knowledgevault_backend

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure API Keys

```bash
# Copy the environment template
cp .env.template .env

# Edit .env and add your OpenAI API key
# nano .env  (or use any text editor)
```

Add your key:
```
OPENAI_API_KEY=sk-your-key-here
```

## Step 3: Test with Small Dataset

Run the pipeline with a limited dataset (500 documents):

```bash
python main.py --limit 500 --skip-videos
```

This will:
- ✓ Parse 500 emails from Enron dataset
- ✓ Cluster by employee
- ✓ Cluster by project using BERTopic
- ✓ Analyze knowledge gaps
- ✓ Generate questions
- ✓ Build vector database
- ✓ Create RAG system
- ✓ Generate PowerPoint presentations

Estimated time: **5-10 minutes**
Estimated cost: **~$0.20**

## Step 4: Query the Knowledge Base

After the pipeline completes, try the interactive RAG chatbot:

```bash
python main.py --limit 500 --skip-videos --interactive-rag
```

Example queries:
- "What projects did employee beck-s work on?"
- "What were the main decisions discussed?"
- "Tell me about the California energy crisis"

## Step 5: Explore the Outputs

Check these directories:

```bash
# View employee clusters
ls -la data/employee_clusters/

# View project clusters
ls -la data/project_clusters/

# View gap analysis
cat output/gap_analysis/*_gaps.json | head -50

# View generated questionnaires
ls -la output/questionnaires/

# View PowerPoint presentations
open output/powerpoints/
```

## Common Commands

### Minimal Test (100 docs, no classification, no videos)
```bash
python main.py --limit 100 --skip-classification --skip-videos
```

### Full Pipeline (all documents)
```bash
python main.py
```

### Interactive Mode
```bash
python main.py --limit 500 --interactive-rag
```

### Run Individual Components

```bash
# Just parse emails
python -m data_processing.enron_parser

# Just cluster by employee
python -m clustering.employee_clustering

# Just build vector database
python -m indexing.vector_database

# Just test RAG
python -m rag.hierarchical_rag
```

## Troubleshooting

### "OPENAI_API_KEY not set"
Make sure you created `.env` file and added your API key.

### "ENRON_MAILDIR not found"
Update the path in `.env`:
```
ENRON_MAILDIR=/path/to/your/maildir
```

### Out of memory
Use `--limit` flag to process fewer documents:
```bash
python main.py --limit 100
```

### Neo4j connection error
This is optional. The system will continue without Neo4j and save queries to a file instead.

## Next Steps

1. **Explore the architecture** - Read `README.md` for detailed documentation
2. **Review the outputs** - Check gap analysis and questionnaires
3. **Query the RAG system** - Try different types of questions
4. **Generate videos** - Remove `--skip-videos` flag
5. **Add more data sources** - Extend parsers for your own documents
6. **Build a frontend** - Create a web UI for the RAG system

## Architecture Overview

```
Raw Emails → Uncluster → Employee Clusters → Project Clusters
                                                     ↓
Gap Analysis ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ┘
     ↓
Questions Generated
     ↓
Knowledge Graph + Vector DB
     ↓
Hierarchical RAG Chatbot
     ↓
PowerPoints + Videos
```

## Example Output

After running with `--limit 500`:

```
EMPLOYEE CLUSTERING STATISTICS
==============================
Total employees: 25
Total documents: 500
Average documents per employee: 20.0

PROJECT CLUSTERING STATISTICS
==============================
Total projects discovered: 47
Projects per employee (avg): 1.9

GAP ANALYSIS SUMMARY
====================
Total questions generated: 156
Avg questions per project: 3.3

VECTOR DATABASE STATISTICS
==========================
Total documents indexed: 500
Collection: knowledgevault
Embedding model: all-mpnet-base-v2

✓ Pipeline complete in 8.5 minutes
```

## Cost Optimization

To minimize API costs during testing:

```bash
# Minimal cost test (<$0.10)
python main.py --limit 50 --skip-classification --skip-videos

# Skip expensive operations
python main.py --limit 200 --skip-classification
```

## Support

For issues or questions:
1. Check `README.md` for detailed documentation
2. Review error messages in console output
3. Check the generated log files in `output/`

---

Happy knowledge managing! 🧠
