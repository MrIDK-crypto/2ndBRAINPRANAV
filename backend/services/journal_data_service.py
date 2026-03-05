"""
Journal Data Service — Fetches and stores academic journal profiles.
Sources: OpenAlex API (primary), SCImago SJR via Firecrawl (enrichment).
Computes composite prestige scores and assigns tiers for journal matching.
"""

import os
import re
import time
import uuid
from datetime import datetime, timezone
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

# ── Field → SCImago subject area code mapping ───────────────────────────────

FIELD_TO_SCIMAGO_AREA = {
    "economics": "2000",
    "cs_data_science": "1700",
    "biomedical": "2700",
    "political_science": "3300",
    "physics": "3100",
    "chemistry": "1600",
    "biology": "1100",
    "psychology": "3200",
    "sociology": "3300",
    "engineering": "2200",
    "mathematics": "2600",
    "environmental_science": "2300",
    "law": "3308",
    "education": "3304",
    "business_management": "1400",
    "history": "1200",
    "philosophy": "1200",
    "linguistics": "1203",
}


class JournalDataService:
    """Fetches journal data from OpenAlex + SCImago SJR, computes prestige tiers, stores in DB."""

    def __init__(self):
        self._session_headers = {
            "User-Agent": f"2ndBrain/1.0 (mailto:{OPENALEX_EMAIL})",
            "Accept": "application/json",
        }

    # ── Public Methods ──────────────────────────────────────────────────────

    def populate_journals(self, field: Optional[str] = None):
        """Fetch journals from OpenAlex, enrich with SJR data, store in DB."""
        fields = [field] if field else list(FIELD_SEARCH_TERMS.keys())
        db = SessionLocal()
        try:
            total_stored = 0
            for f in fields:
                print(f"[JournalData] Populating: {f}")
                sources = self._fetch_openalex_sources(f)
                raw_count = len(sources)
                print(f"[JournalData]   Fetched {raw_count} raw sources from OpenAlex")
                if sources:
                    valid_sources = self._validate_sources(sources)
                    print(f"[JournalData]   {len(valid_sources)}/{raw_count} passed validation")
                    self._store_and_tier(valid_sources, f, db)
                    total_stored += len(valid_sources)
                    print(f"[JournalData]   Stored and tiered {len(valid_sources)} journals for {f}")
                time.sleep(0.5)  # polite rate limiting between fields
            print(f"[JournalData] Done. {total_stored} journals across {len(fields)} fields")
        finally:
            db.close()

    def enrich_with_sjr(self, field: Optional[str] = None):
        """Scrape SCImago SJR data via Firecrawl and merge into existing journals by ISSN."""
        fields = [field] if field else list(FIELD_SEARCH_TERMS.keys())
        db = SessionLocal()
        try:
            total_enriched = 0
            for f in fields:
                print(f"[JournalData] Enriching SJR data for: {f}")
                sjr_data = self._scrape_sjr_for_field(f)
                if sjr_data:
                    count = self._merge_sjr_data(sjr_data, f, db)
                    total_enriched += count
                    print(f"[JournalData]   Enriched {count} journals with SJR data for {f}")
                else:
                    print(f"[JournalData]   No SJR data found for {f}")
                time.sleep(1.0)  # rate limit Firecrawl calls
            print(f"[JournalData] SJR enrichment done. {total_enriched} journals updated")
        finally:
            db.close()

    def full_refresh(self, field: Optional[str] = None):
        """Full pipeline: OpenAlex fetch → validate → store → SJR enrich → recompute tiers."""
        print(f"[JournalData] Starting full refresh...")
        self.populate_journals(field=field)
        self.enrich_with_sjr(field=field)
        self._recompute_tiers_with_sjr(field=field)
        print(f"[JournalData] Full refresh complete")

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

    def get_data_summary(self) -> Dict:
        """Return a summary of all stored journal data — counts per field and tier."""
        db = SessionLocal()
        try:
            rows = db.query(
                JournalProfile.primary_field,
                JournalProfile.computed_tier,
                sa_func.count(JournalProfile.id),
            ).group_by(
                JournalProfile.primary_field,
                JournalProfile.computed_tier,
            ).all()

            summary = {}
            for field, tier, count in rows:
                if field not in summary:
                    summary[field] = {"total": 0, "tier1": 0, "tier2": 0, "tier3": 0, "has_sjr": 0}
                summary[field][f"tier{tier}"] = count
                summary[field]["total"] += count

            # Count how many have SJR data
            sjr_rows = db.query(
                JournalProfile.primary_field,
                sa_func.count(JournalProfile.id),
            ).filter(
                JournalProfile.sjr_score.isnot(None),
            ).group_by(JournalProfile.primary_field).all()

            for field, count in sjr_rows:
                if field in summary:
                    summary[field]["has_sjr"] = count

            # Latest update
            latest = db.query(sa_func.max(JournalProfile.updated_at)).scalar()

            return {
                "fields": summary,
                "total_fields": len(summary),
                "total_journals": sum(f["total"] for f in summary.values()),
                "last_updated": latest.isoformat() if latest else None,
            }
        finally:
            db.close()

    def check_freshness(self) -> bool:
        """Return True if journal data exists and is <30 days old."""
        db = SessionLocal()
        try:
            latest = db.query(sa_func.max(JournalProfile.updated_at)).scalar()
            if not latest:
                return False
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - latest
            return age.days < 30
        finally:
            db.close()

    # ── OpenAlex Fetcher ─────────────────────────────────────────────────────

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
                    f"&sort=summary_stats.h_index:desc"
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

    # ── SJR Scraper (Firecrawl) ──────────────────────────────────────────────

    def _scrape_sjr_for_field(self, field: str) -> List[Dict]:
        """Scrape SCImago journal rankings for a field using Firecrawl."""
        api_key = os.getenv("FIRECRAWL_API_KEY", "")
        if not api_key:
            print(f"[JournalData]   FIRECRAWL_API_KEY not set — skipping SJR enrichment")
            return []

        area_code = FIELD_TO_SCIMAGO_AREA.get(field)
        if not area_code:
            return []

        # SCImago ranking page URL
        sjr_url = f"https://www.scimagojr.com/journalrank.php?area={area_code}&type=j&order=sjr&ord=desc"

        try:
            response = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": sjr_url,
                    "formats": ["markdown"],
                    "waitFor": 3000,  # wait for JS table to render
                },
                timeout=60,
            )

            if response.status_code != 200:
                print(f"[JournalData]   Firecrawl error {response.status_code} for {field}")
                return []

            result = response.json()
            if not result.get("success"):
                print(f"[JournalData]   Firecrawl scrape failed for {field}")
                return []

            markdown = result.get("data", {}).get("markdown", "")
            if not markdown:
                return []

            return self._parse_sjr_markdown(markdown)

        except Exception as e:
            print(f"[JournalData]   SJR scrape error for {field}: {e}")
            return []

    def _parse_sjr_markdown(self, markdown: str) -> List[Dict]:
        """Parse SCImago journal ranking table from Firecrawl markdown output."""
        journals = []

        # SCImago tables typically have: Rank | Title | Type | SJR | H index | ...
        # Look for table rows with journal data
        lines = markdown.split("\n")

        for line in lines:
            # Skip header/separator lines
            if not line.strip() or line.startswith("---") or line.startswith("|---"):
                continue

            # Try to extract journal data from table rows
            # Format varies but typically: | rank | title | type | sjr | h-index | docs | refs | ...
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) < 4:
                continue

            # Try to find SJR score (a decimal number like 12.345)
            sjr_score = None
            h_index = None
            title = None
            issn = None

            for i, cell in enumerate(cells):
                # SJR score: decimal number (not a rank or year)
                if sjr_score is None and re.match(r'^\d+\.\d+$', cell):
                    try:
                        val = float(cell)
                        if 0.01 < val < 100:  # SJR typically 0.1 to 50
                            sjr_score = val
                    except ValueError:
                        pass

                # H-index: integer, typically > 1
                if h_index is None and re.match(r'^\d+$', cell):
                    try:
                        val = int(cell)
                        if 1 < val < 1000:  # h-index range
                            h_index = val
                    except ValueError:
                        pass

                # Title: longest text cell that's not a number
                if not re.match(r'^[\d.]+$', cell) and len(cell) > 10:
                    if title is None or len(cell) > len(title):
                        title = cell

                # ISSN: pattern like 0000-0000
                issn_match = re.search(r'\b(\d{4}-\d{3}[\dXx])\b', cell)
                if issn_match:
                    issn = issn_match.group(1)

            if title and sjr_score is not None:
                # Determine quartile from SJR score relative to others
                # (will be computed after collecting all journals)
                journals.append({
                    "title": title.strip(),
                    "sjr_score": sjr_score,
                    "h_index": h_index,
                    "issn": issn,
                })

        # Assign quartiles based on SJR score ranking
        if journals:
            journals.sort(key=lambda j: j["sjr_score"], reverse=True)
            n = len(journals)
            for i, j in enumerate(journals):
                pct = i / n
                if pct < 0.25:
                    j["quartile"] = "Q1"
                elif pct < 0.50:
                    j["quartile"] = "Q2"
                elif pct < 0.75:
                    j["quartile"] = "Q3"
                else:
                    j["quartile"] = "Q4"

        return journals

    def _merge_sjr_data(self, sjr_data: List[Dict], field: str, db) -> int:
        """Merge scraped SJR data into existing JournalProfile records by name/ISSN match."""
        if not sjr_data:
            return 0

        # Load existing journals for this field
        journals = db.query(JournalProfile).filter(
            JournalProfile.primary_field == field
        ).all()

        if not journals:
            return 0

        # Build lookup dicts
        by_issn = {}
        by_name_lower = {}
        for j in journals:
            if j.issn:
                by_issn[j.issn] = j
            if j.issn_l and j.issn_l != j.issn:
                by_issn[j.issn_l] = j
            by_name_lower[j.name.lower().strip()] = j

        enriched = 0
        for sjr in sjr_data:
            matched_journal = None

            # Try ISSN match first (most reliable)
            if sjr.get("issn") and sjr["issn"] in by_issn:
                matched_journal = by_issn[sjr["issn"]]

            # Fallback to name match
            if not matched_journal and sjr.get("title"):
                sjr_name = sjr["title"].lower().strip()
                if sjr_name in by_name_lower:
                    matched_journal = by_name_lower[sjr_name]

            if matched_journal:
                matched_journal.sjr_score = sjr["sjr_score"]
                matched_journal.sjr_quartile = sjr.get("quartile")
                if matched_journal.data_source == "openalex":
                    matched_journal.data_source = "openalex+sjr"
                enriched += 1

        if enriched > 0:
            db.commit()

        return enriched

    def _recompute_tiers_with_sjr(self, field: Optional[str] = None):
        """Recompute composite scores including SJR data and re-tier."""
        fields = [field] if field else list(FIELD_SEARCH_TERMS.keys())
        db = SessionLocal()
        try:
            for f in fields:
                journals = db.query(JournalProfile).filter(
                    JournalProfile.primary_field == f
                ).all()

                if not journals:
                    continue

                # Collect metric arrays for percentile computation
                h_values = sorted([j.h_index or 0 for j in journals])
                cite_values = sorted([j.citedness_2yr or 0.0 for j in journals])
                sjr_values = sorted([j.sjr_score for j in journals if j.sjr_score is not None])

                def pctile(val, sorted_list):
                    if not sorted_list or val <= 0:
                        return 0.0
                    count_below = sum(1 for v in sorted_list if v < val)
                    return (count_below / len(sorted_list)) * 100

                has_sjr = len(sjr_values) > 0

                for j in journals:
                    h_pct = pctile(j.h_index or 0, h_values)
                    cite_pct = pctile(j.citedness_2yr or 0.0, cite_values)

                    if has_sjr and j.sjr_score is not None:
                        sjr_pct = pctile(j.sjr_score, sjr_values)
                        # 3-factor composite: 40% h-index + 30% citedness + 30% SJR
                        j.composite_score = round(0.4 * h_pct + 0.3 * cite_pct + 0.3 * sjr_pct, 1)
                    else:
                        # 2-factor composite: 50% h-index + 50% citedness
                        j.composite_score = round(0.5 * h_pct + 0.5 * cite_pct, 1)

                # Re-sort and re-tier
                journals.sort(key=lambda j: j.composite_score, reverse=True)
                n = len(journals)
                t1 = int(n * 0.15)
                t2 = int(n * 0.50)

                for i, j in enumerate(journals):
                    if i < t1:
                        j.computed_tier = 1
                    elif i < t2:
                        j.computed_tier = 2
                    else:
                        j.computed_tier = 3

                db.commit()
                sjr_count = sum(1 for j in journals if j.sjr_score is not None)
                print(f"[JournalData]   Recomputed tiers for {f}: {n} journals ({sjr_count} with SJR)")

        finally:
            db.close()

    # ── Validation & Sanitization ────────────────────────────────────────────

    def _sanitize_source(self, src: Dict) -> Dict:
        """Clean and validate a source record before DB insert."""
        for str_key in ("name", "publisher", "homepage_url", "subfield", "openalex_id", "issn", "issn_l"):
            val = src.get(str_key, "") or ""
            val = val.replace("\x00", "").strip()
            src[str_key] = val

        src["h_index"] = max(0, int(src.get("h_index", 0) or 0))
        src["citedness_2yr"] = max(0.0, float(src.get("citedness_2yr", 0.0) or 0.0))
        src["works_count"] = max(0, int(src.get("works_count", 0) or 0))
        return src

    def _validate_sources(self, sources: List[Dict]) -> List[Dict]:
        """Filter out garbage entries — journals must have a name and some metrics."""
        valid = []
        for src in sources:
            src = self._sanitize_source(src)
            if not src["name"] or len(src["name"]) < 3:
                continue
            if src["h_index"] == 0 and src["citedness_2yr"] == 0.0:
                continue
            valid.append(src)
        return valid

    # ── Store & Tier ─────────────────────────────────────────────────────────

    def _store_and_tier(self, sources: List[Dict], field: str, db):
        """Compute composite scores, assign tiers, upsert into DB.
        Expects pre-validated sources from _validate_sources()."""
        if not sources:
            return

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
            src["composite_score"] = round(0.5 * h_pctile + 0.5 * cite_pctile, 1)
            src["impact_factor"] = src["citedness_2yr"]

        sources.sort(key=lambda s: s["composite_score"], reverse=True)

        n = len(sources)
        tier1_cutoff = int(n * 0.15)
        tier2_cutoff = int(n * 0.50)

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
