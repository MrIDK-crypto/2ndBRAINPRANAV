# Grant Finder MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Grant Finder page to 2nd Brain that searches NIH RePORTER + Grants.gov in real-time, scores results against the lab's knowledge base, and shows a "Coming Soon" section for application assistance.

**Architecture:** Backend service queries two free federal APIs (no keys needed), normalizes results, then scores each grant against the lab's Pinecone-indexed documents using embedding similarity. Frontend is a single new page with search, results, profile sidebar, and coming soon cards.

**Tech Stack:** Flask blueprint, requests (HTTP), Pinecone (existing vector store), Azure OpenAI embeddings (existing), Next.js 14, React 18, inline styles (existing pattern)

**Design Doc:** `docs/plans/2026-02-25-grant-finder-design.md`

---

## Task 1: Grant Finder Backend Service

**Files:**
- Create: `backend/services/grant_finder_service.py`

**Step 1: Create the grant finder service with NIH RePORTER integration**

```python
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
```

**Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('backend/services/grant_finder_service.py').read()); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/services/grant_finder_service.py
git commit -m "feat: add grant finder service with NIH RePORTER + Grants.gov integration"
```

---

## Task 2: Grant API Routes

**Files:**
- Create: `backend/api/grant_routes.py`
- Modify: `backend/app_v2.py:206-228`

**Step 1: Create the grant routes blueprint**

```python
"""
Grant Finder API Routes
REST endpoints for searching grants and managing lab research profiles.
"""

from flask import Blueprint, request, jsonify, g
from database.models import SessionLocal, Tenant
from services.auth_service import require_auth
from services.grant_finder_service import get_grant_finder

grant_bp = Blueprint('grants', __name__, url_prefix='/api/grants')


def get_db():
    return SessionLocal()


@grant_bp.route('/search', methods=['GET'])
@require_auth
def search_grants():
    """
    Search grants across NIH RePORTER and Grants.gov.

    Query params:
        q: Search query (required)
        agencies: Comma-separated agency codes (NIH, NSF, DOE, DOD)
        activity_codes: Comma-separated (R01, R21, etc.)
        amount_min: Minimum award amount
        amount_max: Maximum award amount
        limit: Max results (default 20, max 50)
    """
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({
                "success": False,
                "error": "Search query 'q' is required"
            }), 400

        agencies_str = request.args.get('agencies', '')
        agencies = [a.strip() for a in agencies_str.split(',') if a.strip()] or None

        codes_str = request.args.get('activity_codes', '')
        activity_codes = [c.strip() for c in codes_str.split(',') if c.strip()] or None

        amount_min = request.args.get('amount_min', type=int)
        amount_max = request.args.get('amount_max', type=int)
        limit = min(request.args.get('limit', 20, type=int), 50)

        tenant_id = getattr(g, 'tenant_id', 'local-tenant')

        # Get lab profile for scoring
        db = get_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            lab_profile = (tenant.settings or {}).get('grant_profile', {}) if tenant else {}
        finally:
            db.close()

        # Search and score
        finder = get_grant_finder()
        result = finder.search(
            query=query,
            tenant_id=tenant_id,
            lab_profile=lab_profile,
            agencies=agencies,
            activity_codes=activity_codes,
            amount_min=amount_min,
            amount_max=amount_max,
            limit=limit
        )

        return jsonify({
            "success": True,
            **result
        })

    except Exception as e:
        print(f"[GrantSearch] Error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@grant_bp.route('/profile', methods=['GET'])
@require_auth
def get_profile():
    """Get the lab's grant research profile."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'local-tenant')
        db = get_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return jsonify({"success": False, "error": "Tenant not found"}), 404

            profile = (tenant.settings or {}).get('grant_profile', {})
            return jsonify({
                "success": True,
                "profile": profile
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@grant_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile():
    """Update the lab's grant research profile."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        tenant_id = getattr(g, 'tenant_id', 'local-tenant')
        db = get_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return jsonify({"success": False, "error": "Tenant not found"}), 404

            settings = tenant.settings or {}
            settings['grant_profile'] = {
                "research_areas": data.get("research_areas", []),
                "keywords": data.get("keywords", []),
                "department": data.get("department", ""),
                "institution": data.get("institution", ""),
                "preferred_agencies": data.get("preferred_agencies", ["NIH", "NSF"]),
                "budget_range": data.get("budget_range", {"min": 50000, "max": 1000000}),
                "activity_codes": data.get("activity_codes", ["R01", "R21"]),
                "auto_generated": False,
                "last_updated": __import__('datetime').datetime.utcnow().isoformat()
            }
            tenant.settings = settings

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(tenant, 'settings')
            db.commit()

            return jsonify({
                "success": True,
                "profile": settings['grant_profile']
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@grant_bp.route('/auto-profile', methods=['POST'])
@require_auth
def auto_generate_profile():
    """Auto-generate lab profile from ingested documents."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'local-tenant')
        db = get_db()
        try:
            finder = get_grant_finder()
            profile = finder.auto_generate_profile(tenant_id, db)

            # Save to tenant settings
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                settings = tenant.settings or {}
                settings['grant_profile'] = profile
                tenant.settings = settings

                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(tenant, 'settings')
                db.commit()

            return jsonify({
                "success": True,
                "profile": profile
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

**Step 2: Register the blueprint in app_v2.py**

Add after the inventory blueprint import (line ~206):
```python
from api.grant_routes import grant_bp
```

Add after `app.register_blueprint(inventory_bp)` (line ~227):
```python
app.register_blueprint(grant_bp)
```

**Step 3: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('backend/api/grant_routes.py').read()); print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/api/grant_routes.py backend/app_v2.py
git commit -m "feat: add grant finder API routes and register blueprint"
```

---

## Task 3: Sidebar Navigation Update

**Files:**
- Modify: `frontend/components/shared/Sidebar.tsx:50-57` (getActiveItem)
- Modify: `frontend/components/shared/Sidebar.tsx:93-101` (allMenuItems)
- Modify: `frontend/components/shared/Sidebar.tsx:108-171` (renderIcon)

**Step 1: Add Grant Finder to the sidebar**

In `getActiveItem()` (~line 55), add before the `return 'ChatBot'`:
```typescript
    if (pathname === '/grants') return 'Grant Finder'
```

In `allMenuItems` array (~line 97), add after the Knowledge Gaps entry:
```typescript
    { id: 'Grant Finder', label: 'Grant Finder', href: '/grants', icon: 'grants', adminOnly: false },
```

In `renderIcon` switch statement (~line 167), add before the `default:` case:
```typescript
      case 'grants':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
            <path d="M19 10v2a7 7 0 01-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        )
```

Wait — that's a microphone icon. Let me use a proper grant/search icon (magnifying glass + dollar sign concept):

```typescript
      case 'grants':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <path d="M11 8v6" />
            <path d="M8 11h6" />
          </svg>
        )
```

This is a search/plus icon (magnifying glass with +). Clean and appropriate for "find grants."

**Step 2: Commit**

```bash
git add frontend/components/shared/Sidebar.tsx
git commit -m "feat: add Grant Finder to sidebar navigation"
```

---

## Task 4: Frontend Grant Finder Page

**Files:**
- Create: `frontend/app/grants/page.tsx`

**Step 1: Create the full Grant Finder page**

This is the main frontend file. It contains:
- Search bar with filters
- Results list with fit score badges
- Lab Profile sidebar panel
- Coming Soon section with locked cards

The page follows the existing pattern: `Sidebar` + main content, warm theme (#FAF9F7, #C9A598), inline styles.

Use the `frontend-design` skill for high-quality UI. The page should be a single file under `frontend/app/grants/page.tsx` following the exact pattern of `frontend/app/inventory/page.tsx` (page wrapper) but with all component code inline (no separate component file needed for MVP).

Key UI sections:
1. **Header**: "Grant Finder" title + subtitle
2. **Search bar**: Input + filter dropdowns (agency, activity code, amount range)
3. **Results area** (left ~65%): Grant cards with fit score badge, title, agency, amount, deadline, abstract, matching docs, external link
4. **Profile panel** (right ~35%): Auto-detected research areas (editable chips), keywords, preferred agencies, budget range, "Regenerate" button
5. **Coming Soon section** (bottom): Grid of 5 locked feature cards

Colors:
- Fit score badge: `#22C55E` (green, >70), `#EAB308` (yellow, 40-70), `#9CA3AF` (gray, <40)
- Deadline urgency: `#EF4444` (<7 days), `#F59E0B` (<30 days), `#6B7280` (>30 days)
- Coming Soon badge: `#C9A598` background, white text
- Lock icon on coming soon cards: `#C9A598`

API calls pattern (from existing codebase):
```typescript
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'
const response = await axios.get(`${API_BASE}/grants/search?q=${query}`, { headers: authHeaders })
```

**Step 2: Verify page loads**

Run: `cd frontend && npx next build --no-lint 2>&1 | tail -5` (or just navigate to http://localhost:3006/grants)
Expected: No build errors

**Step 3: Commit**

```bash
git add frontend/app/grants/page.tsx
git commit -m "feat: add Grant Finder page with search, scoring, profile, and coming soon section"
```

---

## Task 5: Final Integration and Push

**Step 1: Verify all syntax checks pass**

```bash
python3 -c "import ast; ast.parse(open('backend/services/grant_finder_service.py').read()); print('grant_finder_service: OK')"
python3 -c "import ast; ast.parse(open('backend/api/grant_routes.py').read()); print('grant_routes: OK')"
python3 -c "import ast; ast.parse(open('backend/app_v2.py').read()); print('app_v2: OK')"
```

**Step 2: Verify no existing files broken**

```bash
git diff --stat  # Should only show the 2 modified files + 3 new files
```

**Step 3: Push to deploy**

```bash
git push origin main
```

**Step 4: Monitor deployment**

```bash
gh run list --limit 1
gh run watch <run_id> --exit-status
```

---

## Summary

| Task | Files | Type |
|------|-------|------|
| 1. Grant Finder Service | `backend/services/grant_finder_service.py` | New |
| 2. Grant API Routes | `backend/api/grant_routes.py`, `backend/app_v2.py` | New + Modify |
| 3. Sidebar Update | `frontend/components/shared/Sidebar.tsx` | Modify |
| 4. Frontend Page | `frontend/app/grants/page.tsx` | New |
| 5. Integration & Deploy | — | Push |

**Total new files:** 3
**Total modified files:** 2
**Database changes:** None
**Breaking changes:** None
