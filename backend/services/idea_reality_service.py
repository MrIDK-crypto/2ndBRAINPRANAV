"""
Idea Reality Service — validates research ideas against real-world databases.
Uses GitHub API search as the primary mechanism (no external dependency needed).
"""

import re
import requests
from datetime import datetime
from typing import Dict


class IdeaRealityService:
    """Validates research ideas against GitHub, PyPI, and web sources."""

    def check_idea(self, idea_description: str) -> Dict:
        """Check if similar implementations of this research idea already exist.

        Searches GitHub repos and PyPI packages for competing implementations.
        Returns reality_signal (0-100), competitors, and verdict.
        """
        results = {
            "reality_signal": 0,
            "competitors": [],
            "github_repos": 0,
            "pypi_packages": 0,
            "verdict": "UNKNOWN",
            "recommendation": "",
        }

        # Search GitHub
        try:
            gh_resp = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": idea_description, "sort": "stars", "per_page": 10},
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=15,
            )
            if gh_resp.ok:
                gh_data = gh_resp.json()
                total = gh_data.get("total_count", 0)
                results["github_repos"] = total

                for item in gh_data.get("items", [])[:5]:
                    results["competitors"].append({
                        "name": item["full_name"],
                        "stars": item["stargazers_count"],
                        "url": item["html_url"],
                        "description": (item.get("description") or "")[:200],
                        "language": item.get("language", ""),
                        "updated": item.get("updated_at", "")[:10],
                        "source": "github",
                    })
        except Exception as e:
            print(f"[IdeaReality] GitHub search error: {e}")

        # Search PyPI
        try:
            pypi_resp = requests.get(
                f"https://pypi.org/pypi/{idea_description.replace(' ', '-')}/json",
                timeout=10,
            )
            if pypi_resp.ok:
                results["pypi_packages"] += 1

            # Also try search
            search_resp = requests.get(
                "https://pypi.org/search/",
                params={"q": idea_description},
                headers={"Accept": "text/html"},
                timeout=10,
            )
            if search_resp.ok:
                # Count approximate results from HTML
                matches = re.findall(r'class="package-snippet"', search_resp.text)
                results["pypi_packages"] = max(results["pypi_packages"], len(matches))
        except Exception as e:
            print(f"[IdeaReality] PyPI search error: {e}")

        # Calculate reality signal
        gh_count = results["github_repos"]
        top_stars = max([c["stars"] for c in results["competitors"]] or [0])

        if gh_count > 500 or top_stars > 5000:
            results["reality_signal"] = 90
            results["verdict"] = "HIGH"
            results["recommendation"] = (
                "This space is highly competitive. "
                "Look for a specific niche or novel angle."
            )
        elif gh_count > 100 or top_stars > 1000:
            results["reality_signal"] = 70
            results["verdict"] = "MEDIUM-HIGH"
            results["recommendation"] = (
                "Significant existing work. "
                "Your implementation should clearly differentiate."
            )
        elif gh_count > 30 or top_stars > 200:
            results["reality_signal"] = 50
            results["verdict"] = "MEDIUM"
            results["recommendation"] = (
                "Some competition exists. Room for a novel approach."
            )
        elif gh_count > 5:
            results["reality_signal"] = 30
            results["verdict"] = "LOW"
            results["recommendation"] = (
                "Limited existing implementations. "
                "Good opportunity for a new entry."
            )
        else:
            results["reality_signal"] = 10
            results["verdict"] = "VERY LOW"
            results["recommendation"] = (
                "Very few existing implementations. "
                "This could be a novel contribution."
            )

        # Add trend indicator based on update recency of top repos
        recent_count = 0
        for c in results["competitors"]:
            if c.get("updated"):
                try:
                    updated = datetime.strptime(c["updated"], "%Y-%m-%d")
                    if (datetime.now() - updated).days < 90:
                        recent_count += 1
                except ValueError:
                    pass

        if recent_count >= 3:
            results["trend"] = "accelerating"
        elif recent_count >= 1:
            results["trend"] = "active"
        else:
            results["trend"] = "stable"

        return results


# Singleton
_service = None


def get_idea_reality_service() -> IdeaRealityService:
    global _service
    if _service is None:
        _service = IdeaRealityService()
    return _service
