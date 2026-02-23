"""
Enhanced Search Service - Production RAG with Advanced Features

Ports EnhancedRAGv2 features to work with Pinecone:
- Query expansion (100+ acronyms)
- Cross-encoder reranking
- MMR diversity selection
- Hallucination detection
- Strict citation enforcement
- Freshness scoring

Created: 2025-12-09
"""

import os
import re
import json
import time
import hashlib
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from services.openai_client import get_openai_client


# =============================================================================
# QUERY SANITIZATION (Security)
# =============================================================================

class QuerySanitizer:
    """Sanitize user queries to prevent injection attacks"""

    MAX_QUERY_LENGTH = 2000  # Reasonable max for a search query
    MIN_QUERY_LENGTH = 1

    # Characters that are allowed in queries (whitelist approach)
    ALLOWED_PATTERN = re.compile(r'^[\w\s\-.,!?\'\"():;@#$%&*+=/\[\]{}|<>~`^\n]+$', re.UNICODE)

    # Prompt injection patterns to detect and neutralize
    INJECTION_PATTERNS = [
        r'ignore\s+(previous|above|all)\s+instructions?',
        r'disregard\s+(previous|above|all)',
        r'forget\s+(everything|all|previous)',
        r'you\s+are\s+now\s+a',
        r'act\s+as\s+(if\s+you\s+are|a)',
        r'pretend\s+(to\s+be|you\s+are)',
        r'new\s+instructions?:',
        r'system\s*:\s*',
        r'\[INST\]',
        r'<\|im_start\|>',
        r'<\|system\|>',
    ]

    def __init__(self):
        self.injection_regex = re.compile(
            '|'.join(self.INJECTION_PATTERNS),
            re.IGNORECASE
        )

    def sanitize(self, query: str) -> Tuple[str, List[str]]:
        """
        Sanitize a query string.

        Returns:
            Tuple of (sanitized_query, list_of_warnings)
        """
        warnings = []

        if not query:
            return "", ["Empty query"]

        # Trim whitespace
        query = query.strip()

        # Check length
        if len(query) > self.MAX_QUERY_LENGTH:
            query = query[:self.MAX_QUERY_LENGTH]
            warnings.append(f"Query truncated to {self.MAX_QUERY_LENGTH} chars")

        if len(query) < self.MIN_QUERY_LENGTH:
            return "", ["Query too short"]

        # Check for injection patterns
        if self.injection_regex.search(query):
            warnings.append("Potential prompt injection detected and neutralized")
            # Neutralize by wrapping in quotes and prefixing
            query = f'Search for: "{query}"'

        # Remove null bytes and other control characters
        query = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', query)

        return query, warnings


# Singleton sanitizer
_query_sanitizer = QuerySanitizer()


def sanitize_query(query: str) -> Tuple[str, List[str]]:
    """Convenience function for query sanitization"""
    return _query_sanitizer.sanitize(query)


# Cross-encoder for reranking
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    print("[EnhancedSearch] Warning: sentence-transformers not installed. Reranking disabled.")
    print("[EnhancedSearch] Install with: pip install sentence-transformers")


# =============================================================================
# QUERY EXPANSION
# =============================================================================

class QueryExpander:
    """Query expansion with acronyms and synonyms"""

    # Comprehensive acronym dictionary (100+ terms)
    ACRONYMS = {
        # Healthcare
        'ROI': 'Return on Investment',
        'NICU': 'Neonatal Intensive Care Unit',
        'PICU': 'Pediatric Intensive Care Unit',
        'ICU': 'Intensive Care Unit',
        'OB-ED': 'Obstetric Emergency Department',
        'OBED': 'Obstetric Emergency Department',
        'L&D': 'Labor and Delivery',
        'ED': 'Emergency Department',
        'OR': 'Operating Room',
        'FDU': 'Fetal Diagnostic Unit',
        'LOS': 'Length of Stay',
        'ADT': 'Admission Discharge Transfer',
        'EMR': 'Electronic Medical Record',
        'EHR': 'Electronic Health Record',
        'DRG': 'Diagnosis Related Group',
        'CMS': 'Centers for Medicare and Medicaid Services',
        'HIPAA': 'Health Insurance Portability and Accountability Act',
        'PHI': 'Protected Health Information',
        'RVU': 'Relative Value Unit',
        'FTE': 'Full Time Equivalent',
        'CMO': 'Chief Medical Officer',
        'CNO': 'Chief Nursing Officer',

        # Finance
        'NPV': 'Net Present Value',
        'IRR': 'Internal Rate of Return',
        'EBITDA': 'Earnings Before Interest Taxes Depreciation and Amortization',
        'EBIT': 'Earnings Before Interest and Taxes',
        'P&L': 'Profit and Loss',
        'COGS': 'Cost of Goods Sold',
        'OPEX': 'Operating Expenses',
        'CAPEX': 'Capital Expenditure',
        'DCF': 'Discounted Cash Flow',
        'WACC': 'Weighted Average Cost of Capital',
        'EV': 'Enterprise Value',
        'FCF': 'Free Cash Flow',
        'GP': 'Gross Profit',
        'NI': 'Net Income',
        'AR': 'Accounts Receivable',
        'AP': 'Accounts Payable',
        'YoY': 'Year over Year',
        'QoQ': 'Quarter over Quarter',
        'MoM': 'Month over Month',
        'CAGR': 'Compound Annual Growth Rate',
        'P/E': 'Price to Earnings Ratio',
        'EPS': 'Earnings Per Share',
        'ROE': 'Return on Equity',
        'ROA': 'Return on Assets',
        'ROIC': 'Return on Invested Capital',

        # Market/Business
        'TAM': 'Total Addressable Market',
        'SAM': 'Serviceable Addressable Market',
        'SOM': 'Serviceable Obtainable Market',
        'CAC': 'Customer Acquisition Cost',
        'LTV': 'Lifetime Value',
        'MRR': 'Monthly Recurring Revenue',
        'ARR': 'Annual Recurring Revenue',
        'GMV': 'Gross Merchandise Value',
        'NPS': 'Net Promoter Score',
        'ARPU': 'Average Revenue Per User',
        'DAU': 'Daily Active Users',
        'MAU': 'Monthly Active Users',
        'B2B': 'Business to Business',
        'B2C': 'Business to Consumer',
        'GTM': 'Go to Market',
        'MVP': 'Minimum Viable Product',
        'PMF': 'Product Market Fit',
        'POC': 'Proof of Concept',

        # Consulting
        'SOW': 'Statement of Work',
        'RFP': 'Request for Proposal',
        'RFI': 'Request for Information',
        'NDA': 'Non-Disclosure Agreement',
        'SLA': 'Service Level Agreement',
        'KPI': 'Key Performance Indicator',
        'OKR': 'Objectives and Key Results',
        'SWOT': 'Strengths Weaknesses Opportunities Threats',

        # Tech - General
        'API': 'Application Programming Interface',
        'SDK': 'Software Development Kit',
        'CI/CD': 'Continuous Integration Continuous Deployment',
        'AWS': 'Amazon Web Services',
        'GCP': 'Google Cloud Platform',
        'ML': 'Machine Learning',
        'AI': 'Artificial Intelligence',
        'NLP': 'Natural Language Processing',
        'RAG': 'Retrieval Augmented Generation',
        'LLM': 'Large Language Model',

        # Tech - Web/Backend
        'REST': 'Representational State Transfer',
        'HTTP': 'Hypertext Transfer Protocol',
        'HTTPS': 'Hypertext Transfer Protocol Secure',
        'JSON': 'JavaScript Object Notation',
        'XML': 'Extensible Markup Language',
        'HTML': 'Hypertext Markup Language',
        'CSS': 'Cascading Style Sheets',
        'SQL': 'Structured Query Language',
        'NoSQL': 'Non-relational Database',
        'ORM': 'Object Relational Mapping',
        'MVC': 'Model View Controller',
        'CRUD': 'Create Read Update Delete',
        'JWT': 'JSON Web Token',
        'OAuth': 'Open Authorization',
        'SSO': 'Single Sign On',
        'CORS': 'Cross Origin Resource Sharing',
        'CDN': 'Content Delivery Network',
        'DNS': 'Domain Name System',
        'SSL': 'Secure Sockets Layer',
        'TLS': 'Transport Layer Security',

        # Tech - DevOps
        'K8S': 'Kubernetes',
        'K8s': 'Kubernetes',
        'VM': 'Virtual Machine',
        'CLI': 'Command Line Interface',
        'GUI': 'Graphical User Interface',
        'IDE': 'Integrated Development Environment',
        'PR': 'Pull Request',
        'MR': 'Merge Request',
        'QA': 'Quality Assurance',
        'UAT': 'User Acceptance Testing',
        'SaaS': 'Software as a Service',
        'PaaS': 'Platform as a Service',
        'IaaS': 'Infrastructure as a Service',

        # Tech - Data
        'ETL': 'Extract Transform Load',
        'DB': 'Database',
        'DBMS': 'Database Management System',
        'RDBMS': 'Relational Database Management System',

        # Tech - Frontend
        'DOM': 'Document Object Model',
        'SPA': 'Single Page Application',
        'SSR': 'Server Side Rendering',
        'CSR': 'Client Side Rendering',
        'PWA': 'Progressive Web App',
        'UI': 'User Interface',
        'UX': 'User Experience',
    }

    # Synonym mappings - comprehensive for all domains
    SYNONYMS = {
        # Business/Finance
        'revenue': ['income', 'earnings', 'sales', 'receipts'],
        'cost': ['expense', 'expenditure', 'investment', 'spending'],
        'profit': ['earnings', 'income', 'margin', 'returns'],
        'growth': ['increase', 'expansion', 'rise', 'gain'],
        'decline': ['decrease', 'drop', 'reduction', 'fall'],
        'patients': ['cases', 'admissions', 'individuals'],
        'employees': ['staff', 'workers', 'team members', 'personnel'],

        # CODE/SOFTWARE - Critical for code understanding
        'architecture': ['structure', 'design', 'layout', 'organization', 'system design', 'code structure', 'codebase', 'framework', 'components', 'modules', 'patterns'],
        'structure': ['architecture', 'organization', 'layout', 'hierarchy', 'design', 'arrangement'],
        'function': ['method', 'procedure', 'routine', 'subroutine', 'def', 'func', 'handler'],
        'class': ['object', 'type', 'model', 'entity', 'struct', 'interface'],
        'variable': ['var', 'parameter', 'argument', 'field', 'property', 'attribute', 'constant'],
        'module': ['file', 'package', 'library', 'component', 'unit', 'service'],
        'import': ['require', 'include', 'dependency', 'from', 'using'],
        'error': ['exception', 'bug', 'issue', 'problem', 'failure', 'crash', 'fault'],
        'database': ['db', 'storage', 'data store', 'repository', 'table', 'collection', 'schema'],
        'endpoint': ['route', 'api', 'url', 'path', 'handler', 'controller'],
        'request': ['call', 'query', 'fetch', 'invoke', 'http'],
        'response': ['return', 'result', 'output', 'reply', 'data'],
        'authentication': ['auth', 'login', 'signin', 'credentials', 'token', 'jwt', 'session'],
        'authorization': ['permission', 'access', 'role', 'privilege', 'acl'],
        'component': ['element', 'widget', 'part', 'piece', 'block', 'section'],
        'render': ['display', 'show', 'draw', 'paint', 'output', 'view'],
        'state': ['data', 'store', 'context', 'props', 'variables'],
        'hook': ['lifecycle', 'callback', 'event', 'listener', 'effect'],
        'test': ['spec', 'unit test', 'integration test', 'assertion', 'expect', 'mock'],
        'deploy': ['release', 'publish', 'ship', 'launch', 'rollout'],
        'config': ['configuration', 'settings', 'options', 'parameters', 'env', 'environment'],
        'server': ['backend', 'service', 'api server', 'host', 'node'],
        'client': ['frontend', 'browser', 'ui', 'interface', 'app'],
        'flow': ['process', 'workflow', 'pipeline', 'sequence', 'steps'],
        'logic': ['algorithm', 'code', 'implementation', 'business logic', 'processing'],
        'data': ['information', 'payload', 'content', 'records', 'entries'],
        'schema': ['model', 'structure', 'definition', 'type', 'interface'],
        'query': ['search', 'find', 'lookup', 'filter', 'select', 'retrieve'],
        'update': ['modify', 'change', 'edit', 'patch', 'mutate', 'set'],
        'delete': ['remove', 'destroy', 'drop', 'clear', 'erase'],
        'create': ['add', 'insert', 'new', 'make', 'generate', 'build'],
        'list': ['array', 'collection', 'items', 'records', 'entries', 'all'],
        'how': ['way', 'method', 'approach', 'process', 'steps', 'implementation'],
        'what': ['which', 'describe', 'explain', 'definition'],
        'where': ['location', 'file', 'path', 'place', 'directory'],
        'why': ['reason', 'purpose', 'rationale', 'explanation'],
    }

    # Integration/Source-specific synonyms
    SOURCE_SYNONYMS = {
        # Email sources
        'email': ['mail', 'message', 'correspondence', 'inbox', 'sent', 'gmail', 'outlook'],
        'gmail': ['email', 'google mail', 'inbox', 'message'],
        'outlook': ['email', 'microsoft mail', 'office mail', 'exchange'],

        # Chat/Messaging
        'slack': ['message', 'channel', 'thread', 'chat', 'dm', 'direct message', 'conversation'],
        'message': ['chat', 'slack', 'conversation', 'thread', 'communication'],
        'channel': ['slack channel', 'room', 'group', 'chat room'],

        # Documents/Files
        'document': ['file', 'doc', 'paper', 'report', 'attachment'],
        'file': ['document', 'attachment', 'upload', 'pdf', 'doc'],
        'pdf': ['document', 'file', 'paper', 'report'],
        'spreadsheet': ['excel', 'sheet', 'csv', 'table', 'data', 'numbers'],
        'excel': ['spreadsheet', 'xlsx', 'xls', 'sheet', 'workbook'],
        'presentation': ['powerpoint', 'slides', 'pptx', 'deck', 'ppt'],
        'powerpoint': ['presentation', 'slides', 'deck', 'pptx'],

        # Cloud Storage
        'drive': ['google drive', 'gdrive', 'cloud storage', 'files', 'folders'],
        'gdrive': ['google drive', 'drive', 'docs', 'sheets', 'slides'],
        'onedrive': ['microsoft drive', 'sharepoint', 'cloud storage', 'office files'],
        'box': ['box.com', 'cloud storage', 'files', 'folders'],

        # Code/Development
        'github': ['repository', 'repo', 'code', 'commits', 'pull request', 'pr', 'issues', 'git'],
        'repository': ['repo', 'codebase', 'project', 'git', 'github'],
        'commit': ['change', 'update', 'revision', 'git commit', 'push'],
        'pull request': ['pr', 'merge request', 'code review', 'changes'],
        'issue': ['bug', 'ticket', 'task', 'problem', 'feature request'],

        # Notes/Wiki
        'notion': ['notes', 'wiki', 'documentation', 'pages', 'database'],
        'notes': ['notion', 'memo', 'jot', 'documentation', 'record'],

        # Research
        'zotero': ['reference', 'citation', 'paper', 'research', 'bibliography'],
        'paper': ['article', 'publication', 'research', 'journal', 'study'],
        'research': ['study', 'paper', 'publication', 'analysis', 'findings'],

        # Web
        'webpage': ['website', 'page', 'url', 'link', 'site', 'web'],
        'website': ['webpage', 'site', 'web', 'url', 'link'],
    }

    # Context-aware expansions based on document content type
    CONTEXT_EXPANSIONS = {
        # If query seems code-related, add these terms
        'code_context': ['code', 'implementation', 'function', 'class', 'module', 'file', 'source'],
        # If query seems about structure, add these
        'structure_context': ['architecture', 'design', 'organization', 'layout', 'hierarchy', 'components'],
        # If query seems about communication
        'communication_context': ['email', 'message', 'slack', 'conversation', 'thread'],
        # If query seems about documents
        'document_context': ['file', 'document', 'report', 'pdf', 'attachment'],
    }

    @classmethod
    def expand_acronyms(cls, query: str) -> str:
        """Expand acronyms in query"""
        expanded = query
        for acronym, expansion in cls.ACRONYMS.items():
            pattern = rf'\b{re.escape(acronym)}\b'
            if re.search(pattern, query, re.IGNORECASE):
                match = re.search(pattern, query, re.IGNORECASE)
                if match and expansion.lower() not in query.lower():
                    original = match.group()
                    expanded = expanded.replace(original, f"{original} ({expansion})", 1)
        return expanded

    @classmethod
    def get_synonyms(cls, query: str) -> List[str]:
        """Get synonyms for key terms from all synonym dictionaries"""
        query_lower = query.lower()
        additional = []

        # Check general synonyms
        for term, syns in cls.SYNONYMS.items():
            if term in query_lower:
                additional.extend(syns)

        # Check source/integration synonyms
        for term, syns in cls.SOURCE_SYNONYMS.items():
            if term in query_lower:
                additional.extend(syns)

        return list(set(additional))

    @classmethod
    def detect_context(cls, query: str) -> str:
        """Detect if query is about code, structure, etc."""
        query_lower = query.lower()

        # Code-related indicators
        code_indicators = ['code', 'function', 'class', 'module', 'import', 'api', 'endpoint',
                          'database', 'server', 'client', 'component', 'file', 'folder',
                          'directory', 'package', 'library', 'framework', 'backend', 'frontend',
                          'react', 'python', 'javascript', 'typescript', 'node', 'flask', 'django',
                          'parsed', 'codebase', 'repository', 'repo', 'git', 'source']

        # Structure-related indicators
        structure_indicators = ['architecture', 'structure', 'design', 'layout', 'organization',
                               'hierarchy', 'overview', 'diagram', 'flow', 'how does', 'how is',
                               'explain', 'describe', 'what is the']

        has_code = any(ind in query_lower for ind in code_indicators)
        has_structure = any(ind in query_lower for ind in structure_indicators)

        if has_code and has_structure:
            return 'code_structure'
        elif has_structure:
            return 'structure'  # Might be asking about code structure
        elif has_code:
            return 'code'
        return 'general'

    @classmethod
    def expand(cls, query: str) -> Dict:
        """Full query expansion with context awareness"""
        expanded = cls.expand_acronyms(query)
        synonyms = cls.get_synonyms(query)
        context = cls.detect_context(query)

        # Build enhanced search query
        search_parts = [expanded]

        # Add top synonyms to search query (limit to avoid noise)
        if synonyms:
            top_synonyms = synonyms[:3]  # Limit to top 3 to reduce irrelevant matches
            search_parts.extend(top_synonyms)

        # Context-aware expansion: if asking about "architecture" alone,
        # automatically add code context since they parsed code
        if context == 'structure':
            # User might be asking about code structure - add code context
            search_parts.extend(['code', 'structure', 'design', 'components', 'modules'])
        elif context == 'code_structure':
            search_parts.extend(['architecture', 'design', 'organization', 'layout'])

        # Create the final search query
        search_query = ' '.join(search_parts)

        return {
            'original': query,
            'expanded': expanded,
            'synonyms': synonyms,
            'context': context,
            'search_query': search_query
        }


# =============================================================================
# CROSS-ENCODER RERANKING
# =============================================================================

class CrossEncoderReranker:
    """Cross-encoder for accurate reranking"""

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-12-v2"

    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        if not CROSS_ENCODER_AVAILABLE:
            return
        try:
            self.model = CrossEncoder(self.MODEL_NAME)
            print(f"[EnhancedSearch] Cross-encoder loaded: {self.MODEL_NAME}")
        except Exception as e:
            print(f"[EnhancedSearch] Failed to load cross-encoder: {e}")
            self.model = None

    def rerank(self, query: str, results: List[Dict], top_k: int = 10) -> List[Dict]:
        """Rerank results using cross-encoder with batched predictions for speed"""
        if not self.model or not results:
            return results[:top_k]

        # OPTIMIZATION: Batch all predictions at once instead of one-by-one
        # This is MUCH faster as model inference is batched
        pairs = []
        result_indices = []

        for i, result in enumerate(results):
            content = result.get('content', '') or result.get('content_preview', '')
            if not content:
                continue
            # Only use first 512 chars for speed (covers most relevant info)
            pairs.append((query, content[:512]))
            result_indices.append(i)

        if not pairs:
            return results[:top_k]

        # Single batched prediction - MUCH faster than individual calls
        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            print(f"[EnhancedSearch] Reranking failed: {e}")
            return results[:top_k]

        # Assign scores back to results
        scored_results = []
        score_idx = 0
        for i, result in enumerate(results):
            if i in result_indices:
                score = float(scores[score_idx])
                score_idx += 1
            else:
                score = 0.0
            result['rerank_score'] = score
            scored_results.append((result, score))

        # Sort by rerank score
        scored_results.sort(key=lambda x: x[1], reverse=True)

        return [r for r, _ in scored_results[:top_k]]


# =============================================================================
# MMR DIVERSITY SELECTION
# =============================================================================

class MMRSelector:
    """Maximal Marginal Relevance for diverse results"""

    @staticmethod
    def select(
        results: List[Dict],
        query_embedding: np.ndarray,
        embeddings: np.ndarray,
        k: int = 10,
        lambda_param: float = 0.7
    ) -> List[Dict]:
        """Select diverse results using MMR"""
        if len(results) <= k:
            return results

        # Normalize embeddings
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        emb_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)

        # Compute similarities
        query_sims = np.dot(emb_norms, query_norm)
        doc_sims = np.dot(emb_norms, emb_norms.T)

        selected_indices = []
        remaining = list(range(len(results)))

        for _ in range(k):
            if not remaining:
                break

            mmr_scores = []
            for idx in remaining:
                relevance = query_sims[idx]
                if selected_indices:
                    diversity_penalty = max(doc_sims[idx][s] for s in selected_indices)
                else:
                    diversity_penalty = 0

                mmr = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
                mmr_scores.append((idx, mmr))

            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

        return [results[i] for i in selected_indices]


# =============================================================================
# HALLUCINATION DETECTION
# =============================================================================

class HallucinationDetector:
    """Detect and flag potential hallucinations - Enhanced version"""

    # Common named entity patterns (without requiring spaCy)
    DATE_PATTERNS = [
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
        r'\b(?:Q[1-4]|FY)\s*\d{2,4}\b',
    ]

    # Patterns that often indicate factual claims
    CLAIM_INDICATORS = [
        r'\b(?:is|are|was|were|has|have|had)\s+(?:a|an|the)?\s*\w+',
        r'\b(?:founded|established|created|launched|started)\s+(?:in|on|by)',
        r'\b(?:according to|based on|reported|stated|announced)',
        r'\b(?:increased|decreased|grew|declined|rose|fell)\s+(?:by|to)',
        r'\b(?:costs?|prices?|revenue|profit|sales)\s+(?:of|is|are|was|were)',
    ]

    def __init__(self, client):
        self.client = client
        self.date_regex = re.compile('|'.join(self.DATE_PATTERNS), re.IGNORECASE)
        self.claim_regex = re.compile('|'.join(self.CLAIM_INDICATORS), re.IGNORECASE)

    def extract_claims(self, answer: str) -> List[Dict]:
        """Extract factual claims from answer - Enhanced to catch more claim types"""
        claims = []
        seen_texts = set()  # Avoid duplicate claims

        # 1. Extract numbers with context (existing)
        number_pattern = r'([^.]*?\b\d[\d,\.%$]*\b[^.]*\.)'
        for match in re.finditer(number_pattern, answer):
            text = match.group(1).strip()
            if text not in seen_texts:
                seen_texts.add(text)
                claims.append({
                    'type': 'numerical',
                    'text': text,
                    'value': re.search(r'\d[\d,\.%$]*', match.group(1)).group()
                })

        # 2. Extract source citations (existing)
        citation_pattern = r'\[Source (\d+)\]'
        for match in re.finditer(citation_pattern, answer):
            claims.append({
                'type': 'citation',
                'source_num': int(match.group(1)),
                'context': answer[max(0, match.start()-100):match.end()+50]
            })

        # 3. NEW: Extract date claims
        for match in self.date_regex.finditer(answer):
            # Get surrounding sentence
            start = answer.rfind('.', 0, match.start()) + 1
            end = answer.find('.', match.end())
            if end == -1:
                end = len(answer)
            text = answer[start:end].strip()
            if text not in seen_texts and len(text) > 20:
                seen_texts.add(text)
                claims.append({
                    'type': 'date',
                    'text': text,
                    'value': match.group()
                })

        # 4. NEW: Extract proper nouns (capitalized multi-word phrases) as entity claims
        proper_noun_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        for match in re.finditer(proper_noun_pattern, answer):
            entity = match.group(1)
            # Skip common phrases
            skip_phrases = ['Source Used', 'Sources Used', 'The', 'This', 'Based On']
            if entity not in skip_phrases and entity not in seen_texts:
                # Get surrounding context
                start = max(0, match.start() - 50)
                end = min(len(answer), match.end() + 50)
                context = answer[start:end]
                claims.append({
                    'type': 'entity',
                    'text': context,
                    'value': entity
                })
                seen_texts.add(entity)

        # 5. NEW: Extract key factual statements (sentences with claim indicators)
        sentences = re.split(r'[.!?]\s+', answer)
        for sentence in sentences:
            if len(sentence) > 30 and self.claim_regex.search(sentence):
                if sentence not in seen_texts:
                    seen_texts.add(sentence)
                    claims.append({
                        'type': 'statement',
                        'text': sentence.strip(),
                        'value': None
                    })

        return claims[:50]  # Limit to 50 claims to avoid performance issues

    def verify_claims(self, claims: List[Dict], sources: List[Dict]) -> Dict:
        """Verify claims against sources - Enhanced for all claim types"""
        verified = []
        unverified = []
        hallucinated = []

        # Build combined source text for faster searching
        all_source_text = ' '.join(s.get('content', '') + ' ' + s.get('title', '') for s in sources).lower()

        for claim in claims:
            claim_type = claim['type']

            if claim_type == 'citation':
                source_num = claim['source_num']
                if source_num <= len(sources):
                    source_content = sources[source_num - 1].get('content', '')
                    claim_numbers = set(re.findall(r'\d+\.?\d*', claim['context']))
                    source_numbers = set(re.findall(r'\d+\.?\d*', source_content))

                    if claim_numbers & source_numbers:
                        verified.append(claim)
                    else:
                        unverified.append(claim)
                else:
                    hallucinated.append(claim)

            elif claim_type == 'numerical':
                claim_value = claim['value'].replace(',', '').replace('$', '').replace('%', '')
                if claim_value in all_source_text.replace(',', ''):
                    verified.append(claim)
                else:
                    unverified.append(claim)

            elif claim_type == 'date':
                # Check if date appears in sources
                date_value = claim['value'].lower()
                if date_value in all_source_text:
                    verified.append(claim)
                else:
                    unverified.append(claim)

            elif claim_type == 'entity':
                # Check if entity name appears in sources
                entity = claim['value'].lower()
                if entity in all_source_text:
                    verified.append(claim)
                else:
                    unverified.append(claim)

            elif claim_type == 'statement':
                # For statements, check if key words appear in sources
                # Extract significant words (4+ chars, not stopwords)
                stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'will', 'would', 'could', 'should'}
                words = re.findall(r'\b[a-z]{4,}\b', claim['text'].lower())
                significant_words = [w for w in words if w not in stopwords]

                if not significant_words:
                    continue

                # If >50% of significant words found in sources, consider verified
                found_count = sum(1 for w in significant_words if w in all_source_text)
                if found_count / len(significant_words) > 0.5:
                    verified.append(claim)
                else:
                    unverified.append(claim)

        total = len(claims) or 1
        confidence = len(verified) / total

        return {
            'verified': len(verified),
            'unverified': len(unverified),
            'hallucinated': len(hallucinated),
            'total_claims': len(claims),
            'confidence': confidence,
            'claim_types': {
                'numerical': len([c for c in claims if c['type'] == 'numerical']),
                'citation': len([c for c in claims if c['type'] == 'citation']),
                'date': len([c for c in claims if c['type'] == 'date']),
                'entity': len([c for c in claims if c['type'] == 'entity']),
                'statement': len([c for c in claims if c['type'] == 'statement']),
            },
            'details': {
                'verified': verified[:5],
                'unverified': unverified[:5],
                'hallucinated': hallucinated[:5]
            }
        }

    def check_citation_coverage(self, answer: str) -> Dict:
        """Check what percentage of statements have citations"""
        sentences = re.split(r'[.!?]\s+', answer)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

        if not sentences:
            return {'cited_ratio': 1.0, 'uncited_sentences': []}

        citation_pattern = r'\[Source\s*\d+\]'
        cited_count = 0
        uncited = []

        skip_phrases = ['sources used', 'source:', '?', "i don't have", 'based on the']

        for sentence in sentences:
            if any(skip in sentence.lower() for skip in skip_phrases):
                continue
            if re.search(citation_pattern, sentence, re.IGNORECASE):
                cited_count += 1
            else:
                uncited.append(sentence[:100])

        checkable = len([s for s in sentences if not any(skip in s.lower() for skip in skip_phrases)])

        return {
            'cited_ratio': cited_count / max(checkable, 1),
            'cited_count': cited_count,
            'total_checkable': checkable,
            'uncited_sentences': uncited[:3]
        }


# =============================================================================
# FRESHNESS SCORING
# =============================================================================

class FreshnessScorer:
    """Boost recent documents"""

    DATE_PATTERNS = [
        r'\b(20[1-2]\d)\b',
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20[1-2]\d\b',
        r'\b\d{1,2}/\d{1,2}/20[1-2]\d\b',
        r'\b20[1-2]\d-\d{2}-\d{2}\b',
    ]

    @classmethod
    def extract_year(cls, content: str, metadata: Dict = None) -> Optional[int]:
        """Extract most recent year from content"""
        years = []

        if metadata:
            for key in ['date', 'created', 'modified', 'year', 'source_created_at']:
                if key in metadata:
                    year_match = re.search(r'20[1-2]\d', str(metadata[key]))
                    if year_match:
                        years.append(int(year_match.group()))

        for pattern in cls.DATE_PATTERNS:
            matches = re.findall(pattern, content[:2000])
            for match in matches:
                if isinstance(match, str) and match.isdigit():
                    years.append(int(match))

        return max(years) if years else None

    @classmethod
    def get_boost(cls, year: Optional[int], current_year: int = 2025) -> float:
        """Get freshness boost factor"""
        if year is None:
            return 1.0

        age = current_year - year
        if age <= 0:
            return 1.15
        elif age == 1:
            return 1.1
        elif age <= 2:
            return 1.0
        elif age <= 5:
            return 0.95
        else:
            return 0.9


# =============================================================================
# ENHANCED SEARCH SERVICE
# =============================================================================

class EnhancedSearchService:
    """
    Enhanced search service that adds sophisticated features to Pinecone.

    Features:
    - Query expansion (acronyms, synonyms)
    - Cross-encoder reranking
    - MMR diversity selection
    - Hallucination detection
    - Freshness scoring
    - Strict citation enforcement
    """

    def __init__(self):
        self.client = get_openai_client()

        # Initialize components
        self.reranker = CrossEncoderReranker()
        self.hallucination_detector = HallucinationDetector(self.client)

        # Cache for embeddings
        self._embedding_cache = {}

        print("[EnhancedSearch] Service initialized")
        print(f"[EnhancedSearch] Cross-encoder available: {self.reranker.model is not None}")

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding with caching"""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        response = self.client.create_embedding(
            text=text,
            dimensions=1536
        )
        embedding = np.array(response.data[0].embedding, dtype=np.float32)

        self._embedding_cache[cache_key] = embedding
        if len(self._embedding_cache) > 500:
            # Evict oldest
            keys = list(self._embedding_cache.keys())[:100]
            for k in keys:
                del self._embedding_cache[k]

        return embedding

    def _fast_diversity_select(self, results: List[Dict], k: int) -> List[Dict]:
        """
        Fast diversity selection without embedding API calls.

        Uses source-based diversity to ensure results from different documents/sources.
        This is O(n) and requires NO external API calls vs MMR which needs O(n) embedding calls.

        Strategy:
        1. Group results by source document
        2. Round-robin select from different sources
        3. Fall back to score-based selection for remaining slots
        """
        if len(results) <= k:
            return results

        # Group by source document
        source_groups = {}
        for result in results:
            source = result.get('doc_id') or result.get('metadata', {}).get('document_id', 'unknown')
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(result)

        # Sort each group by score
        for source in source_groups:
            source_groups[source].sort(key=lambda x: x.get('rerank_score', x.get('score', 0)), reverse=True)

        # Round-robin selection for diversity
        selected = []
        sources = list(source_groups.keys())
        source_idx = 0

        while len(selected) < k and any(source_groups.values()):
            # Get next source (round-robin)
            attempts = 0
            while attempts < len(sources):
                source = sources[source_idx % len(sources)]
                source_idx += 1
                attempts += 1

                if source_groups.get(source):
                    selected.append(source_groups[source].pop(0))
                    break
            else:
                # All sources exhausted
                break

        # If we still need more, take highest scoring remaining
        if len(selected) < k:
            remaining = []
            for group in source_groups.values():
                remaining.extend(group)
            remaining.sort(key=lambda x: x.get('rerank_score', x.get('score', 0)), reverse=True)
            selected.extend(remaining[:k - len(selected)])

        return selected[:k]

    def enhanced_search(
        self,
        query: str,
        tenant_id: str,
        vector_store,  # PineconeVectorStore or HybridPineconeStore
        top_k: int = 10,
        use_reranking: bool = True,
        use_mmr: bool = True,
        use_expansion: bool = True,
        use_freshness: bool = True,
        mmr_lambda: float = 0.7,
        boost_doc_ids: list = None
    ) -> Dict:
        """
        Enhanced search with all features.

        Args:
            query: User query
            tenant_id: Tenant ID for isolation
            vector_store: Pinecone vector store instance
            top_k: Number of results to return
            use_reranking: Enable cross-encoder reranking
            use_mmr: Enable MMR diversity
            use_expansion: Enable query expansion
            use_freshness: Enable freshness scoring
            mmr_lambda: MMR relevance vs diversity tradeoff
            boost_doc_ids: List of document IDs to boost (for newly uploaded docs)

        Returns:
            Dict with results and metadata
        """
        start_time = time.time()

        # Step 1: Query expansion with context awareness
        if use_expansion:
            expansion = QueryExpander.expand(query)
            # Use full search_query which includes synonyms and context expansions
            search_query = expansion['search_query']
            context = expansion.get('context', 'general')
            print(f"[EnhancedSearch] Context: {context}")
            print(f"[EnhancedSearch] Expanded: {query} -> {search_query[:150]}...")
        else:
            expansion = {'original': query, 'expanded': query, 'synonyms': [], 'context': 'general'}
            search_query = query

        # Step 2: Initial retrieval from Pinecone (get more for reranking)
        retrieve_k = top_k * 3 if use_reranking else top_k * 2

        # Use hybrid search if available
        if hasattr(vector_store, 'hybrid_search'):
            initial_results = vector_store.hybrid_search(
                query=search_query,
                tenant_id=tenant_id,
                top_k=retrieve_k
            )
        else:
            initial_results = vector_store.search(
                query=search_query,
                tenant_id=tenant_id,
                top_k=retrieve_k
            )

        print(f"[EnhancedSearch] Initial retrieval: {len(initial_results)} results")

        # Filter out very low cosine similarity results (clearly irrelevant)
        MIN_COSINE_SCORE = 0.20
        before_filter = len(initial_results)
        filtered = [r for r in initial_results if r.get('score', 0) >= MIN_COSINE_SCORE]
        if not filtered and initial_results:
            # Keep at least the single best result
            filtered = sorted(initial_results, key=lambda x: x.get('score', 0), reverse=True)[:1]
        initial_results = filtered
        if before_filter != len(initial_results):
            print(f"[EnhancedSearch] Filtered {before_filter - len(initial_results)} low-score results (< {MIN_COSINE_SCORE})")

        if not initial_results:
            return {
                'query': query,
                'expanded_query': search_query,
                'results': [],
                'num_results': 0,
                'search_time': time.time() - start_time,
                'features_used': {
                    'expansion': use_expansion,
                    'reranking': False,
                    'mmr': False,
                    'freshness': False
                }
            }

        # Step 3: Apply freshness scoring
        if use_freshness:
            for result in initial_results:
                content = result.get('content', '') or result.get('content_preview', '')
                metadata = result.get('metadata', {})
                year = FreshnessScorer.extract_year(content, metadata)
                boost = FreshnessScorer.get_boost(year)
                result['freshness_boost'] = boost
                result['score'] = result.get('score', 0) * boost

        # Step 3.5: Boost specific documents (e.g., newly uploaded chat attachments)
        if boost_doc_ids:
            boost_doc_ids_set = set(boost_doc_ids)
            boosted_count = 0
            for result in initial_results:
                doc_id = result.get('doc_id', '') or result.get('metadata', {}).get('document_id', '')
                if doc_id in boost_doc_ids_set:
                    result['score'] = result.get('score', 0) * 1.5  # 50% boost
                    result['upload_boost'] = 1.5
                    result['is_new_upload'] = True
                    boosted_count += 1
            if boosted_count > 0:
                print(f"[EnhancedSearch] Boosted {boosted_count} newly uploaded documents")

        # Step 4: Cross-encoder reranking
        reranked = False
        if use_reranking and self.reranker.model:
            initial_results = self.reranker.rerank(query, initial_results, top_k=top_k * 2)
            reranked = True
            print(f"[EnhancedSearch] Reranked to {len(initial_results)} results")

            # Filter out clearly irrelevant results after reranking
            # ms-marco cross-encoder: scores > 0 = relevant, < -3 = irrelevant
            MIN_RERANK_SCORE = -2.0
            before_rerank_filter = len(initial_results)
            filtered = [r for r in initial_results if r.get('rerank_score', 0) >= MIN_RERANK_SCORE]
            if not filtered and initial_results:
                # Keep at least the top 2 results
                filtered = initial_results[:2]
            initial_results = filtered
            if before_rerank_filter != len(initial_results):
                print(f"[EnhancedSearch] Dropped {before_rerank_filter - len(initial_results)} irrelevant results (rerank < {MIN_RERANK_SCORE})")

        # Step 5: Diversity selection (OPTIMIZED - no API calls needed)
        # Instead of expensive MMR with embeddings, use simple source-based diversity
        mmr_applied = False
        if use_mmr and len(initial_results) > top_k:
            try:
                # FAST diversity: Ensure variety across different sources/documents
                # This avoids 20-30 OpenAI embedding API calls per search!
                initial_results = self._fast_diversity_select(initial_results, top_k)
                mmr_applied = True
                print(f"[EnhancedSearch] Fast diversity selected {len(initial_results)} results")
            except Exception as e:
                print(f"[EnhancedSearch] Diversity selection failed: {e}")
                initial_results = initial_results[:top_k]
        else:
            initial_results = initial_results[:top_k]

        search_time = time.time() - start_time

        return {
            'query': query,
            'expanded_query': search_query,
            'expansion': expansion,
            'results': initial_results,
            'num_results': len(initial_results),
            'search_time': search_time,
            'features_used': {
                'expansion': use_expansion,
                'reranking': reranked,
                'mmr': mmr_applied,
                'freshness': use_freshness
            }
        }

    def _get_mode_config(self, response_mode: int, query: str, context: str):
        """
        Get system prompt, user instruction, temperature, max_tokens, and frequency_penalty based on response mode.
        Mode 1: Sources — just document titles/links, no AI answer
        Mode 2: Sources & Summary — brief summary + source links
        Mode 3: In-Depth — full comprehensive answer with insights (default)

        Returns: (system_prompt, user_instruction, temperature, max_tokens, frequency_penalty)
        """
        if response_mode == 1:
            system_prompt = """You are a document retrieval assistant. Your ONLY job is to identify which source documents are relevant to the user's question.

RULES:
- Do NOT explain, summarize, or interpret the content of the documents
- Do NOT answer the question directly
- List each UNIQUE relevant document ONCE with a one-line note on why it is relevant
- NEVER repeat the same document — if multiple sources have the same title, list it only once
- If no sources are relevant, say "No relevant documents found for this query."
- Keep your response SHORT — just a clean numbered list"""

            user_instruction = """List each UNIQUE relevant document title ONCE with a one-line relevance note.
Do NOT repeat any document. Do NOT answer the question.
Format: [Source N] Title — why it's relevant
Keep it short and clean."""
            return system_prompt, user_instruction, 0.0, 400, 0.8

        elif response_mode == 2:
            system_prompt = """You are a concise knowledge assistant. You answer based on the provided source documents.

RULES:
- Give a short summary (2-4 sentences max) answering the question
- Then list the relevant source documents the user should read
- NEVER repeat yourself — each sentence should add new information
- NEVER list the same document more than once
- Do NOT elaborate or explain in depth
- Cite sources with [Source N]
- If sources don't contain the answer, say so in one sentence"""

            user_instruction = """Answer in 2-4 sentences max. Then list the relevant documents to read.
NEVER repeat the same information or document name. Be concise.

End with "Sources Used: [list numbers]"."""
            return system_prompt, user_instruction, 0.1, 500, 0.8

        else:  # Mode 3 (default) — current full behavior: in-depth with insights
            system_prompt = """You are a precise knowledge assistant. You ONLY answer based on the provided source documents.

CRITICAL ACCURACY RULES (NEVER VIOLATE):
1. **ONLY use information explicitly stated in the sources** - Never infer, assume, or add information not in the sources
2. **If sources don't contain the answer, say so clearly** - "Based on the provided documents, I don't have information about [topic]."
3. **Quote directly when possible** - Use exact text from sources for key claims
4. **Distinguish facts from interpretation** - If you're explaining something, make clear what's from sources vs your explanation
5. **Never hallucinate code, numbers, dates, or names** - Only include these if they appear in sources

RESPONSE FORMAT:
- Use **headers** (## Section) for organization
- Use **code blocks** (```language) ONLY for actual source code - NEVER for tabular data
- Use **numbered lists** for steps/processes
- Use **bullet points** for features/items
- Keep paragraphs focused and clear
- For ANY tabular data, ALWAYS use proper markdown table syntax with | pipes and separator rows:
  | Column 1 | Column 2 |
  |----------|----------|
  | Data 1   | Data 2   |
  NEVER put tables inside code blocks (``` ```) — always use the pipe syntax above

CITATION FORMAT:
- Cite every factual claim: [Source 1], [Source 2]
- For code snippets, cite the source file: [Source 3: filename.py]
- If combining info from multiple sources, cite all: [Source 1, 2]

HONESTY REQUIREMENTS:
- If asked about something not in sources: "I don't have that information in my knowledge base."
- If sources are unclear or contradictory: Acknowledge the uncertainty
- If you can only partially answer: State what you know and what's missing
- Never make up examples, URLs, or specific details

Your goal: Accurate, helpful answers grounded STRICTLY in source documents."""

            user_instruction = """Provide a DETAILED, well-formatted answer:
- Use numbered steps for processes/procedures
- Include code blocks for any code content
- Be thorough - explain concepts fully with examples
- Use conversation history for context (e.g., understand pronouns like "it", "that", "them")
- Cite key facts with [Source X]

End with "Sources Used: [list numbers]"."""
            return system_prompt, user_instruction, 0.1, 2000, 0.0

    def generate_answer(
        self,
        query: str,
        search_results: Dict,
        validate: bool = True,
        max_context_tokens: int = 12000,
        conversation_history: list = None,
        response_mode: int = 3
    ) -> Dict:
        """
        Generate answer with strict citation enforcement and conversation context.

        Args:
            query: User query
            search_results: Results from enhanced_search
            validate: Run hallucination detection
            max_context_tokens: Max tokens for context
            conversation_history: Previous messages for multi-turn conversations
            response_mode: 1=Links Only, 2=Brief, 3=Balanced, 4=Detailed (default)

        Returns:
            Dict with answer and validation results
        """
        conversation_history = conversation_history or []
        results = search_results.get('results', [])

        if not results:
            return {
                'answer': "I couldn't find any relevant information to answer your question.",
                'confidence': 0.0,
                'sources': [],
                'hallucination_check': None
            }

        # Build context with FULL content (not just 500 chars)
        # Only include sources with meaningful relevance scores
        context_parts = []
        sources_used = []  # Track which sources made it into context
        total_chars = 0
        max_chars = max_context_tokens * 4  # ~4 chars per token

        for i, result in enumerate(results[:15], 1):  # Use up to 15 sources
            content = result.get('content', '') or result.get('content_preview', '')
            title = result.get('title', 'Untitled')
            score = result.get('rerank_score', result.get('score', 0))

            # Skip low-relevance sources (but always include at least 1)
            if i > 1 and score < 0.15:
                print(f"[EnhancedSearch] Skipping source {i} '{title[:40]}' - low relevance ({score:.3f})")
                continue

            # Don't truncate aggressively - use more content
            if len(content) > 3000:
                content = content[:3000] + "..."

            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 500:
                    content = content[:remaining]
                else:
                    break

            source_idx = len(context_parts) + 1
            context_parts.append(
                f"[Source {source_idx}] (Relevance: {score:.2%})\n"
                f"Title: {title}\n"
                f"Content: {content}\n"
            )
            sources_used.append(result)
            total_chars += len(content)

        context = "\n---\n".join(context_parts)

        # Get mode-specific prompt configuration
        system_prompt, user_instruction, temperature, max_tokens, freq_penalty = self._get_mode_config(response_mode, query, context)

        # Build conversation context if history exists
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_context = "CONVERSATION HISTORY (for context):\n"
            for i, msg in enumerate(conversation_history[-6:], 1):  # Last 6 messages
                role = "User" if msg.get('role') == 'user' else "Assistant"
                content = msg.get('content', '')[:200]  # Limit to 200 chars per message
                conversation_context += f"{role}: {content}\n"
            conversation_context += "\n"

        user_prompt = f"""{conversation_context}SOURCE DOCUMENTS:
{context}

CURRENT QUESTION: {query}

{user_instruction}"""

        try:
            # Build messages array with conversation history
            messages = [{"role": "system", "content": system_prompt}]

            # Add last 4 messages from history for better context (not too many to avoid token limits)
            if conversation_history and len(conversation_history) > 0:
                for msg in conversation_history[-4:]:
                    messages.append({
                        "role": msg.get('role', 'user'),
                        "content": msg.get('content', '')[:500]  # Limit each to 500 chars
                    })

            # Add current query with sources
            messages.append({"role": "user", "content": user_prompt})

            completion_kwargs = {}
            if freq_penalty > 0:
                completion_kwargs['frequency_penalty'] = freq_penalty
            response = self.client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **completion_kwargs
            )

            answer = response.choices[0].message.content.strip()

            # Validation
            hallucination_check = None
            citation_check = None

            if validate:
                claims = self.hallucination_detector.extract_claims(answer)
                if claims:
                    hallucination_check = self.hallucination_detector.verify_claims(claims, sources_used)
                citation_check = self.hallucination_detector.check_citation_coverage(answer)

            # Calculate confidence
            top_result = sources_used[0] if sources_used else results[0]
            base_confidence = top_result.get('rerank_score', top_result.get('score', 0.5))
            if hallucination_check:
                base_confidence = min(base_confidence, hallucination_check['confidence'])
            if citation_check:
                base_confidence = min(base_confidence, citation_check['cited_ratio'])

            return {
                'answer': answer,
                'confidence': base_confidence,
                'sources': sources_used[:10],
                'hallucination_check': hallucination_check,
                'citation_check': citation_check,
                'context_chars': total_chars,
                'sources_used': len(context_parts)
            }

        except Exception as e:
            return {
                'answer': f"Error generating answer: {str(e)}",
                'confidence': 0.0,
                'sources': sources_used[:10] if sources_used else results[:3],
                'error': str(e)
            }

    def search_and_answer(
        self,
        query: str,
        tenant_id: str,
        vector_store,
        top_k: int = 10,
        validate: bool = True,
        conversation_history: list = None,
        boost_doc_ids: list = None,
        response_mode: int = 3
    ) -> Dict:
        """
        Complete enhanced RAG pipeline with conversation history support.

        Args:
            query: User query
            tenant_id: Tenant ID
            vector_store: Pinecone store
            top_k: Number of sources
            validate: Run hallucination detection
            conversation_history: Previous messages for context (list of {role, content})
            boost_doc_ids: List of document IDs to boost in results (for newly uploaded docs)

        Returns:
            Complete response with answer, sources, and metadata
        """
        # SECURITY: Sanitize query input
        sanitized_query, warnings = sanitize_query(query)
        if warnings:
            print(f"[EnhancedSearch] Query sanitization warnings: {warnings}", flush=True)

        if not sanitized_query:
            return {
                'query': query,
                'answer': "Please provide a valid search query.",
                'confidence': 0.0,
                'sources': [],
                'num_sources': 0,
                'error': "Invalid query"
            }

        # Use sanitized query for search
        query = sanitized_query

        # MEMORY SAFETY: Bound conversation history to prevent memory leaks
        MAX_HISTORY_MESSAGES = 20  # Reasonable max for context
        MAX_MESSAGE_LENGTH = 1000  # Max chars per message

        if conversation_history:
            # Truncate to last N messages
            if len(conversation_history) > MAX_HISTORY_MESSAGES:
                print(f"[EnhancedSearch] Truncating conversation history from {len(conversation_history)} to {MAX_HISTORY_MESSAGES}", flush=True)
                conversation_history = conversation_history[-MAX_HISTORY_MESSAGES:]

            # Validate and truncate individual messages
            bounded_history = []
            for msg in conversation_history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    content = str(msg.get('content', ''))[:MAX_MESSAGE_LENGTH]
                    bounded_history.append({
                        'role': msg.get('role', 'user'),
                        'content': content
                    })
            conversation_history = bounded_history

        # Search
        search_results = self.enhanced_search(
            query=query,
            tenant_id=tenant_id,
            vector_store=vector_store,
            top_k=top_k,
            boost_doc_ids=boost_doc_ids
        )

        # Generate answer with conversation context
        answer_result = self.generate_answer(
            query=query,
            search_results=search_results,
            validate=validate,
            conversation_history=conversation_history or [],
            response_mode=response_mode
        )

        return {
            'query': query,
            'expanded_query': search_results.get('expanded_query'),
            'answer': answer_result['answer'],
            'confidence': answer_result['confidence'],
            'sources': answer_result['sources'],
            'num_sources': len(answer_result['sources']),
            'search_time': search_results.get('search_time', 0),
            'features_used': search_results.get('features_used', {}),
            'hallucination_check': answer_result.get('hallucination_check'),
            'citation_check': answer_result.get('citation_check'),
            'context_chars': answer_result.get('context_chars', 0)
        }

    def generate_answer_stream(
        self,
        query: str,
        search_results: Dict,
        max_context_tokens: int = 12000,
        conversation_history: list = None,
        response_mode: int = 3
    ):
        """
        Generate answer with STREAMING - yields chunks as they arrive.

        Yields:
            dict with 'type' ('chunk' or 'done') and content
        """
        conversation_history = conversation_history or []
        results = search_results.get('results', [])

        if not results:
            yield {'type': 'chunk', 'content': "I couldn't find any relevant information to answer your question."}
            yield {'type': 'done', 'confidence': 0.0, 'sources': []}
            return

        # Build context (same as non-streaming)
        context_parts = []
        total_chars = 0
        max_chars = max_context_tokens * 4

        for i, result in enumerate(results[:15], 1):
            content = result.get('content', '') or result.get('content_preview', '')
            title = result.get('title', 'Untitled')
            score = result.get('rerank_score', result.get('score', 0))

            if len(content) > 3000:
                content = content[:3000] + "..."

            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 500:
                    content = content[:remaining]
                else:
                    break

            context_parts.append(
                f"[Source {i}] (Relevance: {score:.2%})\n"
                f"Title: {title}\n"
                f"Content: {content}\n"
            )
            total_chars += len(content)

        context = "\n---\n".join(context_parts)

        # Get mode-specific prompt configuration
        system_prompt, user_instruction, temperature, max_tokens, freq_penalty = self._get_mode_config(response_mode, query, context)

        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_context = "CONVERSATION HISTORY (for context):\n"
            for i, msg in enumerate(conversation_history[-6:], 1):
                role = "User" if msg.get('role') == 'user' else "Assistant"
                content = msg.get('content', '')[:200]
                conversation_context += f"{role}: {content}\n"
            conversation_context += "\n"

        user_prompt = f"""{conversation_context}SOURCE DOCUMENTS:
{context}

CURRENT QUESTION: {query}

{user_instruction}"""

        try:
            messages = [{"role": "system", "content": system_prompt}]

            if conversation_history and len(conversation_history) > 0:
                for msg in conversation_history[-4:]:
                    messages.append({
                        "role": msg.get('role', 'user'),
                        "content": msg.get('content', '')[:500]
                    })

            messages.append({"role": "user", "content": user_prompt})

            # STREAM the response
            full_answer = ""
            stream_kwargs = {}
            if freq_penalty > 0:
                stream_kwargs['frequency_penalty'] = freq_penalty
            stream = self.client.chat_completion_stream(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **stream_kwargs
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    yield {'type': 'chunk', 'content': content}

            # After streaming, run validation
            hallucination_check = None
            base_confidence = results[0].get('rerank_score', results[0].get('score', 0.5))

            try:
                claims = self.hallucination_detector.extract_claims(full_answer)
                if claims:
                    hallucination_check = self.hallucination_detector.verify_claims(claims, results)
                    if hallucination_check:
                        base_confidence = min(base_confidence, hallucination_check.get('confidence', 1.0))
            except Exception as e:
                print(f"[Stream] Hallucination check error: {e}", flush=True)

            yield {
                'type': 'done',
                'confidence': base_confidence,
                'sources': results[:10],
                'hallucination_check': hallucination_check
            }

        except Exception as e:
            yield {'type': 'chunk', 'content': f"Error generating answer: {str(e)}"}
            yield {'type': 'done', 'confidence': 0.0, 'sources': [], 'error': str(e)}

    def search_and_answer_stream(
        self,
        query: str,
        tenant_id: str,
        vector_store,
        top_k: int = 10,
        conversation_history: list = None,
        boost_doc_ids: list = None,
        response_mode: int = 3
    ):
        """
        Complete RAG pipeline with STREAMING response.

        Yields:
            dict events: 'search_complete', 'chunk', 'done'
        """
        # Sanitize query
        sanitized_query, warnings = sanitize_query(query)
        if not sanitized_query:
            yield {'type': 'chunk', 'content': "Please provide a valid search query."}
            yield {'type': 'done', 'confidence': 0.0, 'sources': []}
            return

        query = sanitized_query

        # Bound conversation history
        MAX_HISTORY_MESSAGES = 20
        MAX_MESSAGE_LENGTH = 1000

        if conversation_history:
            if len(conversation_history) > MAX_HISTORY_MESSAGES:
                conversation_history = conversation_history[-MAX_HISTORY_MESSAGES:]

            bounded_history = []
            for msg in conversation_history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    content = str(msg.get('content', ''))[:MAX_MESSAGE_LENGTH]
                    bounded_history.append({
                        'role': msg.get('role', 'user'),
                        'content': content
                    })
            conversation_history = bounded_history

        # Search (non-streaming - this is fast)
        search_results = self.enhanced_search(
            query=query,
            tenant_id=tenant_id,
            vector_store=vector_store,
            top_k=top_k,
            boost_doc_ids=boost_doc_ids
        )

        # Send search complete event with sources
        yield {
            'type': 'search_complete',
            'expanded_query': search_results.get('expanded_query', query),
            'num_sources': len(search_results.get('results', [])),
            'sources': search_results.get('results', [])[:10],
            'features_used': search_results.get('features_used', {})
        }

        # Stream the answer
        for event in self.generate_answer_stream(
            query=query,
            search_results=search_results,
            conversation_history=conversation_history or [],
            response_mode=response_mode
        ):
            yield event


# Singleton instance
_enhanced_search_service: Optional[EnhancedSearchService] = None


def get_enhanced_search_service() -> EnhancedSearchService:
    """Get or create singleton EnhancedSearchService"""
    global _enhanced_search_service
    if _enhanced_search_service is None:
        _enhanced_search_service = EnhancedSearchService()
    return _enhanced_search_service
