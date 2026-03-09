"""
Feasibility Checker v2 — Graph-backed + RAG + LLM protocol feasibility validation.

Validates proposed experiments by checking:
1. Co-occurrence evidence from protocol corpus (technique-reagent-system compatibility)
2. Similar protocols from BioProBench/protocols.io corpus (RAG)
3. LLM reasoning with graph evidence and protocol context

Behind the protocol_reasoning() abstraction — can be swapped for fine-tuned model later.
"""

import os
import json
import logging
from typing import Optional

from database.models import (
    SessionLocal, ProtocolEntity, ProtocolRelation, ProtocolCooccurrence
)

logger = logging.getLogger(__name__)


class FeasibilityChecker:
    """Graph-backed feasibility validation for proposed experiments."""

    def __init__(self, llm_client=None, chat_deployment: str = None, vector_store=None):
        self.client = llm_client
        self.deployment = chat_deployment or os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")
        self.vector_store = vector_store  # Pinecone store for RAG

    def check(self, experiment: dict, tenant_id: str = None, biological_context: dict = None) -> dict:
        """
        Validate a proposed experiment for feasibility.

        Args:
            experiment: {title, methodology, required_resources, hypothesis, ...}
            tenant_id: Optional tenant for tenant-specific graph data
            biological_context: {organism, cell_type, tissue, disease_model} from manuscript

        Returns:
            {
                score: 0.0-1.0,
                tier: "high"|"medium"|"low"|"infeasible",
                issues: [{type, description, severity, evidence}],
                modifications: [{original, suggested, reason}],
                evidence: {cooccurrence_hits, corpus_matches, negative_evidence},
                reasoning: str
            }
        """
        # Step 1: Extract technique-reagent-system triples from proposal
        triples = self._extract_triples(experiment, biological_context)

        # Step 2: Query co-occurrence graph
        cooccurrence_evidence = self._query_cooccurrences(triples, tenant_id)

        # Step 3: RAG over protocol corpus for similar protocols
        corpus_matches = self._search_protocol_corpus(experiment, biological_context)

        # Step 4: LLM reasoning with all evidence
        result = self._reason_about_feasibility(
            experiment, biological_context, triples,
            cooccurrence_evidence, corpus_matches
        )

        return result

    def _extract_triples(self, experiment: dict, bio_context: dict = None) -> list:
        """Extract technique-reagent-system triples from experiment proposal."""
        triples = []

        methodology = experiment.get("methodology", "")
        resources = experiment.get("required_resources", [])
        title = experiment.get("title", "")
        full_text = f"{title}. {methodology}. {'. '.join(resources) if isinstance(resources, list) else resources}"

        if not self.client:
            return triples

        try:
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_MINI_DEPLOYMENT", "gpt-4o-mini") or self.deployment,
                messages=[
                    {"role": "system", "content": (
                        "Extract technique-reagent-system triples from this experiment proposal. "
                        "Return JSON: {\"triples\": [{\"technique\": \"...\", \"reagent\": \"...\", "
                        "\"system\": \"...\", \"equipment\": \"...\"}]}. "
                        "Each triple should have at least technique + one other field. "
                        "Use null for unknown fields."
                    )},
                    {"role": "user", "content": f"Experiment: {full_text[:2000]}"
                     + (f"\nBiological context: organism={bio_context.get('organism','')}, "
                        f"cell_type={bio_context.get('cell_type','')}, "
                        f"tissue={bio_context.get('tissue','')}"
                        if bio_context else "")},
                ],
                max_tokens=500,
                temperature=0,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            triples = result.get("triples", [])
        except Exception as e:
            logger.warning(f"Triple extraction failed: {e}")

        return triples

    def _query_cooccurrences(self, triples: list, tenant_id: str = None) -> dict:
        """Query co-occurrence graph for evidence about each triple."""
        evidence = {
            "supported": [],      # Pairs with high co-occurrence
            "unsupported": [],    # Pairs with zero co-occurrence (potential issue)
            "unknown": [],        # Entities not in graph
            "total_checked": 0,
        }

        if not triples:
            return evidence

        db = SessionLocal()
        try:
            for triple in triples:
                technique_name = (triple.get("technique") or "").lower().strip()
                if not technique_name:
                    continue

                # Find technique entity
                technique = db.query(ProtocolEntity).filter(
                    ProtocolEntity.normalized_name == technique_name,
                    ProtocolEntity.entity_type == 'technique',
                ).first()

                if not technique:
                    # Try fuzzy match
                    technique = db.query(ProtocolEntity).filter(
                        ProtocolEntity.entity_type == 'technique',
                        ProtocolEntity.normalized_name.ilike(f"%{technique_name}%"),
                    ).first()

                if not technique:
                    evidence["unknown"].append({"technique": technique_name, "reason": "not in graph"})
                    continue

                # Check each target in the triple
                for target_field, target_type in [
                    ("reagent", "reagent"), ("system", "organism"),
                    ("system", "cell_line"), ("equipment", "equipment")
                ]:
                    target_name = (triple.get(target_field) or "").lower().strip()
                    if not target_name:
                        continue

                    evidence["total_checked"] += 1

                    # Look up co-occurrence
                    target = db.query(ProtocolEntity).filter(
                        ProtocolEntity.normalized_name.ilike(f"%{target_name}%"),
                    ).first()

                    if not target:
                        evidence["unknown"].append({
                            "technique": technique_name,
                            target_field: target_name,
                            "reason": f"{target_field} not in graph"
                        })
                        continue

                    cooc = db.query(ProtocolCooccurrence).filter(
                        ProtocolCooccurrence.technique_entity_id == technique.id,
                        ProtocolCooccurrence.target_entity_id == target.id,
                    ).first()

                    if cooc and cooc.cooccurrence_count > 0:
                        evidence["supported"].append({
                            "technique": technique_name,
                            target_field: target_name,
                            "count": cooc.cooccurrence_count,
                            "confidence": cooc.confidence,
                            "sources": len(cooc.source_protocols or []),
                        })
                    else:
                        # Check if there's a conflicts_with relation
                        conflict = db.query(ProtocolRelation).filter(
                            ProtocolRelation.source_entity_id == technique.id,
                            ProtocolRelation.target_entity_id == target.id,
                            ProtocolRelation.relation_type == 'conflicts_with',
                        ).first()

                        evidence["unsupported"].append({
                            "technique": technique_name,
                            target_field: target_name,
                            "has_conflict": conflict is not None,
                            "conflict_context": conflict.context if conflict else None,
                        })
        except Exception as e:
            logger.error(f"Co-occurrence query error: {e}")
        finally:
            db.close()

        return evidence

    def _search_protocol_corpus(self, experiment: dict, bio_context: dict = None) -> list:
        """RAG over protocol corpus (BioProBench + protocols.io) in Pinecone."""
        matches = []

        if not self.vector_store:
            # Try protocol reference store as fallback
            try:
                from services.protocol_reference_store import get_store
                store = get_store()
                if store and store.loaded:
                    query_text = f"{experiment.get('title', '')} {experiment.get('methodology', '')}"
                    results = store.find_similar_protocols(query_text[:500], top_k=5)
                    for r in results:
                        matches.append({
                            "title": r.get("title", ""),
                            "domain": r.get("domain", ""),
                            "similarity": r.get("similarity", 0),
                            "source": "reference_store",
                        })
            except Exception as e:
                logger.debug(f"Reference store fallback failed: {e}")
            return matches

        try:
            query_text = f"{experiment.get('title', '')} {experiment.get('methodology', '')}"
            if bio_context:
                query_text += f" {bio_context.get('organism', '')} {bio_context.get('cell_type', '')}"

            # Search protocol-corpus namespace
            results = self.vector_store.search(
                query=query_text[:500],
                top_k=5,
                namespace="protocol-corpus",
            )
            for r in results:
                matches.append({
                    "title": r.get("metadata", {}).get("title", ""),
                    "content": r.get("metadata", {}).get("text", "")[:500],
                    "domain": r.get("metadata", {}).get("domain", ""),
                    "source": r.get("metadata", {}).get("source", ""),
                    "similarity": r.get("score", 0),
                })
        except Exception as e:
            logger.debug(f"Protocol corpus search failed: {e}")

        return matches

    def _reason_about_feasibility(self, experiment: dict, bio_context: dict,
                                   triples: list, cooccurrence: dict,
                                   corpus_matches: list) -> dict:
        """LLM reasoning about feasibility using all collected evidence."""

        # Build evidence summary
        evidence_text = self._format_evidence(cooccurrence, corpus_matches)

        if not self.client:
            # No LLM available — score from co-occurrence data alone
            return self._score_from_evidence_only(cooccurrence)

        try:
            system_prompt = """You are an experienced lab manager evaluating experiment feasibility.
You receive a proposed experiment, its biological context, and evidence from a protocol knowledge graph.

Evaluate feasibility and return JSON:
{
    "score": 0.0-1.0,
    "tier": "high"|"medium"|"low"|"infeasible",
    "issues": [{"type": "incompatibility|missing_resource|parameter_concern|timeline_risk", "description": "...", "severity": "critical|warning|info"}],
    "modifications": [{"original": "what was proposed", "suggested": "what would work", "reason": "why"}],
    "reasoning": "2-3 sentence explanation"
}

Score guide:
- 0.8-1.0 (high): Well-supported by evidence, standard combinations
- 0.5-0.8 (medium): Partially supported, some concerns but workable
- 0.2-0.5 (low): Significant issues, needs major modifications
- 0.0-0.2 (infeasible): Fundamental incompatibilities found"""

            bio_text = ""
            if bio_context:
                bio_text = f"\nBiological context: {json.dumps(bio_context)}"

            user_prompt = f"""Evaluate this experiment:

Title: {experiment.get('title', 'Untitled')}
Hypothesis: {experiment.get('hypothesis', 'Not specified')}
Methodology: {experiment.get('methodology', 'Not specified')}
Required resources: {json.dumps(experiment.get('required_resources', []))}
{bio_text}

Evidence from protocol knowledge graph:
{evidence_text}

Return your feasibility assessment as JSON."""

            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=800,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            # Normalize and validate
            score = min(1.0, max(0.0, float(result.get("score", 0.5))))
            tier = result.get("tier", "medium")
            if tier not in ("high", "medium", "low", "infeasible"):
                tier = "high" if score >= 0.8 else "medium" if score >= 0.5 else "low" if score >= 0.2 else "infeasible"

            return {
                "score": score,
                "tier": tier,
                "issues": result.get("issues", []),
                "modifications": result.get("modifications", []),
                "evidence": {
                    "cooccurrence_hits": len(cooccurrence.get("supported", [])),
                    "unsupported_pairs": len(cooccurrence.get("unsupported", [])),
                    "unknown_entities": len(cooccurrence.get("unknown", [])),
                    "corpus_matches": len(corpus_matches),
                    "total_checked": cooccurrence.get("total_checked", 0),
                },
                "reasoning": result.get("reasoning", ""),
            }

        except Exception as e:
            logger.error(f"Feasibility reasoning failed: {e}")
            return self._score_from_evidence_only(cooccurrence)

    def _format_evidence(self, cooccurrence: dict, corpus_matches: list) -> str:
        """Format evidence for LLM prompt."""
        lines = []

        supported = cooccurrence.get("supported", [])
        if supported:
            lines.append("SUPPORTED combinations (found in protocol corpus):")
            for s in supported[:10]:
                technique = s.get("technique", "?")
                target_fields = [f"{k}: {v}" for k, v in s.items()
                                if k not in ("technique", "count", "confidence", "sources")]
                lines.append(f"  - {technique} + {', '.join(target_fields)} "
                           f"(seen {s.get('count', 0)} times, {s.get('sources', 0)} sources)")

        unsupported = cooccurrence.get("unsupported", [])
        if unsupported:
            lines.append("\nUNSUPPORTED combinations (not found or conflicting):")
            for u in unsupported[:10]:
                technique = u.get("technique", "?")
                target_fields = [f"{k}: {v}" for k, v in u.items()
                                if k not in ("technique", "has_conflict", "conflict_context")]
                conflict_note = f" — CONFLICT: {u['conflict_context']}" if u.get("has_conflict") else ""
                lines.append(f"  - {technique} + {', '.join(target_fields)}{conflict_note}")

        unknown = cooccurrence.get("unknown", [])
        if unknown:
            lines.append(f"\nUNKNOWN: {len(unknown)} entities not found in protocol graph")

        if corpus_matches:
            lines.append("\nSimilar protocols found in corpus:")
            for m in corpus_matches[:5]:
                lines.append(f"  - {m.get('title', 'Untitled')} ({m.get('domain', '')}), "
                           f"similarity: {m.get('similarity', 0):.2f}")

        if not lines:
            lines.append("No evidence found in protocol knowledge graph (graph may not be populated yet)")

        return "\n".join(lines)

    def _score_from_evidence_only(self, cooccurrence: dict) -> dict:
        """Score feasibility from co-occurrence data alone (no LLM)."""
        supported = len(cooccurrence.get("supported", []))
        unsupported = len(cooccurrence.get("unsupported", []))
        conflicts = sum(1 for u in cooccurrence.get("unsupported", []) if u.get("has_conflict"))
        total = cooccurrence.get("total_checked", 0)

        if total == 0:
            score = 0.5  # Unknown
            tier = "medium"
            reasoning = "No co-occurrence data available; feasibility undetermined"
        elif conflicts > 0:
            score = max(0.0, 0.3 - (conflicts * 0.15))
            tier = "infeasible" if score < 0.2 else "low"
            reasoning = f"Found {conflicts} known conflicts in protocol graph"
        elif unsupported > supported:
            score = max(0.2, 0.5 - (unsupported - supported) * 0.1)
            tier = "low"
            reasoning = f"More unsupported ({unsupported}) than supported ({supported}) combinations"
        else:
            ratio = supported / max(1, total)
            score = min(1.0, 0.5 + ratio * 0.5)
            tier = "high" if score >= 0.8 else "medium"
            reasoning = f"{supported}/{total} technique-resource pairs validated in protocol corpus"

        return {
            "score": score,
            "tier": tier,
            "issues": [{"type": "incompatibility", "description": u.get("conflict_context", "Unknown conflict"), "severity": "critical"}
                       for u in cooccurrence.get("unsupported", []) if u.get("has_conflict")],
            "modifications": [],
            "evidence": {
                "cooccurrence_hits": supported,
                "unsupported_pairs": unsupported,
                "unknown_entities": len(cooccurrence.get("unknown", [])),
                "corpus_matches": 0,
                "total_checked": total,
            },
            "reasoning": reasoning,
        }


def protocol_reasoning(experiment: dict, tenant_id: str = None,
                       biological_context: dict = None,
                       llm_client=None, vector_store=None) -> dict:
    """
    Top-level function for protocol feasibility reasoning.
    Abstraction layer — currently uses FeasibilityChecker (graph + RAG + LLM).
    Can be swapped for a fine-tuned model endpoint later.
    """
    checker = FeasibilityChecker(
        llm_client=llm_client,
        vector_store=vector_store,
    )
    return checker.check(experiment, tenant_id, biological_context)
