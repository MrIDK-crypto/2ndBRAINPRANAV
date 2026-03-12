"""
Paper Analysis Service
=======================
Unified orchestrator for analyzing uploaded research papers.

Workflow:
1. Parse document (PDF/DOCX) into text
2. Detect paper type (experimental, review, meta_analysis, case_report, protocol)
3. Run type-specific analysis:
   - Experimental: gap detection, experiment suggestions, feasibility
   - Review: scope assessment, coverage gaps via LLM + OpenAlex
   - Protocol: protocol classification, reference store comparison, pattern check
   - Meta-analysis: methodology critique, heterogeneity assessment
   - Case report: completeness check, differential assessment
4. Search Pinecone for related protocols/papers (when available)
5. Search OpenAlex for literature context
6. Return structured analysis with categorical confidence flags

Existing services reused (not rewritten):
- ResearchGapDetector
- ExperimentSuggestionService
- FeasibilityChecker
- ProtocolClassifier
- ProtocolReferenceStore
- protocol_patterns
- OpenAlexSearchService
- CitationGraphService
"""

import json
import logging
import os
import tempfile
from typing import Dict, Any, Optional, List, Generator

logger = logging.getLogger(__name__)


class PaperAnalysisService:
    """Orchestrates analysis of uploaded research papers."""

    def __init__(self):
        self._openai_client = None
        self._vector_store = None
        self._openalex = None

    # ── Lazy initializers ────────────────────────────────────────────────

    @property
    def openai_client(self):
        if self._openai_client is None:
            try:
                from services.openai_client import get_openai_client
                self._openai_client = get_openai_client()
            except Exception as e:
                logger.warning(f"[PaperAnalysis] OpenAI client unavailable: {e}")
        return self._openai_client

    @property
    def vector_store(self):
        if self._vector_store is None:
            try:
                from vector_stores.pinecone_store import PineconeVectorStore
                self._vector_store = PineconeVectorStore()
            except Exception as e:
                logger.debug(f"[PaperAnalysis] Pinecone unavailable: {e}")
        return self._vector_store

    @property
    def openalex(self):
        if self._openalex is None:
            try:
                from services.openalex_search_service import OpenAlexSearchService
                self._openalex = OpenAlexSearchService()
            except Exception as e:
                logger.debug(f"[PaperAnalysis] OpenAlex unavailable: {e}")
        return self._openalex

    # ── Core analysis (non-streaming) ───────────────────────────────────

    def analyze(self, file_bytes: bytes, filename: str,
                tenant_id: str = None) -> Dict[str, Any]:
        """
        Full paper analysis pipeline (non-streaming).

        Args:
            file_bytes: Raw file content
            filename: Original filename (for extension detection)
            tenant_id: Optional tenant ID for Pinecone search

        Returns:
            Dict with paper_type, analysis sections, related work, etc.
        """
        result = {
            'filename': filename,
            'paper_type': None,
            'type_detection': {},
            'sections': {},
            'related_literature': [],
            'related_protocols': [],
            'gaps': [],
            'suggestions': [],
            'errors': [],
        }

        # Step 1: Parse document
        text, title, parse_meta = self._parse_document(file_bytes, filename)
        if not text:
            result['errors'].append('Failed to parse document. Supported formats: PDF, DOCX.')
            return result
        result['title'] = title or filename
        result['text_length'] = len(text)
        result['parse_metadata'] = parse_meta

        # Step 2: Detect paper type
        from services.paper_type_detector import PaperTypeDetector
        detector = PaperTypeDetector(openai_client=self.openai_client)
        type_result = detector.detect(text, title=title or '')
        result['paper_type'] = type_result['paper_type']
        result['type_detection'] = type_result

        # Step 3: Run type-specific analysis
        paper_type = type_result['paper_type']
        if paper_type == 'experimental':
            result['sections'] = self._analyze_experimental(text, title)
        elif paper_type == 'review':
            result['sections'] = self._analyze_review(text, title)
        elif paper_type == 'meta_analysis':
            result['sections'] = self._analyze_meta_analysis(text, title)
        elif paper_type == 'case_report':
            result['sections'] = self._analyze_case_report(text, title)
        elif paper_type == 'protocol':
            result['sections'] = self._analyze_protocol(text, title)

        # Step 4: Search for related literature (OpenAlex)
        result['related_literature'] = self._search_related_literature(text, title)

        # Step 5: Search for related protocols (Pinecone / reference store)
        result['related_protocols'] = self._search_related_protocols(text, tenant_id)

        # Step 6: Generate experiment suggestions for experimental papers
        if paper_type == 'experimental':
            result['suggestions'] = self._generate_experiment_suggestions(text, title, tenant_id)

        # Step 7: Run gap detection
        result['gaps'] = self._detect_gaps(text, title, paper_type)

        return result

    # ── Streaming analysis (SSE) ────────────────────────────────────────

    def analyze_stream(self, file_bytes: bytes, filename: str,
                       tenant_id: str = None) -> Generator[str, None, None]:
        """
        Streaming paper analysis pipeline. Yields SSE events as analysis progresses.

        Events:
            - event: progress  data: {step, message}
            - event: result    data: {section, data}
            - event: complete  data: {summary}
            - event: error     data: {error}
        """
        def emit(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        try:
            # Step 1: Parse
            yield emit('progress', {'step': 'parsing', 'message': f'Parsing {filename}...'})
            text, title, parse_meta = self._parse_document(file_bytes, filename)
            if not text:
                yield emit('error', {'error': 'Failed to parse document. Supported formats: PDF, DOCX.'})
                return

            yield emit('result', {'section': 'parse_info', 'data': {
                'title': title or filename,
                'text_length': len(text),
                'metadata': parse_meta,
            }})

            # Step 2: Detect type
            yield emit('progress', {'step': 'type_detection', 'message': 'Detecting paper type...'})
            from services.paper_type_detector import PaperTypeDetector
            detector = PaperTypeDetector(openai_client=self.openai_client)
            type_result = detector.detect(text, title=title or '')
            yield emit('result', {'section': 'type_detection', 'data': type_result})

            paper_type = type_result['paper_type']

            # Step 3: Type-specific analysis
            yield emit('progress', {'step': 'analysis',
                                    'message': f'Running {paper_type} analysis...'})
            if paper_type == 'experimental':
                sections = self._analyze_experimental(text, title)
            elif paper_type == 'review':
                sections = self._analyze_review(text, title)
            elif paper_type == 'meta_analysis':
                sections = self._analyze_meta_analysis(text, title)
            elif paper_type == 'case_report':
                sections = self._analyze_case_report(text, title)
            elif paper_type == 'protocol':
                sections = self._analyze_protocol(text, title)
            else:
                sections = self._analyze_experimental(text, title)

            yield emit('result', {'section': 'analysis', 'data': sections})

            # Step 4: Related literature
            yield emit('progress', {'step': 'literature', 'message': 'Searching related literature...'})
            related_lit = self._search_related_literature(text, title)
            yield emit('result', {'section': 'related_literature', 'data': related_lit})

            # Step 5: Related protocols
            yield emit('progress', {'step': 'protocols', 'message': 'Searching related protocols...'})
            related_protocols = self._search_related_protocols(text, tenant_id)
            yield emit('result', {'section': 'related_protocols', 'data': related_protocols})

            # Step 6: Experiment suggestions (experimental papers only)
            if paper_type == 'experimental':
                yield emit('progress', {'step': 'suggestions', 'message': 'Generating experiment suggestions...'})
                suggestions = self._generate_experiment_suggestions(text, title, tenant_id)
                yield emit('result', {'section': 'suggestions', 'data': suggestions})

            # Step 7: Gap detection
            yield emit('progress', {'step': 'gaps', 'message': 'Detecting knowledge gaps...'})
            gaps = self._detect_gaps(text, title, paper_type)
            yield emit('result', {'section': 'gaps', 'data': gaps})

            # Complete
            yield emit('complete', {
                'paper_type': paper_type,
                'title': title or filename,
                'sections_analyzed': list(sections.keys()) if isinstance(sections, dict) else [],
                'related_papers_found': len(related_lit),
                'related_protocols_found': len(related_protocols),
                'gaps_found': len(gaps),
            })

        except Exception as e:
            logger.error(f"[PaperAnalysis] Stream error: {e}", exc_info=True)
            yield emit('error', {'error': str(e)})

    # ── Document parsing ────────────────────────────────────────────────

    def _parse_document(self, file_bytes: bytes, filename: str):
        """Parse uploaded document bytes into text. Returns (text, title, metadata)."""
        ext = ''
        if '.' in filename:
            ext = '.' + filename.rsplit('.', 1)[1].lower()

        if ext not in ('.pdf', '.docx'):
            return None, None, {'error': f'Unsupported format: {ext}'}

        try:
            from parsers.document_parser import DocumentParser
            parser = DocumentParser()

            # Write to temp file for parser
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                result = parser.parse(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            if not result or not result.get('content'):
                return None, None, {'error': 'Parser returned empty content'}

            content = result['content']
            metadata = result.get('metadata', {})

            # Try to extract title from first line or metadata
            title = metadata.get('title', '')
            if not title:
                first_lines = content[:500].split('\n')
                for line in first_lines:
                    line = line.strip()
                    if 10 < len(line) < 200:
                        title = line
                        break

            return content, title, metadata

        except Exception as e:
            logger.error(f"[PaperAnalysis] Document parse failed: {e}")
            return None, None, {'error': str(e)}

    # ── Type-specific analyzers ─────────────────────────────────────────

    def _analyze_experimental(self, text: str, title: str) -> Dict[str, Any]:
        """Analyze an experimental research paper."""
        if not self.openai_client:
            return {'error': 'LLM unavailable for analysis'}

        sample = text[:15000]
        prompt = f"""Analyze this experimental research paper and extract structured information.

PAPER: {title or 'Untitled'}
TEXT:
{sample}

Extract and respond in JSON:
{{
    "summary": "2-3 sentence summary of the paper",
    "research_question": "Main research question or hypothesis",
    "methodology": {{
        "study_design": "e.g., randomized controlled trial, cohort study, in vitro",
        "techniques": ["list of key experimental techniques used"],
        "model_system": "e.g., cell line, animal model, human subjects",
        "sample_size": "if mentioned"
    }},
    "key_findings": ["list of 3-5 main findings"],
    "limitations": ["limitations mentioned or apparent"],
    "statistical_methods": ["statistical tests used"],
    "reproducibility_assessment": {{
        "methods_completeness": "complete|partial|insufficient",
        "data_availability": "available|partial|not_mentioned",
        "reagent_details": "complete|partial|missing",
        "issues": ["specific reproducibility concerns"]
    }}
}}"""

        try:
            result = self._llm_json_call(
                system="You are a research methodology expert analyzing experimental papers.",
                user=prompt,
                max_tokens=2000,
            )
            return result or {'error': 'LLM returned empty response'}
        except Exception as e:
            logger.error(f"[PaperAnalysis] Experimental analysis failed: {e}")
            return {'error': str(e)}

    def _analyze_review(self, text: str, title: str) -> Dict[str, Any]:
        """Analyze a review paper with predictiveness, practical applicability, and author reputation."""
        if not self.openai_client:
            return {'error': 'LLM unavailable for analysis'}

        sample = text[:15000]
        prompt = f"""Analyze this review paper and extract structured information.

PAPER: {title or 'Untitled'}
TEXT:
{sample}

Extract and respond in JSON:
{{
    "summary": "2-3 sentence summary",
    "review_type": "systematic|narrative|scoping|umbrella",
    "scope": {{
        "topic": "main topic reviewed",
        "time_range": "years covered if mentioned",
        "databases_searched": ["databases mentioned"],
        "inclusion_criteria": "if mentioned"
    }},
    "key_themes": ["3-5 main themes or topics covered"],
    "conclusions": [
        {{
            "statement": "the conclusion",
            "type": "predictive|descriptive|prescriptive",
            "evidence_strength": "strong|moderate|weak"
        }}
    ],
    "identified_gaps": ["research gaps identified by the review authors"],
    "coverage_assessment": {{
        "breadth": "comprehensive|moderate|narrow",
        "recency": "up_to_date|somewhat_dated|outdated",
        "bias_concerns": ["potential bias issues noted"]
    }},
    "practical_applicability": {{
        "level": "high|medium|low",
        "actionable_recommendations": ["specific actionable items for researchers or practitioners"],
        "reasoning": "why this review is or is not practically useful"
    }}
}}

For conclusions:
- "predictive" = makes forward-looking claims about what will happen or what should be expected
- "descriptive" = summarizes what has been found without prediction
- "prescriptive" = recommends specific actions or approaches"""

        try:
            result = self._llm_json_call(
                system="You are a literature review expert.",
                user=prompt,
                max_tokens=2500,
            )

            if result and not result.get('error'):
                # Supplement with OpenAlex search for coverage check
                if self.openalex:
                    topic = (result.get('scope', {}).get('topic', '') or
                             result.get('summary', '')[:100])
                    if topic:
                        recent_papers = self.openalex.search_works(
                            topic, max_results=5, from_year=2023, min_citations=10
                        )
                        if recent_papers:
                            result['recent_related_papers'] = [
                                {'title': p['title'], 'year': p['year'],
                                 'cited_by': p['cited_by_count']}
                                for p in recent_papers
                            ]

                # Author reputation lookup via OpenAlex
                result['author_reputation'] = self._lookup_author_reputation(text)

            return result or {'error': 'LLM returned empty response'}
        except Exception as e:
            logger.error(f"[PaperAnalysis] Review analysis failed: {e}")
            return {'error': str(e)}

    def _lookup_author_reputation(self, text: str) -> list:
        """Look up author h-index and citation count from OpenAlex.

        Extracts author names from the first ~500 chars of the paper and
        searches OpenAlex authors API.
        """
        import requests as req

        # Extract potential author names from the beginning of the paper
        # (typically after the title, before the abstract)
        header = text[:1000]
        authors_info = []

        if not self.openai_client:
            return authors_info

        try:
            # Use LLM to extract author names from the header
            resp = self.openai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "Extract author names from this paper header. Return JSON only."},
                    {"role": "user", "content": (
                        f"Extract the first 3 author names from this paper header:\n\n{header}\n\n"
                        'Return JSON: {"authors": ["First Last", "First Last"]}\n'
                        'If no authors found, return {"authors": []}'
                    )},
                ],
                temperature=0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            author_names = json.loads(raw).get("authors", [])[:3]
        except Exception:
            return authors_info

        # Look up each author on OpenAlex
        OPENALEX_EMAIL = "prmogathala@gmail.com"
        headers = {"User-Agent": f"2ndBrain/1.0 (mailto:{OPENALEX_EMAIL})"}

        for name in author_names:
            if not name:
                continue
            try:
                resp = req.get(
                    "https://api.openalex.org/authors",
                    params={
                        "search": name,
                        "per_page": 1,
                        "select": "id,display_name,summary_stats,works_count,cited_by_count,last_known_institutions",
                        "mailto": OPENALEX_EMAIL,
                    },
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                results = resp.json().get("results", [])
                if not results:
                    continue
                author = results[0]
                stats = author.get("summary_stats", {})
                institutions = author.get("last_known_institutions", [])
                inst_name = institutions[0].get("display_name", "") if institutions else ""

                authors_info.append({
                    "name": author.get("display_name", name),
                    "h_index": stats.get("h_index", 0),
                    "cited_by_count": author.get("cited_by_count", 0),
                    "works_count": author.get("works_count", 0),
                    "i10_index": stats.get("i10_index", 0),
                    "institution": inst_name,
                })
            except Exception as e:
                logger.debug(f"[PaperAnalysis] Author lookup failed for '{name}': {e}")
                continue

        return authors_info

    def _analyze_meta_analysis(self, text: str, title: str) -> Dict[str, Any]:
        """Analyze a meta-analysis paper."""
        if not self.openai_client:
            return {'error': 'LLM unavailable for analysis'}

        sample = text[:15000]
        prompt = f"""Analyze this meta-analysis paper and extract structured information.

PAPER: {title or 'Untitled'}
TEXT:
{sample}

Extract and respond in JSON:
{{
    "summary": "2-3 sentence summary",
    "research_question": "main question the meta-analysis addresses",
    "methodology": {{
        "search_strategy": "databases and search approach",
        "study_selection": "inclusion/exclusion criteria",
        "studies_included": "number of studies if mentioned",
        "statistical_model": "fixed|random|mixed effects",
        "heterogeneity_measure": "I-squared or other measure if reported"
    }},
    "main_findings": ["key pooled results"],
    "quality_assessment": {{
        "risk_of_bias_tool": "tool used (e.g., Cochrane, NOS)",
        "publication_bias": "assessed|not_assessed",
        "sensitivity_analyses": "performed|not_mentioned"
    }},
    "limitations": ["limitations noted"],
    "methodological_concerns": ["any issues with the meta-analysis methodology"]
}}"""

        try:
            result = self._llm_json_call(
                system="You are a biostatistician reviewing meta-analyses.",
                user=prompt,
                max_tokens=2000,
            )
            return result or {'error': 'LLM returned empty response'}
        except Exception as e:
            logger.error(f"[PaperAnalysis] Meta-analysis analysis failed: {e}")
            return {'error': str(e)}

    def _analyze_case_report(self, text: str, title: str) -> Dict[str, Any]:
        """Analyze a case report."""
        if not self.openai_client:
            return {'error': 'LLM unavailable for analysis'}

        sample = text[:15000]
        prompt = f"""Analyze this case report and extract structured information.

PAPER: {title or 'Untitled'}
TEXT:
{sample}

Extract and respond in JSON:
{{
    "summary": "2-3 sentence summary of the case",
    "patient_demographics": "age, sex, relevant background if mentioned",
    "presentation": "chief complaint and presenting symptoms",
    "diagnosis": "final diagnosis",
    "treatment": "treatment approach and outcome",
    "key_takeaways": ["clinical lessons from this case"],
    "literature_context": "how authors relate this to existing literature",
    "completeness": {{
        "care_checklist_adherence": "follows_care|partial|not_mentioned",
        "missing_elements": ["any missing standard case report elements"]
    }}
}}"""

        try:
            result = self._llm_json_call(
                system="You are a clinical reviewer analyzing case reports.",
                user=prompt,
                max_tokens=1500,
            )
            return result or {'error': 'LLM returned empty response'}
        except Exception as e:
            logger.error(f"[PaperAnalysis] Case report analysis failed: {e}")
            return {'error': str(e)}

    def _analyze_protocol(self, text: str, title: str) -> Dict[str, Any]:
        """Analyze a protocol paper using existing protocol services."""
        result = {}

        # Use ProtocolClassifier for content classification
        try:
            from services.protocol_classifier import is_protocol_content
            is_protocol, confidence = is_protocol_content(text)
            result['protocol_classification'] = {
                'is_protocol': is_protocol,
                'classifier_confidence': round(confidence, 3),
            }
        except Exception as e:
            logger.debug(f"[PaperAnalysis] Protocol classifier failed: {e}")

        # Use protocol_patterns for heuristic check
        try:
            from services.protocol_patterns import is_protocol_content as heuristic_check
            is_proto_heur, heur_conf = heuristic_check(text)
            result['heuristic_check'] = {
                'is_protocol': is_proto_heur,
                'heuristic_confidence': round(heur_conf, 3),
            }
        except Exception as e:
            logger.debug(f"[PaperAnalysis] Heuristic check failed: {e}")

        # Use ProtocolReferenceStore for comparison
        try:
            from services.protocol_reference_store import get_store
            store = get_store()
            if store and store.protocols:
                similar = store.find_similar_protocols(text[:5000], top_k=5)
                result['similar_protocols'] = similar

                # Find missing steps (reference corpus)
                import re
                steps = re.findall(r'^\s*\d+\.\s+(.+)$', text[:10000], re.MULTILINE)
                if steps:
                    missing = store.find_missing_steps(steps)
                    result['potentially_missing_steps'] = missing
        except Exception as e:
            logger.debug(f"[PaperAnalysis] Reference store failed: {e}")

        # ML-based missing step detection
        try:
            from services.protocol_classifier import detect_missing_steps_in_sequence
            import re
            steps = re.findall(r'^\s*\d+\.\s+(.+)$', text[:10000], re.MULTILINE)
            if len(steps) >= 2:
                step_gaps = detect_missing_steps_in_sequence(steps)
                if step_gaps:
                    result['ml_missing_steps'] = step_gaps
        except Exception as e:
            logger.debug(f"[PaperAnalysis] ML step detection failed: {e}")

        # ML-based completeness scoring
        try:
            from services.protocol_classifier import score_completeness
            completeness = score_completeness(text[:5000])
            result['completeness_score'] = completeness
        except Exception as e:
            logger.debug(f"[PaperAnalysis] Completeness scoring failed: {e}")

        # LLM analysis of protocol structure
        if self.openai_client:
            sample = text[:15000]
            prompt = f"""Analyze this laboratory/clinical protocol and extract structured information.

PROTOCOL: {title or 'Untitled'}
TEXT:
{sample}

Extract and respond in JSON:
{{
    "summary": "1-2 sentence description of what this protocol does",
    "domain": "e.g., molecular biology, cell culture, chemistry, clinical",
    "steps_found": "number of identifiable steps",
    "reagents_mentioned": ["list of key reagents"],
    "equipment_mentioned": ["list of key equipment"],
    "safety_notes": ["any safety warnings"],
    "completeness_issues": ["missing details that would hinder reproduction"],
    "parameters_specified": ["key parameters with values, e.g., '37C for 1 hour'"],
    "parameters_vague": ["vague parameters, e.g., 'incubate briefly'"]
}}"""
            try:
                llm_result = self._llm_json_call(
                    system="You are a lab protocol expert.",
                    user=prompt,
                    max_tokens=1500,
                )
                if llm_result:
                    result['llm_analysis'] = llm_result
            except Exception as e:
                logger.debug(f"[PaperAnalysis] Protocol LLM analysis failed: {e}")

        return result

    # ── Supporting analysis steps ───────────────────────────────────────

    def _search_related_literature(self, text: str, title: str) -> List[Dict]:
        """Search OpenAlex for related papers."""
        if not self.openalex:
            return []

        # Build search query from title + key sentences
        query = title or ''
        if not query:
            # Use first substantive sentence as query
            sentences = text[:2000].split('.')
            for s in sentences:
                s = s.strip()
                if len(s) > 30:
                    query = s[:200]
                    break

        if not query:
            return []

        try:
            results = self.openalex.search_works(query, max_results=10, min_citations=5)
            return results
        except Exception as e:
            logger.debug(f"[PaperAnalysis] OpenAlex search failed: {e}")
            return []

    def _search_related_protocols(self, text: str, tenant_id: str = None) -> List[Dict]:
        """Search for related protocols in Pinecone and reference store."""
        results = []

        # Try reference store first (local, no API needed)
        try:
            from services.protocol_reference_store import get_store
            store = get_store()
            if store and store.protocols:
                similar = store.find_similar_protocols(text[:3000], top_k=5)
                results.extend(similar)
        except Exception as e:
            logger.debug(f"[PaperAnalysis] Reference store search failed: {e}")

        # Try Pinecone protocol-corpus namespace (shared data)
        if self.vector_store and tenant_id:
            try:
                query_embedding = self.vector_store.get_query_embedding(text[:1000])
                pinecone_results = self.vector_store.search_shared_namespace(
                    query_embedding=query_embedding,
                    namespace="protocol-corpus",
                    top_k=5,
                )
                for r in pinecone_results:
                    results.append({
                        'title': r.get('title', ''),
                        'source': 'pinecone',
                        'similarity': r.get('score', 0),
                        'content': r.get('content', '')[:200],
                    })
            except Exception as e:
                logger.debug(f"[PaperAnalysis] Pinecone search failed: {e}")

        return results

    def _generate_experiment_suggestions(self, text: str, title: str,
                                          tenant_id: str = None) -> List[Dict]:
        """Generate follow-up experiment suggestions for experimental papers."""
        try:
            from services.experiment_suggestion_service import ExperimentSuggestionService
            from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

            client = get_azure_client()
            service = ExperimentSuggestionService(client, AZURE_CHAT_DEPLOYMENT)

            # Build protocol context from reference store
            protocol_context = ''
            try:
                from services.protocol_reference_store import get_store
                store = get_store()
                if store and store.protocols:
                    similar = store.find_similar_protocols(text[:3000], top_k=3)
                    if similar:
                        protocol_lines = []
                        for p in similar:
                            protocol_lines.append(
                                f"[Protocol: {p.get('title', 'Untitled')}] "
                                f"Domain: {p.get('domain', 'unknown')}, "
                                f"Steps: {p.get('num_steps', '?')}"
                            )
                        protocol_context = '\n'.join(protocol_lines)
            except Exception:
                pass

            # Extract research question from text
            research_question = f"Based on the paper '{title or 'Untitled'}', suggest follow-up experiments."

            suggestions = service.suggest_experiments(
                research_question=research_question,
                paper_context=text[:8000],
                protocol_context=protocol_context or None,
            )
            return suggestions
        except Exception as e:
            logger.warning(f"[PaperAnalysis] Experiment suggestion failed: {e}")
            return []

    def _detect_gaps(self, text: str, title: str, paper_type: str) -> List[Dict]:
        """Detect knowledge gaps using ResearchGapDetector."""
        try:
            from services.research_gap_detector import ResearchGapDetector

            detector = ResearchGapDetector()
            detector.add_document(
                doc_id='uploaded_paper',
                title=title or 'Uploaded Paper',
                content=text,
                doc_type='paper' if paper_type in ('experimental', 'review', 'meta_analysis') else paper_type,
            )

            result = detector.analyze()
            gaps = result.get('gaps', [])

            # Limit to top 10 gaps
            return gaps[:10]
        except Exception as e:
            logger.warning(f"[PaperAnalysis] Gap detection failed: {e}")
            return []

    # ── LLM helper ──────────────────────────────────────────────────────

    def _llm_json_call(self, system: str, user: str,
                       max_tokens: int = 2000) -> Optional[Dict]:
        """Make an LLM call expecting JSON response."""
        if not self.openai_client:
            return None

        try:
            if hasattr(self.openai_client, 'chat_completion'):
                response = self.openai_client.chat_completion(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
            else:
                chat_deployment = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")
                response = self.openai_client.chat.completions.create(
                    model=chat_deployment,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"[PaperAnalysis] LLM returned invalid JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"[PaperAnalysis] LLM call failed: {e}")
            return None


# Singleton
_service_instance = None


def get_paper_analysis_service() -> PaperAnalysisService:
    """Get or create the paper analysis service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PaperAnalysisService()
    return _service_instance
