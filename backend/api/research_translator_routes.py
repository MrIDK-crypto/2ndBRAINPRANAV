"""
Research Translator — Blueprint for app_v2.py
Endpoints under /api/co-researcher:
  POST /analyze              — Upload "my research" + "papers I read", starts pipeline
  POST /analyze-with-context — Context-aware version using lab profile
  GET  /stream/<id>          — SSE event stream
  POST /chat/<id>            — Interactive refinement chat
"""

import uuid
import json
import threading
import re
import tempfile
from queue import Queue, Empty
from urllib.parse import urlparse
from typing import Optional, Dict, List, Any

import requests
from flask import Blueprint, request, jsonify, Response, g, current_app

from co_researcher.parser import parse_document
from co_researcher.decomposer import extract_context, decompose_layers
from co_researcher.translator import translate_insight
from co_researcher.adversarial import run_adversarial
from co_researcher.chat import build_chat_context, handle_chat_message

# Optional imports for context-aware features
try:
    from services.lab_profile_service import get_lab_profile_service, LabProfile
    from vector_stores.pinecone_store import get_pinecone_store
    from services.auth_service import AuthService
    LAB_PROFILE_AVAILABLE = True
except ImportError:
    LAB_PROFILE_AVAILABLE = False
    print("[ResearchTranslator] Lab profile service not available - context features disabled")

try:
    from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False


def fetch_paper_from_url(url: str) -> tuple[bytes, str]:
    """
    Fetch a paper from a URL (DOI, arXiv, or direct PDF link).
    Returns (file_bytes, filename) or raises an exception.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; 2ndBrain/1.0; +https://use2ndbrain.com)'
    }

    # Handle DOI URLs - resolve to actual paper URL
    if 'doi.org' in url:
        # Try to get PDF from DOI
        try:
            resp = requests.get(url, headers=headers, allow_redirects=True, timeout=30)
            # Check if we got a PDF directly
            if resp.headers.get('content-type', '').startswith('application/pdf'):
                doi_part = url.split('doi.org/')[-1].replace('/', '_')
                return resp.content, f"doi_{doi_part}.pdf"
            # Otherwise try unpaywall or direct publisher
            doi = url.split('doi.org/')[-1]
            unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email=support@use2ndbrain.com"
            unpaywall_resp = requests.get(unpaywall_url, timeout=15)
            if unpaywall_resp.ok:
                data = unpaywall_resp.json()
                if data.get('best_oa_location', {}).get('url_for_pdf'):
                    pdf_url = data['best_oa_location']['url_for_pdf']
                    pdf_resp = requests.get(pdf_url, headers=headers, timeout=60)
                    if pdf_resp.ok:
                        return pdf_resp.content, f"doi_{doi.replace('/', '_')}.pdf"
        except Exception as e:
            print(f"[ResearchTranslator] DOI fetch failed: {e}")

    # Handle arXiv URLs
    if 'arxiv.org' in url:
        # Extract arXiv ID
        arxiv_match = re.search(r'(\d{4}\.\d{4,5})', url)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            resp = requests.get(pdf_url, headers=headers, timeout=60)
            if resp.ok:
                return resp.content, f"arxiv_{arxiv_id}.pdf"

    # Handle PubMed URLs - try to get PMC PDF
    if 'pubmed' in url or 'ncbi.nlm.nih.gov' in url:
        # Try to extract PMID
        pmid_match = re.search(r'(\d{7,8})', url)
        if pmid_match:
            pmid = pmid_match.group(1)
            # Try PMC first
            pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/pmid/{pmid}/pdf/"
            try:
                resp = requests.get(pmc_url, headers=headers, allow_redirects=True, timeout=30)
                if resp.ok and resp.headers.get('content-type', '').startswith('application/pdf'):
                    return resp.content, f"pubmed_{pmid}.pdf"
            except Exception:
                pass

    # Direct PDF URL
    if url.endswith('.pdf') or 'pdf' in url.lower():
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.ok:
            # Extract filename from URL
            parsed = urlparse(url)
            filename = parsed.path.split('/')[-1] or 'paper.pdf'
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            return resp.content, filename

    # Generic URL - try to fetch and see if it's a PDF
    resp = requests.get(url, headers=headers, allow_redirects=True, timeout=30)
    if resp.ok:
        content_type = resp.headers.get('content-type', '')
        if 'pdf' in content_type:
            parsed = urlparse(url)
            filename = parsed.path.split('/')[-1] or 'paper.pdf'
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            return resp.content, filename

    raise ValueError(f"Could not fetch paper from URL: {url}")


def _fetch_translator_context(query: str, tenant_id: str, db=None, top_k: int = 15) -> Dict[str, Any]:
    """
    Fetch comprehensive lab context for enhanced research translation.
    Returns structured lab profile + relevant documents.

    IMPORTANT: Uses DIVERSE document sources from the database (Drive, Box, Email, Slack, etc.)
    rather than just search results which may be biased toward one source type.
    """
    if not LAB_PROFILE_AVAILABLE:
        return {"documents": [], "summary": "", "profile": None, "count": 0}

    try:
        profile_service = get_lab_profile_service()

        # PRIORITY: Fetch diverse documents directly from database across ALL source types
        all_documents = []
        lab_profile = None

        if db:
            diverse_docs = profile_service.fetch_diverse_documents(tenant_id, db, max_per_source=10, total_max=50)
            if diverse_docs:
                all_documents = diverse_docs
                lab_profile = profile_service.build_profile(tenant_id, diverse_docs)
                print(f"[ResearchTranslator] Built profile from {len(diverse_docs)} diverse DB documents", flush=True)

        # Fallback: Use Pinecone search if no DB docs
        if not all_documents:
            store = get_pinecone_store()

            # Search with multiple queries for comprehensive context
            search_queries = [
                query,
                "research methodology experiments findings",
                "protocols techniques equipment",
                "publications journal papers"
            ]

            seen_ids = set()

            for search_query in search_queries:
                results = store.hybrid_search(
                    query=search_query,
                    tenant_id=tenant_id,
                    top_k=top_k,
                    alpha=0.7
                )

                for doc in results:
                    doc_id = doc.get('id', doc.get('metadata', {}).get('document_id', ''))
                    if doc_id and doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        all_documents.append({
                            "content": doc.get("content", doc.get("text", "")),
                            "metadata": doc.get("metadata", {}),
                            "score": doc.get("score", 0.0),
                            "title": doc.get("metadata", {}).get("title", "Untitled")
                        })

            if all_documents and not lab_profile:
                lab_profile = profile_service.build_profile(tenant_id, all_documents)
                print(f"[ResearchTranslator] Built profile from {len(all_documents)} search results (fallback)", flush=True)

        if not all_documents or not lab_profile:
            return {"documents": [], "summary": "", "profile": None, "count": 0}

        profile_context = lab_profile.to_prompt_context()

        return {
            "documents": all_documents[:20],  # Top 20 most relevant
            "summary": profile_context,
            "profile": lab_profile.to_dict(),
            "count": len(all_documents)
        }

    except Exception as e:
        print(f"[ResearchTranslator] Context fetch error: {e}")
        return {"documents": [], "summary": "", "profile": None, "count": 0}


def _generate_translator_context_analysis(
    profile: Dict,
    target_description: str,
    source_papers: List[str]
) -> Dict[str, Any]:
    """
    Generate LLM-powered context analysis showing how lab profile
    enhances translation quality.
    """
    if not AZURE_AVAILABLE or not profile:
        return {}

    try:
        client = get_azure_client()

        # Build profile summary
        profile_summary = f"""
Research Focus: {', '.join(profile.get('research_focus_areas', [])[:5])}
Methodologies: {', '.join(profile.get('methodologies', [])[:5])}
Model Systems: {', '.join(profile.get('model_systems', [])[:5])}
Equipment: {', '.join(profile.get('equipment', [])[:5])}
Expertise: {', '.join(profile.get('expertise_areas', [])[:5])}
Publication Tier: {profile.get('typical_impact_tier', 3)}
Known Issues: {len(profile.get('known_issues', []))} documented
"""

        prompt = f"""Analyze how this researcher's lab profile enhances cross-domain research translation.

LAB PROFILE:
{profile_summary}

TARGET RESEARCH DESCRIPTION:
{target_description[:2000]}

SOURCE PAPERS TO TRANSLATE FROM:
{', '.join(source_papers[:5])}

Provide a JSON analysis with:
1. "domain_expertise_match": {{"score": 0-100, "assessment": "brief text", "leverageable_expertise": ["list"]}}
2. "methodology_transferability": {{"summary": "how lab's methods help adapt insights", "relevant_methods": ["list"]}}
3. "equipment_compatibility": {{"score": 0-100, "assessment": "text", "available_equipment": ["list"], "may_need": ["list"]}}
4. "translation_advantages": ["list of 2-3 specific advantages this lab has"]
5. "potential_pitfalls": ["list of 1-2 things to watch out for based on lab history"]
6. "recommended_focus": {{"area": "which translation aspect to prioritize", "rationale": "why"}}

Return ONLY valid JSON."""

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a research translation advisor analyzing how a lab's existing capabilities can enhance cross-domain insight transfer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1200,
            response_format={"type": "json_object"}
        )

        import json
        result = json.loads(response.choices[0].message.content)

        # Include sources from lab profile for transparency
        if profile.get('sources'):
            result['sources'] = profile['sources']

        return result

    except Exception as e:
        print(f"[ResearchTranslator] Context analysis error: {e}")
        return {"sources": profile.get('sources', {}) if profile else {}}


def _enhance_target_context_with_profile(target_context: Dict, lab_profile: Dict) -> Dict:
    """
    Enhance the target context with lab profile information for better translations.
    """
    if not lab_profile:
        return target_context

    enhanced = dict(target_context)

    # Add lab capabilities
    if lab_profile.get('equipment'):
        enhanced['available_equipment'] = lab_profile['equipment']

    if lab_profile.get('methodologies'):
        enhanced['established_methods'] = lab_profile['methodologies']

    if lab_profile.get('model_systems'):
        enhanced['model_systems'] = lab_profile['model_systems']

    if lab_profile.get('expertise_areas'):
        enhanced['expertise_areas'] = lab_profile['expertise_areas']

    # Add constraints from known issues
    if lab_profile.get('known_issues'):
        enhanced['known_constraints'] = [
            issue.get('description', str(issue))[:200]
            for issue in lab_profile['known_issues'][:3]
        ]

    # Add publication context
    if lab_profile.get('typical_impact_tier'):
        enhanced['typical_publication_tier'] = lab_profile['typical_impact_tier']

    if lab_profile.get('successful_strategies'):
        enhanced['proven_strategies'] = lab_profile['successful_strategies'][:3]

    return enhanced


research_translator_bp = Blueprint(
    'research_translator', __name__, url_prefix='/api/co-researcher'
)

# In-memory session store for translation pipelines
_rt_sessions = {}


def _emit_event(session_id: str, event_type: str, data: dict):
    if session_id in _rt_sessions:
        _rt_sessions[session_id]["events"].put({
            "event": event_type,
            "data": data,
        })


def _run_pipeline(session_id: str, lab_profile: Optional[Dict] = None, context_analysis: Optional[Dict] = None):
    session = _rt_sessions[session_id]

    try:
        papers = session["papers"]
        total_papers = len(papers)

        # ALWAYS emit context analysis (either real or fallback explanation)
        if context_analysis:
            _emit_event(session_id, "context_analysis", context_analysis)
        else:
            # Should not happen anymore, but just in case
            _emit_event(session_id, "context_analysis", {
                "has_context": False,
                "no_context_reason": "No context analysis available"
            })

        # Phase 1: Parse
        _emit_event(session_id, "parsing_status", {
            "stage": "target", "progress": 5,
            "message": "Parsing your research document..."
        })

        # Handle text description vs file upload
        if session.get("target_is_text"):
            # Text description - use directly
            target_text = session["target_bytes"].decode('utf-8') if isinstance(session["target_bytes"], bytes) else session["target_bytes"]
        else:
            # File upload - parse the document
            target_text = parse_document(session["target_bytes"], session["target_name"])

        session["target_text"] = target_text

        _emit_event(session_id, "parsing_status", {
            "stage": "target", "progress": 20,
            "message": "Your research parsed. Parsing source papers..."
        })

        source_texts = []
        for i, paper in enumerate(papers):
            pct = 20 + int((i + 1) / total_papers * 30)
            _emit_event(session_id, "parsing_status", {
                "stage": "source", "progress": pct,
                "paper_index": i,
                "message": f"Parsing paper {i+1}/{total_papers}: {paper['name']}..."
            })
            text = parse_document(paper["bytes"], paper["name"])
            source_texts.append(text)

        session["source_texts"] = source_texts
        _emit_event(session_id, "parsing_status", {
            "stage": "complete", "progress": 50,
            "message": "All documents parsed."
        })

        # Phase 2: Context extraction + decomposition
        _emit_event(session_id, "context_extracting", {
            "message": "Extracting structured context from your research..."
        })
        target_context = extract_context(target_text, "target")

        # Enhance target context with lab profile if available
        if lab_profile:
            target_context = _enhance_target_context_with_profile(target_context, lab_profile)
            _emit_event(session_id, "lab_profile_applied", {
                "message": "Applied lab profile to enhance translation context",
                "equipment_count": len(lab_profile.get('equipment', [])),
                "methods_count": len(lab_profile.get('methodologies', [])),
                "expertise_areas": lab_profile.get('expertise_areas', [])[:3]
            })

        session["target_context"] = target_context

        _emit_event(session_id, "context_extracted", {
            "role": "target",
            "context": target_context,
            "enhanced_with_profile": lab_profile is not None
        })

        source_contexts = []
        all_decompositions = []

        for i, (paper, text) in enumerate(zip(papers, source_texts)):
            _emit_event(session_id, "context_extracting", {
                "paper_index": i,
                "paper_name": paper["name"],
                "message": f"Extracting context from paper {i+1}: {paper['name']}..."
            })
            source_ctx = extract_context(text, "source")
            source_contexts.append(source_ctx)

            _emit_event(session_id, "context_extracted", {
                "role": "source",
                "paper_index": i,
                "paper_name": paper["name"],
                "context": source_ctx,
            })

            items_to_decompose = (
                source_ctx.get("key_methods", [])[:3] +
                source_ctx.get("key_findings", [])[:2]
            )

            _emit_event(session_id, "decomposition_started", {
                "paper_index": i,
                "paper_name": paper["name"],
                "item_count": len(items_to_decompose),
            })

            for j, item in enumerate(items_to_decompose):
                layers = decompose_layers(source_ctx, item)
                decomposition = {
                    "paper_index": i,
                    "paper_name": paper["name"],
                    "item": item,
                    "layers": layers,
                }
                all_decompositions.append(decomposition)

                _emit_event(session_id, "layer_extracted", {
                    "paper_index": i,
                    "paper_name": paper["name"],
                    "item_index": j,
                    "item_name": item.get("name", item.get("finding", "Unknown")),
                    "layers": layers,
                })

        session["source_contexts"] = source_contexts
        session["decompositions"] = all_decompositions

        _emit_event(session_id, "decomposition_complete", {
            "total_decompositions": len(all_decompositions),
        })

        # Phase 3: Translation
        _emit_event(session_id, "translation_started", {
            "total": len(all_decompositions),
            "message": "Translating insights into your research domain..."
        })

        translations = []
        for idx, decomp in enumerate(all_decompositions):
            paper_idx = decomp["paper_index"]
            source_ctx = source_contexts[paper_idx]

            _emit_event(session_id, "translating_insight", {
                "index": idx,
                "total": len(all_decompositions),
                "paper_name": decomp["paper_name"],
                "item_name": decomp["item"].get("name", decomp["item"].get("finding", "Unknown")),
            })

            translation = translate_insight(source_ctx, target_context, decomp["layers"])
            translation["paper_index"] = paper_idx
            translation["paper_name"] = decomp["paper_name"]
            translation["translation_index"] = idx
            translations.append(translation)

            _emit_event(session_id, "translation_complete", {
                "index": idx,
                "translation": translation,
            })

        session["translations"] = translations

        # Phase 4: Adversarial stress-test
        _emit_event(session_id, "adversarial_started", {
            "total_translations": len(translations),
            "message": "Stress-testing each translation..."
        })

        adversarial_results = []

        for idx, translation in enumerate(translations):
            paper_idx = translation["paper_index"]
            source_ctx = source_contexts[paper_idx]

            _emit_event(session_id, "adversarial_testing", {
                "translation_index": idx,
                "title": translation.get("title", ""),
                "message": f"Stress-testing translation {idx+1}/{len(translations)}..."
            })

            result = run_adversarial(translation, source_ctx, target_context)
            result["translation_index"] = idx
            adversarial_results.append(result)

            for verdict in result.get("verdicts", []):
                _emit_event(session_id, "agent_verdict", {
                    "translation_index": idx,
                    "translation_title": translation.get("title", ""),
                    "agent_id": verdict.get("agent_id"),
                    "agent_name": verdict.get("agent_name"),
                    "agent_color": verdict.get("agent_color"),
                    "agent_role": verdict.get("agent_role"),
                    "verdict": verdict.get("verdict"),
                    "attack": verdict.get("attack", ""),
                })

            _emit_event(session_id, "adversarial_complete", {
                "translation_index": idx,
                "title": translation.get("title", ""),
                "survival_score": result["survival_score"],
                "has_fatal": result["has_fatal"],
                "verdicts": result["verdicts"],
            })

        session["adversarial_results"] = adversarial_results

        # Sort by survival score
        ranked = sorted(
            range(len(translations)),
            key=lambda i: (
                adversarial_results[i]["survival_score"],
                -int(adversarial_results[i]["has_fatal"]),
            ),
            reverse=True,
        )

        ranked_translations = [translations[i] for i in ranked]
        ranked_adversarial = [adversarial_results[i] for i in ranked]

        session["ranked_translations"] = ranked_translations
        session["ranked_adversarial"] = ranked_adversarial

        _emit_event(session_id, "results_ready", {
            "translations": ranked_translations,
            "adversarial": ranked_adversarial,
            "source_contexts": source_contexts,
            "target_context": target_context,
        })

        chat_ctx = build_chat_context(
            source_contexts, target_context,
            ranked_translations, ranked_adversarial,
        )
        session["chat_context"] = chat_ctx
        session["chat_history"] = []

        _emit_event(session_id, "chat_ready", {
            "message": "Interactive refinement available. Share constraints or ask questions."
        })

    except Exception as e:
        _emit_event(session_id, "error", {"message": str(e)})

    finally:
        _emit_event(session_id, "pipeline_complete", {})


@research_translator_bp.route('/analyze', methods=['POST'])
def rt_analyze():
    # Check for either file upload OR text description
    research_description = request.form.get('research_description', '').strip()
    has_file = 'my_research' in request.files and request.files['my_research'].filename

    if not has_file and not research_description:
        return jsonify({"error": "Please upload a research file (PDF/DOCX) or provide a research description"}), 400

    paper_files = request.files.getlist('papers')
    paper_urls_json = request.form.get('paper_urls', '[]')

    try:
        paper_urls = json.loads(paper_urls_json) if paper_urls_json else []
    except json.JSONDecodeError:
        paper_urls = []

    # Filter out empty file entries (happens when no files selected)
    paper_files = [pf for pf in paper_files if pf.filename]

    total_papers = len(paper_files) + len(paper_urls)
    if total_papers < 1:
        return jsonify({"error": "At least one source paper is required (upload files or provide URLs)"}), 400
    if total_papers > 5:
        return jsonify({"error": "Maximum 5 source papers allowed"}), 400

    allowed_exts = ('.pdf', '.docx', '.doc')

    # Process target research (either file or text)
    target_bytes = None
    target_name = "research_description.txt"

    if has_file:
        target_file = request.files['my_research']
        if not target_file.filename.lower().endswith(allowed_exts):
            return jsonify({"error": "Your research must be a PDF or DOCX file"}), 400
        target_bytes = target_file.read()
        target_name = target_file.filename
    else:
        # Use text description - encode as bytes for consistent handling
        target_bytes = research_description.encode('utf-8')
        target_name = "research_description.txt"

    papers = []

    # Process uploaded files
    for pf in paper_files:
        if not pf.filename.lower().endswith(allowed_exts):
            return jsonify({"error": f"'{pf.filename}' must be PDF or DOCX"}), 400
        papers.append({"bytes": pf.read(), "name": pf.filename})

    # Process paper URLs - fetch them
    for url in paper_urls:
        try:
            file_bytes, filename = fetch_paper_from_url(url)
            papers.append({"bytes": file_bytes, "name": filename})
            print(f"[ResearchTranslator] Fetched paper from URL: {filename}")
        except Exception as e:
            print(f"[ResearchTranslator] Failed to fetch URL {url}: {e}")
            return jsonify({"error": f"Could not fetch paper from URL: {url}. Please try uploading the PDF directly."}), 400

    session_id = str(uuid.uuid4())
    _rt_sessions[session_id] = {
        "events": Queue(),
        "target_bytes": target_bytes,
        "target_name": target_name,
        "target_is_text": not has_file,
        "papers": papers,
        "target_text": "",
        "source_texts": [],
        "target_context": {},
        "source_contexts": [],
        "decompositions": [],
        "translations": [],
        "adversarial_results": [],
        "ranked_translations": [],
        "ranked_adversarial": [],
        "chat_context": "",
        "chat_history": [],
    }

    thread = threading.Thread(target=_run_pipeline, args=(session_id, None, None), daemon=True)
    thread.start()

    return jsonify({"session_id": session_id, "paper_count": len(papers)})


@research_translator_bp.route('/analyze-with-context', methods=['POST'])
def rt_analyze_with_context():
    """
    Context-aware research translation using the user's lab profile.
    Requires authentication. Falls back to regular analyze if no context available.
    """
    from functools import wraps

    # Get auth token
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"error": "Authentication required for context-aware analysis"}), 401

    token = auth_header.split(' ')[1]

    # Validate token and get tenant
    try:
        auth_service = AuthService()
        payload = auth_service.validate_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        tenant_id = payload.get('tenant_id')
    except Exception as e:
        return jsonify({"error": f"Authentication failed: {str(e)}"}), 401

    # Check for either file upload OR text description
    research_description = request.form.get('research_description', '').strip()
    has_file = 'my_research' in request.files and request.files['my_research'].filename

    if not has_file and not research_description:
        return jsonify({"error": "Please upload a research file (PDF/DOCX) or provide a research description"}), 400

    paper_files = request.files.getlist('papers')
    paper_urls_json = request.form.get('paper_urls', '[]')

    try:
        paper_urls = json.loads(paper_urls_json) if paper_urls_json else []
    except json.JSONDecodeError:
        paper_urls = []

    # Filter out empty file entries
    paper_files = [pf for pf in paper_files if pf.filename]

    total_papers = len(paper_files) + len(paper_urls)
    if total_papers < 1:
        return jsonify({"error": "At least one source paper is required (upload files or provide URLs)"}), 400
    if total_papers > 5:
        return jsonify({"error": "Maximum 5 source papers allowed"}), 400

    allowed_exts = ('.pdf', '.docx', '.doc')

    # Process target research (either file or text)
    target_bytes = None
    target_name = "research_description.txt"

    if has_file:
        target_file = request.files['my_research']
        if not target_file.filename.lower().endswith(allowed_exts):
            return jsonify({"error": "Your research must be a PDF or DOCX file"}), 400
        target_bytes = target_file.read()
        target_name = target_file.filename
    else:
        target_bytes = research_description.encode('utf-8')
        target_name = "research_description.txt"

    papers = []

    # Process uploaded files
    for pf in paper_files:
        if not pf.filename.lower().endswith(allowed_exts):
            return jsonify({"error": f"'{pf.filename}' must be PDF or DOCX"}), 400
        papers.append({"bytes": pf.read(), "name": pf.filename})

    # Process paper URLs - fetch them
    for url in paper_urls:
        try:
            file_bytes, filename = fetch_paper_from_url(url)
            papers.append({"bytes": file_bytes, "name": filename})
            print(f"[ResearchTranslator] Fetched paper from URL: {filename}")
        except Exception as e:
            print(f"[ResearchTranslator] Failed to fetch URL {url}: {e}")
            return jsonify({"error": f"Could not fetch paper from URL: {url}. Please try uploading the PDF directly."}), 400

    # Fetch lab context for enhanced translation
    lab_profile = None
    context_analysis = None

    # Create database session for diverse document fetching
    from database.models import SessionLocal
    db = SessionLocal()

    if LAB_PROFILE_AVAILABLE and tenant_id:
        try:
            # Build search query from research description
            search_query = research_description[:500] if research_description else "research methodology experiments"

            context_data = _fetch_translator_context(search_query, tenant_id, db=db)
            doc_count = context_data.get('count', 0)

            if context_data.get('profile'):
                lab_profile = context_data['profile']
                print(f"[ResearchTranslator] Lab profile loaded: {len(lab_profile.get('methodologies', []))} methods, {len(lab_profile.get('equipment', []))} equipment items")

                # Generate context analysis
                source_paper_names = [p['name'] for p in papers]
                context_analysis = _generate_translator_context_analysis(
                    lab_profile,
                    research_description or "Research document uploaded",
                    source_paper_names
                )
                if context_analysis:
                    context_analysis['has_context'] = True
            else:
                # No profile - create fallback explanation
                print(f"[ResearchTranslator] No lab profile found (searched {doc_count} docs)")
                context_analysis = {
                    "has_context": False,
                    "no_context_reason": "No relevant lab context found - translations will be generic",
                    "documents_searched": doc_count,
                    "tip": "Sync documents from Slack, Google Drive, etc. to enable lab-specific translations"
                }

        except Exception as e:
            print(f"[ResearchTranslator] Context fetch failed (continuing without): {e}")
            context_analysis = {
                "has_context": False,
                "no_context_reason": f"Context fetch error: {str(e)}",
                "tip": "Try again later or check your integrations"
            }
    elif tenant_id and not LAB_PROFILE_AVAILABLE:
        # Lab profile service not available
        context_analysis = {
            "has_context": False,
            "no_context_reason": "Lab profile service not configured",
            "tip": "Contact support to enable lab context features"
        }
    elif not tenant_id:
        # Not logged in
        context_analysis = {
            "has_context": False,
            "no_context_reason": "Log in to enable personalized translations",
            "tip": "Sync your lab documents after logging in"
        }

    session_id = str(uuid.uuid4())
    _rt_sessions[session_id] = {
        "events": Queue(),
        "target_bytes": target_bytes,
        "target_name": target_name,
        "target_is_text": not has_file,
        "papers": papers,
        "target_text": "",
        "source_texts": [],
        "target_context": {},
        "source_contexts": [],
        "decompositions": [],
        "translations": [],
        "adversarial_results": [],
        "ranked_translations": [],
        "ranked_adversarial": [],
        "chat_context": "",
        "chat_history": [],
        "lab_profile": lab_profile,  # Store for reference
    }

    # Close db session now that we're done fetching context
    db.close()

    # Start pipeline with lab profile
    thread = threading.Thread(
        target=_run_pipeline,
        args=(session_id, lab_profile, context_analysis),
        daemon=True
    )
    thread.start()

    return jsonify({
        "session_id": session_id,
        "paper_count": len(papers),
        "context_enhanced": lab_profile is not None,
        "profile_summary": {
            "methodologies": len(lab_profile.get('methodologies', [])) if lab_profile else 0,
            "equipment": len(lab_profile.get('equipment', [])) if lab_profile else 0,
            "expertise_areas": lab_profile.get('expertise_areas', [])[:3] if lab_profile else []
        } if lab_profile else None
    })


@research_translator_bp.route('/stream/<session_id>', methods=['GET'])
def rt_stream(session_id):
    if session_id not in _rt_sessions:
        return jsonify({"error": "Session not found"}), 404

    def event_stream():
        while True:
            try:
                event = _rt_sessions[session_id]["events"].get(timeout=120)
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

                if event["event"] == "pipeline_complete":
                    break
            except Empty:
                yield ": keepalive\n\n"

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@research_translator_bp.route('/chat/<session_id>', methods=['POST'])
def rt_chat(session_id):
    if session_id not in _rt_sessions:
        return jsonify({"error": "Session not found"}), 404

    session = _rt_sessions[session_id]
    if not session.get("chat_context"):
        return jsonify({"error": "Analysis not complete yet"}), 400

    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    result = handle_chat_message(
        chat_context=session["chat_context"],
        chat_history=session["chat_history"],
        user_message=user_message,
    )

    session["chat_history"].append({"role": "user", "content": user_message})
    session["chat_history"].append({"role": "assistant", "content": result["response"]})

    return jsonify(result)
