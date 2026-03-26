"""
Citation Analyzer Service - "Who Should I Cite?"
Analyzes a manuscript and finds missing citations, over-cited authors, and citation gaps.
"""

import re
import json
from typing import Dict, List, Optional, Generator
from collections import Counter

from services.openalex_search_service import OpenAlexSearchService
from services.openai_client import get_openai_client


def _sse(event: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class CitationAnalyzerService:
    """Analyze manuscript citations and find gaps."""

    def __init__(self):
        self.openalex = OpenAlexSearchService()
        self.openai = get_openai_client()

    def extract_references_from_text(self, text: str) -> List[Dict]:
        """Extract references from manuscript text using LLM."""
        try:
            response = self.openai.chat_completion(
                messages=[{
                    "role": "system",
                    "content": """Extract all cited references from this manuscript text.
Return JSON array of references with whatever info you can find:
[
  {"authors": "Smith et al.", "year": 2023, "title": "...", "doi": "..."},
  ...
]
Only include actual citations found in the text. If no citations found, return [].
Keep DOIs if present, otherwise leave as null."""
                }, {
                    "role": "user",
                    "content": text[:30000]  # Cap for token limits
                }],
                temperature=0,
                max_tokens=4000
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]

            refs = json.loads(content)
            return refs if isinstance(refs, list) else []
        except Exception as e:
            print(f"[CitationAnalyzer] Reference extraction failed: {e}")
            return []

    def extract_keywords_and_field(self, text: str) -> Dict:
        """Extract research keywords and field from manuscript."""
        try:
            response = self.openai.chat_completion(
                messages=[{
                    "role": "system",
                    "content": """Analyze this research manuscript and extract:
1. Primary research field (e.g., "molecular biology", "machine learning", "economics")
2. Subfield (e.g., "CRISPR gene editing", "transformer models", "behavioral economics")
3. Key methodologies mentioned
4. Main topics/concepts (5-10 keywords)
5. Organism/model system if applicable

Return JSON:
{
  "field": "...",
  "subfield": "...",
  "methodologies": ["..."],
  "keywords": ["..."],
  "organism": "..." or null
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
            print(f"[CitationAnalyzer] Keyword extraction failed: {e}")
            return {"field": "unknown", "subfield": "unknown", "keywords": [], "methodologies": []}

    def find_must_cite_papers(self, keywords: List[str], field: str,
                              subfield: str, from_year: int = 2020) -> List[Dict]:
        """Find seminal/important papers that should be cited."""
        papers = []

        # Search by subfield (most specific)
        if subfield and subfield != "unknown":
            results = self.openalex.search_works(
                query=subfield,
                max_results=20,
                from_year=from_year,
                min_citations=50
            )
            papers.extend(results)

        # Search by keywords
        for kw in keywords[:5]:
            results = self.openalex.search_works(
                query=f"{field} {kw}",
                max_results=10,
                from_year=from_year,
                min_citations=20
            )
            papers.extend(results)

        # Deduplicate by DOI
        seen_dois = set()
        unique_papers = []
        for p in papers:
            doi = p.get('doi') or p.get('title', '')
            if doi not in seen_dois:
                seen_dois.add(doi)
                unique_papers.append(p)

        # Sort by citations
        unique_papers.sort(key=lambda x: x.get('cited_by_count', 0), reverse=True)

        return unique_papers[:30]

    def analyze_citation_gaps(self, user_refs: List[Dict],
                               must_cite: List[Dict]) -> Dict:
        """Compare user citations against must-cite papers."""

        # Normalize user references for comparison
        user_dois = set()
        user_titles_lower = set()
        user_authors = Counter()

        for ref in user_refs:
            if ref.get('doi'):
                user_dois.add(ref['doi'].lower().replace('https://doi.org/', ''))
            if ref.get('title'):
                user_titles_lower.add(ref['title'].lower()[:50])
            if ref.get('authors'):
                # Extract first author
                author = ref['authors'].split(',')[0].split(' et al')[0].strip()
                user_authors[author] += 1

        # Find missing citations
        missing = []
        for paper in must_cite:
            paper_doi = (paper.get('doi') or '').lower().replace('https://doi.org/', '')
            paper_title = (paper.get('title') or '').lower()[:50]

            # Check if already cited
            is_cited = (
                (paper_doi and paper_doi in user_dois) or
                paper_title in user_titles_lower
            )

            if not is_cited:
                citations = paper.get('cited_by_count', 0)
                severity = 'high' if citations > 200 else 'medium' if citations > 50 else 'low'

                missing.append({
                    'title': paper.get('title', ''),
                    'authors': paper.get('authors', [])[:3],
                    'year': paper.get('year'),
                    'doi': paper.get('doi'),
                    'cited_by_count': citations,
                    'journal': paper.get('journal', ''),
                    'severity': severity,
                    'reason': f"Highly cited paper ({citations} citations) in your field"
                })

        # Sort missing by severity and citations
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        missing.sort(key=lambda x: (severity_order[x['severity']], -x['cited_by_count']))

        # Find over-cited authors
        over_cited = []
        for author, count in user_authors.most_common():
            if count >= 5:
                over_cited.append({
                    'author': author,
                    'count': count,
                    'warning': f"Cited {count} times - consider diversifying references"
                })

        return {
            'missing_citations': missing[:15],
            'over_cited_authors': over_cited,
            'total_user_citations': len(user_refs),
            'must_cite_found': len(must_cite),
            'citation_gap_count': len(missing)
        }

    def analyze_stream(self, manuscript_text: str) -> Generator[str, None, None]:
        """Stream citation analysis results."""

        try:
            # Step 1: Extract keywords and field
            yield _sse("progress", {"step": 1, "message": "Analyzing your manuscript...", "percent": 10})

            context = self.extract_keywords_and_field(manuscript_text)

            yield _sse("context", {
                "field": context.get('field'),
                "subfield": context.get('subfield'),
                "keywords": context.get('keywords', [])[:8],
                "methodologies": context.get('methodologies', [])[:5]
            })

            # Step 2: Extract existing citations
            yield _sse("progress", {"step": 2, "message": "Extracting your citations...", "percent": 30})

            user_refs = self.extract_references_from_text(manuscript_text)

            yield _sse("user_citations", {
                "count": len(user_refs),
                "sample": user_refs[:5]
            })

            # Step 3: Find must-cite papers
            yield _sse("progress", {"step": 3, "message": "Searching for seminal papers in your field...", "percent": 50})

            must_cite = self.find_must_cite_papers(
                keywords=context.get('keywords', []),
                field=context.get('field', ''),
                subfield=context.get('subfield', '')
            )

            yield _sse("must_cite_found", {"count": len(must_cite)})

            # Step 4: Analyze gaps
            yield _sse("progress", {"step": 4, "message": "Analyzing citation gaps...", "percent": 75})

            analysis = self.analyze_citation_gaps(user_refs, must_cite)

            # Step 5: Generate recommendations
            yield _sse("progress", {"step": 5, "message": "Generating recommendations...", "percent": 90})

            # Final result
            yield _sse("complete", {
                "success": True,
                "field": context.get('field'),
                "subfield": context.get('subfield'),
                "your_citations": len(user_refs),
                "missing_citations": analysis['missing_citations'],
                "over_cited_authors": analysis['over_cited_authors'],
                "citation_gap_count": analysis['citation_gap_count'],
                "coverage_score": max(0, 100 - (analysis['citation_gap_count'] * 5)),
                "recommendations": self._generate_recommendations(analysis, context)
            })

        except Exception as e:
            print(f"[CitationAnalyzer] Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            yield _sse("error", {"message": str(e)})

    def _generate_recommendations(self, analysis: Dict, context: Dict) -> List[str]:
        """Generate actionable recommendations."""
        recs = []

        high_severity = [m for m in analysis['missing_citations'] if m['severity'] == 'high']
        if high_severity:
            recs.append(f"Add {len(high_severity)} highly-cited seminal papers to strengthen your literature review")

        if analysis['over_cited_authors']:
            recs.append(f"Diversify citations - {analysis['over_cited_authors'][0]['author']} is cited {analysis['over_cited_authors'][0]['count']} times")

        if analysis['citation_gap_count'] > 10:
            recs.append("Consider expanding your literature review section")
        elif analysis['citation_gap_count'] < 3:
            recs.append("Good citation coverage! Only minor gaps detected")

        return recs


# Singleton
_service = None

def get_citation_analyzer_service() -> CitationAnalyzerService:
    global _service
    if _service is None:
        _service = CitationAnalyzerService()
    return _service
