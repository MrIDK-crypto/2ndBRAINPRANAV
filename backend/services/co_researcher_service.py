"""
Co-Researcher Service
Orchestrates research sessions, hypothesis testing, and knowledge synthesis
by combining existing services (EnhancedSearch, PubMed, OpenAI).
"""

import os
import json
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import requests
import xml.etree.ElementTree as ET

from database.models import (
    SessionLocal, ResearchSession, ResearchMessage, Hypothesis, Evidence,
    ResearchSessionStatus, HypothesisStatus, EvidenceType, EvidenceSource
)
from services.openai_client import get_openai_client


# PubMed E-utilities endpoints
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
PUBMED_RATE_DELAY = 0.1 if PUBMED_API_KEY else 0.34


class CoResearcherService:
    """Orchestrates co-researcher workflows."""

    def __init__(self):
        self.openai = get_openai_client()

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def create_session(self, tenant_id: str, user_id: str, initial_message: str, db) -> Dict:
        """
        Create a new research session from the user's first message.
        Generates title, research plan, and initial brief via GPT.
        """
        # Generate title and research question from the initial message
        title_resp = self.openai.chat_completion(
            messages=[
                {"role": "system", "content": "Generate a short title (max 8 words) for a research session based on the user's message. Return ONLY the title, no quotes."},
                {"role": "user", "content": initial_message}
            ],
            temperature=0.3,
            max_tokens=30
        )
        title = title_resp.choices[0].message.content.strip().strip('"')

        # Create the session
        session = ResearchSession(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            research_question=initial_message,
            status=ResearchSessionStatus.ACTIVE,
            research_plan=[],
            research_brief={},
        )
        db.add(session)
        db.flush()

        # Save the user message
        user_msg = ResearchMessage(
            session_id=session.id,
            tenant_id=tenant_id,
            role="user",
            content=initial_message,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(session)

        return session.to_dict(include_messages=True)

    def get_session(self, session_id: str, tenant_id: str, db) -> Optional[Dict]:
        """Get a session with messages and hypotheses."""
        session = db.query(ResearchSession).filter(
            ResearchSession.id == session_id,
            ResearchSession.tenant_id == tenant_id,
        ).first()
        if not session:
            return None
        return session.to_dict(include_messages=True, include_hypotheses=True)

    def list_sessions(self, tenant_id: str, user_id: str, db, limit=20, offset=0) -> List[Dict]:
        """List sessions for a user, most recent first."""
        sessions = db.query(ResearchSession).filter(
            ResearchSession.tenant_id == tenant_id,
            ResearchSession.user_id == user_id,
            ResearchSession.status != ResearchSessionStatus.ARCHIVED,
        ).order_by(ResearchSession.last_activity_at.desc()).offset(offset).limit(limit).all()
        return [s.to_dict() for s in sessions]

    def update_session(self, session_id: str, tenant_id: str, updates: Dict, db) -> Optional[Dict]:
        """Update session title, status, or tags."""
        session = db.query(ResearchSession).filter(
            ResearchSession.id == session_id,
            ResearchSession.tenant_id == tenant_id,
        ).first()
        if not session:
            return None

        if "title" in updates:
            session.title = updates["title"]
        if "status" in updates:
            session.status = ResearchSessionStatus(updates["status"])
        if "tags" in updates:
            session.tags = updates["tags"]

        db.commit()
        db.refresh(session)
        return session.to_dict()

    def delete_session(self, session_id: str, tenant_id: str, db) -> bool:
        """Archive (soft delete) a session."""
        session = db.query(ResearchSession).filter(
            ResearchSession.id == session_id,
            ResearchSession.tenant_id == tenant_id,
        ).first()
        if not session:
            return False
        session.status = ResearchSessionStatus.ARCHIVED
        db.commit()
        return True

    # =========================================================================
    # MESSAGE PROCESSING (STREAMING)
    # =========================================================================

    def process_message_stream(self, session_id: str, tenant_id: str, user_message: str, db, skip_user_save: bool = False):
        """
        Process a user message and stream the response as SSE events.

        Args:
            skip_user_save: If True, skip saving the user message (already saved by createSession).

        Yields SSE-formatted strings:
          event: action\ndata: {...}\n\n
          event: chunk\ndata: {...}\n\n
          event: plan_update\ndata: {...}\n\n
          event: brief_update\ndata: {...}\n\n
          event: context_update\ndata: {...}\n\n
          event: hypothesis_update\ndata: {...}\n\n
          event: done\ndata: {...}\n\n
        """
        session = db.query(ResearchSession).filter(
            ResearchSession.id == session_id,
            ResearchSession.tenant_id == tenant_id,
        ).first()

        if not session:
            yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
            return

        # Save user message (skip if already saved during session creation)
        if not skip_user_save:
            user_msg = ResearchMessage(
                session_id=session_id,
                tenant_id=tenant_id,
                role="user",
                content=user_message,
            )
            db.add(user_msg)
            db.commit()

        # Get conversation history
        history = self._get_conversation_history(session_id, db)

        # Classify intent
        intent = self._classify_intent(user_message, history)
        print(f"[CoResearcher] Intent: {intent} for: '{user_message[:60]}...'", flush=True)

        actions = []
        sources = []
        context_data = {"documents": [], "pubmed_papers": [], "gaps": []}

        try:
            if intent == "hypothesis":
                yield from self._handle_hypothesis_stream(
                    session, user_message, history, actions, sources, context_data, db
                )
            elif intent == "synthesize":
                yield from self._handle_synthesize_stream(
                    session, history, actions, db
                )
            else:
                # Default: research_query or follow_up
                yield from self._handle_research_query_stream(
                    session, user_message, history, actions, sources, context_data, db
                )

            # Update session activity timestamp
            session.last_activity_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            print(f"[CoResearcher] Error: {e}", flush=True)
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    # =========================================================================
    # INTENT CLASSIFICATION
    # =========================================================================

    def _classify_intent(self, message: str, history: List[Dict]) -> str:
        """Classify user intent using GPT."""
        recent_history = history[-6:] if len(history) > 6 else history
        history_text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in recent_history])

        resp = self.openai.chat_completion(
            messages=[
                {"role": "system", "content": """Classify the user's intent into exactly one of:
- research_query: asking a research question, wants information
- hypothesis: proposing or asking to test a hypothesis (contains words like "hypothesize", "hypothesis", "test whether", "I think that", "could X cause Y")
- follow_up: asking for more detail on previous topic ("tell me more", "elaborate", "what about")
- synthesize: wants a summary of findings ("summarize", "synthesize", "what have we found")

Respond with ONLY the intent name."""},
                {"role": "user", "content": f"Conversation context:\n{history_text}\n\nUser message: {message}"}
            ],
            temperature=0.1,
            max_tokens=20
        )
        intent = resp.choices[0].message.content.strip().lower()
        valid_intents = {"research_query", "hypothesis", "follow_up", "synthesize"}
        return intent if intent in valid_intents else "research_query"

    # =========================================================================
    # RESEARCH QUERY HANDLER
    # =========================================================================

    def _handle_research_query_stream(self, session, message, history, actions, sources, context_data, db):
        """Handle a research query: search KB + PubMed, synthesize, stream response."""
        tenant_id = session.tenant_id

        # --- Step 1: Search internal KB ---
        yield f"event: action\ndata: {json.dumps({'type': 'searching_kb', 'text': 'Searching knowledge base...'})}\n\n"
        actions.append({"icon": "search", "text": "Searched knowledge base"})

        kb_results = self._search_internal_kb(message, tenant_id)
        kb_sources = kb_results.get("sources", [])
        if kb_sources:
            actions.append({"icon": "doc", "text": f"Found {len(kb_sources)} relevant documents"})
            context_data["documents"] = [
                {"title": s.get("title", "Untitled"), "doc_id": s.get("doc_id"), "score": s.get("score", 0), "preview": s.get("content_preview", "")}
                for s in kb_sources[:10]
            ]

        # --- Step 2: Search PubMed ---
        yield f"event: action\ndata: {json.dumps({'type': 'searching_pubmed', 'text': 'Searching PubMed...'})}\n\n"

        pubmed_results = self._search_pubmed(message, max_results=8)
        if pubmed_results:
            actions.append({"icon": "search", "text": f"Found {len(pubmed_results)} PubMed papers"})
            context_data["pubmed_papers"] = pubmed_results
        yield f"event: action\ndata: {json.dumps({'type': 'pubmed_done', 'text': f'Found {len(pubmed_results)} PubMed papers'})}\n\n"

        # --- Step 2b: Search journal database ---
        yield f"event: action\ndata: {json.dumps({'type': 'searching_journals', 'text': 'Querying journal database...'})}\n\n"
        journal_results = self._search_journals(message, db)

        # --- Step 2c: Search reproducibility archive ---
        yield f"event: action\ndata: {json.dumps({'type': 'searching_experiments', 'text': 'Checking reproducibility archive...'})}\n\n"
        experiment_results = self._search_experiments(message, db)

        # --- Step 3: Send context update with ALL sources ---
        context_data["journals"] = journal_results
        context_data["experiments"] = experiment_results
        yield f"event: context_update\ndata: {json.dumps(context_data)}\n\n"

        # --- Step 4: Generate research plan if empty ---
        if not session.research_plan:
            plan = self._generate_research_plan(message)
            session.research_plan = plan
            yield f"event: plan_update\ndata: {json.dumps({'plan': plan})}\n\n"
        else:
            # Update existing plan
            plan = self._advance_plan(session.research_plan, "research_query")
            session.research_plan = plan
            yield f"event: plan_update\ndata: {json.dumps({'plan': plan})}\n\n"

        # --- Step 5: Synthesize and stream answer ---
        yield f"event: action\ndata: {json.dumps({'type': 'synthesizing', 'text': 'Synthesizing findings...'})}\n\n"
        actions.append({"icon": "plan", "text": "Synthesizing research findings"})

        # Build extra context from journal and experiment results
        extra_context = ""
        if journal_results:
            extra_context += "\n\n--- JOURNAL DATABASE ---\n"
            for j in journal_results:
                extra_context += f"Journal: {j['title']} (Field: {j['field']}, Impact: {j.get('impact_factor', 'N/A')}, Tier: {j.get('tier', 'N/A')})\n"
        if experiment_results:
            extra_context += "\n\n--- REPRODUCIBILITY ARCHIVE ---\n"
            for e in experiment_results:
                extra_context += f"Experiment: {e['title']}\nHypothesis: {e['hypothesis']}\nWhat Failed: {e['what_failed']}\nLessons: {e['lessons_learned']}\n\n"
        kb_results["extra_context"] = extra_context

        answer_text = ""
        for chunk in self._synthesize_stream(message, kb_results, pubmed_results, history, session):
            answer_text += chunk
            yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

        # --- Step 6: Update brief ---
        brief = self._generate_brief(message, answer_text, kb_sources, pubmed_results)
        session.research_brief = brief
        yield f"event: brief_update\ndata: {json.dumps({'brief': brief})}\n\n"

        # --- Step 7: Save assistant message ---
        all_sources = [{"title": s.get("title"), "doc_id": s.get("doc_id"), "source_type": "internal"} for s in kb_sources[:5]]
        all_sources += [{"title": p.get("title"), "source_url": p.get("url"), "source_type": "pubmed"} for p in pubmed_results[:5]]

        assistant_msg = ResearchMessage(
            session_id=session.id,
            tenant_id=session.tenant_id,
            role="assistant",
            content=answer_text,
            actions=actions,
            sources=all_sources,
        )
        db.add(assistant_msg)
        db.commit()

        yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg.id, 'sources': all_sources, 'actions': actions})}\n\n"

    # =========================================================================
    # HYPOTHESIS HANDLER
    # =========================================================================

    def _handle_hypothesis_stream(self, session, message, history, actions, sources, context_data, db):
        """Handle hypothesis testing: extract, gather evidence, assess, stream."""
        tenant_id = session.tenant_id

        # --- Step 1: Extract hypothesis ---
        yield f"event: action\ndata: {json.dumps({'type': 'extracting_hypothesis', 'text': 'Extracting hypothesis...'})}\n\n"

        hyp_data = self._extract_hypothesis(message)
        statement = hyp_data.get("statement", message)
        null_hyp = hyp_data.get("null_hypothesis", "")
        rationale = hyp_data.get("rationale", "")

        actions.append({"icon": "plan", "text": f"Hypothesis: {statement[:80]}..."})

        # Create hypothesis record
        hypothesis = Hypothesis(
            session_id=session.id,
            tenant_id=tenant_id,
            statement=statement,
            null_hypothesis=null_hyp,
            rationale=rationale,
            status=HypothesisStatus.TESTING,
        )
        db.add(hypothesis)
        db.flush()

        # --- Step 2: Search for evidence ---
        yield f"event: action\ndata: {json.dumps({'type': 'searching_kb', 'text': 'Searching knowledge base for evidence...'})}\n\n"
        kb_results = self._search_internal_kb(statement, tenant_id)
        kb_sources = kb_results.get("sources", [])

        yield f"event: action\ndata: {json.dumps({'type': 'searching_pubmed', 'text': 'Searching PubMed for evidence...'})}\n\n"
        pubmed_results = self._search_pubmed(statement, max_results=10)

        context_data["documents"] = [
            {"title": s.get("title", "Untitled"), "doc_id": s.get("doc_id"), "score": s.get("score", 0), "preview": s.get("content_preview", "")}
            for s in kb_sources[:10]
        ]
        context_data["pubmed_papers"] = pubmed_results
        yield f"event: context_update\ndata: {json.dumps(context_data)}\n\n"

        # --- Step 3: Classify evidence ---
        yield f"event: action\ndata: {json.dumps({'type': 'analyzing', 'text': 'Classifying evidence...'})}\n\n"

        evidence_items = self._classify_evidence(statement, kb_sources, pubmed_results)
        supporting = [e for e in evidence_items if e["evidence_type"] == "supporting"]
        contradicting = [e for e in evidence_items if e["evidence_type"] == "contradicting"]
        neutral = [e for e in evidence_items if e["evidence_type"] == "neutral"]

        actions.append({"icon": "doc", "text": f"{len(supporting)} supporting, {len(contradicting)} contradicting, {len(neutral)} neutral evidence"})

        # Save evidence records
        for ev in evidence_items[:20]:  # Cap at 20
            evidence_record = Evidence(
                hypothesis_id=hypothesis.id,
                tenant_id=tenant_id,
                title=ev.get("title", ""),
                content=ev.get("content", ""),
                source_type=EvidenceSource(ev.get("source_type", "internal")),
                evidence_type=EvidenceType(ev["evidence_type"]),
                source_id=ev.get("source_id"),
                source_url=ev.get("source_url"),
                relevance_score=ev.get("relevance_score", 0.5),
                explanation=ev.get("explanation"),
            )
            db.add(evidence_record)

        hypothesis.supporting_count = len(supporting)
        hypothesis.contradicting_count = len(contradicting)
        hypothesis.neutral_count = len(neutral)

        # --- Step 4: Assess and stream ---
        yield f"event: action\ndata: {json.dumps({'type': 'assessing', 'text': 'Assessing hypothesis...'})}\n\n"

        answer_text = ""
        assessment_data = {"status": "inconclusive", "confidence": 0.5}
        for chunk in self._assess_hypothesis_stream(hypothesis, evidence_items):
            if isinstance(chunk, dict):
                # Final assessment metadata
                assessment_data = chunk
            else:
                answer_text += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

        # Update hypothesis with assessment
        hypothesis.assessment = answer_text
        hypothesis.assessment_at = datetime.now(timezone.utc)
        hypothesis.confidence_score = assessment_data.get("confidence", 0.5)
        status_map = {"supported": HypothesisStatus.SUPPORTED, "refuted": HypothesisStatus.REFUTED}
        hypothesis.status = status_map.get(assessment_data.get("status"), HypothesisStatus.INCONCLUSIVE)

        db.flush()

        yield f"event: hypothesis_update\ndata: {json.dumps(hypothesis.to_dict(include_evidence=True))}\n\n"

        # Update plan and brief
        if not session.research_plan:
            plan = self._generate_research_plan(session.research_question or message)
            session.research_plan = plan
        plan = self._advance_plan(session.research_plan, "hypothesis")
        session.research_plan = plan
        yield f"event: plan_update\ndata: {json.dumps({'plan': plan})}\n\n"

        brief = self._generate_brief(
            session.research_question or message,
            answer_text,
            kb_sources,
            pubmed_results,
            hypothesis=hypothesis
        )
        session.research_brief = brief
        yield f"event: brief_update\ndata: {json.dumps({'brief': brief})}\n\n"

        # Save assistant message
        assistant_msg = ResearchMessage(
            session_id=session.id,
            tenant_id=session.tenant_id,
            role="assistant",
            content=answer_text,
            actions=actions,
            sources=[],
            extra_data={"hypothesis_id": hypothesis.id},
        )
        db.add(assistant_msg)
        db.commit()

        yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg.id, 'actions': actions, 'hypothesis_id': hypothesis.id})}\n\n"

    # =========================================================================
    # SYNTHESIS HANDLER
    # =========================================================================

    def _handle_synthesize_stream(self, session, history, actions, db):
        """Generate a comprehensive synthesis of all session findings."""
        yield f"event: action\ndata: {json.dumps({'type': 'synthesizing', 'text': 'Generating research synthesis...'})}\n\n"
        actions.append({"icon": "plan", "text": "Generating comprehensive synthesis"})

        # Gather all session data
        hypotheses = db.query(Hypothesis).filter(Hypothesis.session_id == session.id).all()
        hyp_summaries = []
        for h in hypotheses:
            hyp_summaries.append(f"- Hypothesis: {h.statement}\n  Status: {h.status.value}, Confidence: {h.confidence_score:.0%}\n  Assessment: {h.assessment or 'N/A'}")

        history_text = "\n".join([f"{m['role']}: {m['content'][:300]}" for m in history[-20:]])

        messages = [
            {"role": "system", "content": """You are a research synthesis expert. Generate a comprehensive summary of the research session including:
1. Executive Summary (2-3 sentences)
2. Key Findings (bullet points)
3. Hypothesis Results (if any)
4. Knowledge Gaps (what's still unknown)
5. Recommended Next Steps

Use clear, concise scientific language. Cite specific findings from the conversation."""},
            {"role": "user", "content": f"Research question: {session.research_question}\n\nConversation:\n{history_text}\n\nHypotheses tested:\n{chr(10).join(hyp_summaries) if hyp_summaries else 'None'}\n\nPlease synthesize all findings."}
        ]

        answer_text = ""
        for chunk in self.openai.chat_completion_stream(messages, temperature=0.3, max_tokens=2000):
            delta = chunk.choices[0].delta
            if delta and delta.content:
                answer_text += delta.content
                yield f"event: chunk\ndata: {json.dumps({'content': delta.content})}\n\n"

        # Save assistant message
        assistant_msg = ResearchMessage(
            session_id=session.id,
            tenant_id=session.tenant_id,
            role="assistant",
            content=answer_text,
            actions=actions,
        )
        db.add(assistant_msg)
        db.commit()

        yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg.id, 'actions': actions})}\n\n"

    # =========================================================================
    # INTERNAL KB SEARCH
    # =========================================================================

    def _search_internal_kb(self, query: str, tenant_id: str) -> Dict:
        """Search the knowledge base using EnhancedSearchService."""
        try:
            from services.enhanced_search_service import get_enhanced_search_service
            from vector_stores.pinecone_store import get_hybrid_store

            if not os.getenv("PINECONE_API_KEY"):
                return {"answer": "", "sources": []}

            vector_store = get_hybrid_store()
            enhanced_service = get_enhanced_search_service()

            result = enhanced_service.search_and_answer(
                query=query,
                tenant_id=tenant_id,
                vector_store=vector_store,
                top_k=10,
                validate=False,  # Skip hallucination detection for speed
            )
            return result
        except Exception as e:
            print(f"[CoResearcher] KB search error: {e}", flush=True)
            return {"answer": "", "sources": []}

    # =========================================================================
    # PUBMED SEARCH (real-time, not via connector)
    # =========================================================================

    def _search_pubmed(self, query: str, max_results: int = 8) -> List[Dict]:
        """Search PubMed and return paper summaries."""
        try:
            # Step 1: Search for PMIDs
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance",
            }
            if PUBMED_API_KEY:
                params["api_key"] = PUBMED_API_KEY

            time.sleep(PUBMED_RATE_DELAY)
            resp = requests.get(PUBMED_ESEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            pmids = resp.json().get("esearchresult", {}).get("idlist", [])

            if not pmids:
                return []

            # Step 2: Fetch abstracts
            time.sleep(PUBMED_RATE_DELAY)
            fetch_resp = requests.get(PUBMED_EFETCH_URL, params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
                **({"api_key": PUBMED_API_KEY} if PUBMED_API_KEY else {})
            }, timeout=30)
            fetch_resp.raise_for_status()

            return self._parse_pubmed_xml(fetch_resp.text)

        except Exception as e:
            print(f"[CoResearcher] PubMed search error: {e}", flush=True)
            return []

    def _parse_pubmed_xml(self, xml_text: str) -> List[Dict]:
        """Parse PubMed XML into simple dicts."""
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

                    # Abstract
                    abstract_parts = []
                    for at in article.findall(".//AbstractText"):
                        label = at.get("Label", "")
                        text = at.text or ""
                        abstract_parts.append(f"{label}: {text}" if label else text)
                    abstract = "\n".join(abstract_parts)

                    # Authors
                    authors = []
                    for author in article.findall(".//Author"):
                        last = author.find(".//LastName")
                        first = author.find(".//ForeName")
                        if last is not None and last.text:
                            name = last.text
                            if first is not None and first.text:
                                name = f"{last.text} {first.text[0]}"
                            authors.append(name)

                    # Journal and year
                    journal_elem = article.find(".//Journal/Title")
                    journal = journal_elem.text if journal_elem is not None else ""
                    year_elem = article.find(".//PubDate/Year")
                    year = year_elem.text if year_elem is not None else ""

                    papers.append({
                        "pmid": pmid,
                        "title": title,
                        "abstract": abstract[:500],
                        "authors": authors[:5],
                        "journal": journal,
                        "year": year,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"[CoResearcher] PubMed XML parse error: {e}", flush=True)
        return papers

    # =========================================================================
    # JOURNAL & EXPERIMENT SEARCH
    # =========================================================================

    def _search_journals(self, query: str, db, limit=5):
        """Search JournalProfile table for relevant journals."""
        from database.models import JournalProfile
        from sqlalchemy import or_

        try:
            journals = db.query(JournalProfile).filter(
                or_(
                    JournalProfile.name.ilike(f'%{query}%'),
                    JournalProfile.primary_field.ilike(f'%{query}%'),
                    JournalProfile.primary_subfield.ilike(f'%{query}%'),
                )
            ).order_by(JournalProfile.composite_score.desc()).limit(limit).all()

            return [{
                'source_type': 'journal_database',
                'title': j.name,
                'field': j.primary_field,
                'subfield': getattr(j, 'primary_subfield', ''),
                'h_index': getattr(j, 'h_index', None),
                'impact_factor': getattr(j, 'impact_factor', None),
                'tier': getattr(j, 'computed_tier', None),
                'sjr_quartile': getattr(j, 'sjr_quartile', None),
            } for j in journals]
        except Exception as e:
            print(f"[CoResearcher] Journal search error: {e}")
            return []

    def _search_experiments(self, query: str, db, limit=5):
        """Search FailedExperiment table for relevant experiments."""
        from database.models import FailedExperiment
        from sqlalchemy import or_

        try:
            experiments = db.query(FailedExperiment).filter(
                or_(
                    FailedExperiment.title.ilike(f'%{query}%'),
                    FailedExperiment.hypothesis.ilike(f'%{query}%'),
                    FailedExperiment.what_failed.ilike(f'%{query}%'),
                    FailedExperiment.field.ilike(f'%{query}%'),
                )
            ).order_by(FailedExperiment.upvotes.desc()).limit(limit).all()

            return [{
                'source_type': 'reproducibility_archive',
                'title': e.title,
                'field': getattr(e, 'field', ''),
                'category': getattr(e, 'category', ''),
                'hypothesis': getattr(e, 'hypothesis', ''),
                'what_failed': getattr(e, 'what_failed', ''),
                'lessons_learned': getattr(e, 'lessons_learned', ''),
                'upvotes': getattr(e, 'upvotes', 0),
            } for e in experiments]
        except Exception as e:
            print(f"[CoResearcher] Experiment search error: {e}")
            return []

    # =========================================================================
    # SYNTHESIS (STREAMING)
    # =========================================================================

    def _synthesize_stream(self, query, kb_results, pubmed_results, history, session):
        """Stream a synthesized answer from KB + PubMed results."""
        # Format KB results
        kb_context = ""
        kb_sources = kb_results.get("sources", [])
        for i, src in enumerate(kb_sources[:8], 1):
            kb_context += f"[Internal-{i}] {src.get('title', 'Untitled')}: {src.get('content', '')[:400]}\n\n"

        # Format PubMed results
        pubmed_context = ""
        for i, paper in enumerate(pubmed_results[:6], 1):
            authors = ", ".join(paper.get("authors", [])[:3])
            pubmed_context += f"[PubMed-{i}] {paper['title']} ({authors}, {paper.get('year', 'N/A')})\n{paper.get('abstract', '')[:300]}\n\n"

        # Format extra context (journals + experiments) if available
        extra_context = kb_results.get("extra_context", "")

        # Conversation context
        recent = history[-8:] if len(history) > 8 else history
        history_text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in recent])

        messages = [
            {"role": "system", "content": f"""You are a research co-pilot. Synthesize findings from the user's knowledge base and PubMed to answer their question.

Research context: {session.research_question or query}

Instructions:
- Cite sources using [Internal-N] and [PubMed-N] tags
- Distinguish internal knowledge from external papers
- Highlight agreements and contradictions between sources
- Note knowledge gaps if information is incomplete
- Be specific and evidence-based
- Use clear, professional language

When citing information, indicate the source type:
- [KB] for knowledge base documents
- [PubMed] for academic papers
- [Journal DB] for journal database entries
- [Repro Archive] for reproducibility archive experiments"""},
            {"role": "user", "content": f"""Internal Knowledge Base Results:
{kb_context if kb_context else 'No internal documents found.'}

PubMed Results:
{pubmed_context if pubmed_context else 'No PubMed papers found.'}
{extra_context}
Recent conversation:
{history_text}

Question: {query}"""}
        ]

        for chunk in self.openai.chat_completion_stream(messages, temperature=0.4, max_tokens=2000):
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    # =========================================================================
    # HYPOTHESIS EXTRACTION
    # =========================================================================

    def _extract_hypothesis(self, message: str) -> Dict:
        """Extract structured hypothesis from natural language."""
        resp = self.openai.chat_completion(
            messages=[
                {"role": "system", "content": """Extract a structured hypothesis from the user's message.
Return JSON with:
- statement: the hypothesis (e.g., "X leads to Y")
- null_hypothesis: the negation (e.g., "X does NOT lead to Y")
- rationale: brief reason why this is worth testing

Return ONLY valid JSON, no markdown."""},
                {"role": "user", "content": message}
            ],
            temperature=0.2,
            max_tokens=300
        )
        try:
            text = resp.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception:
            return {"statement": message, "null_hypothesis": "", "rationale": ""}

    # =========================================================================
    # EVIDENCE CLASSIFICATION
    # =========================================================================

    def _classify_evidence(self, hypothesis: str, kb_sources: List, pubmed_results: List) -> List[Dict]:
        """Classify each piece of evidence as supporting/contradicting/neutral."""
        evidence_items = []

        # Prepare texts for classification
        items_to_classify = []
        for src in kb_sources[:8]:
            items_to_classify.append({
                "text": f"{src.get('title', '')}: {src.get('content', '')[:300]}",
                "title": src.get("title", "Untitled"),
                "source_type": "internal",
                "source_id": src.get("doc_id"),
            })
        for paper in pubmed_results[:8]:
            items_to_classify.append({
                "text": f"{paper['title']}: {paper.get('abstract', '')[:300]}",
                "title": paper["title"],
                "source_type": "pubmed",
                "source_id": paper.get("pmid"),
                "source_url": paper.get("url"),
            })

        if not items_to_classify:
            return []

        # Batch classify with GPT
        numbered = "\n".join([f"{i+1}. {item['text'][:200]}" for i, item in enumerate(items_to_classify)])
        resp = self.openai.chat_completion(
            messages=[
                {"role": "system", "content": f"""Classify each piece of evidence relative to this hypothesis:
"{hypothesis}"

For each numbered item, respond with a JSON array of objects:
[{{"index": 1, "type": "supporting"|"contradicting"|"neutral", "relevance": 0.0-1.0, "explanation": "brief reason"}}]

Return ONLY the JSON array."""},
                {"role": "user", "content": numbered}
            ],
            temperature=0.2,
            max_tokens=1500
        )

        try:
            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            classifications = json.loads(text)
        except Exception:
            # Fallback: mark all as neutral
            classifications = [{"index": i+1, "type": "neutral", "relevance": 0.5, "explanation": ""} for i in range(len(items_to_classify))]

        for c in classifications:
            idx = c.get("index", 0) - 1
            if 0 <= idx < len(items_to_classify):
                item = items_to_classify[idx]
                evidence_items.append({
                    "title": item["title"],
                    "content": item["text"][:500],
                    "source_type": item["source_type"],
                    "evidence_type": c.get("type", "neutral"),
                    "source_id": item.get("source_id"),
                    "source_url": item.get("source_url"),
                    "relevance_score": c.get("relevance", 0.5),
                    "explanation": c.get("explanation", ""),
                })

        return evidence_items

    # =========================================================================
    # HYPOTHESIS ASSESSMENT (STREAMING)
    # =========================================================================

    def _assess_hypothesis_stream(self, hypothesis, evidence_items):
        """Stream hypothesis assessment. Yields text chunks and a final dict."""
        supporting = [e for e in evidence_items if e["evidence_type"] == "supporting"]
        contradicting = [e for e in evidence_items if e["evidence_type"] == "contradicting"]
        neutral = [e for e in evidence_items if e["evidence_type"] == "neutral"]

        sup_text = "\n".join([f"- {e['title']}: {e.get('explanation', '')}" for e in supporting]) or "None found"
        con_text = "\n".join([f"- {e['title']}: {e.get('explanation', '')}" for e in contradicting]) or "None found"

        messages = [
            {"role": "system", "content": """You are a research hypothesis evaluator. Assess the hypothesis based on evidence.

Provide:
1. Overall assessment (2-3 paragraphs)
2. At the very end, on a new line, output EXACTLY this format:
VERDICT: supported|refuted|inconclusive
CONFIDENCE: 0.XX"""},
            {"role": "user", "content": f"""Hypothesis: {hypothesis.statement}
Null Hypothesis: {hypothesis.null_hypothesis}

Supporting Evidence ({len(supporting)} items):
{sup_text}

Contradicting Evidence ({len(contradicting)} items):
{con_text}

Neutral Evidence: {len(neutral)} items"""}
        ]

        full_text = ""
        for chunk in self.openai.chat_completion_stream(messages, temperature=0.3, max_tokens=1500):
            delta = chunk.choices[0].delta
            if delta and delta.content:
                full_text += delta.content
                yield delta.content

        # Parse verdict and confidence from the end of the response
        status = "inconclusive"
        confidence = 0.5
        for line in full_text.split("\n"):
            line = line.strip()
            if line.startswith("VERDICT:"):
                v = line.split(":", 1)[1].strip().lower()
                if v in ("supported", "refuted", "inconclusive"):
                    status = v
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        yield {"status": status, "confidence": confidence}

    # =========================================================================
    # RESEARCH PLAN GENERATION
    # =========================================================================

    def _generate_research_plan(self, research_question: str) -> List[Dict]:
        """Generate a 3-phase research plan."""
        resp = self.openai.chat_completion(
            messages=[
                {"role": "system", "content": """Generate a research plan with 3 phases for the given research question.
Return JSON array:
[
  {"id": "phase1", "title": "Phase title", "items": [{"text": "Step description", "status": "pending"}]},
  ...
]
Each phase should have 3-4 items. First phase first item should be "active", rest "pending".
Return ONLY valid JSON."""},
                {"role": "user", "content": research_question}
            ],
            temperature=0.3,
            max_tokens=600
        )
        try:
            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            plan = json.loads(text)
            # Ensure first item is active
            if plan and plan[0].get("items"):
                plan[0]["items"][0]["status"] = "active"
            return plan
        except Exception:
            return [
                {"id": "phase1", "title": "Initial research", "items": [
                    {"text": "Review research question", "status": "active"},
                    {"text": "Search knowledge base", "status": "pending"},
                    {"text": "Search external sources", "status": "pending"},
                ]},
                {"id": "phase2", "title": "Deep analysis", "items": [
                    {"text": "Analyze findings", "status": "pending"},
                    {"text": "Test hypotheses", "status": "pending"},
                    {"text": "Cross-reference sources", "status": "pending"},
                ]},
                {"id": "phase3", "title": "Synthesis", "items": [
                    {"text": "Synthesize findings", "status": "pending"},
                    {"text": "Identify knowledge gaps", "status": "pending"},
                    {"text": "Generate recommendations", "status": "pending"},
                ]},
            ]

    def _advance_plan(self, plan: List[Dict], action_type: str) -> List[Dict]:
        """Advance plan items based on completed action."""
        # Mark active items as done and advance to next pending
        found_active = False
        for phase in plan:
            for item in phase.get("items", []):
                if item["status"] == "active":
                    item["status"] = "done"
                    found_active = True
                elif item["status"] == "pending" and found_active:
                    item["status"] = "active"
                    found_active = False
                    break
            if not found_active:
                continue
            break
        return plan

    # =========================================================================
    # RESEARCH BRIEF GENERATION
    # =========================================================================

    def _generate_brief(self, question, answer, kb_sources, pubmed_results, hypothesis=None) -> Dict:
        """Generate/update the research brief."""
        key_points = []
        if kb_sources:
            key_points.append(f"{len(kb_sources)} internal documents analyzed")
        if pubmed_results:
            key_points.append(f"{len(pubmed_results)} PubMed papers found")
        if hypothesis:
            key_points.append(f"Hypothesis: {hypothesis.status.value} (confidence: {hypothesis.confidence_score:.0%})")
            key_points.append(f"{hypothesis.supporting_count} supporting, {hypothesis.contradicting_count} contradicting evidence")

        # Extract key points from answer
        resp = self.openai.chat_completion(
            messages=[
                {"role": "system", "content": "Extract 3-5 key bullet points from this research answer. Return a JSON array of strings. ONLY the JSON array."},
                {"role": "user", "content": answer[:2000]}
            ],
            temperature=0.2,
            max_tokens=300
        )
        try:
            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            extracted = json.loads(text)
            if isinstance(extracted, list):
                key_points.extend(extracted[:5])
        except Exception:
            pass

        return {
            "heading": question[:100] if question else "Research Brief",
            "description": answer[:300] + "..." if len(answer) > 300 else answer,
            "keyPoints": key_points[:8],
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_conversation_history(self, session_id: str, db) -> List[Dict]:
        """Get conversation history as list of {role, content} dicts."""
        messages = db.query(ResearchMessage).filter(
            ResearchMessage.session_id == session_id,
        ).order_by(ResearchMessage.created_at).all()
        return [{"role": m.role, "content": m.content} for m in messages]


# Singleton
_co_researcher_service = None


def get_co_researcher_service() -> CoResearcherService:
    """Get or create singleton CoResearcherService."""
    global _co_researcher_service
    if _co_researcher_service is None:
        _co_researcher_service = CoResearcherService()
    return _co_researcher_service
