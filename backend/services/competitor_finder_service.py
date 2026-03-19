"""
Competitor Finder Service
Searches OpenAlex, arXiv, and NIH Reporter to find competing labs,
recent preprints, and active grants for a research paper's topic.
Yields SSE events for each step.
"""

import json
import re
import traceback
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Generator

import requests

from services.openai_client import get_openai_client


class CompetitorFinderService:
    """Finds competitors for a research paper across OpenAlex, arXiv, and NIH Reporter."""

    def __init__(self):
        self.openai = get_openai_client()

    # ── Public entry point ────────────────────────────────────────────────

    def find_competitors(
        self,
        paper_text: str,
        field: str = '',
        keywords: list[str] | None = None,
    ) -> Generator[str, None, None]:
        """
        Main pipeline. Yields SSE event strings for each step:
          1. Extract topic via GPT
          2. Search OpenAlex for competing labs
          3. Search arXiv for recent preprints
          4. Search NIH Reporter for active grants
          5. Calculate urgency score
        """
        try:
            # ── Step 1: Extract topic ──────────────────────────────────────
            yield self._sse('progress', {'step': 1, 'message': 'Extracting research topic...', 'percent': 10})
            topic_info = self._extract_topic(paper_text, field, keywords)
            yield self._sse('topic_extracted', topic_info)

            # ── Step 2: Search OpenAlex ────────────────────────────────────
            yield self._sse('progress', {'step': 2, 'message': 'Searching OpenAlex for competing labs...', 'percent': 30})
            labs = self._search_openalex(topic_info)
            yield self._sse('competing_labs', {'labs': labs})

            # ── Step 3: Search arXiv ───────────────────────────────────────
            yield self._sse('progress', {'step': 3, 'message': 'Searching arXiv for recent preprints...', 'percent': 55})
            preprints = self._search_arxiv(topic_info)
            yield self._sse('preprints', {'preprints': preprints})

            # ── Step 4: Search NIH Reporter ────────────────────────────────
            yield self._sse('progress', {'step': 4, 'message': 'Searching NIH Reporter for active grants...', 'percent': 75})
            grants = self._search_nih(topic_info)
            yield self._sse('grants', {'grants': grants})

            # ── Step 5: Calculate urgency ──────────────────────────────────
            yield self._sse('progress', {'step': 5, 'message': 'Calculating competition urgency...', 'percent': 90})
            urgency = self._calculate_urgency(labs, preprints, grants)
            yield self._sse('urgency', urgency)

            # ── Done ──────────────────────────────────────────────────────
            yield self._sse('progress', {'step': 5, 'message': 'Complete!', 'percent': 100})
            yield self._sse('complete', {
                'topic': topic_info,
                'competing_labs': labs,
                'preprints': preprints,
                'grants': grants,
                'urgency': urgency,
            })

        except Exception as e:
            print(f"[CompetitorFinder] Pipeline error: {e}", flush=True)
            traceback.print_exc()
            yield self._sse('error', {'error': str(e)})

    # ── SSE helper ────────────────────────────────────────────────────────

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    # ── Step 1: Extract topic via GPT ──────────────────────────────────────

    def _extract_topic(self, paper_text: str, field: str, keywords: list[str] | None) -> dict:
        text_excerpt = paper_text[:10000]
        kw_str = ', '.join(keywords) if keywords else 'auto-detect'

        prompt = (
            "You are an expert research analyst. Analyze the following research paper excerpt and "
            "extract the core research topic for competitor analysis.\n\n"
            f"Field: {field or 'auto-detect'}\n"
            f"Keywords provided by user: {kw_str}\n\n"
            "Return a JSON object with these keys:\n"
            "- topic: string — concise description of the research topic (1-2 sentences)\n"
            "- search_queries: list of 3 strings — specific search queries to find competing work\n"
            "- key_terms: list of strings — 5-8 key technical terms from the paper\n"
            "- arxiv_categories: list of strings — relevant arXiv category codes (e.g. 'cs.AI', 'q-bio.BM')\n\n"
            "Return ONLY the JSON object, no markdown fences.\n\n"
            f"PAPER EXCERPT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1000,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback
        return {
            "topic": "Research topic extracted from paper",
            "search_queries": [field or "research"] if field else ["research"],
            "key_terms": keywords or ["research"],
            "arxiv_categories": [],
        }

    # ── Step 2: Search OpenAlex ────────────────────────────────────────────

    def _search_openalex(self, topic_info: dict) -> list[dict]:
        """Search OpenAlex for competing labs. Deduplicates by institution, keeps highest cited."""
        queries = topic_info.get('search_queries', [])
        if not queries:
            queries = [topic_info.get('topic', 'research')]

        two_years_ago = (datetime.now(timezone.utc) - timedelta(days=730)).strftime('%Y-%m-%d')
        institution_map: dict[str, dict] = {}  # institution -> best result

        for query in queries[:3]:
            try:
                params = {
                    'search': query,
                    'filter': f'from_publication_date:{two_years_ago}',
                    'sort': 'cited_by_count:desc',
                    'per_page': 15,
                    'mailto': 'prmogathala@gmail.com',
                }
                resp = requests.get('https://api.openalex.org/works', params=params, timeout=15)
                if resp.status_code != 200:
                    print(f"[CompetitorFinder] OpenAlex returned {resp.status_code} for query: {query}", flush=True)
                    continue

                data = resp.json()
                for work in data.get('results', []):
                    # Extract institutions and lead author
                    authorships = work.get('authorships', [])
                    if not authorships:
                        continue

                    lead = authorships[0]
                    author_name = lead.get('author', {}).get('display_name', 'Unknown')
                    institutions = lead.get('institutions', [])
                    institution_name = institutions[0].get('display_name', 'Unknown Institution') if institutions else 'Unknown Institution'

                    cited_by = work.get('cited_by_count', 0)
                    pub_year = work.get('publication_year', 0)
                    doi = work.get('doi', '')
                    title = work.get('title', 'Untitled')

                    # Deduplicate by institution, keep highest cited
                    existing = institution_map.get(institution_name)
                    if existing is None or cited_by > existing.get('cited_by', 0):
                        institution_map[institution_name] = {
                            'institution': institution_name,
                            'lead_author': author_name,
                            'paper_title': title,
                            'year': pub_year,
                            'cited_by': cited_by,
                            'doi': doi,
                        }

                # Rate limit courtesy
                time.sleep(0.3)

            except Exception as e:
                print(f"[CompetitorFinder] OpenAlex error for query '{query}': {e}", flush=True)
                continue

        # Sort by cited_by descending and return up to 15
        labs = sorted(institution_map.values(), key=lambda x: x.get('cited_by', 0), reverse=True)
        return labs[:15]

    # ── Step 3: Search arXiv ──────────────────────────────────────────────

    def _search_arxiv(self, topic_info: dict) -> list[dict]:
        """Search arXiv API for recent preprints. Flags papers from last 14 days."""
        queries = topic_info.get('search_queries', [])
        if not queries:
            queries = [topic_info.get('topic', 'research')]

        # Build arXiv query
        # Combine queries with OR, and optionally add category filters
        search_parts = []
        for q in queries[:3]:
            # Escape special arXiv query chars
            clean_q = q.replace('"', '').replace('(', '').replace(')', '')
            search_parts.append(f'all:"{clean_q}"')

        arxiv_query = ' OR '.join(search_parts)

        # Add category filter if available
        categories = topic_info.get('arxiv_categories', [])
        if categories:
            cat_filter = ' OR '.join(f'cat:{c}' for c in categories[:3])
            arxiv_query = f'({arxiv_query}) AND ({cat_filter})'

        preprints = []
        now = datetime.now(timezone.utc)
        fourteen_days_ago = now - timedelta(days=14)

        try:
            params = {
                'search_query': arxiv_query,
                'start': 0,
                'max_results': 20,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending',
            }
            resp = requests.get('http://export.arxiv.org/api/query', params=params, timeout=20)
            if resp.status_code != 200:
                print(f"[CompetitorFinder] arXiv returned {resp.status_code}", flush=True)
                return []

            # Parse Atom XML
            root = ET.fromstring(resp.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            for entry in root.findall('atom:entry', ns):
                title_el = entry.find('atom:title', ns)
                title = title_el.text.strip().replace('\n', ' ') if title_el is not None and title_el.text else 'Untitled'

                # Authors
                authors = []
                for author_el in entry.findall('atom:author', ns):
                    name_el = author_el.find('atom:name', ns)
                    if name_el is not None and name_el.text:
                        authors.append(name_el.text.strip())

                # Published date
                published_el = entry.find('atom:published', ns)
                published_str = published_el.text.strip() if published_el is not None and published_el.text else ''
                published_date = None
                days_ago = None
                is_recent = False
                if published_str:
                    try:
                        published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                        days_ago = (now - published_date).days
                        is_recent = published_date >= fourteen_days_ago
                    except (ValueError, TypeError):
                        pass

                # URL
                url = ''
                for link_el in entry.findall('atom:link', ns):
                    if link_el.get('type') == 'text/html' or link_el.get('rel') == 'alternate':
                        url = link_el.get('href', '')
                        break
                if not url:
                    id_el = entry.find('atom:id', ns)
                    url = id_el.text.strip() if id_el is not None and id_el.text else ''

                # Summary
                summary_el = entry.find('atom:summary', ns)
                summary = summary_el.text.strip().replace('\n', ' ')[:300] if summary_el is not None and summary_el.text else ''

                preprints.append({
                    'title': title,
                    'authors': authors[:5],
                    'published': published_str[:10] if published_str else '',
                    'days_ago': days_ago,
                    'is_recent': is_recent,
                    'url': url,
                    'summary': summary,
                })

        except Exception as e:
            print(f"[CompetitorFinder] arXiv error: {e}", flush=True)
            traceback.print_exc()

        return preprints[:20]

    # ── Step 4: Search NIH Reporter ────────────────────────────────────────

    def _search_nih(self, topic_info: dict) -> list[dict]:
        """Search NIH Reporter API for active grants matching the topic."""
        topic = topic_info.get('topic', '')
        key_terms = topic_info.get('key_terms', [])

        # Build search text: combine topic and key terms
        search_text = topic
        if key_terms:
            search_text += ' ' + ' '.join(key_terms[:5])

        grants = []
        try:
            payload = {
                'criteria': {
                    'advanced_text_search': {
                        'operator': 'and',
                        'search_field': 'projecttitle,terms',
                        'search_text': search_text[:500],
                    },
                    'is_active': True,
                },
                'offset': 0,
                'limit': 15,
                'sort_field': 'FiscalYear',
                'sort_order': 'desc',
            }

            resp = requests.post(
                'https://api.reporter.nih.gov/v2/projects/search',
                json=payload,
                timeout=20,
                headers={'Content-Type': 'application/json'},
            )

            if resp.status_code != 200:
                print(f"[CompetitorFinder] NIH Reporter returned {resp.status_code}", flush=True)
                return []

            data = resp.json()
            for project in data.get('results', []):
                pi_names = []
                for pi in project.get('principal_investigators', []):
                    name = pi.get('full_name', '') or f"{pi.get('first_name', '')} {pi.get('last_name', '')}".strip()
                    if name:
                        pi_names.append(name)

                org = project.get('organization', {})
                org_name = org.get('org_name', 'Unknown') if org else 'Unknown'

                award_amount = project.get('award_amount', None)
                if award_amount is not None:
                    try:
                        award_amount = int(award_amount)
                    except (ValueError, TypeError):
                        award_amount = None

                grants.append({
                    'title': project.get('project_title', 'Untitled'),
                    'pi': ', '.join(pi_names) if pi_names else 'Unknown',
                    'organization': org_name,
                    'activity_code': project.get('activity_code', ''),
                    'award_amount': award_amount,
                    'fiscal_year': project.get('fiscal_year', None),
                    'project_num': project.get('project_num', ''),
                })

        except Exception as e:
            print(f"[CompetitorFinder] NIH Reporter error: {e}", flush=True)
            traceback.print_exc()

        return grants[:15]

    # ── Step 5: Calculate urgency ─────────────────────────────────────────

    def _calculate_urgency(self, labs: list, preprints: list, grants: list) -> dict:
        """Score competition urgency based on recent activity."""
        score = 0
        reasons = []

        # Recent preprints (<14 days)
        recent_count = sum(1 for p in preprints if p.get('is_recent'))
        if recent_count >= 3:
            score += 40
            reasons.append(f'{recent_count} preprints in last 14 days')
        elif recent_count >= 1:
            score += 20
            reasons.append(f'{recent_count} preprint(s) in last 14 days')

        # Competing labs
        lab_count = len(labs)
        if lab_count >= 10:
            score += 30
            reasons.append(f'{lab_count} competing labs identified')
        elif lab_count >= 5:
            score += 15
            reasons.append(f'{lab_count} competing labs identified')

        # Active grants
        grant_count = len(grants)
        if grant_count >= 5:
            score += 20
            reasons.append(f'{grant_count} active NIH grants')
        elif grant_count >= 2:
            score += 10
            reasons.append(f'{grant_count} active NIH grants')

        # Total preprints
        total_preprints = len(preprints)
        if total_preprints >= 15:
            score += 10
            reasons.append(f'{total_preprints} total preprints found')

        # Determine level
        if score >= 60:
            level = 'high'
        elif score >= 30:
            level = 'medium'
        else:
            level = 'low'

        return {
            'score': score,
            'level': level,
            'reasons': reasons,
            'recent_preprints': recent_count,
            'competing_labs': lab_count,
            'active_grants': grant_count,
            'total_preprints': total_preprints,
        }


# ── Singleton ─────────────────────────────────────────────────────────────

_service = None


def get_competitor_finder_service() -> CompetitorFinderService:
    global _service
    if _service is None:
        _service = CompetitorFinderService()
    return _service
