"""
Grant Finder Service
Searches NIH RePORTER and Grants.gov APIs, scores results against lab knowledge base.
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Optional, Any, Tuple
from collections import Counter
from datetime import datetime

from services.openai_client import get_openai_client
from vector_stores.pinecone_store import get_vector_store

logger = logging.getLogger(__name__)

# API Endpoints (no keys required)
NIH_REPORTER_URL = "https://api.reporter.nih.gov/v2/projects/search"
GRANTS_GOV_URL = "https://api.grants.gov/v1/api/search2"

# Activity code descriptions
ACTIVITY_CODE_LABELS = {
    "R01": "Research Project Grant",
    "R21": "Exploratory/Developmental Research",
    "R03": "Small Research Grant",
    "R35": "Outstanding Investigator Award",
    "R41": "SBIR Phase I",
    "R42": "SBIR Phase II",
    "R43": "STTR Phase I",
    "R44": "STTR Phase II",
    "U01": "Cooperative Agreement",
    "P01": "Program Project Grant",
    "K01": "Mentored Research Scientist Career Dev",
    "K99": "Pathway to Independence Award",
    "F31": "Predoctoral Fellowship",
    "F32": "Postdoctoral Fellowship",
    "T32": "Training Grant",
}


class GrantFinderService:
    """
    Searches federal grant databases and scores results against lab context.
    """

    def __init__(self):
        self._client = None
        self._vector_store = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_openai_client()
        return self._client

    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    # ========================================================================
    # NIH REPORTER
    # ========================================================================

    def search_nih_reporter(
        self,
        query: str,
        agencies: Optional[List[str]] = None,
        activity_codes: Optional[List[str]] = None,
        amount_min: Optional[int] = None,
        amount_max: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search NIH RePORTER for funded projects."""
        try:
            criteria = {
                "include_active_projects": True,
                "exclude_subprojects": True,
                "fiscal_years": [2024, 2025, 2026],
            }

            if query:
                criteria["advanced_text_search"] = {
                    "operator": "and",
                    "search_field": "projecttitle,abstracttext,terms",
                    "search_text": query
                }

            if activity_codes:
                criteria["activity_codes"] = activity_codes

            if amount_min or amount_max:
                criteria["award_amount_range"] = {}
                if amount_min:
                    criteria["award_amount_range"]["min_amount"] = amount_min
                if amount_max:
                    criteria["award_amount_range"]["max_amount"] = amount_max

            body = {
                "criteria": criteria,
                "offset": 0,
                "limit": min(limit, 50),
                "sort_field": "project_start_date",
                "sort_order": "desc",
                "include_fields": [
                    "ApplId", "ProjectNum", "ProjectTitle", "AbstractText",
                    "Organization", "AwardAmount", "IsActive",
                    "ProjectStartDate", "ProjectEndDate",
                    "PrincipalInvestigators", "AgencyIcAdmin",
                    "AgencyIcFundings", "ActivityCode"
                ]
            }

            resp = requests.post(NIH_REPORTER_URL, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("results", []):
                # Extract PI name
                pis = item.get("principal_investigators") or []
                contact_pi = next((p for p in pis if p.get("is_contact_pi")), pis[0] if pis else {})
                pi_name = contact_pi.get("full_name", "").strip() or "Unknown PI"
                pi_title = contact_pi.get("title", "")

                # Extract agency
                agency_info = item.get("agency_ic_admin") or {}
                agency_abbr = agency_info.get("abbreviation", "NIH")
                agency_full = agency_info.get("name", "National Institutes of Health")

                # Extract org
                org_info = item.get("organization") or {}
                org_name = org_info.get("org_name", "")
                org_city = org_info.get("org_city", "")
                org_state = org_info.get("org_state", "")

                # Extract funding
                fundings = item.get("agency_ic_fundings") or []
                total_cost = sum(f.get("total_cost", 0) or 0 for f in fundings)
                award_amount = total_cost or item.get("award_amount") or 0

                results.append({
                    "id": f"nih_{item.get('appl_id', '')}",
                    "source": "nih_reporter",
                    "title": (item.get("project_title") or "Untitled").strip(),
                    "abstract": (item.get("abstract_text") or "").strip(),
                    "agency": agency_abbr,
                    "agency_full": agency_full,
                    "pi_name": pi_name,
                    "pi_title": pi_title,
                    "organization": org_name,
                    "org_location": f"{org_city}, {org_state}" if org_city else "",
                    "award_amount": int(award_amount),
                    "start_date": item.get("project_start_date", ""),
                    "end_date": item.get("project_end_date", ""),
                    "deadline": None,  # NIH Reporter shows funded projects, not open calls
                    "activity_code": item.get("activity_code", ""),
                    "project_num": item.get("project_num", ""),
                    "status": "active" if item.get("is_active") else "completed",
                    "url": f"https://reporter.nih.gov/project-details/{item.get('appl_id', '')}",
                    "fit_score": 0,
                    "fit_reasons": [],
                    "matching_docs": []
                })

            logger.info(f"[GrantFinder] NIH RePORTER returned {len(results)} results for '{query}'")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"[GrantFinder] NIH RePORTER API error: {e}")
            return []
        except Exception as e:
            logger.error(f"[GrantFinder] NIH RePORTER parse error: {e}")
            return []

    # ========================================================================
    # GRANTS.GOV
    # ========================================================================

    def search_grants_gov(
        self,
        query: str,
        agencies: Optional[List[str]] = None,
        amount_min: Optional[int] = None,
        amount_max: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search Grants.gov for open funding opportunities."""
        try:
            body = {
                "keyword": query,
                "oppStatuses": "posted|forecasted",
                "rows": min(limit, 25),
                "startRecordNum": 0,
                "sortBy": "openDate|desc"
            }

            # Filter by agency if specified
            if agencies:
                # Grants.gov uses agency codes like "NSF", "HHS-NIH", "DOD"
                body["agencies"] = ",".join(agencies)

            # Filter by funding category for science/research
            body["fundingCategories"] = "ST"  # Science & Technology

            resp = requests.post(GRANTS_GOV_URL, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("data", {}).get("oppHits", []):
                # Parse dates
                open_date = item.get("openDate", "")
                close_date = item.get("closeDate", "")

                results.append({
                    "id": f"grants_gov_{item.get('id', '')}",
                    "source": "grants_gov",
                    "title": (item.get("title") or "Untitled").strip(),
                    "abstract": "",  # Grants.gov search doesn't return abstracts
                    "agency": item.get("agencyCode", "").split("-")[0],  # "HHS-NIH" -> "HHS"
                    "agency_full": item.get("agency", ""),
                    "pi_name": "",
                    "pi_title": "",
                    "organization": "",
                    "org_location": "",
                    "award_amount": 0,  # Not in search results
                    "start_date": open_date,
                    "end_date": "",
                    "deadline": close_date if close_date else None,
                    "activity_code": "",
                    "project_num": item.get("number", ""),
                    "status": item.get("oppStatus", "posted"),
                    "url": f"https://www.grants.gov/search-results-detail/{item.get('id', '')}",
                    "fit_score": 0,
                    "fit_reasons": [],
                    "matching_docs": []
                })

            logger.info(f"[GrantFinder] Grants.gov returned {len(results)} results for '{query}'")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"[GrantFinder] Grants.gov API error: {e}")
            return []
        except Exception as e:
            logger.error(f"[GrantFinder] Grants.gov parse error: {e}")
            return []

    # ========================================================================
    # NSF AWARD SEARCH (National Science Foundation)
    # ========================================================================

    def search_nsf_awards(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict]:
        """Search NSF Award Search API for funded research grants."""
        try:
            params = {
                "keyword": query,
                "printFields": "id,title,abstractText,agency,piFirstName,piLastName,piEmail,awardeeName,awardeeCity,awardeeStateCode,startDate,expDate,fundsObligatedAmt,fundProgramName,primaryProgram",
                "offset": 1,
                "rpp": min(limit, 25)
            }

            resp = requests.get(
                "https://api.nsf.gov/services/v1/awards.json",
                params=params,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("response", {}).get("award", []):
                pi_name = f"{item.get('piFirstName', '')} {item.get('piLastName', '')}".strip()
                location = f"{item.get('awardeeCity', '')}, {item.get('awardeeStateCode', '')}".strip(', ')

                results.append({
                    "id": f"nsf_{item.get('id', '')}",
                    "source": "nsf",
                    "title": (item.get("title") or "Untitled").strip(),
                    "abstract": (item.get("abstractText") or "")[:2000],
                    "agency": "NSF",
                    "agency_full": "National Science Foundation",
                    "pi_name": pi_name,
                    "pi_title": "",
                    "organization": item.get("awardeeName", ""),
                    "org_location": location,
                    "award_amount": int(item.get("fundsObligatedAmt", 0) or 0),
                    "start_date": item.get("startDate", ""),
                    "end_date": item.get("expDate", ""),
                    "deadline": None,
                    "activity_code": item.get("primaryProgram", ""),
                    "project_num": item.get("id", ""),
                    "status": "active",
                    "url": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={item.get('id', '')}",
                    "fit_score": 0,
                    "fit_reasons": [],
                    "matching_docs": []
                })

            logger.info(f"[GrantFinder] NSF returned {len(results)} results for '{query}'")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"[GrantFinder] NSF API error: {e}")
            return []
        except Exception as e:
            logger.error(f"[GrantFinder] NSF parse error: {e}")
            return []

    # ========================================================================
    # COMBINED SEARCH + SCORING
    # ========================================================================

    def search(
        self,
        query: str,
        tenant_id: str,
        lab_profile: Optional[Dict] = None,
        agencies: Optional[List[str]] = None,
        activity_codes: Optional[List[str]] = None,
        amount_min: Optional[int] = None,
        amount_max: Optional[int] = None,
        limit: int = 20
    ) -> Dict:
        """
        Search both APIs, score results against lab context, return ranked results.
        """
        # Query both APIs
        nih_results = self.search_nih_reporter(
            query=query,
            activity_codes=activity_codes,
            amount_min=amount_min,
            amount_max=amount_max,
            limit=limit
        )
        grants_gov_results = self.search_grants_gov(
            query=query,
            agencies=agencies,
            amount_min=amount_min,
            amount_max=amount_max,
            limit=limit
        )

        # Combine
        all_results = nih_results + grants_gov_results

        if not all_results:
            return {
                "results": [],
                "total": 0,
                "sources": {"nih_reporter": 0, "grants_gov": 0}
            }

        # Score against lab context
        scored = self._score_results(all_results, tenant_id, lab_profile or {})

        # Sort by fit_score descending
        scored.sort(key=lambda x: x["fit_score"], reverse=True)

        return {
            "results": scored[:limit],
            "total": len(all_results),
            "sources": {
                "nih_reporter": len(nih_results),
                "grants_gov": len(grants_gov_results)
            }
        }

    def _score_results(
        self,
        results: List[Dict],
        tenant_id: str,
        lab_profile: Dict
    ) -> List[Dict]:
        """Score each grant result against lab's knowledge base."""
        profile_keywords = set(
            [k.lower() for k in lab_profile.get("keywords", [])] +
            [a.lower() for a in lab_profile.get("research_areas", [])]
        )
        preferred_agencies = set(
            a.upper() for a in lab_profile.get("preferred_agencies", [])
        )
        preferred_codes = set(lab_profile.get("activity_codes", []))

        for result in results:
            try:
                # Build text for similarity search
                search_text = f"{result['title']} {result['abstract']}"
                if len(search_text.strip()) < 20:
                    search_text = result['title']

                if len(search_text.strip()) < 5:
                    result["fit_score"] = 0
                    continue

                # 1. Semantic similarity (60% weight)
                # Search lab's Pinecone namespace for similar documents
                try:
                    pinecone_results = self.vector_store.search(
                        query=search_text[:500],  # Truncate for embedding
                        tenant_id=tenant_id,
                        top_k=5
                    )
                    if pinecone_results:
                        avg_sim = sum(r["score"] for r in pinecone_results) / len(pinecone_results)
                        semantic_score = min(avg_sim * 100, 100)

                        # Add matching docs info
                        result["matching_docs"] = [
                            {
                                "id": r.get("doc_id", ""),
                                "title": r.get("title", "Untitled"),
                                "similarity": round(r["score"], 3)
                            }
                            for r in pinecone_results[:3]
                            if r["score"] > 0.3
                        ]
                    else:
                        semantic_score = 0
                except Exception as e:
                    logger.warning(f"[GrantFinder] Pinecone search failed: {e}")
                    semantic_score = 0

                # 2. Keyword overlap (25% weight)
                if profile_keywords:
                    grant_text_lower = search_text.lower()
                    matches = sum(1 for kw in profile_keywords if kw in grant_text_lower)
                    keyword_score = min((matches / max(len(profile_keywords), 1)) * 100, 100)
                else:
                    keyword_score = 0

                # 3. Preference match (15% weight)
                agency_match = 100 if result.get("agency", "").upper() in preferred_agencies else 30
                code_match = 100 if result.get("activity_code", "") in preferred_codes else 50
                if not preferred_agencies and not preferred_codes:
                    preference_score = 50  # neutral
                else:
                    preference_score = (agency_match + code_match) / 2

                # Weighted total
                fit_score = int(
                    semantic_score * 0.60 +
                    keyword_score * 0.25 +
                    preference_score * 0.15
                )
                result["fit_score"] = min(fit_score, 100)

                # Generate fit reasons
                reasons = []
                if semantic_score > 50 and result["matching_docs"]:
                    top_doc = result["matching_docs"][0]
                    reasons.append(f"Matches your document \"{top_doc['title']}\" ({int(top_doc['similarity']*100)}% similar)")
                if keyword_score > 30:
                    matched_kws = [kw for kw in profile_keywords if kw in search_text.lower()]
                    if matched_kws:
                        reasons.append(f"Keywords match: {', '.join(matched_kws[:3])}")
                if result.get("agency", "").upper() in preferred_agencies:
                    reasons.append(f"{result['agency']} is in your preferred agencies")
                result["fit_reasons"] = reasons

            except Exception as e:
                logger.error(f"[GrantFinder] Scoring error for {result.get('id')}: {e}")
                result["fit_score"] = 0

        return results

    # ========================================================================
    # LAB PROFILE
    # ========================================================================

    def auto_generate_profile(self, tenant_id: str, db) -> Dict:
        """
        Auto-generate a lab research profile from indexed documents.
        Uses the lab's Pinecone-indexed content to extract research areas and keywords.
        """
        from database.models import Document, DocumentStatus, DocumentClassification

        # Get confirmed work documents
        documents = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False,
            Document.status == DocumentStatus.CONFIRMED,
            Document.classification == DocumentClassification.WORK
        ).limit(50).all()

        if not documents:
            return {
                "research_areas": [],
                "keywords": [],
                "department": "",
                "institution": "",
                "preferred_agencies": ["NIH", "NSF"],
                "budget_range": {"min": 50000, "max": 1000000},
                "activity_codes": ["R01", "R21"],
                "auto_generated": True,
                "last_updated": datetime.utcnow().isoformat()
            }

        # Collect all topics and entities from structured summaries
        all_topics = []
        all_entities = {"people": [], "systems": [], "organizations": []}

        for doc in documents:
            if doc.structured_summary:
                summary = doc.structured_summary
                all_topics.extend(summary.get("key_topics", []))
                entities = summary.get("entities", {})
                for key in all_entities:
                    all_entities[key].extend(entities.get(key, []))

        # Get top topics as research areas
        topic_counts = Counter(t.lower() for t in all_topics)
        research_areas = [t for t, _ in topic_counts.most_common(10)]

        # Get top entities as keywords
        all_keywords = all_topics + all_entities["systems"]
        keyword_counts = Counter(k.lower() for k in all_keywords)
        keywords = [k for k, _ in keyword_counts.most_common(15)]

        # Try to detect institution from org entities
        org_counts = Counter(o for o in all_entities["organizations"] if len(o) > 3)
        institution = org_counts.most_common(1)[0][0] if org_counts else ""

        profile = {
            "research_areas": research_areas,
            "keywords": keywords,
            "department": "",
            "institution": institution,
            "preferred_agencies": ["NIH", "NSF"],
            "budget_range": {"min": 50000, "max": 1000000},
            "activity_codes": ["R01", "R21"],
            "auto_generated": True,
            "last_updated": datetime.utcnow().isoformat()
        }

        logger.info(f"[GrantFinder] Auto-generated profile: {len(research_areas)} areas, {len(keywords)} keywords")
        return profile


# Singleton
_grant_finder_instance = None

def get_grant_finder() -> GrantFinderService:
    global _grant_finder_instance
    if _grant_finder_instance is None:
        _grant_finder_instance = GrantFinderService()
    return _grant_finder_instance
