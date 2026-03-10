"""
NoveltyVerifier — Verifies novelty claims against existing literature.

Extracts novelty claims from a manuscript, searches OpenAlex for prior work,
and adjusts the novelty score based on literature verification.

Final score = 40% LLM assessment + 60% literature verification.
"""

import json
import re
import time
from typing import List, Dict, Optional

from services.openai_client import get_openai_client


class NoveltyVerifier:
    """Verify novelty claims in a manuscript against published literature."""

    def __init__(self, openai_client=None):
        self.openai = openai_client or get_openai_client()
        self._openalex = None

    @property
    def openalex(self):
        if self._openalex is None:
            from services.openalex_search_service import OpenAlexSearchService
            self._openalex = OpenAlexSearchService()
        return self._openalex

    def verify(self, text: str, title: str = "", llm_novelty_score: int = 50,
               paper_type: str = "experimental") -> Dict:
        """Run full novelty verification pipeline.

        Args:
            text: Full manuscript text
            title: Manuscript title
            llm_novelty_score: Initial novelty score from LLM (0-100)
            paper_type: Detected paper type

        Returns:
            Dict with verified_score, claims, prior_work, verification_details
        """
        try:
            # Step 1: Extract novelty claims from manuscript
            claims = self._extract_novelty_claims(text, title, paper_type)
            if not claims:
                return {
                    "verified_score": llm_novelty_score,
                    "claims": [],
                    "prior_work": [],
                    "verification_summary": "No explicit novelty claims detected.",
                    "score_breakdown": {
                        "llm_component": round(llm_novelty_score * 0.4),
                        "literature_component": round(llm_novelty_score * 0.6),
                    },
                }

            # Step 2: Search OpenAlex for prior work on each claim
            prior_work = self._search_prior_work(claims, title)

            # Step 3: Verify claims against found literature
            verification = self._verify_claims(claims, prior_work, text)

            # Step 4: Calculate final score (40% LLM + 60% literature)
            lit_score = self._calculate_literature_score(verification)
            final_score = round(llm_novelty_score * 0.4 + lit_score * 0.6)
            final_score = min(100, max(0, final_score))

            return {
                "verified_score": final_score,
                "claims": verification,
                "prior_work": prior_work[:10],  # cap for response size
                "verification_summary": self._summarize_verification(verification),
                "score_breakdown": {
                    "llm_component": round(llm_novelty_score * 0.4),
                    "literature_component": round(lit_score * 0.6),
                    "llm_raw": llm_novelty_score,
                    "literature_raw": lit_score,
                },
            }
        except Exception as e:
            print(f"[NoveltyVerifier] Verification failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "verified_score": llm_novelty_score,
                "claims": [],
                "prior_work": [],
                "verification_summary": f"Verification unavailable: {e}",
                "score_breakdown": {
                    "llm_component": round(llm_novelty_score * 0.4),
                    "literature_component": round(llm_novelty_score * 0.6),
                },
                "error": str(e),
            }

    def _extract_novelty_claims(self, text: str, title: str,
                                 paper_type: str) -> List[Dict]:
        """Use LLM to extract explicit novelty claims from the manuscript."""
        sample = text[:12000]

        type_context = ""
        if paper_type == "review":
            type_context = (
                "This is a REVIEW paper. Novelty claims may include: "
                "first comprehensive review of X, novel taxonomy/framework, "
                "new synthesis connecting previously unrelated fields, "
                "identification of previously unrecognized research gaps."
            )
        elif paper_type == "meta_analysis":
            type_context = (
                "This is a META-ANALYSIS. Novelty claims may include: "
                "first meta-analysis of X, largest pooled sample for Y, "
                "novel subgroup analysis, new methodological approach to pooling."
            )
        elif paper_type == "protocol":
            type_context = (
                "This is a PROTOCOL paper. Novelty claims may include: "
                "novel technique, improved efficiency over existing methods, "
                "first application to this model system, simplified procedure."
            )

        prompt = (
            "Extract all NOVELTY CLAIMS from this manuscript. A novelty claim is "
            "any statement where the authors assert they are doing something new, "
            "first, or different from prior work.\n\n"
            f"{type_context}\n\n"
            "Look for phrases like:\n"
            "- 'for the first time', 'novel', 'unprecedented', 'we are the first'\n"
            "- 'no previous study has', 'unlike prior work', 'in contrast to'\n"
            "- 'we propose a new', 'our approach differs', 'not been explored'\n"
            "- 'to our knowledge', 'hitherto unknown', 'we demonstrate for the first time'\n\n"
            f"TITLE: {title}\n\n"
            f"TEXT:\n{sample}\n\n"
            "Return JSON:\n"
            '{"claims": [\n'
            '  {\n'
            '    "claim": "The specific novelty claim (verbatim or close paraphrase)",\n'
            '    "search_query": "A concise search query to find prior work on this topic (5-10 words)",\n'
            '    "claim_type": "first_study|new_method|new_finding|new_framework|improved_method|new_application",\n'
            '    "strength": "strong|moderate|weak",\n'
            '    "section": "where in the paper this claim appears (abstract/intro/discussion)"\n'
            '  }\n'
            ']}\n\n'
            "Extract up to 5 claims. If no novelty claims are found, return {\"claims\": []}."
        )

        try:
            resp = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": "Extract novelty claims. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            result = json.loads(raw)
            return result.get("claims", [])[:5]
        except Exception as e:
            print(f"[NoveltyVerifier] Claim extraction failed: {e}")
            return []

    def _search_prior_work(self, claims: List[Dict],
                            title: str) -> List[Dict]:
        """Search OpenAlex for prior work related to each novelty claim."""
        all_prior = []
        seen_dois = set()

        for claim in claims:
            query = claim.get("search_query", "")
            if not query:
                continue

            try:
                works = self.openalex.search_works(
                    query,
                    max_results=5,
                    min_citations=2,
                )
                for work in works:
                    doi = work.get("doi", "")
                    work_title = work.get("title", "")
                    # Skip self-matches
                    if work_title and title and (
                        work_title.lower().strip() == title.lower().strip()
                    ):
                        continue
                    # Dedup by DOI
                    if doi and doi in seen_dois:
                        continue
                    if doi:
                        seen_dois.add(doi)

                    all_prior.append({
                        "title": work_title,
                        "doi": doi,
                        "year": work.get("year"),
                        "citations": work.get("cited_by_count", 0),
                        "authors": work.get("authors", ""),
                        "journal": work.get("journal", ""),
                        "related_claim": claim.get("claim", ""),
                        "search_query": query,
                    })
            except Exception as e:
                print(f"[NoveltyVerifier] OpenAlex search failed for '{query}': {e}")
                continue

        return all_prior

    def _verify_claims(self, claims: List[Dict], prior_work: List[Dict],
                        text: str) -> List[Dict]:
        """Verify each novelty claim against the found prior work."""
        if not prior_work:
            # No prior work found — claims are likely novel
            return [
                {
                    **claim,
                    "status": "likely_novel",
                    "confidence": "moderate",
                    "conflicting_papers": [],
                    "reasoning": "No closely related prior work found in OpenAlex.",
                }
                for claim in claims
            ]

        # Group prior work by the claim it relates to
        claim_prior = {}
        for pw in prior_work:
            related = pw.get("related_claim", "")
            if related not in claim_prior:
                claim_prior[related] = []
            claim_prior[related].append(pw)

        # Use LLM to assess each claim against its prior work
        verified = []
        for claim in claims:
            claim_text = claim.get("claim", "")
            related_papers = claim_prior.get(claim_text, [])

            if not related_papers:
                verified.append({
                    **claim,
                    "status": "likely_novel",
                    "confidence": "moderate",
                    "conflicting_papers": [],
                    "reasoning": "No prior work found for this specific claim.",
                })
                continue

            # Format prior work for LLM assessment
            papers_text = "\n".join(
                f"- {p['title']} ({p.get('year', '?')}, {p.get('citations', 0)} citations) "
                f"[{p.get('journal', 'Unknown')}]"
                for p in related_papers[:5]
            )

            prompt = (
                f"NOVELTY CLAIM from manuscript: \"{claim_text}\"\n\n"
                f"POTENTIALLY RELATED PRIOR WORK:\n{papers_text}\n\n"
                "Based on the titles and metadata of these prior papers, assess:\n"
                "1. Does any prior paper appear to have already done what this claim says is novel?\n"
                "2. Is this claim still likely novel despite related work existing?\n\n"
                "Respond in JSON:\n"
                '{"status": "novel|partially_novel|likely_not_novel|uncertain", '
                '"confidence": "high|moderate|low", '
                '"reasoning": "1-2 sentence explanation", '
                '"conflicting_paper_indices": [0, 1]}\n\n'
                "conflicting_paper_indices should list the 0-based indices of papers "
                "that most directly challenge this novelty claim. Empty list if none."
            )

            try:
                resp = self.openai.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a novelty assessor. Respond only in valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=300,
                    response_format={"type": "json_object"},
                )
                raw = resp.choices[0].message.content.strip()
                assessment = json.loads(raw)

                conflicting_indices = assessment.get("conflicting_paper_indices", [])
                conflicting = [
                    related_papers[i] for i in conflicting_indices
                    if isinstance(i, int) and 0 <= i < len(related_papers)
                ]

                verified.append({
                    **claim,
                    "status": assessment.get("status", "uncertain"),
                    "confidence": assessment.get("confidence", "low"),
                    "conflicting_papers": conflicting,
                    "reasoning": assessment.get("reasoning", ""),
                })
            except Exception as e:
                print(f"[NoveltyVerifier] Claim verification failed: {e}")
                verified.append({
                    **claim,
                    "status": "uncertain",
                    "confidence": "low",
                    "conflicting_papers": [],
                    "reasoning": f"Verification error: {e}",
                })

        return verified

    def _calculate_literature_score(self, verified_claims: List[Dict]) -> int:
        """Calculate a literature-based novelty score from verified claims.

        Scoring:
        - novel → 90-100 points
        - partially_novel → 60-75 points
        - likely_not_novel → 20-40 points
        - uncertain → 50-60 points
        """
        if not verified_claims:
            return 70  # Default when no claims to verify

        status_scores = {
            "novel": 95,
            "likely_novel": 90,
            "partially_novel": 68,
            "likely_not_novel": 30,
            "uncertain": 55,
        }

        confidence_multipliers = {
            "high": 1.0,
            "moderate": 0.9,
            "low": 0.8,
        }

        total = 0
        for claim in verified_claims:
            base = status_scores.get(claim.get("status", "uncertain"), 55)
            mult = confidence_multipliers.get(claim.get("confidence", "low"), 0.8)
            total += base * mult

        avg = total / len(verified_claims)
        return min(100, max(0, round(avg)))

    def _summarize_verification(self, verified_claims: List[Dict]) -> str:
        """Generate a human-readable summary of verification results."""
        if not verified_claims:
            return "No novelty claims were found to verify."

        novel_count = sum(
            1 for c in verified_claims
            if c.get("status") in ("novel", "likely_novel")
        )
        partial_count = sum(
            1 for c in verified_claims
            if c.get("status") == "partially_novel"
        )
        challenged_count = sum(
            1 for c in verified_claims
            if c.get("status") == "likely_not_novel"
        )

        parts = []
        total = len(verified_claims)
        parts.append(f"Verified {total} novelty claim{'s' if total != 1 else ''}.")

        if novel_count:
            parts.append(f"{novel_count} confirmed as likely novel.")
        if partial_count:
            parts.append(f"{partial_count} partially novel (related work exists but differs).")
        if challenged_count:
            parts.append(
                f"{challenged_count} potentially challenged by existing literature — "
                "authors should acknowledge prior work."
            )

        return " ".join(parts)


# Singleton
_novelty_verifier = None


def get_novelty_verifier() -> NoveltyVerifier:
    global _novelty_verifier
    if _novelty_verifier is None:
        _novelty_verifier = NoveltyVerifier()
    return _novelty_verifier
