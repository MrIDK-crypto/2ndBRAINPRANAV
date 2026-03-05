"""
Journal Data Service — Fetches and stores academic journal profiles from OpenAlex.
Computes composite prestige scores and assigns tiers for journal matching.
"""

import time
import uuid
from typing import Dict, List, Optional

import requests
from sqlalchemy import func as sa_func

from database.models import JournalProfile, SessionLocal


# ── OpenAlex Configuration ──────────────────────────────────────────────────

OPENALEX_BASE = "https://api.openalex.org"
OPENALEX_EMAIL = "prmogathala@gmail.com"  # polite pool
RESULTS_PER_PAGE = 200
MAX_PAGES = 5  # 200 * 5 = 1000 journals per field max

# ── Field → OpenAlex topic search mapping ───────────────────────────────────

FIELD_SEARCH_TERMS = {
    "economics": ["economics", "econometrics", "finance"],
    "cs_data_science": ["computer science", "machine learning", "artificial intelligence", "data science"],
    "biomedical": ["medicine", "biomedical", "clinical", "public health"],
    "political_science": ["political science", "international relations", "public policy"],
    "physics": ["physics", "astrophysics", "quantum"],
    "chemistry": ["chemistry", "chemical engineering"],
    "biology": ["biology", "ecology", "genetics", "molecular biology"],
    "psychology": ["psychology", "cognitive science", "behavioral science"],
    "sociology": ["sociology", "social science", "demography"],
    "engineering": ["engineering", "mechanical engineering", "electrical engineering"],
    "mathematics": ["mathematics", "applied mathematics", "statistics"],
    "environmental_science": ["environmental science", "climate", "sustainability"],
    "law": ["law", "legal studies", "jurisprudence"],
    "education": ["education", "pedagogy", "educational research"],
    "business_management": ["business", "management", "organizational studies"],
    "history": ["history", "historical studies", "archaeology"],
    "philosophy": ["philosophy", "ethics", "logic"],
    "linguistics": ["linguistics", "language", "computational linguistics"],
}


class JournalDataService:
    """Fetches journal data from OpenAlex, computes prestige tiers, stores in DB."""

    def __init__(self):
        self._session_headers = {
            "User-Agent": f"2ndBrain/1.0 (mailto:{OPENALEX_EMAIL})",
            "Accept": "application/json",
        }

    # ── Public Methods ──────────────────────────────────────────────────────

    def populate_journals(self, field: Optional[str] = None):
        """Fetch journals from OpenAlex and store in DB. Optionally filter by field."""
        fields = [field] if field else list(FIELD_SEARCH_TERMS.keys())
        db = SessionLocal()
        try:
            for f in fields:
                print(f"[JournalData] Populating: {f}")
                sources = self._fetch_openalex_sources(f)
                print(f"[JournalData]   Fetched {len(sources)} sources from OpenAlex")
                if sources:
                    self._store_and_tier(sources, f, db)
                    print(f"[JournalData]   Stored and tiered {len(sources)} journals for {f}")
                time.sleep(0.5)  # polite rate limiting between fields
            print(f"[JournalData] Done. Total fields: {len(fields)}")
        finally:
            db.close()

    def get_journals_for_field(self, field: str, tier: Optional[int] = None) -> List[Dict]:
        """Get stored journals for a field, optionally filtered by tier."""
        db = SessionLocal()
        try:
            query = db.query(JournalProfile).filter(
                JournalProfile.primary_field == field
            ).order_by(JournalProfile.composite_score.desc())
            if tier is not None:
                query = query.filter(JournalProfile.computed_tier == tier)
            return [j.to_dict() for j in query.limit(50).all()]
        finally:
            db.close()

    def get_journal_landscape(self, field: str) -> Dict:
        """Return distribution stats for a field — median, percentiles, tier thresholds."""
        db = SessionLocal()
        try:
            journals = db.query(JournalProfile).filter(
                JournalProfile.primary_field == field
            ).order_by(JournalProfile.composite_score.desc()).all()

            if not journals:
                return {"total": 0, "field": field}

            scores = [j.composite_score for j in journals]
            h_indices = [j.h_index for j in journals if j.h_index]
            impact_factors = [j.impact_factor for j in journals if j.impact_factor]

            tier1 = [j for j in journals if j.computed_tier == 1]
            tier2 = [j for j in journals if j.computed_tier == 2]
            tier3 = [j for j in journals if j.computed_tier == 3]

            return {
                "field": field,
                "total_journals": len(journals),
                "tier1_count": len(tier1),
                "tier2_count": len(tier2),
                "tier3_count": len(tier3),
                "tier1_threshold": tier1[-1].composite_score if tier1 else 85,
                "tier2_threshold": tier2[-1].composite_score if tier2 else 50,
                "median_composite": sorted(scores)[len(scores) // 2] if scores else 0,
                "median_h_index": sorted(h_indices)[len(h_indices) // 2] if h_indices else 0,
                "median_impact_factor": sorted(impact_factors)[len(impact_factors) // 2] if impact_factors else 0,
                "max_h_index": max(h_indices) if h_indices else 0,
                "max_impact_factor": max(impact_factors) if impact_factors else 0,
            }
        finally:
            db.close()

    def get_percentile_for_score(self, field: str, score: float) -> float:
        """Given a manuscript score, return the percentile rank within the field's journal landscape."""
        db = SessionLocal()
        try:
            total = db.query(sa_func.count(JournalProfile.id)).filter(
                JournalProfile.primary_field == field
            ).scalar() or 0
            if total == 0:
                return 50.0
            below = db.query(sa_func.count(JournalProfile.id)).filter(
                JournalProfile.primary_field == field,
                JournalProfile.composite_score <= score
            ).scalar() or 0
            return round((below / total) * 100, 1)
        finally:
            db.close()

    def check_freshness(self) -> bool:
        """Return True if journal data exists and is <30 days old."""
        db = SessionLocal()
        try:
            latest = db.query(sa_func.max(JournalProfile.updated_at)).scalar()
            if not latest:
                return False
            from datetime import datetime, timezone, timedelta
            if latest.tzinfo is None:
                from datetime import timezone as tz
                latest = latest.replace(tzinfo=tz.utc)
            age = datetime.now(timezone.utc) - latest
            return age.days < 30
        finally:
            db.close()

    # ── Private Methods ─────────────────────────────────────────────────────

    def _fetch_openalex_sources(self, field: str) -> List[Dict]:
        """Fetch journal sources from OpenAlex for a given field."""
        search_terms = FIELD_SEARCH_TERMS.get(field, [field])
        all_sources = {}  # dedup by openalex_id

        for term in search_terms:
            for page in range(1, MAX_PAGES + 1):
                url = (
                    f"{OPENALEX_BASE}/sources"
                    f"?search={requests.utils.quote(term)}"
                    f"&filter=type:journal"
                    f"&per_page={RESULTS_PER_PAGE}"
                    f"&page={page}"
                    f"&sort=h_index:desc"
                    f"&mailto={OPENALEX_EMAIL}"
                )
                try:
                    resp = requests.get(url, headers=self._session_headers, timeout=30)
                    if resp.status_code != 200:
                        print(f"[JournalData]   OpenAlex error {resp.status_code} for '{term}' page {page}")
                        break
                    data = resp.json()
                    results = data.get("results", [])
                    if not results:
                        break

                    for src in results:
                        oa_id = src.get("id", "")
                        if oa_id and oa_id not in all_sources:
                            issn_l = src.get("issn_l") or ""
                            issns = src.get("issn") or []
                            summary = src.get("summary_stats", {})

                            # Extract topic/subfield from OpenAlex topics
                            topics = src.get("topics", [])
                            subfield = ""
                            if topics:
                                top_topic = topics[0]
                                subfield = top_topic.get("subfield", {}).get("display_name", "")

                            all_sources[oa_id] = {
                                "openalex_id": oa_id,
                                "issn": issn_l or (issns[0] if issns else ""),
                                "issn_l": issn_l,
                                "name": src.get("display_name", "Unknown"),
                                "h_index": summary.get("h_index", 0) or 0,
                                "citedness_2yr": summary.get("2yr_mean_citedness", 0.0) or 0.0,
                                "works_count": src.get("works_count", 0) or 0,
                                "publisher": (src.get("host_organization_name") or ""),
                                "homepage_url": src.get("homepage_url") or "",
                                "subfield": subfield,
                            }

                    # If fewer results than per_page, no more pages
                    if len(results) < RESULTS_PER_PAGE:
                        break

                    time.sleep(0.15)  # stay well within rate limits
                except Exception as e:
                    print(f"[JournalData]   Error fetching '{term}' page {page}: {e}")
                    break

        return list(all_sources.values())

    def _store_and_tier(self, sources: List[Dict], field: str, db):
        """Compute composite scores, assign tiers, upsert into DB."""
        if not sources:
            return

        # Compute percentile ranks for h_index and citedness
        h_values = sorted([s["h_index"] for s in sources])
        cite_values = sorted([s["citedness_2yr"] for s in sources])

        def percentile_rank(val, sorted_list):
            if not sorted_list or val <= 0:
                return 0.0
            count_below = sum(1 for v in sorted_list if v < val)
            return (count_below / len(sorted_list)) * 100

        for src in sources:
            h_pctile = percentile_rank(src["h_index"], h_values)
            cite_pctile = percentile_rank(src["citedness_2yr"], cite_values)
            # Composite: 50% h-index percentile + 50% citedness percentile
            src["composite_score"] = round(0.5 * h_pctile + 0.5 * cite_pctile, 1)
            # Impact factor approximation: 2yr citedness
            src["impact_factor"] = src["citedness_2yr"]

        # Sort by composite score descending
        sources.sort(key=lambda s: s["composite_score"], reverse=True)

        # Assign tiers: Top 15% = Tier 1, next 35% = Tier 2, rest = Tier 3
        n = len(sources)
        tier1_cutoff = int(n * 0.15)
        tier2_cutoff = int(n * 0.50)  # 15% + 35%

        for i, src in enumerate(sources):
            if i < tier1_cutoff:
                src["tier"] = 1
            elif i < tier2_cutoff:
                src["tier"] = 2
            else:
                src["tier"] = 3

        # Delete old entries for this field
        db.query(JournalProfile).filter(JournalProfile.primary_field == field).delete()
        db.flush()

        # Insert new entries
        for src in sources:
            journal = JournalProfile(
                id=str(uuid.uuid4()),
                openalex_id=src["openalex_id"],
                issn=src["issn"],
                issn_l=src.get("issn_l"),
                name=src["name"],
                h_index=src["h_index"],
                citedness_2yr=src["citedness_2yr"],
                works_count=src.get("works_count", 0),
                impact_factor=src["impact_factor"],
                primary_field=field,
                primary_subfield=src.get("subfield", ""),
                composite_score=src["composite_score"],
                computed_tier=src["tier"],
                publisher=src.get("publisher", ""),
                homepage_url=src.get("homepage_url", ""),
                data_source="openalex",
            )
            db.add(journal)

        db.commit()


# ── Singleton ───────────────────────────────────────────────────────────────

_service = None


def get_journal_data_service() -> JournalDataService:
    global _service
    if _service is None:
        _service = JournalDataService()
    return _service
