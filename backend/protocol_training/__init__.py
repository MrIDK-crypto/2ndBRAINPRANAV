"""
Protocol Training Data Pipeline
================================
Ingest, normalize, and mine patterns from 5 external protocol datasets
to enhance the IntelligentGapDetector with scientific/biomedical domain knowledge.

Sources:
  1. Stanford ChEMH MCAC protocols (markdown, mass spectrometry)
  2. BioProtocolBench (JSON, 27K protocols, 5 ML tasks)
  3. WLP-Parser (BRAT annotations, wet lab NER)
  4. OpenWetWare (MediaWiki, biology/bioengineering)
  5. protocols.io (public JSON API, multi-domain)
"""

import os

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_corpus')
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_models')
REPOS_DIR = os.path.join(CORPUS_DIR, 'repos')

try:
    os.makedirs(CORPUS_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(REPOS_DIR, exist_ok=True)
except OSError:
    pass  # Read-only filesystem (e.g., ECS Fargate) — directories created in Dockerfile
