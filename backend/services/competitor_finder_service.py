"""
Competitor Finder Service - "Find My Competitors"
Finds labs, researchers, and preprints working on similar problems.
"""

import re
import json
import requests
from typing import Dict, List, Optional, Generator
from collections import defaultdict
from datetime import datetime, timedelta

from services.openalex_search_service import OpenAlexSearchService
from services.openai_client import get_openai_client


def _sse(event: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class CompetitorFinderService:
    """Find competing labs, researchers, and recent work in user's research area."""

    ARXIV_API = "http://export.arxiv.org/api/query"
    NIH_REPORTER_API = "https://api.reporter.nih.gov/v2/projects/search"

    def __init__(self):
        self.openalex = OpenAlexSearchService()
        self.openai = get_openai_client()
        self.session = requests.Session()

    def extract_research_focus(self, text: str) -> Dict:
        """Extract key research focus from manuscript."""
        try:
            response = self.openai.chat_completion(
                messages=[{
                    "role": "system",
                    "content": """Analyze this research manuscript and extract:
1. Main research question/hypothesis
2. Key methodology/approach
3. Target domain (e.g., "Alzheimer's disease", "RNA sequencing", "climate modeling")
4. Unique contribution/innovation
5. Search keywords for finding similar work (5-8 terms)
6. arXiv categories if applicable (e.g., "cs.LG", "q-bio.GN")

Return JSON:
{
  "research_question": "...",
  "methodology": "...",
  "domain": "...",
  "innovation": "...",
  "search_keywords": ["..."],
  "arxiv_categories": ["..."] or []
}"""
                }, {
                    "role": "user",
                    "content": text[:15000]
                }],
                temperature=0,
                max_tokens=1000
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]

            return json.loads(content)
        except Exception as e:
            print(f"[CompetitorFinder] Focus extraction failed: {e}")
            return {"domain": "unknown", "search_keywords": [], "arxiv_categories": []}

    def search_openalex_competitors(self, keywords: List[str], domain: str,
                                     from_year: int = 2023) -> List[Dict]:
        """Search OpenAlex for recent papers and group by institution."""

        all_papers = []

        # Search by domain + keywords
        for kw in keywords[:5]:
            query = f"{domain} {kw}"
            results = self.openalex.search_works(
                query=query,
                max_results=15,
                from_year=from_year
            )
            all_papers.extend(results)

        # Group by institution
        labs = defaultdict(lambda: {"papers": [], "authors": set(), "total_citations": 0})

        for paper in all_papers:
            # Skip if no author info
            if not paper.get('authors'):
                continue

            # Get institution from first author
            # Note: OpenAlex doesn't return institution in basic search, so we use author names
            first_author = paper['authors'][0] if paper['authors'] else "Unknown"

            # Use author name as proxy for lab identification
            lab_key = first_author.split()[-1] if first_author else "Unknown"  # Last name

            labs[lab_key]["papers"].append(paper)
            labs[lab_key]["authors"].update(paper['authors'])
            labs[lab_key]["total_citations"] += paper.get('cited_by_count', 0)

        # Convert to list and calculate overlap scores
        competitor_labs = []
        for lab_name, data in labs.items():
            if len(data["papers"]) >= 1:
                competitor_labs.append({
                    "name": lab_name,
                    "institution": data["papers"][0].get('journal', 'Unknown'),
                    "recent_papers": len(data["papers"]),
                    "total_citations": data["total_citations"],
                    "key_authors": list(data["authors"])[:5],
                    "top_papers": sorted(data["papers"],
                                        key=lambda x: x.get('cited_by_count', 0),
                                        reverse=True)[:3],
                    "most_recent_year": max(p.get('year', 0) for p in data["papers"])
                })

        # Sort by number of recent papers (activity level)
        competitor_labs.sort(key=lambda x: (x['recent_papers'], x['total_citations']), reverse=True)

        return competitor_labs[:10]

    def search_arxiv_preprints(self, keywords: List[str], categories: List[str],
                                days_back: int = 60) -> List[Dict]:
        """Search arXiv for recent preprints."""

        preprints = []
        query_terms = ' OR '.join([f'all:{kw}' for kw in keywords[:5]])

        try:
            params = {
                'search_query': query_terms,
                'start': 0,
                'max_results': 20,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }

            resp = self.session.get(self.ARXIV_API, params=params, timeout=15)

            if resp.status_code == 200:
                # Parse Atom XML response
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.content)

                ns = {'atom': 'http://www.w3.org/2005/Atom',
                      'arxiv': 'http://arxiv.org/schemas/atom'}

                for entry in root.findall('atom:entry', ns):
                    title = entry.find('atom:title', ns)
                    summary = entry.find('atom:summary', ns)
                    published = entry.find('atom:published', ns)
                    arxiv_id = entry.find('atom:id', ns)

                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name = author.find('atom:name', ns)
                        if name is not None:
                            authors.append(name.text)

                    # Get categories
                    cats = []
                    for cat in entry.findall('atom:category', ns):
                        cats.append(cat.get('term', ''))

                    if title is not None:
                        # Parse date
                        pub_date = published.text if published is not None else ""
                        days_ago = 0
                        if pub_date:
                            try:
                                pub_dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                                days_ago = (datetime.now(pub_dt.tzinfo) - pub_dt).days
                            except:
                                pass

                        preprints.append({
                            'title': title.text.strip().replace('\n', ' '),
                            'authors': authors[:5],
                            'abstract': (summary.text.strip()[:300] + '...') if summary is not None else '',
                            'arxiv_id': arxiv_id.text.split('/')[-1] if arxiv_id is not None else '',
                            'url': arxiv_id.text if arxiv_id is not None else '',
                            'published': pub_date[:10] if pub_date else '',
                            'days_ago': days_ago,
                            'categories': cats[:3],
                            'is_very_recent': days_ago <= 14
                        })

        except Exception as e:
            print(f"[CompetitorFinder] arXiv search failed: {e}")

        return preprints[:15]

    def search_nih_grants(self, keywords: List[str], domain: str) -> List[Dict]:
        """Search NIH Reporter for active grants on similar topics."""

        grants = []

        try:
            # Build search query
            search_text = f"{domain} {' '.join(keywords[:3])}"

            payload = {
                "criteria": {
                    "use_relevance": True,
                    "include_active_projects": True,
                    "exclude_subprojects": True,
                    "advanced_text_search": {
                        "operator": "and",
                        "search_field": "all",
                        "search_text": search_text
                    }
                },
                "offset": 0,
                "limit": 15,
                "sort_field": "project_start_date",
                "sort_order": "desc"
            }

            resp = self.session.post(
                self.NIH_REPORTER_API,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=15
            )

            if resp.status_code == 200:
                data = resp.json()
                for project in data.get('results', []):
                    grants.append({
                        'title': project.get('project_title', ''),
                        'pi_name': project.get('contact_pi_name', ''),
                        'organization': project.get('organization', {}).get('org_name', ''),
                        'total_cost': project.get('award_amount', 0),
                        'start_date': project.get('project_start_date', '')[:10] if project.get('project_start_date') else '',
                        'end_date': project.get('project_end_date', '')[:10] if project.get('project_end_date') else '',
                        'abstract': (project.get('abstract_text', '') or '')[:300] + '...',
                        'nih_link': f"https://reporter.nih.gov/project-details/{project.get('application_id', '')}"
                    })

        except Exception as e:
            print(f"[CompetitorFinder] NIH search failed: {e}")

        return grants

    def calculate_overlap_analysis(self, user_focus: Dict, competitors: List[Dict],
                                    preprints: List[Dict]) -> Dict:
        """Analyze overlap and generate actionable insights."""

        insights = []
        urgency_level = "low"

        # Check for very recent preprints
        very_recent = [p for p in preprints if p.get('is_very_recent')]
        if very_recent:
            urgency_level = "high"
            insights.append({
                "type": "urgent",
                "message": f"{len(very_recent)} preprint(s) dropped in the last 2 weeks on your topic!",
                "action": "Review immediately and differentiate your approach"
            })

        # Check for active competitors
        active_labs = [c for c in competitors if c.get('recent_papers', 0) >= 3]
        if len(active_labs) >= 3:
            if urgency_level != "high":
                urgency_level = "medium"
            insights.append({
                "type": "competition",
                "message": f"{len(active_labs)} labs are actively publishing in your area",
                "action": "Focus on your unique contribution to differentiate"
            })

        # Identify top threat
        if competitors:
            top_competitor = competitors[0]
            insights.append({
                "type": "top_threat",
                "message": f"{top_competitor['name']} lab has {top_competitor['recent_papers']} recent papers",
                "action": f"Review their work and cite appropriately"
            })

        return {
            "urgency_level": urgency_level,
            "insights": insights,
            "total_competitors": len(competitors),
            "total_preprints": len(preprints),
            "very_recent_preprints": len(very_recent)
        }

    def find_competitors(self, manuscript_text: str, field: str = None, keywords: List[str] = None) -> Generator[str, None, None]:
        """
        Find competing labs, preprints, and grants. Alias for analyze_stream with additional params.

        Args:
            manuscript_text: The research paper/manuscript text
            field: Optional field/domain override
            keywords: Optional keyword list override
        """
        # For now, delegate to analyze_stream (field/keywords will be extracted from text)
        # TODO: Use field/keywords overrides if provided
        yield from self.analyze_stream(manuscript_text)

    def analyze_stream(self, manuscript_text: str) -> Generator[str, None, None]:
        """Stream competitor analysis results."""

        try:
            # Step 1: Extract research focus
            yield _sse("progress", {"step": 1, "message": "Analyzing your research focus...", "percent": 10})

            focus = self.extract_research_focus(manuscript_text)

            yield _sse("focus", {
                "domain": focus.get('domain'),
                "research_question": focus.get('research_question', '')[:200],
                "methodology": focus.get('methodology', '')[:150],
                "innovation": focus.get('innovation', '')[:150],
                "keywords": focus.get('search_keywords', [])[:8]
            })

            # Step 2: Search OpenAlex for competing labs
            yield _sse("progress", {"step": 2, "message": "Finding competing labs...", "percent": 30})

            competitors = self.search_openalex_competitors(
                keywords=focus.get('search_keywords', []),
                domain=focus.get('domain', '')
            )

            yield _sse("competitors_found", {
                "count": len(competitors),
                "labs": competitors[:5]
            })

            # Step 3: Search arXiv for recent preprints
            yield _sse("progress", {"step": 3, "message": "Scanning recent preprints...", "percent": 55})

            preprints = self.search_arxiv_preprints(
                keywords=focus.get('search_keywords', []),
                categories=focus.get('arxiv_categories', [])
            )

            very_recent = [p for p in preprints if p.get('is_very_recent')]

            yield _sse("preprints_found", {
                "count": len(preprints),
                "very_recent": len(very_recent),
                "alert": len(very_recent) > 0
            })

            # Step 4: Search NIH for active grants
            yield _sse("progress", {"step": 4, "message": "Checking active NIH grants...", "percent": 75})

            grants = self.search_nih_grants(
                keywords=focus.get('search_keywords', []),
                domain=focus.get('domain', '')
            )

            yield _sse("grants_found", {"count": len(grants)})

            # Step 5: Generate overlap analysis
            yield _sse("progress", {"step": 5, "message": "Analyzing competition landscape...", "percent": 90})

            analysis = self.calculate_overlap_analysis(focus, competitors, preprints)

            # Final result
            yield _sse("complete", {
                "success": True,
                "domain": focus.get('domain'),
                "research_question": focus.get('research_question', ''),
                "urgency_level": analysis['urgency_level'],
                "insights": analysis['insights'],
                "competitor_labs": competitors,
                "recent_preprints": preprints,
                "active_grants": grants,
                "summary": {
                    "total_competitors": len(competitors),
                    "total_preprints": len(preprints),
                    "very_recent_preprints": len(very_recent),
                    "active_grants": len(grants)
                }
            })

        except Exception as e:
            print(f"[CompetitorFinder] Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            yield _sse("error", {"message": str(e)})


# Singleton
_service = None

def get_competitor_finder_service() -> CompetitorFinderService:
    global _service
    if _service is None:
        _service = CompetitorFinderService()
    return _service
