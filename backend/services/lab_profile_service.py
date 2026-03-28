"""
Lab Profile Service - Extracts structured research profiles from user documents.

This service analyzes a lab's document corpus to build a comprehensive profile
that enables context-aware analysis in tools like High Impact Journal and Protocol Optimizer.

The profile includes:
- Research focus areas and methodologies
- Publication history and typical journal tiers
- Equipment and techniques commonly used
- Collaboration networks
- Known issues and failed experiments
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from services.openai_client import get_openai_client


@dataclass
class LabProfile:
    """Structured lab profile for context-aware analysis."""

    # Core research identity
    research_focus_areas: List[str]  # Main research topics/areas
    methodologies: List[str]  # Common techniques and methods
    model_systems: List[str]  # Cell lines, organisms, etc.

    # Publication history
    publication_history: List[Dict]  # [{journal, year, topic, impact_tier}]
    typical_impact_tier: int  # 1-4, where 1 is highest (Nature/Science)
    preferred_journals: List[str]  # Journals they frequently publish in

    # Lab capabilities
    equipment: List[str]  # Known equipment/platforms
    expertise_areas: List[str]  # What they're known for

    # Collaboration & network
    collaborators: List[str]  # Institutions, key collaborators
    funding_sources: List[str]  # NIH, NSF, etc.

    # Issues & learnings
    known_issues: List[Dict]  # Past failures, rejected submissions
    successful_strategies: List[str]  # What has worked

    # Source tracking - maps field to list of source documents
    sources: Dict[str, List[Dict]]  # {"methodologies": [{"title": "...", "source_type": "slack", "excerpt": "..."}]}

    # Metadata
    document_count: int
    last_updated: str
    confidence_score: float  # 0-1, how confident we are in the profile

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_prompt_context(self) -> str:
        """Format profile for inclusion in LLM prompts."""
        sections = []

        def format_with_sources(field_name: str, items: List[str], label: str) -> str:
            """Format a field with source citations."""
            result = f"**{label}:** {', '.join(items)}"
            if field_name in self.sources and self.sources[field_name]:
                src_list = self.sources[field_name][:2]  # Top 2 sources
                src_refs = []
                for src in src_list:
                    src_type = src.get('source_type', 'document')
                    title = src.get('title', 'Unknown')[:40]
                    src_refs.append(f"[{src_type}: {title}]")
                if src_refs:
                    result += f"\n  _Sources: {', '.join(src_refs)}_"
            return result

        # Research Identity
        if self.research_focus_areas:
            sections.append(format_with_sources('research_focus_areas', self.research_focus_areas, 'Research Focus Areas'))
        if self.methodologies:
            sections.append(format_with_sources('methodologies', self.methodologies, 'Common Methodologies'))
        if self.model_systems:
            sections.append(format_with_sources('model_systems', self.model_systems, 'Model Systems'))

        # Publication History
        if self.publication_history:
            pub_summary = []
            for pub in self.publication_history[:5]:  # Top 5
                pub_summary.append(f"- {pub.get('journal', 'Unknown')} ({pub.get('year', '?')}): {pub.get('topic', 'N/A')}")
            sections.append(f"**Recent Publications:**\n" + "\n".join(pub_summary))

        if self.preferred_journals:
            sections.append(f"**Preferred Journals:** {', '.join(self.preferred_journals[:5])}")

        sections.append(f"**Typical Publication Tier:** Tier {self.typical_impact_tier} (1=Nature/Science, 4=Specialized)")

        # Capabilities
        if self.equipment:
            sections.append(format_with_sources('equipment', self.equipment, 'Lab Equipment'))
        if self.expertise_areas:
            sections.append(format_with_sources('expertise_areas', self.expertise_areas, 'Expertise Areas'))

        # Issues & Strategies with sources
        if self.known_issues:
            issues_with_src = []
            for i in self.known_issues[:3]:
                issue_text = f"- {i.get('description', str(i))}"
                if i.get('source'):
                    issue_text += f" _[Source: {i.get('source', 'Unknown')[:30]}]_"
                issues_with_src.append(issue_text)
            sections.append(f"**Known Issues/Past Failures:**\n" + "\n".join(issues_with_src))

        if self.successful_strategies:
            sections.append(f"**What Has Worked:** {'; '.join(self.successful_strategies[:3])}")

        return "\n\n".join(sections)


class LabProfileService:
    """Service for building and managing lab profiles."""

    def __init__(self):
        self.openai = get_openai_client()

    def build_profile(
        self,
        tenant_id: str,
        documents: List[Dict],
        existing_profile: Optional[Dict] = None
    ) -> LabProfile:
        """
        Build a comprehensive lab profile from documents.

        Args:
            tenant_id: The tenant ID
            documents: List of documents with 'content', 'title', 'metadata'
            existing_profile: Previous profile to update (incremental)

        Returns:
            LabProfile with structured information
        """
        if not documents:
            return self._empty_profile()

        # Prepare document summaries for analysis
        doc_summaries = self._prepare_documents(documents)

        # Extract profile components in parallel-ish
        profile_data = self._extract_profile_with_llm(doc_summaries)

        # Extract publication history specifically
        publications = self._extract_publications(documents)

        # Detect equipment and methods with source tracking
        equipment_methods = self._extract_equipment_methods(documents)

        # Detect known issues/failures
        issues = self._extract_issues(documents)

        # Merge with existing profile if provided
        if existing_profile:
            profile_data = self._merge_profiles(existing_profile, profile_data)

        # Calculate confidence based on document count and quality
        confidence = min(1.0, len(documents) / 20)  # Full confidence at 20+ docs

        # Build sources map from documents
        sources = self._build_sources_map(documents, equipment_methods, profile_data)

        return LabProfile(
            research_focus_areas=profile_data.get('research_focus_areas', []),
            methodologies=profile_data.get('methodologies', []) + equipment_methods.get('methods', []),
            model_systems=profile_data.get('model_systems', []),
            publication_history=publications,
            typical_impact_tier=self._calculate_typical_tier(publications),
            preferred_journals=self._extract_preferred_journals(publications),
            equipment=equipment_methods.get('equipment', []),
            expertise_areas=profile_data.get('expertise_areas', []),
            collaborators=profile_data.get('collaborators', []),
            funding_sources=profile_data.get('funding_sources', []),
            known_issues=issues,
            successful_strategies=profile_data.get('successful_strategies', []),
            sources=sources,
            document_count=len(documents),
            last_updated=datetime.utcnow().isoformat(),
            confidence_score=confidence
        )

    def _prepare_documents(self, documents: List[Dict], max_chars: int = 50000) -> str:
        """Prepare document content for LLM analysis."""
        summaries = []
        total_chars = 0

        for doc in documents:
            title = doc.get('metadata', {}).get('title', doc.get('title', 'Untitled'))
            content = doc.get('content', '')[:2000]  # First 2000 chars per doc
            source = doc.get('metadata', {}).get('source_type', 'document')

            summary = f"[{source.upper()}] {title}\n{content}\n---"

            if total_chars + len(summary) > max_chars:
                break

            summaries.append(summary)
            total_chars += len(summary)

        return "\n\n".join(summaries)

    def _extract_profile_with_llm(self, doc_summaries: str) -> Dict:
        """Use LLM to extract structured profile from documents."""
        prompt = f"""Analyze these research documents and extract a structured lab profile.

DOCUMENTS:
{doc_summaries[:40000]}

Extract the following information. Be specific and evidence-based - only include what you can infer from the documents.

Return JSON:
{{
    "research_focus_areas": ["list of 2-5 main research topics/areas this lab works on"],
    "methodologies": ["list of techniques/methods commonly used (e.g., CRISPR, RNA-seq, Western blot)"],
    "model_systems": ["organisms, cell lines, or systems used (e.g., mice, HeLa cells, zebrafish)"],
    "expertise_areas": ["what this lab is particularly skilled at or known for"],
    "collaborators": ["institutions or notable collaborators mentioned"],
    "funding_sources": ["NIH, NSF, or other funding mentioned"],
    "successful_strategies": ["approaches or methods that seem to work well for them"],
    "research_style": "brief description of their research approach (e.g., 'highly quantitative', 'translational focus', 'methods development')"
}}

Be conservative - only include items you're confident about from the documents. Use empty lists if uncertain."""

        try:
            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a research analyst extracting structured information from academic documents. Be precise and evidence-based."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"[LabProfile] LLM extraction error: {e}")
            return {}

    def _extract_publications(self, documents: List[Dict]) -> List[Dict]:
        """Extract publication history from documents."""
        publications = []

        # Look for publication patterns in documents
        journal_patterns = [
            r'published in ([A-Z][a-zA-Z\s&]+)',
            r'appeared in ([A-Z][a-zA-Z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\s*\(\d{4}\)',
            r'Journal:\s*([A-Za-z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\.\s+\d{4}',  # "Journal Name. 2024"
        ]

        year_pattern = r'\b(20\d{2}|19\d{2})\b'

        # Publication source types - including PubMed!
        publication_source_types = ('paper', 'publication', 'article', 'pubmed', 'zotero')

        for doc in documents:
            content = doc.get('content', '')
            title = doc.get('metadata', {}).get('title', doc.get('title', ''))
            metadata = doc.get('metadata', {})

            # Check if this document IS a publication
            source_type = metadata.get('source_type', '')
            if source_type in publication_source_types:
                journal = None
                year = None

                # PRIORITY 1: Check metadata directly (PubMed stores journal here)
                if metadata.get('journal'):
                    journal = metadata['journal']
                    # Extract year from content or metadata
                    year_match = re.search(year_pattern, content[:1000])
                    year = year_match.group(1) if year_match else None

                # PRIORITY 2: Try regex patterns on content
                if not journal:
                    for pattern in journal_patterns:
                        match = re.search(pattern, content[:3000])
                        if match:
                            journal = match.group(1).strip()
                            year_match = re.search(year_pattern, content[:1000])
                            year = year_match.group(1) if year_match else None
                            break

                # Add publication if we found a journal
                if journal:
                    publications.append({
                        'journal': journal,
                        'year': year,
                        'topic': title[:100] if title else 'Unknown',
                        'impact_tier': self._estimate_journal_tier(journal),
                        'source_type': source_type,
                        'pmid': metadata.get('pmid'),
                        'authors': metadata.get('authors', [])[:3]  # First 3 authors
                    })
                    print(f"[LabProfile] Found publication: {journal} ({year}) - {title[:50]}", flush=True)

        print(f"[LabProfile] Extracted {len(publications)} publications from {len(documents)} documents", flush=True)

        # Deduplicate
        seen = set()
        unique_pubs = []
        for pub in publications:
            key = (pub.get('journal', ''), pub.get('year', ''), pub.get('topic', '')[:30])
            if key not in seen:
                seen.add(key)
                unique_pubs.append(pub)

        return unique_pubs[:15]  # Top 15

    def _extract_equipment_methods(self, documents: List[Dict]) -> Dict:
        """Extract equipment and methods mentioned in documents with source tracking."""
        # Common equipment patterns
        equipment_keywords = [
            'microscope', 'sequencer', 'spectrometer', 'centrifuge', 'PCR',
            'flow cytometer', 'FACS', 'mass spec', 'NMR', 'MRI', 'CT scan',
            'Illumina', 'NovaSeq', '10X Genomics', 'Oxford Nanopore',
            'confocal', 'electron microscope', 'plate reader', 'HPLC',
            'LC-MS', 'GC-MS', 'qPCR', 'real-time PCR', 'droplet digital PCR'
        ]

        # Common method patterns
        method_keywords = [
            'CRISPR', 'RNA-seq', 'ChIP-seq', 'ATAC-seq', 'Western blot',
            'immunoprecipitation', 'co-IP', 'pull-down', 'transfection',
            'electroporation', 'viral transduction', 'lentiviral',
            'single-cell', 'bulk RNA', 'proteomics', 'metabolomics',
            'ELISA', 'immunofluorescence', 'immunohistochemistry', 'IHC',
            'flow cytometry', 'cell sorting', 'cloning', 'mutagenesis',
            'knockout', 'knockdown', 'siRNA', 'shRNA', 'guide RNA'
        ]

        equipment_found = {}  # {keyword: [sources]}
        methods_found = {}    # {keyword: [sources]}

        for doc in documents:
            content = doc.get('content', '').lower()
            doc_source = {
                'title': doc.get('metadata', {}).get('title', doc.get('title', 'Unknown'))[:50],
                'source_type': doc.get('metadata', {}).get('source_type', 'document'),
            }

            for eq in equipment_keywords:
                if eq.lower() in content:
                    if eq not in equipment_found:
                        equipment_found[eq] = []
                    if len(equipment_found[eq]) < 3:  # Track up to 3 sources per item
                        # Extract excerpt around the keyword
                        idx = content.find(eq.lower())
                        excerpt = content[max(0, idx-30):min(len(content), idx+50)]
                        doc_source_with_excerpt = dict(doc_source)
                        doc_source_with_excerpt['excerpt'] = excerpt.strip()
                        equipment_found[eq].append(doc_source_with_excerpt)

            for method in method_keywords:
                if method.lower() in content:
                    if method not in methods_found:
                        methods_found[method] = []
                    if len(methods_found[method]) < 3:
                        idx = content.find(method.lower())
                        excerpt = content[max(0, idx-30):min(len(content), idx+50)]
                        doc_source_with_excerpt = dict(doc_source)
                        doc_source_with_excerpt['excerpt'] = excerpt.strip()
                        methods_found[method].append(doc_source_with_excerpt)

        return {
            'equipment': list(equipment_found.keys()),
            'methods': list(methods_found.keys()),
            'equipment_sources': equipment_found,
            'methods_sources': methods_found
        }

    def _build_sources_map(self, documents: List[Dict], equipment_methods: Dict, profile_data: Dict) -> Dict[str, List[Dict]]:
        """Build a map of field names to their source documents."""
        sources = {}

        # Build general sources FIRST from all documents (these are always available)
        general_sources = []
        for doc in documents[:15]:  # Sample up to 15 documents
            title = doc.get('metadata', {}).get('title', doc.get('title', 'Unknown'))
            source_type = doc.get('metadata', {}).get('source_type', 'document')
            if title and title != 'Unknown':
                general_sources.append({
                    'title': title[:60],
                    'source_type': source_type,
                })

        # Always add general sources to main fields
        sources['research_focus_areas'] = general_sources[:4]
        sources['expertise_areas'] = general_sources[:4]
        sources['model_systems'] = general_sources[:3]
        sources['general'] = general_sources[:6]  # Add a "general" category

        # Add equipment-specific sources if found
        if 'equipment_sources' in equipment_methods and equipment_methods['equipment_sources']:
            all_eq_sources = []
            for eq, src_list in equipment_methods['equipment_sources'].items():
                all_eq_sources.extend(src_list[:1])  # Top source per equipment
            if all_eq_sources:
                sources['equipment'] = all_eq_sources[:5]
            else:
                sources['equipment'] = general_sources[:3]  # Fallback
        else:
            sources['equipment'] = general_sources[:3]  # Fallback

        # Add methodology-specific sources if found
        if 'methods_sources' in equipment_methods and equipment_methods['methods_sources']:
            all_method_sources = []
            for method, src_list in equipment_methods['methods_sources'].items():
                all_method_sources.extend(src_list[:1])
            if all_method_sources:
                sources['methodologies'] = all_method_sources[:5]
            else:
                sources['methodologies'] = general_sources[:3]  # Fallback
        else:
            sources['methodologies'] = general_sources[:3]  # Fallback

        print(f"[LabProfile] Built sources map with fields: {list(sources.keys())}, total sources: {sum(len(v) for v in sources.values())}", flush=True)

        return sources

    def _extract_issues(self, documents: List[Dict]) -> List[Dict]:
        """Extract known issues and failures from documents."""
        issues = []

        # Keywords indicating problems/failures
        issue_keywords = [
            'failed', 'didn\'t work', 'not working', 'troubleshoot',
            'problem', 'issue', 'error', 'rejected', 'negative result',
            'unsuccessful', 'limitation', 'challenge', 'difficulty'
        ]

        for doc in documents:
            content = doc.get('content', '').lower()
            title = doc.get('metadata', {}).get('title', doc.get('title', ''))

            for keyword in issue_keywords:
                if keyword in content:
                    # Extract context around the issue
                    idx = content.find(keyword)
                    context = content[max(0, idx-100):min(len(content), idx+200)]

                    issues.append({
                        'type': keyword,
                        'description': context[:200],
                        'source': title[:50]
                    })
                    break  # One issue per document

        return issues[:5]  # Top 5 issues

    def _estimate_journal_tier(self, journal_name: str) -> int:
        """Estimate impact tier from journal name."""
        journal_lower = journal_name.lower()

        # Tier 1: Top journals
        tier1 = ['nature', 'science', 'cell', 'nejm', 'lancet', 'jama']
        if any(j in journal_lower for j in tier1):
            return 1

        # Tier 2: High-impact specialty
        tier2 = ['nature communications', 'cell reports', 'pnas', 'plos biology',
                 'elife', 'current biology', 'molecular cell', 'neuron']
        if any(j in journal_lower for j in tier2):
            return 2

        # Tier 3: Good specialty journals
        tier3 = ['plos one', 'scientific reports', 'frontiers', 'bmc',
                 'journal of biological chemistry', 'biochemistry']
        if any(j in journal_lower for j in tier3):
            return 3

        # Default to Tier 3
        return 3

    def _calculate_typical_tier(self, publications: List[Dict]) -> int:
        """Calculate the lab's typical publication tier."""
        if not publications:
            return 3  # Default assumption

        tiers = [pub.get('impact_tier', 3) for pub in publications]
        # Use median tier
        sorted_tiers = sorted(tiers)
        mid = len(sorted_tiers) // 2
        return sorted_tiers[mid]

    def _extract_preferred_journals(self, publications: List[Dict]) -> List[str]:
        """Extract journals the lab frequently publishes in."""
        journal_counts = {}
        for pub in publications:
            journal = pub.get('journal', '')
            if journal:
                journal_counts[journal] = journal_counts.get(journal, 0) + 1

        # Sort by frequency
        sorted_journals = sorted(journal_counts.items(), key=lambda x: -x[1])
        return [j[0] for j in sorted_journals[:5]]

    def _merge_profiles(self, old: Dict, new: Dict) -> Dict:
        """Merge new profile data with existing profile."""
        merged = {}

        for key in set(list(old.keys()) + list(new.keys())):
            old_val = old.get(key, [])
            new_val = new.get(key, [])

            if isinstance(old_val, list) and isinstance(new_val, list):
                # Merge lists, keeping unique values
                merged[key] = list(set(old_val + new_val))
            else:
                # Prefer new value
                merged[key] = new_val if new_val else old_val

        return merged

    def _empty_profile(self) -> LabProfile:
        """Return an empty profile."""
        return LabProfile(
            research_focus_areas=[],
            methodologies=[],
            model_systems=[],
            publication_history=[],
            typical_impact_tier=3,
            preferred_journals=[],
            equipment=[],
            expertise_areas=[],
            collaborators=[],
            funding_sources=[],
            known_issues=[],
            successful_strategies=[],
            sources={},
            document_count=0,
            last_updated=datetime.utcnow().isoformat(),
            confidence_score=0.0
        )


    def fetch_diverse_documents(self, tenant_id: str, db, max_per_source: int = 10, total_max: int = 50) -> List[Dict]:
        """
        Fetch documents from the database with diversity across source types.

        This ensures the lab profile is built from ALL document sources (Slack, Drive, Box,
        Email, etc.) rather than just search results which may be biased toward one source.

        Args:
            tenant_id: The tenant ID
            db: Database session
            max_per_source: Maximum documents to fetch per source type
            total_max: Maximum total documents to return

        Returns:
            List of document dicts with 'content', 'title', 'metadata'
        """
        from database.models import Document, DocumentClassification
        from sqlalchemy import func, desc

        try:
            # Get distinct source types for this tenant
            source_types_query = db.query(Document.source_type).filter(
                Document.tenant_id == tenant_id,
                Document.classification == DocumentClassification.WORK,
                Document.source_type.isnot(None)
            ).distinct().all()

            source_types = [st[0] for st in source_types_query if st[0]]

            if not source_types:
                print(f"[LabProfile] No documents with source_type found for tenant")
                return []

            print(f"[LabProfile] Found {len(source_types)} source types: {source_types}")

            all_documents = []

            # Prioritize certain source types for richer context
            # PubMed and Zotero papers should be HIGH priority for publication history!
            priority_order = ['pubmed', 'zotero', 'paper', 'file', 'document', 'protocol', 'email', 'message', 'slack', 'drive', 'box']

            # Sort source types by priority (prioritized first, then alphabetically)
            def sort_key(st):
                st_lower = st.lower() if st else ''
                for i, p in enumerate(priority_order):
                    if p in st_lower:
                        return (i, st)
                return (len(priority_order), st)

            sorted_sources = sorted(source_types, key=sort_key)

            for source_type in sorted_sources:
                if len(all_documents) >= total_max:
                    break

                # Fetch recent documents from this source type
                docs = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.source_type == source_type,
                    Document.classification == DocumentClassification.WORK,
                    Document.content.isnot(None),
                    func.length(Document.content) > 100  # Skip very short documents
                ).order_by(
                    desc(Document.created_at)
                ).limit(max_per_source).all()

                for doc in docs:
                    if len(all_documents) >= total_max:
                        break
                    all_documents.append({
                        'content': doc.content or '',
                        'title': doc.title or 'Untitled',
                        'metadata': {
                            'title': doc.title or 'Untitled',
                            'source_type': doc.source_type or 'document',
                            'doc_id': doc.id,
                            'created_at': doc.created_at.isoformat() if doc.created_at else None,
                            'sender': doc.sender,
                            'sender_email': doc.sender_email,
                        }
                    })

            # Log source distribution
            source_counts = {}
            for doc in all_documents:
                st = doc.get('metadata', {}).get('source_type', 'unknown')
                source_counts[st] = source_counts.get(st, 0) + 1

            print(f"[LabProfile] Fetched {len(all_documents)} documents with distribution: {source_counts}")

            return all_documents

        except Exception as e:
            print(f"[LabProfile] Error fetching diverse documents: {e}")
            import traceback
            traceback.print_exc()
            return []

    def build_profile_from_db(self, tenant_id: str, db) -> LabProfile:
        """
        Build a comprehensive lab profile by fetching diverse documents from the database.

        This is the preferred method for building profiles as it ensures all document
        sources are represented, not just what semantic search returns.

        Args:
            tenant_id: The tenant ID
            db: Database session

        Returns:
            LabProfile with structured information from all sources
        """
        documents = self.fetch_diverse_documents(tenant_id, db, max_per_source=10, total_max=50)

        if not documents:
            print(f"[LabProfile] No documents found, returning empty profile")
            return self._empty_profile()

        return self.build_profile(tenant_id, documents)


# Singleton instance
_lab_profile_service = None

def get_lab_profile_service() -> LabProfileService:
    global _lab_profile_service
    if _lab_profile_service is None:
        _lab_profile_service = LabProfileService()
    return _lab_profile_service
