"""
Protocol Optimizer Service
Analyzes protocols against user context and suggests optimizations.
Uses protocol corpus, PubMed/OpenAlex literature, and failed experiments database.
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator

import requests

from services.openai_client import get_openai_client_with_timeout
from services.protocol_patterns import is_protocol_content, PROTOCOL_MISSING_PATTERNS


# PubMed E-utilities
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
PUBMED_RATE_DELAY = 0.1 if PUBMED_API_KEY else 0.34

# OpenAlex
OPENALEX_API_URL = "https://api.openalex.org"
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "research@2ndbrain.com")


def _sse(event: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ProtocolOptimizerService:
    """
    Analyzes protocols and suggests context-specific optimizations.

    Flow:
    1. Parse user context (organism, tissue, technique, issue)
    2. Parse protocol into structured steps
    3. Identify context mismatches (protocol designed for X, user has Y)
    4. Search corpus for protocols matching user's context
    5. Search literature (PubMed/OpenAlex) for optimizations
    6. Check failed experiments database
    7. Generate optimization suggestions with evidence
    8. Calculate reproducibility score
    """

    def __init__(self):
        # Use client with extended timeout for Protocol Optimizer's multiple sequential API calls
        self.openai = get_openai_client_with_timeout(timeout=120.0)

    # =========================================================================
    # MAIN ANALYSIS (STREAMING)
    # =========================================================================

    def analyze_protocol_stream(self, context: str, protocol_text: str, db=None) -> Generator[str, None, None]:
        """
        Main entry point - analyzes protocol and streams results.

        Args:
            context: User's description of their context and issues
            protocol_text: The protocol to analyze (text or parsed from file)
            db: Database session for corpus/failed experiments lookup

        Yields:
            SSE events with analysis progress and results
        """
        start_time = time.time()

        try:
            # ── Step 1: Parse Context ──────────────────────────────────────
            print(f"[ProtocolOptimizer] Starting Step 1 - Parse Context", flush=True)
            yield _sse("progress", {"step": 1, "message": "Analyzing your context...", "percent": 5})

            step1_start = time.time()
            user_context = self._parse_user_context(context)
            print(f"[ProtocolOptimizer] Step 1 completed in {time.time() - step1_start:.1f}s", flush=True)

            yield _sse("context_parsed", {
                "user_context": user_context,
                "message": f"Detected: {user_context.get('organism', 'Unknown organism')}, {user_context.get('technique', 'Unknown technique')}"
            })

            # ── Step 2: Parse Protocol ─────────────────────────────────────
            print(f"[ProtocolOptimizer] Starting Step 2 - Parse Protocol", flush=True)
            yield _sse("progress", {"step": 2, "message": "Parsing protocol steps...", "percent": 15})

            step2_start = time.time()
            protocol_data = self._parse_protocol(protocol_text)
            print(f"[ProtocolOptimizer] Step 2 completed in {time.time() - step2_start:.1f}s", flush=True)
            steps = protocol_data.get("steps", [])
            protocol_context = protocol_data.get("designed_for", {})

            yield _sse("protocol_parsed", {
                "num_steps": len(steps),
                "designed_for": protocol_context,
                "reagents_found": len(protocol_data.get("reagents", [])),
                "equipment_found": len(protocol_data.get("equipment", []))
            })

            # ── Step 3: Detect Context Mismatch ────────────────────────────
            yield _sse("progress", {"step": 3, "message": "Checking context compatibility...", "percent": 25})

            mismatches = self._detect_context_mismatch(user_context, protocol_context, steps)

            yield _sse("mismatch_detected", {
                "has_mismatch": len(mismatches) > 0,
                "mismatches": mismatches,
                "message": f"Found {len(mismatches)} potential context issues"
            })

            # ── Step 4: Search Protocol Corpus ─────────────────────────────
            yield _sse("progress", {"step": 4, "message": "Searching protocol corpus...", "percent": 35})

            corpus_results = self._search_protocol_corpus(user_context, protocol_data, db)

            yield _sse("corpus_searched", {
                "protocols_found": len(corpus_results.get("matching_protocols", [])),
                "typical_parameters": corpus_results.get("typical_parameters", {}),
                "corpus_stats": corpus_results.get("stats", {})
            })

            # ── Step 5: Search Literature ──────────────────────────────────
            yield _sse("progress", {"step": 5, "message": "Searching PubMed & OpenAlex...", "percent": 50})

            literature_results = self._search_literature(user_context, protocol_data)

            yield _sse("literature_searched", {
                "pubmed_papers": len(literature_results.get("pubmed", [])),
                "openalex_papers": len(literature_results.get("openalex", [])),
                "key_findings": literature_results.get("key_findings", [])
            })

            # ── Step 6: Check Failed Experiments ───────────────────────────
            yield _sse("progress", {"step": 6, "message": "Checking failed experiments database...", "percent": 60})

            failed_experiments = self._search_failed_experiments(user_context, protocol_data, db)

            yield _sse("failures_checked", {
                "related_failures": len(failed_experiments),
                "failures": failed_experiments[:5]  # Top 5
            })

            # ── Step 7: Generate Optimization Suggestions ──────────────────
            print(f"[ProtocolOptimizer] Starting Step 7 - Generate Suggestions", flush=True)
            step7_start = time.time()
            yield _sse("progress", {"step": 7, "message": "Generating optimization suggestions...", "percent": 75})

            # Combine all evidence
            all_evidence = {
                "user_context": user_context,
                "protocol_context": protocol_context,
                "mismatches": mismatches,
                "corpus_results": corpus_results,
                "literature": literature_results,
                "failed_experiments": failed_experiments
            }

            issues = self._generate_issues_and_optimizations(
                steps, all_evidence, protocol_text
            )

            # Sort issues by risk level: high → medium → low
            risk_order = {"high": 0, "medium": 1, "low": 2}
            issues = sorted(issues, key=lambda x: risk_order.get(x.get("risk_level", "low"), 3))

            yield _sse("issues_generated", {
                "num_issues": len(issues),
                "high_risk": len([i for i in issues if i.get("risk_level") == "high"]),
                "medium_risk": len([i for i in issues if i.get("risk_level") == "medium"]),
                "low_risk": len([i for i in issues if i.get("risk_level") == "low"])
            })

            # ── Step 8: Calculate Reproducibility Score ────────────────────
            yield _sse("progress", {"step": 8, "message": "Calculating reproducibility score...", "percent": 85})

            scores = self._calculate_reproducibility_score(
                steps, issues, all_evidence
            )

            yield _sse("score_calculated", {
                "current_score": scores["current"],
                "potential_score": scores["after_optimization"],
                "breakdown": scores["breakdown"]
            })

            # ── Step 9: Generate Optimized Protocol ────────────────────────
            yield _sse("progress", {"step": 9, "message": "Generating optimized protocol...", "percent": 95})

            optimized_protocol = self._generate_optimized_protocol(
                protocol_text, steps, issues
            )

            # ── Final Results ──────────────────────────────────────────────
            elapsed = time.time() - start_time

            yield _sse("complete", {
                "success": True,
                "elapsed_seconds": round(elapsed, 2),
                "user_context": user_context,
                "protocol_context": protocol_context,
                "issues": issues,
                "reproducibility_score": scores["current"],
                "reproducibility_score_after": scores["after_optimization"],
                "score_breakdown": scores["breakdown"],
                "corpus_evidence": {
                    "matching_protocols": len(corpus_results.get("matching_protocols", [])),
                    "typical_parameters": corpus_results.get("typical_parameters", {})
                },
                "literature_evidence": {
                    "papers_found": len(literature_results.get("pubmed", [])) + len(literature_results.get("openalex", [])),
                    "key_papers": literature_results.get("pubmed", [])[:3] + literature_results.get("openalex", [])[:2]
                },
                "failed_experiments": failed_experiments[:3],
                "optimized_protocol": optimized_protocol
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})

    # =========================================================================
    # CONTEXT PARSING
    # =========================================================================

    def _parse_user_context(self, context: str) -> Dict:
        """Extract structured context from user's description."""
        try:
            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": """Extract the experimental context from the user's description.
Return JSON:
{
    "organism": "species name or null",
    "organism_type": "plant|animal|bacteria|yeast|cell_line|other",
    "tissue": "tissue type or null",
    "cell_type": "cell type or null",
    "developmental_stage": "stage or null",
    "technique": "main technique (e.g., immunofluorescence, western blot, PCR)",
    "specific_target": "what they're trying to detect/measure (e.g., Sox2 protein)",
    "issue_reported": "what problem they're having (e.g., high background, no signal)",
    "equipment_mentioned": ["list of equipment mentioned"],
    "constraints": ["any constraints mentioned"]
}
Return ONLY valid JSON."""},
                    {"role": "user", "content": context}
                ],
                temperature=0.1,
                max_tokens=500
            )

            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            print(f"[ProtocolOptimizer] Context parsing failed: {e}")
            return {
                "organism": None,
                "technique": None,
                "issue_reported": context[:200]
            }

    # =========================================================================
    # PROTOCOL PARSING
    # =========================================================================

    def _parse_protocol(self, protocol_text: str) -> Dict:
        """Parse protocol into structured steps with parameters."""
        try:
            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": """Parse this scientific protocol into structured format.
Return JSON:
{
    "designed_for": {
        "organism": "what organism/system this was designed for (if detectable)",
        "tissue": "tissue type if mentioned",
        "technique": "main technique"
    },
    "steps": [
        {
            "number": 1,
            "action": "the action (e.g., Fix tissue)",
            "full_text": "complete step text",
            "parameters": {
                "reagent": "reagent name",
                "concentration": "concentration if specified",
                "duration": "time if specified",
                "temperature": "temperature if specified",
                "other": "other parameters"
            },
            "is_critical": true/false,
            "context_sensitive": true/false
        }
    ],
    "reagents": ["list of all reagents mentioned"],
    "equipment": ["list of equipment mentioned"],
    "total_time_estimate": "estimated total time"
}
Mark steps as context_sensitive if they involve:
- Fixation (different tissues need different times)
- Permeabilization (cell walls vs membranes)
- Antibody dilutions (varies by target)
- Incubation times (varies by sample thickness)
- Staining (dyes that work differently in different systems)

Return ONLY valid JSON."""},
                    {"role": "user", "content": protocol_text[:10000]}  # Cap length
                ],
                temperature=0.1,
                max_tokens=2500
            )

            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            print(f"[ProtocolOptimizer] Protocol parsing failed: {e}")
            # Fallback: simple line-based parsing
            lines = protocol_text.strip().split("\n")
            steps = []
            for i, line in enumerate(lines):
                if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("-")):
                    steps.append({
                        "number": i + 1,
                        "action": line.strip(),
                        "full_text": line.strip(),
                        "parameters": {},
                        "context_sensitive": False
                    })
            return {"steps": steps, "designed_for": {}, "reagents": [], "equipment": []}

    # =========================================================================
    # CONTEXT MISMATCH DETECTION
    # =========================================================================

    def _detect_context_mismatch(self, user_context: Dict, protocol_context: Dict, steps: List) -> List[Dict]:
        """Detect mismatches between user context and protocol design."""
        mismatches = []

        # Organism type mismatch
        user_org_type = user_context.get("organism_type", "").lower()
        protocol_org = (protocol_context.get("organism") or "").lower()

        # Common mismatches
        mismatch_pairs = [
            (["plant", "arabidopsis", "tobacco", "rice", "maize"], ["mammal", "mouse", "human", "hela", "hek"]),
            (["bacteria", "e.coli", "bacterial"], ["mammal", "mouse", "human", "eukaryot"]),
            (["yeast", "saccharomyces", "s.cerevisiae"], ["mammal", "mouse", "human"]),
            (["zebrafish", "danio"], ["mouse", "mammal", "human"]),
            (["drosophila", "fly"], ["mammal", "mouse", "human", "vertebrate"]),
            (["c.elegans", "worm", "nematode"], ["mammal", "mouse", "vertebrate"]),
        ]

        user_org = (user_context.get("organism") or "").lower()

        for group1, group2 in mismatch_pairs:
            user_in_g1 = any(term in user_org or term in user_org_type for term in group1)
            protocol_in_g2 = any(term in protocol_org for term in group2)

            if user_in_g1 and protocol_in_g2:
                mismatches.append({
                    "type": "organism_mismatch",
                    "severity": "high",
                    "user_context": user_context.get("organism") or user_org_type,
                    "protocol_context": protocol_context.get("organism"),
                    "message": f"Protocol designed for {protocol_context.get('organism', 'different organism')}, but you're working with {user_context.get('organism', user_org_type)}"
                })
                break

            user_in_g2 = any(term in user_org or term in user_org_type for term in group2)
            protocol_in_g1 = any(term in protocol_org for term in group1)

            if user_in_g2 and protocol_in_g1:
                mismatches.append({
                    "type": "organism_mismatch",
                    "severity": "high",
                    "user_context": user_context.get("organism") or user_org_type,
                    "protocol_context": protocol_context.get("organism"),
                    "message": f"Protocol designed for {protocol_context.get('organism', 'different organism')}, but you're working with {user_context.get('organism', user_org_type)}"
                })
                break

        # Tissue type mismatch (whole mount vs sections, etc.)
        user_tissue = (user_context.get("tissue") or "").lower()
        protocol_tissue = (protocol_context.get("tissue") or "").lower()

        if "embryo" in user_tissue or "whole" in user_tissue:
            if "section" in protocol_tissue or "slice" in protocol_tissue:
                mismatches.append({
                    "type": "sample_type_mismatch",
                    "severity": "medium",
                    "user_context": user_tissue,
                    "protocol_context": protocol_tissue,
                    "message": "Protocol designed for tissue sections, but you're working with whole-mount samples"
                })

        return mismatches

    # =========================================================================
    # CORPUS SEARCH
    # =========================================================================

    def _search_protocol_corpus(self, user_context: Dict, protocol_data: Dict, db) -> Dict:
        """Search protocol corpus for matching protocols."""
        results = {
            "matching_protocols": [],
            "typical_parameters": {},
            "stats": {}
        }

        if not db:
            return results

        try:
            from database.models import ProtocolEntity, ProtocolCooccurrence
            from sqlalchemy import func, or_

            organism = user_context.get("organism", "")
            technique = user_context.get("technique", "")

            # Search for protocols with this organism + technique combo
            if organism:
                # Check co-occurrence table
                coocs = db.query(ProtocolCooccurrence).join(
                    ProtocolEntity,
                    ProtocolCooccurrence.technique_entity_id == ProtocolEntity.id
                ).filter(
                    ProtocolEntity.normalized_name.ilike(f"%{technique.lower()}%") if technique else True
                ).limit(50).all()

                results["stats"]["cooccurrence_count"] = len(coocs)

                # Get typical parameters from corpus
                if coocs:
                    results["matching_protocols"] = [
                        {
                            "technique": c.technique.name if c.technique else "",
                            "target": c.target.name if c.target else "",
                            "count": c.cooccurrence_count,
                            "confidence": c.confidence
                        }
                        for c in coocs[:10]
                    ]

            # Search for reagent alternatives
            reagents = protocol_data.get("reagents", [])
            for reagent in reagents[:5]:
                reagent_lower = reagent.lower()

                # Find entities matching this reagent
                entities = db.query(ProtocolEntity).filter(
                    ProtocolEntity.normalized_name.ilike(f"%{reagent_lower}%"),
                    ProtocolEntity.entity_type == "reagent"
                ).limit(10).all()

                if entities:
                    results["typical_parameters"][reagent] = {
                        "found_in_corpus": len(entities),
                        "typical_attributes": [e.attributes for e in entities if e.attributes][:3]
                    }

        except Exception as e:
            print(f"[ProtocolOptimizer] Corpus search failed: {e}")

        return results

    # =========================================================================
    # LITERATURE SEARCH
    # =========================================================================

    def _search_literature(self, user_context: Dict, protocol_data: Dict) -> Dict:
        """Search PubMed and OpenAlex for relevant papers."""
        results = {
            "pubmed": [],
            "openalex": [],
            "key_findings": []
        }

        # Build search query
        organism = user_context.get("organism", "")
        technique = user_context.get("technique", "")
        issue = user_context.get("issue_reported", "")

        if not (organism or technique):
            return results

        # PubMed search
        try:
            query_parts = []
            if organism:
                query_parts.append(organism)
            if technique:
                query_parts.append(technique)
            if "protocol" not in " ".join(query_parts).lower():
                query_parts.append("protocol OR method")

            query = " AND ".join(query_parts)

            time.sleep(PUBMED_RATE_DELAY)
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": 10,
                "retmode": "json",
                "sort": "relevance"
            }
            if PUBMED_API_KEY:
                params["api_key"] = PUBMED_API_KEY

            resp = requests.get(PUBMED_ESEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            pmids = resp.json().get("esearchresult", {}).get("idlist", [])

            if pmids:
                time.sleep(PUBMED_RATE_DELAY)
                fetch_resp = requests.get(PUBMED_EFETCH_URL, params={
                    "db": "pubmed",
                    "id": ",".join(pmids[:8]),
                    "retmode": "xml",
                    "rettype": "abstract",
                    **({"api_key": PUBMED_API_KEY} if PUBMED_API_KEY else {})
                }, timeout=30)
                fetch_resp.raise_for_status()

                results["pubmed"] = self._parse_pubmed_xml(fetch_resp.text)
        except Exception as e:
            print(f"[ProtocolOptimizer] PubMed search failed: {e}")

        # OpenAlex search
        try:
            search_query = f"{organism} {technique}".strip()
            if search_query:
                resp = requests.get(
                    f"{OPENALEX_API_URL}/works",
                    params={
                        "search": search_query,
                        "filter": "type:article",
                        "per_page": 10,
                        "mailto": OPENALEX_EMAIL
                    },
                    timeout=15
                )
                resp.raise_for_status()
                data = resp.json()

                for work in data.get("results", [])[:8]:
                    results["openalex"].append({
                        "title": work.get("title", ""),
                        "year": work.get("publication_year"),
                        "doi": work.get("doi"),
                        "url": work.get("id"),
                        "cited_by_count": work.get("cited_by_count", 0),
                        "abstract": " ".join(list((work.get("abstract_inverted_index") or {}).keys())[:100]) if work.get("abstract_inverted_index") else None
                    })
        except Exception as e:
            print(f"[ProtocolOptimizer] OpenAlex search failed: {e}")

        return results

    def _parse_pubmed_xml(self, xml_text: str) -> List[Dict]:
        """Parse PubMed XML into simple dicts."""
        import xml.etree.ElementTree as ET
        papers = []
        try:
            root = ET.fromstring(xml_text)
            for article in root.findall(".//PubmedArticle"):
                try:
                    pmid_elem = article.find(".//PMID")
                    pmid = pmid_elem.text if pmid_elem is not None else None
                    if not pmid:
                        continue

                    title_elem = article.find(".//ArticleTitle")
                    title = title_elem.text if title_elem is not None else "Untitled"

                    abstract_parts = []
                    for at in article.findall(".//AbstractText"):
                        label = at.get("Label", "")
                        text = at.text or ""
                        abstract_parts.append(f"{label}: {text}" if label else text)
                    abstract = " ".join(abstract_parts)

                    journal_elem = article.find(".//Journal/Title")
                    journal = journal_elem.text if journal_elem is not None else ""

                    year_elem = article.find(".//PubDate/Year")
                    year = year_elem.text if year_elem is not None else ""

                    papers.append({
                        "pmid": pmid,
                        "title": title,
                        "abstract": abstract[:500],
                        "journal": journal,
                        "year": year,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"[ProtocolOptimizer] PubMed XML parse error: {e}")
        return papers

    # =========================================================================
    # FAILED EXPERIMENTS SEARCH
    # =========================================================================

    def _search_failed_experiments(self, user_context: Dict, protocol_data: Dict, db) -> List[Dict]:
        """Search failed experiments database for relevant warnings."""
        if not db:
            return []

        try:
            from database.models import FailedExperiment
            from sqlalchemy import or_

            organism = user_context.get("organism", "")
            technique = user_context.get("technique", "")
            reagents = protocol_data.get("reagents", [])

            # Build search terms
            search_terms = []
            if organism:
                search_terms.append(organism)
            if technique:
                search_terms.append(technique)
            search_terms.extend(reagents[:3])

            if not search_terms:
                return []

            # Search
            filters = []
            for term in search_terms:
                if term and len(term) > 2:
                    filters.append(FailedExperiment.title.ilike(f"%{term}%"))
                    filters.append(FailedExperiment.hypothesis.ilike(f"%{term}%"))
                    filters.append(FailedExperiment.what_failed.ilike(f"%{term}%"))
                    filters.append(FailedExperiment.methodology.ilike(f"%{term}%"))

            if not filters:
                return []

            experiments = db.query(FailedExperiment).filter(
                or_(*filters)
            ).order_by(FailedExperiment.upvotes.desc()).limit(10).all()

            return [
                {
                    "title": e.title,
                    "what_failed": e.what_failed,
                    "why_failed": e.why_failed,
                    "lessons_learned": e.lessons_learned,
                    "field": e.field,
                    "upvotes": e.upvotes
                }
                for e in experiments
            ]
        except Exception as e:
            print(f"[ProtocolOptimizer] Failed experiments search error: {e}")
            return []

    # =========================================================================
    # ISSUE & OPTIMIZATION GENERATION
    # =========================================================================

    def _generate_issues_and_optimizations(self, steps: List, evidence: Dict, protocol_text: str) -> List[Dict]:
        """Generate issues and optimization suggestions using LLM + evidence."""
        try:
            # Build evidence summary for LLM
            evidence_text = self._format_evidence_for_llm(evidence)

            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": """You are a protocol optimization expert. Analyze this protocol against the user's context and evidence.

For each problematic step, generate an issue with:
- Risk level (high/medium/low)
- Clear explanation of the problem
- Specific optimization suggestion with exact parameters
- Evidence supporting the suggestion

Focus on:
1. Steps that won't work in the user's context (organism mismatch, etc.)
2. Reagents that have better alternatives for the user's system
3. Parameters (concentrations, times, temperatures) that need adjustment
4. Missing steps that are needed for the user's context

Return JSON:
{
    "issues": [
        {
            "step_number": 1,
            "step_text": "original step text",
            "risk_level": "high|medium|low",
            "issue_type": "reagent_incompatible|parameter_wrong|step_missing|technique_mismatch",
            "problem": "Clear explanation of why this won't work",
            "explanation": "Detailed scientific explanation",
            "corpus_evidence": {
                "matching_protocols_found": 5,
                "typical_value_in_corpus": "what similar protocols use"
            },
            "literature_evidence": [
                {"title": "Paper title", "url": "https://pubmed.ncbi.nlm.nih.gov/12345/", "finding": "What the paper says"}
            ],
            "failed_experiment_warning": "relevant failure if any",
            "suggested_optimization": "Exact change to make",
            "alternative_reagents": ["list of alternatives if applicable"],
            "confidence": 0.85
        }
    ],
    "general_recommendations": [
        "Overall recommendations not tied to specific steps"
    ]
}

Be specific with numbers (concentrations, times). Cite evidence."""},
                    {"role": "user", "content": f"""USER CONTEXT:
{json.dumps(evidence.get('user_context', {}), indent=2)}

PROTOCOL DESIGNED FOR:
{json.dumps(evidence.get('protocol_context', {}), indent=2)}

CONTEXT MISMATCHES DETECTED:
{json.dumps(evidence.get('mismatches', []), indent=2)}

PROTOCOL STEPS:
{json.dumps(steps, indent=2)}

{evidence_text}

Analyze each step and identify issues. Be specific about what to change and why."""}
                ],
                temperature=0.2,
                max_tokens=3000
            )

            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(text)
            return result.get("issues", [])

        except Exception as e:
            print(f"[ProtocolOptimizer] Issue generation failed: {e}")
            return []

    def _format_evidence_for_llm(self, evidence: Dict) -> str:
        """Format evidence for LLM context."""
        parts = []

        # Corpus evidence
        corpus = evidence.get("corpus_results", {})
        if corpus.get("matching_protocols"):
            parts.append("CORPUS EVIDENCE:")
            for p in corpus["matching_protocols"][:5]:
                parts.append(f"  - {p.get('technique', 'Unknown')}: {p.get('count', 0)} occurrences")
            if corpus.get("typical_parameters"):
                parts.append("  Typical parameters from corpus:")
                for reagent, data in list(corpus["typical_parameters"].items())[:3]:
                    parts.append(f"    {reagent}: {data}")

        # Literature evidence - include URLs for citation linking
        literature = evidence.get("literature", {})
        pubmed = literature.get("pubmed", [])
        if pubmed:
            parts.append("\nLITERATURE EVIDENCE (PubMed) - USE THESE EXACT URLs IN YOUR RESPONSE:")
            for paper in pubmed[:5]:
                url = paper.get('url', '')
                parts.append(f"  - Title: {paper.get('title', 'Unknown')}")
                parts.append(f"    Year: {paper.get('year', 'N/A')}")
                parts.append(f"    URL: {url}")
                if paper.get("abstract"):
                    parts.append(f"    Abstract: {paper['abstract'][:200]}...")

        openalex = literature.get("openalex", [])
        if openalex:
            parts.append("\nLITERATURE EVIDENCE (OpenAlex) - USE THESE EXACT URLs IN YOUR RESPONSE:")
            for paper in openalex[:3]:
                url = paper.get('url', '') or paper.get('doi', '')
                if url and not url.startswith('http'):
                    url = f"https://doi.org/{url}" if url.startswith('10.') else url
                parts.append(f"  - Title: {paper.get('title', 'Unknown')}")
                parts.append(f"    Year: {paper.get('year', 'N/A')}, Citations: {paper.get('cited_by_count', 0)}")
                parts.append(f"    URL: {url}")

        # Failed experiments
        failures = evidence.get("failed_experiments", [])
        if failures:
            parts.append("\nFAILED EXPERIMENTS:")
            for f in failures[:3]:
                parts.append(f"  - {f.get('title', 'Unknown')}")
                parts.append(f"    What failed: {f.get('what_failed', 'N/A')}")
                parts.append(f"    Lesson: {f.get('lessons_learned', 'N/A')}")

        return "\n".join(parts)

    # =========================================================================
    # REPRODUCIBILITY SCORING
    # =========================================================================

    def _calculate_reproducibility_score(self, steps: List, issues: List, evidence: Dict) -> Dict:
        """Calculate reproducibility score before and after optimization.

        Uses capped penalties to prevent extreme score drops and realistic
        improvement estimates for after-optimization scores.
        """
        # Base score
        base_score = 100

        # Deductions with caps per category
        breakdown = {
            "context_mismatch": 0,
            "high_risk_issues": 0,
            "medium_risk_issues": 0,
            "low_risk_issues": 0,
            "missing_parameters": 0,
            "no_corpus_support": 0
        }

        # Context mismatch penalty (capped at 15)
        mismatches = evidence.get("mismatches", [])
        mismatch_penalty = 0
        for m in mismatches:
            if m.get("severity") == "high":
                mismatch_penalty += 8
            elif m.get("severity") == "medium":
                mismatch_penalty += 4
        breakdown["context_mismatch"] = min(15, mismatch_penalty)

        # Issue penalties with diminishing returns and caps
        high_count = sum(1 for i in issues if i.get("risk_level") == "high")
        medium_count = sum(1 for i in issues if i.get("risk_level") == "medium")
        low_count = sum(1 for i in issues if i.get("risk_level") not in ["high", "medium"])

        # High risk: 8 points for first, 5 for second, 3 for rest (cap at 20)
        high_penalty = min(8, high_count) * 3 + min(2, max(0, high_count - 1)) * 2
        breakdown["high_risk_issues"] = min(20, high_penalty)

        # Medium risk: 4 points each (cap at 12)
        breakdown["medium_risk_issues"] = min(12, medium_count * 4)

        # Low risk: 2 points each (cap at 6)
        breakdown["low_risk_issues"] = min(6, low_count * 2)

        # Corpus support penalty (reduced)
        corpus = evidence.get("corpus_results", {})
        if corpus.get("stats", {}).get("cooccurrence_count", 0) < 5:
            breakdown["no_corpus_support"] = 5

        # Calculate current score (minimum 25 to avoid discouraging scores)
        total_deduction = sum(breakdown.values())
        current_score = max(25, base_score - total_deduction)

        # Realistic improvement estimate:
        # - Can fix ~50% of issue-related penalties through optimization
        # - Context mismatch can be partially mitigated (~30%)
        # - Max improvement capped at 15 points to be realistic
        fixable_penalty = breakdown["high_risk_issues"] + breakdown["medium_risk_issues"]
        potential_recovery = min(15, fixable_penalty * 0.5 + breakdown["context_mismatch"] * 0.3)
        after_score = min(95, current_score + potential_recovery)  # Cap at 95, not 100

        return {
            "current": round(current_score),
            "after_optimization": round(after_score),
            "breakdown": breakdown
        }

    # =========================================================================
    # OPTIMIZED PROTOCOL GENERATION
    # =========================================================================

    def _generate_optimized_protocol(self, original_protocol: str, steps: List, issues: List) -> str:
        """Generate the optimized protocol with suggested changes applied."""
        try:
            # Build issue map by step
            issue_map = {}
            for issue in issues:
                step_num = issue.get("step_number")
                if step_num:
                    if step_num not in issue_map:
                        issue_map[step_num] = []
                    issue_map[step_num].append(issue)

            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": """Generate an optimized version of this protocol with the suggested changes applied.

For each changed step:
1. Show the optimized step text
2. Add a brief inline note explaining the change

Format:
```
OPTIMIZED PROTOCOL

1. [Original or modified step text]
   💡 Note: [Brief explanation if modified]

2. [Next step]
...
```

Keep the same structure but apply all the optimizations. Add any missing steps that were suggested."""},
                    {"role": "user", "content": f"""ORIGINAL PROTOCOL:
{original_protocol}

ISSUES AND OPTIMIZATIONS:
{json.dumps(issues, indent=2)}

Generate the optimized protocol with all changes applied."""}
                ],
                temperature=0.2,
                max_tokens=2000
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[ProtocolOptimizer] Optimized protocol generation failed: {e}")
            return original_protocol


# Singleton
_protocol_optimizer_service = None


def get_protocol_optimizer_service() -> ProtocolOptimizerService:
    """Get or create singleton ProtocolOptimizerService."""
    global _protocol_optimizer_service
    if _protocol_optimizer_service is None:
        _protocol_optimizer_service = ProtocolOptimizerService()
    return _protocol_optimizer_service
