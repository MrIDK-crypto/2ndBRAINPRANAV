"""
OpenAlex Search Service — Search academic papers via the OpenAlex API.
Used for literature search in co-work RAG pipeline.
"""

import time
import requests
from typing import Optional


class OpenAlexSearchService:
    """Search OpenAlex for academic papers, citations, and references."""

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str = "prmogathala@gmail.com"):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = f'2ndBrain/1.0 (mailto:{email})'
        self._last_request = 0

    def _rate_limit(self):
        """Respect OpenAlex polite pool: max 10 req/sec."""
        elapsed = time.time() - self._last_request
        if elapsed < 0.1:
            time.sleep(0.1 - elapsed)
        self._last_request = time.time()

    def search_works(self, query: str, max_results: int = 10,
                     from_year: Optional[int] = None,
                     to_year: Optional[int] = None,
                     min_citations: int = 0) -> list:
        """Search OpenAlex for academic papers matching query.

        Args:
            query: Search query string
            max_results: Max papers to return (capped at 50)
            from_year: Only papers published after this year
            to_year: Only papers published before or in this year (for year-aware recommendations)
            min_citations: Minimum citation count filter

        Returns:
            List of paper dicts with title, authors, abstract, DOI, etc.
        """
        self._rate_limit()
        params = {
            'search': query,
            'per_page': min(max_results, 50),
            'sort': 'relevance_score:desc',
            'select': 'id,doi,title,publication_year,cited_by_count,authorships,primary_location,abstract_inverted_index,concepts,type',
        }

        filters = []
        if from_year:
            filters.append(f'publication_year:>{from_year}')
        if to_year:
            filters.append(f'publication_year:<={to_year}')
        if min_citations > 0:
            filters.append(f'cited_by_count:>{min_citations}')
        if filters:
            params['filter'] = ','.join(filters)

        try:
            resp = self.session.get(f'{self.BASE_URL}/works', params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[OpenAlex] Search failed: {e}")
            return []

        results = []
        for work in resp.json().get('results', []):
            abstract = self._reconstruct_abstract(work.get('abstract_inverted_index'))

            authors = [a.get('author', {}).get('display_name', '')
                       for a in work.get('authorships', [])[:5]]

            journal = ''
            loc = work.get('primary_location') or {}
            if loc.get('source'):
                journal = loc['source'].get('display_name', '')

            results.append({
                'openalex_id': work.get('id', ''),
                'doi': work.get('doi', ''),
                'title': work.get('title', ''),
                'authors': authors,
                'year': work.get('publication_year'),
                'cited_by_count': work.get('cited_by_count', 0),
                'journal': journal,
                'abstract': abstract,
                'concepts': [c.get('display_name', '') for c in work.get('concepts', [])[:5]],
                'source_origin': 'openalex',
                'source_origin_label': 'OpenAlex',
            })

        return results

    def get_citations(self, openalex_id: str, max_results: int = 25) -> list:
        """Get papers that cite a given work.

        Args:
            openalex_id: OpenAlex work ID (e.g., 'https://openalex.org/W...')
            max_results: Max citing papers to return

        Returns:
            List of citing paper dicts
        """
        self._rate_limit()
        work_id = openalex_id.replace('https://openalex.org/', '')
        params = {
            'filter': f'cites:{work_id}',
            'per_page': min(max_results, 50),
            'sort': 'cited_by_count:desc',
            'select': 'id,doi,title,publication_year,cited_by_count,authorships,primary_location',
        }

        try:
            resp = self.session.get(f'{self.BASE_URL}/works', params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[OpenAlex] Citations fetch failed: {e}")
            return []

        return [{
            'openalex_id': w.get('id', ''),
            'doi': w.get('doi', ''),
            'title': w.get('title', ''),
            'year': w.get('publication_year'),
            'cited_by_count': w.get('cited_by_count', 0),
            'authors': [a.get('author', {}).get('display_name', '') for a in w.get('authorships', [])[:3]],
            'journal': (w.get('primary_location') or {}).get('source', {}).get('display_name', '') if w.get('primary_location') else '',
        } for w in resp.json().get('results', [])]

    def get_references(self, openalex_id: str) -> list:
        """Get papers referenced by a given work.

        Args:
            openalex_id: OpenAlex work ID

        Returns:
            List of referenced paper dicts
        """
        self._rate_limit()
        work_id = openalex_id.replace('https://openalex.org/', '')

        try:
            resp = self.session.get(f'{self.BASE_URL}/works/{work_id}',
                                    params={'select': 'referenced_works'}, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[OpenAlex] References fetch failed: {e}")
            return []

        ref_ids = resp.json().get('referenced_works', [])
        if not ref_ids:
            return []

        # Batch fetch referenced works (max 25)
        filter_str = '|'.join(r.replace('https://openalex.org/', '') for r in ref_ids[:25])
        self._rate_limit()

        try:
            resp2 = self.session.get(f'{self.BASE_URL}/works',
                                      params={'filter': f'openalex:{filter_str}',
                                              'per_page': 25,
                                              'select': 'id,doi,title,publication_year,cited_by_count'},
                                      timeout=15)
            resp2.raise_for_status()
        except Exception as e:
            print(f"[OpenAlex] Batch reference fetch failed: {e}")
            return []

        return [{
            'openalex_id': w.get('id', ''),
            'doi': w.get('doi', ''),
            'title': w.get('title', ''),
            'year': w.get('publication_year'),
            'cited_by_count': w.get('cited_by_count', 0),
        } for w in resp2.json().get('results', [])]

    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ''
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return ' '.join(w for _, w in word_positions)
