"""
Grant Finder Service
Searches NIH RePORTER, Grants.gov, NSF, SBIR, and Federal RePORTER APIs.
Scores results against lab knowledge base.
"""

import os
import re
import json
import time
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
GRANTS_GOV_DETAIL_URL = "https://api.grants.gov/v1/api/fetchOpportunity"
NSF_AWARDS_URL = "https://api.nsf.gov/services/v1/awards.json"
SBIR_API_URL = "https://api.www.sbir.gov/public/api/awards"
FEDERAL_REPORTER_URL = "https://api.federalreporter.nih.gov/v1/Projects/search"

# Rate limiting
API_REQUEST_DELAY = 0.3  # seconds between requests
MAX_RETRIES = 3

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


def _request_with_retry(method, url, retries=MAX_RETRIES, delay=API_REQUEST_DELAY, **kwargs):
    """Make HTTP request with retry on 429/5xx and exponential backoff."""
    last_resp = None
    for attempt in range(retries + 1):
        try:
            resp = method(url, **kwargs)
            last_resp = resp
            if resp.status_code == 429:
                wait = (2 ** attempt) * delay
                logger.warning(f"[GrantFinder] Rate limited (429). Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = (2 ** attempt) * delay
                logger.warning(f"[GrantFinder] Server error ({resp.status_code}). Retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            return resp
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                wait = (2 ** attempt) * delay
                logger.warning(f"[GrantFinder] Request error: {e}. Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise
    return last_resp


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', clean).strip()


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
            current_year = datetime.now().year
            criteria = {
                "include_active_projects": True,
                "exclude_subprojects": True,
                "fiscal_years": [current_year - 1, current_year, current_year + 1],
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

            # NIH RePORTER supports up to 500 results per request
            page_size = min(limit, 500)
            results = []
            offset = 0

            while len(results) < limit:
                body = {
                    "criteria": criteria,
                    "offset": offset,
                    "limit": min(page_size, limit - len(results)),
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

                resp = _request_with_retry(requests.post, NIH_REPORTER_URL, json=body, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                page_results = data.get("results", [])
                if not page_results:
                    break

                for item in page_results:
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
                        "deadline": None,
                        "activity_code": item.get("activity_code", ""),
                        "project_num": item.get("project_num", ""),
                        "status": "active" if item.get("is_active") else "completed",
                        "url": f"https://reporter.nih.gov/project-details/{item.get('appl_id', '')}",
                        "fit_score": 0,
                        "fit_reasons": [],
                        "matching_docs": []
                    })

                offset += len(page_results)
                # Stop if we got fewer results than requested (last page)
                if len(page_results) < page_size:
                    break
                time.sleep(API_REQUEST_DELAY)

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

    def _fetch_grants_gov_detail(self, opportunity_id: str) -> Dict:
        """Fetch detailed info for a single Grants.gov opportunity."""
        try:
            resp = _request_with_retry(
                requests.post,
                GRANTS_GOV_DETAIL_URL,
                json={"opportunityId": int(opportunity_id)},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            synopsis = data.get("synopsis", {}) or {}
            description = _strip_html(synopsis.get("synopsisDesc", "") or "")
            award_ceiling = synopsis.get("awardCeiling", 0) or 0
            award_floor = synopsis.get("awardFloor", 0) or 0

            return {
                "description": description[:3000],
                "award_ceiling": int(award_ceiling),
                "award_floor": int(award_floor),
            }
        except Exception as e:
            logger.warning(f"[GrantFinder] Grants.gov detail fetch failed for {opportunity_id}: {e}")
            return {"description": "", "award_ceiling": 0, "award_floor": 0}

    def search_grants_gov(
        self,
        query: str,
        agencies: Optional[List[str]] = None,
        funding_categories: Optional[str] = None,
        amount_min: Optional[int] = None,
        amount_max: Optional[int] = None,
        fetch_details: bool = True,
        limit: int = 20
    ) -> List[Dict]:
        """Search Grants.gov for open funding opportunities with pagination."""
        try:
            results = []
            page_size = 25  # Grants.gov max per page
            start_record = 0

            while len(results) < limit:
                body = {
                    "keyword": query,
                    "oppStatuses": "posted|forecasted",
                    "rows": min(page_size, limit - len(results)),
                    "startRecordNum": start_record,
                    "sortBy": "openDate|desc"
                }

                if agencies:
                    body["agencies"] = ",".join(agencies)

                # Only filter by category if explicitly specified
                if funding_categories:
                    body["fundingCategories"] = funding_categories

                resp = _request_with_retry(requests.post, GRANTS_GOV_URL, json=body, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                page_items = data.get("data", {}).get("oppHits", [])
                if not page_items:
                    break

                for item in page_items:
                    open_date = item.get("openDate", "")
                    close_date = item.get("closeDate", "")
                    opp_id = item.get("id", "")

                    # Fetch detail for abstract and award amounts
                    abstract = ""
                    award_amount = 0
                    if fetch_details and opp_id:
                        detail = self._fetch_grants_gov_detail(str(opp_id))
                        abstract = detail["description"]
                        award_amount = detail["award_ceiling"] or detail["award_floor"]
                        time.sleep(API_REQUEST_DELAY)

                    results.append({
                        "id": f"grants_gov_{opp_id}",
                        "source": "grants_gov",
                        "title": (item.get("title") or "Untitled").strip(),
                        "abstract": abstract,
                        "agency": item.get("agencyCode", "").split("-")[0],
                        "agency_full": item.get("agency", ""),
                        "pi_name": "",
                        "pi_title": "",
                        "organization": "",
                        "org_location": "",
                        "award_amount": int(award_amount),
                        "start_date": open_date,
                        "end_date": "",
                        "deadline": close_date if close_date else None,
                        "activity_code": "",
                        "project_num": item.get("number", ""),
                        "status": item.get("oppStatus", "posted"),
                        "url": f"https://www.grants.gov/search-results-detail/{opp_id}",
                        "fit_score": 0,
                        "fit_reasons": [],
                        "matching_docs": []
                    })

                start_record += len(page_items)
                if len(page_items) < page_size:
                    break
                time.sleep(API_REQUEST_DELAY)

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
        """Search NSF Award Search API for funded research grants with pagination."""
        try:
            results = []
            page_size = 25  # NSF max per page
            offset = 1  # NSF uses 1-based offset

            while len(results) < limit:
                params = {
                    "keyword": query,
                    "printFields": "id,title,abstractText,agency,piFirstName,piLastName,piEmail,awardeeName,awardeeCity,awardeeStateCode,startDate,expDate,fundsObligatedAmt,fundProgramName,primaryProgram",
                    "offset": offset,
                    "rpp": min(page_size, limit - len(results))
                }

                resp = _request_with_retry(
                    requests.get, NSF_AWARDS_URL,
                    params=params, timeout=15
                )
                resp.raise_for_status()
                data = resp.json()

                page_items = data.get("response", {}).get("award", [])
                if not page_items:
                    break

                for item in page_items:
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

                offset += len(page_items)
                if len(page_items) < page_size:
                    break
                time.sleep(API_REQUEST_DELAY)

            logger.info(f"[GrantFinder] NSF returned {len(results)} results for '{query}'")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"[GrantFinder] NSF API error: {e}")
            return []
        except Exception as e:
            logger.error(f"[GrantFinder] NSF parse error: {e}")
            return []

    # ========================================================================
    # SBIR.GOV (SBIR/STTR Awards)
    # ========================================================================

    def search_sbir(
        self,
        query: str = "",
        agency: str = "",
        year: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search SBIR.gov for SBIR/STTR awards."""
        try:
            results = []
            page_size = min(limit, 100)
            start = 0

            if not year:
                year = datetime.now().year

            while len(results) < limit:
                params = {
                    "year": year,
                    "start": start,
                    "rows": min(page_size, limit - len(results)),
                }
                if agency:
                    params["agency"] = agency
                if query:
                    params["keyword"] = query

                resp = _request_with_retry(
                    requests.get, SBIR_API_URL,
                    params=params, timeout=15
                )
                resp.raise_for_status()
                data = resp.json()

                items = data if isinstance(data, list) else data.get("results", [])
                if not items:
                    break

                for item in items:
                    pi_name = item.get("piName", "") or ""
                    if not pi_name:
                        first = item.get("piFirstName", "")
                        last = item.get("piLastName", "")
                        pi_name = f"{first} {last}".strip()

                    results.append({
                        "id": f"sbir_{item.get('awardId', item.get('agency_tracking_number', ''))}",
                        "source": "sbir",
                        "title": (item.get("award_title", item.get("awardTitle", "")) or "Untitled").strip(),
                        "abstract": (item.get("abstract", "") or "")[:2000],
                        "agency": (item.get("agency", "") or "").upper(),
                        "agency_full": item.get("agency", ""),
                        "pi_name": pi_name,
                        "pi_title": "",
                        "organization": item.get("firm", "") or "",
                        "org_location": f"{item.get('awardeeCity', '')}, {item.get('awardeeState', '')}".strip(", "),
                        "award_amount": int(item.get("award_amount", item.get("awardAmount", 0)) or 0),
                        "start_date": item.get("proposal_award_date", ""),
                        "end_date": item.get("contract_end_date", ""),
                        "deadline": None,
                        "activity_code": f"SBIR {item.get('phase', '')}".strip(),
                        "project_num": str(item.get("agency_tracking_number", item.get("awardId", ""))),
                        "status": "active",
                        "url": f"https://www.sbir.gov/awards/{item.get('awardId', '')}",
                        "fit_score": 0,
                        "fit_reasons": [],
                        "matching_docs": []
                    })

                start += len(items)
                if len(items) < page_size:
                    break
                time.sleep(API_REQUEST_DELAY)

            logger.info(f"[GrantFinder] SBIR returned {len(results)} results for agency='{agency}' year={year}")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"[GrantFinder] SBIR API error: {e}")
            return []
        except Exception as e:
            logger.error(f"[GrantFinder] SBIR parse error: {e}")
            return []

    # ========================================================================
    # FEDERAL REPORTER (Multi-Agency)
    # ========================================================================

    def search_federal_reporter(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict]:
        """Search Federal RePORTER for multi-agency federal grants."""
        try:
            current_year = datetime.now().year
            params = {
                "query": f"text:{query}$fy:{current_year}",
                "offset": 1,
                "limit": min(limit, 50),
            }

            resp = _request_with_retry(
                requests.get, FEDERAL_REPORTER_URL,
                params=params, timeout=15
            )

            if resp.status_code in (502, 503, 504):
                logger.warning("[GrantFinder] Federal RePORTER unavailable, skipping")
                return []

            resp.raise_for_status()
            data = resp.json()

            results = []
            items = data.get("items", [])

            for item in items:
                pi_name = item.get("contactPi", "") or item.get("otherPis", "") or ""

                results.append({
                    "id": f"fedreporter_{item.get('projectNumber', item.get('smApplId', ''))}",
                    "source": "federal_reporter",
                    "title": (item.get("title") or "Untitled").strip(),
                    "abstract": (item.get("abstractText") or "")[:2000],
                    "agency": item.get("agency", ""),
                    "agency_full": item.get("agencyFullName", item.get("agency", "")),
                    "pi_name": pi_name,
                    "pi_title": "",
                    "organization": item.get("orgName", ""),
                    "org_location": f"{item.get('orgCity', '')}, {item.get('orgState', '')}".strip(", "),
                    "award_amount": int(item.get("totalCostAmount", 0) or 0),
                    "start_date": item.get("projectStartDate", ""),
                    "end_date": item.get("projectEndDate", ""),
                    "deadline": None,
                    "activity_code": item.get("activityCode", ""),
                    "project_num": item.get("projectNumber", ""),
                    "status": "active",
                    "url": f"https://federalreporter.nih.gov/Projects/Details/?projectId={item.get('projectId', '')}",
                    "fit_score": 0,
                    "fit_reasons": [],
                    "matching_docs": []
                })

            logger.info(f"[GrantFinder] Federal RePORTER returned {len(results)} results for '{query}'")
            return results

        except requests.exceptions.ConnectionError:
            logger.warning("[GrantFinder] Federal RePORTER unreachable, skipping")
            return []
        except Exception as e:
            logger.error(f"[GrantFinder] Federal RePORTER error: {e}")
            return []

    # ========================================================================
    # CROSS-SOURCE DEDUPLICATION
    # ========================================================================

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize a grant title for fuzzy matching."""
        t = title.lower().strip()
        t = re.sub(r'[^a-z0-9\s]', '', t)
        t = re.sub(r'\s+', ' ', t)
        return t

    @staticmethod
    def deduplicate_cross_source(grants: List[Dict]) -> List[Dict]:
        """Remove cross-source duplicates by normalized title matching.
        Keeps the result with more data (longer abstract or higher award)."""
        seen_titles = {}  # normalized_title -> index in deduped
        deduped = []

        for grant in grants:
            norm_title = GrantFinderService._normalize_title(grant.get('title', ''))
            if not norm_title or len(norm_title) < 10:
                deduped.append(grant)
                continue

            if norm_title in seen_titles:
                idx = seen_titles[norm_title]
                existing = deduped[idx]
                # Keep the one with more data
                if (len(grant.get('abstract', '')) > len(existing.get('abstract', ''))
                        or grant.get('award_amount', 0) > existing.get('award_amount', 0)):
                    deduped[idx] = grant
            else:
                seen_titles[norm_title] = len(deduped)
                deduped.append(grant)

        return deduped

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
        Search all APIs, score results against lab context, return ranked results.
        """
        # Query all APIs
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
            fetch_details=False,  # Skip detail API in live search for speed
            limit=limit
        )
        nsf_results = self.search_nsf_awards(
            query=query,
            limit=limit
        )
        federal_results = self.search_federal_reporter(
            query=query,
            limit=limit
        )

        # Combine and deduplicate
        all_results = nih_results + grants_gov_results + nsf_results + federal_results
        all_results = self.deduplicate_cross_source(all_results)

        if not all_results:
            return {
                "results": [],
                "total": 0,
                "sources": {"nih_reporter": 0, "grants_gov": 0, "nsf": 0, "federal_reporter": 0}
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
                "grants_gov": len(grants_gov_results),
                "nsf": len(nsf_results),
                "federal_reporter": len(federal_results)
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
                try:
                    pinecone_results = self.vector_store.search(
                        query=search_text[:500],
                        tenant_id=tenant_id,
                        top_k=5
                    )
                    if pinecone_results:
                        avg_sim = sum(r["score"] for r in pinecone_results) / len(pinecone_results)
                        semantic_score = min(avg_sim * 100, 100)
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
                    preference_score = 50
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

        all_topics = []
        all_entities = {"people": [], "systems": [], "organizations": []}

        for doc in documents:
            if doc.structured_summary:
                summary = doc.structured_summary
                all_topics.extend(summary.get("key_topics", []))
                entities = summary.get("entities", {})
                for key in all_entities:
                    all_entities[key].extend(entities.get(key, []))

        topic_counts = Counter(t.lower() for t in all_topics)
        research_areas = [t for t, _ in topic_counts.most_common(10)]

        all_keywords = all_topics + all_entities["systems"]
        keyword_counts = Counter(k.lower() for k in all_keywords)
        keywords = [k for k, _ in keyword_counts.most_common(15)]

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
