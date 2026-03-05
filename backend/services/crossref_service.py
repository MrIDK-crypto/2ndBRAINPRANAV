"""
CrossRef Service — Verifies DOIs and retrieves citation counts.
Used by the journal scorer to validate references found in manuscripts.
"""

import re
import time
from typing import Dict, List, Optional

import requests


CROSSREF_BASE = "https://api.crossref.org"
POLITE_EMAIL = "prmogathala@gmail.com"
MAX_VERIFY = 10  # max DOIs to verify per manuscript (rate limit friendly)


class CrossRefService:
    """Lightweight CrossRef API client for DOI verification."""

    def __init__(self):
        self._headers = {
            "User-Agent": f"2ndBrain/1.0 (mailto:{POLITE_EMAIL})",
            "Accept": "application/json",
        }

    def extract_dois_from_text(self, text: str) -> List[str]:
        """Extract DOI strings from manuscript text using regex."""
        # Matches 10.XXXX/... pattern (standard DOI format)
        pattern = r'10\.\d{4,9}/[^\s,;"\'\]>}]+'
        raw = re.findall(pattern, text)
        # Clean trailing punctuation
        cleaned = []
        seen = set()
        for doi in raw:
            doi = doi.rstrip(".")
            if doi not in seen:
                seen.add(doi)
                cleaned.append(doi)
        return cleaned[:MAX_VERIFY]

    def verify_dois(self, dois: List[str]) -> Dict[str, Dict]:
        """Verify a list of DOIs against CrossRef. Returns dict keyed by DOI."""
        results = {}
        for doi in dois[:MAX_VERIFY]:
            results[doi] = self._verify_single(doi)
            time.sleep(0.12)  # ~8 req/sec, within polite pool limits
        return results

    def _verify_single(self, doi: str) -> Dict:
        """Verify a single DOI and return metadata."""
        url = f"{CROSSREF_BASE}/works/{requests.utils.quote(doi, safe='')}"
        try:
            resp = requests.get(url, headers=self._headers, timeout=10)
            if resp.status_code == 200:
                work = resp.json().get("message", {})
                title_parts = work.get("title", [])
                title = title_parts[0] if title_parts else "Unknown"
                # Extract year
                issued = work.get("issued", {}).get("date-parts", [[None]])
                year = issued[0][0] if issued and issued[0] else None
                return {
                    "valid": True,
                    "title": title[:200],
                    "year": year,
                    "citations": work.get("is-referenced-by-count", 0),
                    "journal": work.get("container-title", [""])[0] if work.get("container-title") else "",
                    "type": work.get("type", ""),
                }
            elif resp.status_code == 404:
                return {"valid": False, "error": "DOI not found"}
            else:
                return {"valid": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}


# ── Singleton ───────────────────────────────────────────────────────────────

_service = None


def get_crossref_service() -> CrossRefService:
    global _service
    if _service is None:
        _service = CrossRefService()
    return _service
