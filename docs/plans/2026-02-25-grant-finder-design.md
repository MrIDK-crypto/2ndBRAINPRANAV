# Grant Finder MVP — Design Document

**Date:** 2026-02-25
**Status:** Approved
**Target:** Research labs (NIH, NSF, DOE, SBIR/STTR federal grants)

---

## Problem

Research labs need to find relevant grants, but existing tools (Instrumentl, Grantable, Granted.ai) target nonprofits and don't leverage a lab's existing knowledge base. 2nd Brain already has the lab's emails, Slack threads, papers, protocols, and Notion docs indexed — we can use that context to score grant fit automatically.

## Solution

A Grant Finder page with three sections:
1. **Live Grant Search** — Real-time search across NIH RePORTER + Grants.gov APIs
2. **Context-Based Fit Scoring** — Score each grant against the lab's Pinecone-indexed knowledge base + user-editable research profile
3. **Coming Soon: Application Assistance** — Locked cards for future features (talking points, compliance checks, budget helpers)

## Architecture

```
User searches "machine learning drug discovery"
       |
       v
Backend: grant_finder_service.py
  |--- NIH RePORTER API (POST, no key) -----> funded projects + open opportunities
  |--- Grants.gov search2 API (POST, no key) -> open federal opportunities
       |
       v
Normalize to common GrantResult format
       |
       v
For each result:
  1. Embed grant abstract via openai_client.create_embedding()
  2. Query Pinecone for top-5 similar lab documents (tenant namespace)
  3. Compute fit_score = weighted(semantic_similarity, keyword_overlap, entity_match)
       |
       v
Return scored, ranked results to frontend
```

## Data Flow

### No New Database Models
Results are live from APIs, not stored. Lab research profile stored in Tenant.settings JSON field (already exists).

### API Endpoints

```
GET  /api/grants/search?q=...&agency=...&amount_min=...&amount_max=...&activity_codes=...
     -> { results: GrantResult[], lab_profile: LabProfile, total: int }

GET  /api/grants/profile
     -> { profile: LabProfile }

PUT  /api/grants/profile
     -> { profile: LabProfile }  (user edits their research profile)

POST /api/grants/auto-profile
     -> { profile: LabProfile }  (auto-generate from lab documents)
```

### GrantResult Shape (normalized from both APIs)
```python
{
    "id": "nih_11293556" | "grants_gov_358687",
    "source": "nih_reporter" | "grants_gov",
    "title": "Examining the Role of...",
    "abstract": "This project aims to...",
    "agency": "NIEHS" | "NSF" | "DOD",
    "agency_full": "National Institute of Environmental Health Sciences",
    "pi_name": "Daniel Reker",
    "pi_title": "ASSISTANT PROFESSOR",
    "organization": "DUKE UNIVERSITY",
    "award_amount": 444125,
    "start_date": "2026-01-01",
    "end_date": "2030-12-31",
    "deadline": "2026-06-15" | null,
    "activity_code": "R21" | null,
    "status": "active" | "posted" | "forecasted",
    "url": "https://reporter.nih.gov/project-details/11293556",
    "fit_score": 82,
    "fit_reasons": [
        "Your lab's proteomics work aligns with Aim 2",
        "PI Reker collaborates with your department",
        "3 of your documents reference similar methodology"
    ],
    "matching_docs": [
        {"id": "doc_123", "title": "Proteomics Protocol v3", "similarity": 0.89}
    ]
}
```

### LabProfile Shape
```python
{
    "research_areas": ["drug discovery", "machine learning", "proteomics"],
    "keywords": ["CRISPR", "high-throughput screening", "small molecule"],
    "department": "Biomedical Engineering",
    "institution": "Duke University",
    "preferred_agencies": ["NIH", "NSF"],
    "budget_range": {"min": 100000, "max": 2000000},
    "activity_codes": ["R01", "R21", "R35"],
    "auto_generated": true,
    "last_updated": "2026-02-25T..."
}
```

## Fit Scoring Algorithm

```python
def compute_fit_score(grant_abstract, tenant_id, lab_profile):
    # 1. Semantic similarity (60% weight)
    grant_embedding = openai_client.create_embedding(grant_abstract)
    pinecone_results = vector_store.search_by_vector(grant_embedding, tenant_id, top_k=5)
    avg_similarity = mean([r.score for r in pinecone_results])
    semantic_score = avg_similarity * 100  # 0-100

    # 2. Keyword overlap (25% weight)
    grant_terms = extract_keywords(grant_abstract)
    profile_terms = set(lab_profile.keywords + lab_profile.research_areas)
    overlap = len(grant_terms & profile_terms) / max(len(profile_terms), 1)
    keyword_score = overlap * 100

    # 3. Agency/activity code preference match (15% weight)
    agency_match = 100 if grant.agency in lab_profile.preferred_agencies else 30
    activity_match = 100 if grant.activity_code in lab_profile.activity_codes else 50
    preference_score = (agency_match + activity_match) / 2

    # Weighted total
    fit_score = int(
        semantic_score * 0.60 +
        keyword_score * 0.25 +
        preference_score * 0.15
    )
    return min(fit_score, 100)
```

## Files

### New Files (3)

**`backend/services/grant_finder_service.py`**
- `GrantFinderService` class
- `search_nih_reporter(query, filters)` — calls NIH RePORTER API
- `search_grants_gov(query, filters)` — calls Grants.gov search2 API
- `normalize_results(nih_results, grants_gov_results)` — common format
- `score_grants(results, tenant_id, lab_profile)` — fit scoring via Pinecone
- `auto_generate_profile(tenant_id)` — build profile from lab documents
- `extract_keywords(text)` — TF-IDF keyword extraction

**`backend/api/grant_routes.py`**
- Blueprint: `grant_bp`, prefix `/api/grants`
- `GET /search` — main search endpoint
- `GET /profile` — get lab profile
- `PUT /profile` — update lab profile
- `POST /auto-profile` — auto-generate profile

**`frontend/app/grants/page.tsx`**
- Full Grant Finder page with:
  - Search bar + filters (agency, amount range, activity codes)
  - Results list with fit scores, color-coded badges
  - Lab Profile sidebar (auto-detected + editable)
  - "Coming Soon" section with locked cards
  - External links to NIH/Grants.gov for each result

### Modified Files (2)

**`backend/app_v2.py`** — Add 2 lines:
```python
from api.grant_routes import grant_bp    # line ~207
app.register_blueprint(grant_bp)          # line ~228
```

**`frontend/components/shared/Sidebar.tsx`** — Add 1 menu item:
```typescript
// After 'Knowledge Gaps' item (~line 96):
{ id: 'Grant Finder', label: 'Grant Finder', href: '/grants', icon: 'grants', adminOnly: false },
```

## Frontend Design

### Layout
- Sidebar (existing) + main content area
- Follows existing warm theme (#FAF9F7 bg, #C9A598 primary, #FFFFFE cards)
- Three-column layout on desktop: filters | results | profile sidebar

### Search Section
- Search input with placeholder "Search grants (e.g., 'CRISPR drug discovery')"
- Filter chips: Agency (NIH, NSF, DOE, DOD), Amount range, Activity codes (R01, R21, etc.)
- "Auto-detect from my documents" button that fills search from lab profile

### Results Cards
- Fit score badge (color: green >70, yellow 40-70, gray <40)
- Title (linked to external source)
- Agency badge + activity code
- Award amount + deadline (with urgency coloring)
- Abstract snippet (expandable)
- "Why this matches" expandable section showing matching documents
- "View on NIH" / "View on Grants.gov" external link button

### Lab Profile Panel (right sidebar)
- Auto-generated research areas (editable chips)
- Keywords (editable)
- Preferred agencies (toggles)
- Budget range (slider)
- "Regenerate Profile" button

### Coming Soon Section
- Grid of locked feature cards:
  - "Talking Points Generator" — Generate key arguments from your lab's publications
  - "Budget Template Helper" — Pre-fill budgets based on similar funded grants
  - "Compliance Checklist" — NIH/NSF-specific submission requirements
  - "Prior Art Finder" — Find relevant papers from your lab's collection
  - "Application Draft Assistant" — AI-assisted specific aims and significance sections
- Each card: lock icon, title, 1-line description, "Coming Soon" badge

## External API Details

### NIH RePORTER (no key required)
- POST `https://api.reporter.nih.gov/v2/projects/search`
- Rate limit: ~1 req/sec recommended
- Max 500 results per page, 15,000 per query

### Grants.gov (no key required)
- POST `https://api.grants.gov/v1/api/search2`
- Filter by agency, category, status (posted/forecasted)
- Max 25 results per page

## Break-Nothing Guarantees

- Zero database schema changes (no migrations)
- Zero changes to existing API endpoints
- Zero changes to existing services (only imports get_vector_store, get_openai_client)
- Sidebar adds one item — all existing items unchanged
- New blueprint registered after all existing ones
- Frontend is a new `/grants` route — no existing routes affected
- If external APIs are down, returns empty results with error message (graceful degradation)

## Testing Plan

1. Backend: Verify NIH/Grants.gov API responses parse correctly
2. Backend: Verify fit scoring returns 0-100 scores
3. Frontend: Page renders with no results (empty state)
4. Frontend: Search returns and displays scored results
5. Integration: Lab profile auto-generation from existing documents
6. Regression: All existing pages still load correctly
