"""
OpenAlex Journal Abstract Indexer (Tier 2)
============================================
Indexes abstracts and metadata from 10K+ journals into Pinecone
for broad technique/method coverage without full-text download.

Namespace: journal-abstracts
"""

import os
import json
import time
import logging
import hashlib
from typing import List, Dict, Any, Optional

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

OPENALEX_API = "https://api.openalex.org"
USER_EMAIL = os.getenv("OPENALEX_EMAIL", "prmogathala@gmail.com")
BATCH_SIZE = 50

# Rate limit: be respectful
RATE_LIMIT_SECONDS = 0.1


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""

    # Build position -> word mapping
    positions = {}
    for word, pos_list in inverted_index.items():
        if not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            positions[pos] = word

    # Reconstruct in order
    if not positions:
        return ""
    max_pos = max(positions.keys())
    words = [positions.get(i, "") for i in range(max_pos + 1)]
    return " ".join(w for w in words if w)


def _fetch_works_batch(concept_id: str = None, topic: str = None,
                       search_term: str = None,
                       per_page: int = 200, max_works: int = 1000,
                       from_year: int = 2018) -> list:
    """Fetch works from OpenAlex with abstracts.

    Tries concept filter first; falls back to keyword search if 0 results.
    """
    try:
        import httpx
    except ImportError:
        raise ImportError('httpx library required for OpenAlex ingestion')

    def _do_fetch(filter_str, max_w):
        fetched = []
        cur = "*"
        while len(fetched) < max_w:
            url = (
                f"{OPENALEX_API}/works"
                f"?filter={filter_str}"
                f"&per_page={min(per_page, 200)}"
                f"&cursor={cur}"
                f"&mailto={USER_EMAIL}"
                f"&select=id,doi,title,publication_year,abstract_inverted_index,"
                f"primary_location,concepts,topics,cited_by_count"
            )
            try:
                resp = httpx.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                page_results = data.get("results", [])
                if not page_results:
                    break
                fetched.extend(page_results)
                cur = data.get("meta", {}).get("next_cursor")
                if not cur:
                    break
                time.sleep(RATE_LIMIT_SECONDS)
            except Exception as e:
                logger.warning(f'[JournalAbs] OpenAlex fetch error: {e}')
                break
        return fetched[:max_w]

    # Build concept-based filter
    filters = [f"publication_year:>{from_year}", "has_abstract:true"]
    if concept_id:
        filters.append(f"concepts.id:{concept_id}")
    if topic:
        filters.append(f"topics.id:{topic}")

    works = _do_fetch(",".join(filters), max_works)

    # Fallback: if concept filter returned 0, try keyword search
    if not works and search_term:
        logger.info(f'[JournalAbs] Concept filter returned 0, falling back to keyword search: {search_term}')
        fallback_filters = [f"publication_year:>{from_year}", "has_abstract:true",
                            f"default.search:{search_term}"]
        works = _do_fetch(",".join(fallback_filters), max_works)

    return works


def _get_biomedical_topics() -> List[tuple]:
    """Get top biomedical concept IDs from OpenAlex for broad coverage.
    Heavily weighted toward oncology to support cancer research experiment suggestions.

    Format: (concept_id, concept_name, max_works, search_fallback)
    search_fallback is used when concept_id returns 0 results.
    """
    return [
        # === ONCOLOGY (primary focus — 10K+ papers) ===
        ("C142724271", "Oncology", 3000, "oncology cancer"),
        ("C126838900", "Breast cancer", 2000, "breast cancer"),
        ("C174481974", "Lung cancer", 1500, "lung cancer NSCLC"),
        ("C121332964", "Colorectal cancer", 1000, "colorectal cancer"),
        ("C17781377", "Prostate cancer", 1000, "prostate cancer"),
        ("C64875637", "Leukemia", 1000, "leukemia lymphoma"),
        ("C185544564", "Melanoma", 800, "melanoma skin cancer"),
        ("C41008148", "Immunotherapy", 1500, "immunotherapy checkpoint inhibitor"),
        ("C59822182", "Chemotherapy", 1000, "chemotherapy cytotoxic"),
        ("C56900677", "Radiation therapy", 800, "radiation therapy radiotherapy"),
        ("C44104778", "Tumor", 2000, "tumor neoplasm"),
        ("C2778587917", "Cancer biomarkers", 1000, "cancer biomarker"),
        ("C2778793408", "Targeted therapy", 800, "targeted therapy kinase inhibitor"),
        # === Core Biology & Methods ===
        ("C86803240", "Biology", 2000, None),
        ("C185592680", "Chemistry", 1000, None),
        ("C71924100", "Medicine", 2000, None),
        ("C126322002", "Biochemistry", 1500, None),
        ("C55493867", "Molecular biology", 1500, None),
        ("C95444343", "Cell biology", 1500, None),
        ("C54355233", "Genetics", 1000, None),
        ("C153911025", "Bioinformatics", 500, None),
        ("C104317684", "Microbiology", 500, None),
        ("C199360897", "Immunology", 1500, None),
        ("C502942594", "Neuroscience", 500, None),
        ("C159110408", "Pathology", 800, None),
        ("C203014093", "Computational biology", 500, None),
        ("C181199279", "Pharmacology", 800, None),
        # === Experimental Techniques ===
        ("C76155785", "Flow cytometry", 500, "flow cytometry FACS"),
        ("C88519984", "Western blot", 500, "western blot immunoblot"),
        ("C46312422", "PCR", 500, "PCR polymerase chain reaction"),
        ("C121955636", "CRISPR", 800, "CRISPR Cas9 gene editing"),
    ]


def ingest(embedding_client=None, vector_store=None,
           max_per_topic: int = 1000, from_year: int = 2018) -> dict:
    """
    Index journal abstracts from OpenAlex into Pinecone.
    Covers 10K+ journals across biomedical domains.

    Args:
        embedding_client: Azure OpenAI client for embeddings
        vector_store: Pinecone vector store instance
        max_per_topic: Max papers per topic
        from_year: Start year for papers

    Returns:
        dict with ingestion stats
    """
    stats = {
        "topics_processed": 0,
        "abstracts_embedded": 0,
        "journals_seen": set(),
        "errors": 0,
    }

    if not embedding_client or not vector_store:
        logger.error('[JournalAbs] embedding_client and vector_store are required')
        return {**stats, "journals_seen": 0}

    deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    topics = _get_biomedical_topics()

    logger.info(f'[JournalAbs] Starting abstract indexing ({len(topics)} topics, max {max_per_topic}/topic)...')

    for concept_id, concept_name, max_works, search_fallback in topics:
        logger.info(f'[JournalAbs] Indexing topic: {concept_name} (max {max_works} works)')

        try:
            works = _fetch_works_batch(
                concept_id=concept_id,
                search_term=search_fallback,
                max_works=min(max_works, max_per_topic),
                from_year=from_year,
            )

            vectors_batch = []

            for work in works:
                abstract = _reconstruct_abstract(work.get("abstract_inverted_index", {}))
                if not abstract or len(abstract) < 100:
                    continue

                title = work.get("title", "")
                work_id = work.get("id", "").split("/")[-1]
                year = work.get("publication_year", 0)
                citations = work.get("cited_by_count", 0)

                # Get journal info
                location = work.get("primary_location", {}) or {}
                source = location.get("source", {}) or {}
                journal_name = source.get("display_name", "Unknown")
                journal_id = source.get("id", "")

                stats["journals_seen"].add(journal_name)

                # Get concepts/topics
                concepts = [c.get("display_name", "") for c in work.get("concepts", [])[:5]]
                topics_list = [t.get("display_name", "") for t in work.get("topics", [])[:3]]

                # Embed title + abstract
                text = f"{title}. {abstract}"[:1500]
                vec_id = hashlib.md5(f"oa-abs-{work_id}".encode()).hexdigest()

                try:
                    resp = embedding_client.embeddings.create(
                        model=deployment,
                        input=text,
                        dimensions=1536,
                    )
                    embedding = resp.data[0].embedding
                except Exception as e:
                    stats["errors"] += 1
                    continue

                vectors_batch.append({
                    "id": vec_id,
                    "values": embedding,
                    "metadata": {
                        "text": text[:800],
                        "title": title[:150],
                        "journal": journal_name[:80],
                        "year": year,
                        "citations": citations,
                        "concepts": [c[:50] for c in concepts[:3]],
                        "domain": concept_name.lower(),
                        "source": "openalex_abstract",
                        "type": "journal_abstract",
                        "doi": (work.get("doi") or "")[:100],
                    }
                })
                stats["abstracts_embedded"] += 1

                if len(vectors_batch) >= BATCH_SIZE:
                    try:
                        vector_store.index.upsert(
                            vectors=vectors_batch,
                            namespace="journal-abstracts"
                        )
                    except Exception as e:
                        logger.error(f'[JournalAbs] Pinecone upsert failed: {e}')
                        stats["errors"] += 1
                    vectors_batch = []

            # Flush remaining
            if vectors_batch:
                try:
                    vector_store.index.upsert(vectors=vectors_batch, namespace="journal-abstracts")
                except Exception as e:
                    logger.error(f'[JournalAbs] Final upsert failed: {e}')

            stats["topics_processed"] += 1
            logger.info(f'[JournalAbs]   {concept_name}: {len(works)} works, '
                        f'{stats["abstracts_embedded"]} total abstracts embedded')

        except Exception as e:
            logger.error(f'[JournalAbs] Topic {concept_name} failed: {e}')
            stats["errors"] += 1

    final_stats = {
        "topics_processed": stats["topics_processed"],
        "abstracts_embedded": stats["abstracts_embedded"],
        "unique_journals": len(stats["journals_seen"]),
        "errors": stats["errors"],
    }
    logger.info(f'[JournalAbs] Abstract indexing complete: {final_stats}')
    return final_stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print('OpenAlex Journal Abstract Indexer')
    print('Requires embedding_client and vector_store arguments.')
    print('Run via the orchestrator or pass Azure OpenAI + Pinecone clients.')
