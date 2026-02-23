#!/usr/bin/env python3
"""
One-time ingest of CTSI research cores data into a shared Pinecone namespace.

Reads scraped CTSI facility data and external crawl pages, chunks them,
generates embeddings, and upserts into the shared "ctsi-shared" Pinecone
namespace. This data is accessible by ALL tenants via search_shared_namespace().

NO Document DB rows are created -- this is a pure vector-store operation.

Usage (from backend/ directory):
    python -m scripts.ingest_ctsi_shared
    python -m scripts.ingest_ctsi_shared --dry-run
    python -m scripts.ingest_ctsi_shared --clear-first
    python -m scripts.ingest_ctsi_shared --clear-first --dry-run
"""

import os
import sys
import json
import hashlib
import argparse
import time
import traceback
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Add backend/ to sys.path so we can import project modules
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from vector_stores.pinecone_store import (
    PineconeVectorStore,
    SHARED_CTSI_NAMESPACE,
    SHARED_CTSI_TENANT_ID,
    EMBEDDING_DIMENSIONS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 400
BATCH_SIZE = 200  # Matches PineconeVectorStore.BATCH_SIZE
EMBEDDING_BATCH_SIZE = 50  # Matches PineconeVectorStore.EMBEDDING_BATCH_SIZE
MAX_EMBEDDING_CHARS = 30000  # Safety limit per chunk

DATA_DIR = os.path.join(BACKEND_DIR, "scraped_data", "ctsi")
FACILITIES_FILE = os.path.join(DATA_DIR, "_all_facilities.json")
EXTERNAL_DIR = os.path.join(DATA_DIR, "external")

# Sentence boundary patterns (ordered by preference), mirroring pinecone_store._chunk_text
SENTENCE_ENDINGS = [
    "\n\n",  # Paragraph break (highest priority)
    ".\n",   # Sentence + newline
    "!\n",   # Exclamation + newline
    "?\n",   # Question + newline
    ". ",    # Period + space
    "! ",    # Exclamation + space
    "? ",    # Question + space
    ".\t",   # Period + tab
    "\n",    # Single newline
    "; ",    # Semicolon (fallback)
]


# ---------------------------------------------------------------------------
# Chunking (mirrors PineconeVectorStore._chunk_text)
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Tuple[str, int]]:
    """
    Split text into overlapping chunks with sentence-aware boundaries.

    Returns a list of (chunk_text, chunk_index) tuples.  Logic is intentionally
    equivalent to PineconeVectorStore._chunk_text so that the stored vectors
    are consistent with how the rest of the application chunks documents.
    """
    if not text or not text.strip():
        return []

    chunks: List[Tuple[str, int]] = []
    start = 0
    chunk_idx = 0
    prev_start = -1  # Track previous start to prevent infinite loops

    while start < len(text):
        # Prevent infinite loop
        if start == prev_start:
            start += chunk_size // 2  # Force progress
            if start >= len(text):
                break
        prev_start = start

        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        # If not at end of text, find best sentence boundary
        actual_end = end
        if end < len(text):
            best_break = -1

            for boundary in SENTENCE_ENDINGS:
                pos = chunk.rfind(boundary)
                # Only use if it's in the latter half of the chunk
                if pos > chunk_size * 0.5:
                    best_break = pos + len(boundary)
                    break

            if best_break > 0:
                chunk = chunk[:best_break]
                actual_end = start + best_break

        # Add chunk if it has content
        stripped = chunk.strip()
        if stripped:
            chunks.append((stripped, chunk_idx))
            chunk_idx += 1

        # Move start position (with overlap, but ensure forward progress)
        next_start = actual_end - overlap
        if next_start <= start:
            next_start = actual_end  # Force forward progress
        start = next_start

    return chunks


# ---------------------------------------------------------------------------
# Vector ID generation
# ---------------------------------------------------------------------------

def generate_vector_id(namespace: str, doc_id: str, chunk_idx: int) -> str:
    """
    Generate a deterministic vector ID for deduplication.

    Using MD5 of (namespace + doc_id + chunk_idx) means re-running the script
    with the same data simply upserts (overwrites) rather than creating
    duplicates.
    """
    raw = f"{namespace}:{doc_id}:{chunk_idx}"
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Batch embedding helper
# ---------------------------------------------------------------------------

def get_embeddings_batch(
    store: PineconeVectorStore,
    texts: List[str],
) -> List[Optional[List[float]]]:
    """
    Get embeddings for a list of texts using the vector store's batch method.

    Wraps store._get_embeddings_batch and handles the private-method access
    centrally so the rest of the script can stay clean.
    """
    # Safety truncation
    processed = []
    for t in texts:
        if t and len(t) > MAX_EMBEDDING_CHARS:
            print(f"  [embed] WARNING: Truncating text from {len(t)} to {MAX_EMBEDDING_CHARS} chars")
            processed.append(t[:MAX_EMBEDDING_CHARS])
        else:
            processed.append(t if t else "")

    return store._get_embeddings_batch(processed)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_facilities() -> List[Dict]:
    """Load facility records from _all_facilities.json."""
    if not os.path.exists(FACILITIES_FILE):
        print(f"[ERROR] Facilities file not found: {FACILITIES_FILE}")
        print("        Run the scraper first:  python -m scripts.scrape_ctsi scrape")
        return []

    with open(FACILITIES_FILE, "r") as f:
        data = json.load(f)

    facilities = data.get("facilities", [])
    metadata = data.get("scrape_metadata", {})

    print(f"[data] Loaded {len(facilities)} facilities from {FACILITIES_FILE}")
    if metadata:
        print(f"       Scraped at: {metadata.get('scraped_at', 'unknown')}")
        print(f"       With external URLs: {metadata.get('facilities_with_external_url', '?')}")
        print(f"       External pages total: {metadata.get('total_external_pages', '?')}")

    return facilities


def load_external_crawls() -> List[Dict]:
    """
    Load all external crawl files from scraped_data/ctsi/external/.

    Each file contains: source_url, facility_name, facility_slug,
    pages_crawled, crawled_at, pages (list of page dicts).
    """
    if not os.path.isdir(EXTERNAL_DIR):
        print(f"[data] No external crawl directory found: {EXTERNAL_DIR}")
        return []

    crawl_files = sorted(
        f for f in os.listdir(EXTERNAL_DIR) if f.endswith("_crawl.json")
    )

    if not crawl_files:
        print(f"[data] No *_crawl.json files in {EXTERNAL_DIR}")
        return []

    crawls: List[Dict] = []
    for fname in crawl_files:
        filepath = os.path.join(EXTERNAL_DIR, fname)
        try:
            with open(filepath, "r") as f:
                crawl_data = json.load(f)
            crawls.append(crawl_data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [WARN] Could not read {filepath}: {e}")

    total_pages = sum(len(c.get("pages", [])) for c in crawls)
    print(f"[data] Loaded {len(crawls)} external crawl files ({total_pages} total pages)")

    return crawls


# ---------------------------------------------------------------------------
# Prepare vectors
# ---------------------------------------------------------------------------

def prepare_facility_vectors(facilities: List[Dict]) -> List[Dict]:
    """
    Chunk facility full_text and build vector metadata dicts (without embeddings).

    Returns a list of dicts ready for embedding:
        {text, vector_id, metadata}
    """
    vectors: List[Dict] = []
    skipped = 0

    for facility in facilities:
        slug = facility.get("slug", "")
        name = facility.get("name", "Unknown Facility")
        full_text = facility.get("full_text", "")
        ctsi_url = facility.get("ctsi_url", "")
        description = facility.get("description", "")
        services = facility.get("services", [])

        if not full_text or not full_text.strip():
            skipped += 1
            continue

        # Build enriched content: name + description + services + full_text
        content_parts = [f"# {name}\n"]
        if description:
            content_parts.append(f"{description}\n")
        if services:
            content_parts.append("\n## Services\n")
            for svc in services:
                content_parts.append(f"- {svc}")
        content_parts.append(f"\n## Full Page Content\n{full_text}")
        enriched_content = "\n".join(content_parts)

        # Chunk the enriched content
        chunks = chunk_text(enriched_content)

        for chunk_str, chunk_idx in chunks:
            doc_id = slug or hashlib.md5(ctsi_url.encode()).hexdigest()
            vector_id = generate_vector_id(SHARED_CTSI_NAMESPACE, doc_id, chunk_idx)

            vectors.append({
                "text": chunk_str,
                "vector_id": vector_id,
                "metadata": {
                    "source_url": ctsi_url,
                    "facility_name": name[:200],
                    "source_type": "ctsi_shared",
                    "title": f"CTSI: {name}"[:200],
                    "content_preview": chunk_str[:500],
                    "doc_id": doc_id,
                    "chunk_idx": chunk_idx,
                    "tenant_id": SHARED_CTSI_TENANT_ID,
                },
            })

    if skipped:
        print(f"  [facility] Skipped {skipped} facilities with no text content")

    return vectors


def prepare_external_vectors(crawls: List[Dict]) -> List[Dict]:
    """
    Chunk external crawl pages and build vector metadata dicts (without embeddings).

    Returns a list of dicts ready for embedding:
        {text, vector_id, metadata}
    """
    vectors: List[Dict] = []
    pages_processed = 0
    pages_skipped = 0

    for crawl in crawls:
        facility_name = crawl.get("facility_name", "Unknown")
        facility_slug = crawl.get("facility_slug", "")
        source_url = crawl.get("source_url", "")
        pages = crawl.get("pages", [])

        for page in pages:
            page_url = page.get("url", "")
            page_content = page.get("content", "")
            page_title = page.get("title", "")

            if not page_content or not page_content.strip():
                pages_skipped += 1
                continue

            pages_processed += 1

            # Use page URL hash as the doc_id for external pages
            page_doc_id = hashlib.md5(page_url.encode()).hexdigest() if page_url else hashlib.md5(page_content[:200].encode()).hexdigest()

            # Chunk the page content
            chunks = chunk_text(page_content)

            for chunk_str, chunk_idx in chunks:
                vector_id = generate_vector_id(
                    SHARED_CTSI_NAMESPACE, page_doc_id, chunk_idx
                )

                vectors.append({
                    "text": chunk_str,
                    "vector_id": vector_id,
                    "metadata": {
                        "source_url": page_url or source_url,
                        "facility_name": facility_name[:200],
                        "source_type": "ctsi_shared",
                        "title": (page_title or f"External: {facility_name}")[:200],
                        "content_preview": chunk_str[:500],
                        "doc_id": page_doc_id,
                        "chunk_idx": chunk_idx,
                        "tenant_id": SHARED_CTSI_TENANT_ID,
                    },
                })

    if pages_skipped:
        print(f"  [external] Skipped {pages_skipped} pages with no content")

    return vectors


# ---------------------------------------------------------------------------
# Embed & upsert
# ---------------------------------------------------------------------------

def embed_and_upsert(
    store: PineconeVectorStore,
    vectors: List[Dict],
    dry_run: bool = False,
) -> Dict:
    """
    Embed all vector texts and upsert them to Pinecone in batches.

    Args:
        store: Initialized PineconeVectorStore
        vectors: List of {text, vector_id, metadata} dicts
        dry_run: If True, skip actual embedding and upsert

    Returns:
        Stats dict: {total, upserted, errors, elapsed_seconds}
    """
    total = len(vectors)
    upserted = 0
    errors: List[Dict] = []
    start_time = time.time()

    if total == 0:
        print("[upsert] No vectors to process.")
        return {"total": 0, "upserted": 0, "errors": [], "elapsed_seconds": 0}

    if dry_run:
        print(f"[upsert] DRY RUN: Would embed and upsert {total} vectors "
              f"into namespace '{SHARED_CTSI_NAMESPACE}'")
        return {
            "total": total,
            "upserted": 0,
            "errors": [],
            "elapsed_seconds": 0,
            "dry_run": True,
        }

    print(f"[upsert] Embedding and upserting {total} vectors into "
          f"namespace '{SHARED_CTSI_NAMESPACE}'...")

    for batch_start in range(0, total, BATCH_SIZE):
        batch = vectors[batch_start : batch_start + BATCH_SIZE]
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        try:
            # Extract texts for embedding
            texts = [v["text"] for v in batch]

            # Get embeddings (uses the store's batch method internally)
            embeddings = get_embeddings_batch(store, texts)

            # Build Pinecone vector tuples, skipping failed embeddings
            pinecone_vectors = []
            batch_skipped = 0
            for vec, embedding in zip(batch, embeddings):
                if embedding is None:
                    batch_skipped += 1
                    print(f"  [WARN] Skipping vector {vec['vector_id']} - embedding failed")
                    continue

                pinecone_vectors.append({
                    "id": vec["vector_id"],
                    "values": embedding,
                    "metadata": vec["metadata"],
                })

            if not pinecone_vectors:
                print(f"  [WARN] Batch {batch_num} produced no valid vectors, skipping upsert")
                errors.append({
                    "batch": batch_start,
                    "error": "All embeddings in batch failed",
                })
                continue

            # Upsert to Pinecone with retry
            max_retries = 3
            for retry in range(max_retries):
                try:
                    store.index.upsert(
                        vectors=pinecone_vectors,
                        namespace=SHARED_CTSI_NAMESPACE,
                    )
                    upserted += len(pinecone_vectors)
                    break  # Success
                except Exception as e:
                    if retry < max_retries - 1:
                        wait = (retry + 1) * 2
                        print(f"  [RETRY] Batch {batch_num} attempt {retry + 1} failed: {e}. "
                              f"Retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        raise  # Re-raise on final retry

            if batch_skipped:
                print(f"  [batch {batch_num}/{total_batches}] Upserted {len(pinecone_vectors)} vectors "
                      f"({batch_skipped} skipped) | Total: {upserted}/{total}")
            else:
                print(f"  [batch {batch_num}/{total_batches}] Upserted {len(pinecone_vectors)} vectors "
                      f"| Total: {upserted}/{total}")

        except Exception as e:
            errors.append({
                "batch": batch_start,
                "error": f"{type(e).__name__}: {e}",
            })
            print(f"  [ERROR] Batch {batch_num}/{total_batches} failed: {type(e).__name__}: {e}")
            traceback.print_exc()

    elapsed = time.time() - start_time

    return {
        "total": total,
        "upserted": upserted,
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest CTSI scraped data into shared Pinecone namespace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.ingest_ctsi_shared                # Full ingest
  python -m scripts.ingest_ctsi_shared --dry-run      # Report only, no changes
  python -m scripts.ingest_ctsi_shared --clear-first   # Wipe namespace, then ingest
        """,
    )

    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Delete all vectors in the shared CTSI namespace before ingesting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be embedded without actually doing it",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Banner
    # ------------------------------------------------------------------
    print("=" * 70)
    print("  CTSI SHARED NAMESPACE INGEST")
    print(f"  Namespace:  {SHARED_CTSI_NAMESPACE}")
    print(f"  Tenant ID:  {SHARED_CTSI_TENANT_ID}")
    print(f"  Data dir:   {DATA_DIR}")
    print(f"  Chunk size: {CHUNK_SIZE} chars, overlap: {CHUNK_OVERLAP} chars")
    print(f"  Batch size: {BATCH_SIZE} vectors")
    if args.dry_run:
        print("  Mode:       DRY RUN (no changes will be made)")
    if args.clear_first:
        print("  Clear:      Will wipe namespace before ingesting")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Initialize vector store
    # ------------------------------------------------------------------
    print("\n[init] Connecting to Pinecone...")
    try:
        store = PineconeVectorStore()
    except Exception as e:
        print(f"[FATAL] Could not initialize PineconeVectorStore: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Print current stats
    stats = store.get_stats()
    ns_stats = stats.get("namespaces", {})
    current_count = ns_stats.get(SHARED_CTSI_NAMESPACE, 0)
    print(f"[init] Current vectors in '{SHARED_CTSI_NAMESPACE}': {current_count}")
    print(f"[init] Total vectors in index: {stats.get('total_vectors', 0)}")

    # ------------------------------------------------------------------
    # Clear namespace if requested
    # ------------------------------------------------------------------
    if args.clear_first:
        if args.dry_run:
            print(f"\n[clear] DRY RUN: Would delete all vectors in '{SHARED_CTSI_NAMESPACE}'")
        else:
            print(f"\n[clear] Deleting all vectors in '{SHARED_CTSI_NAMESPACE}'...")
            try:
                store.index.delete(delete_all=True, namespace=SHARED_CTSI_NAMESPACE)
                print("[clear] Namespace cleared successfully.")
                # Give Pinecone a moment to process the delete
                time.sleep(2)
            except Exception as e:
                print(f"[clear] WARNING: Could not clear namespace: {type(e).__name__}: {e}")
                traceback.print_exc()

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("PHASE 1: Loading scraped data")
    print("-" * 70)

    facilities = load_facilities()
    crawls = load_external_crawls()

    if not facilities and not crawls:
        print("\n[FATAL] No data to ingest. Run the scraper first:")
        print("        python -m scripts.scrape_ctsi scrape")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Prepare vectors (chunk + build metadata)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("PHASE 2: Chunking content and preparing vectors")
    print("-" * 70)

    facility_vectors = prepare_facility_vectors(facilities)
    print(f"[chunk] Facility vectors: {len(facility_vectors)} "
          f"(from {len(facilities)} facilities)")

    external_vectors = prepare_external_vectors(crawls)
    ext_pages = sum(len(c.get("pages", [])) for c in crawls)
    print(f"[chunk] External vectors: {len(external_vectors)} "
          f"(from {ext_pages} pages across {len(crawls)} crawl files)")

    all_vectors = facility_vectors + external_vectors
    print(f"\n[chunk] Total vectors to embed: {len(all_vectors)}")

    if not all_vectors:
        print("\n[DONE] No vectors to embed. Check that scraped data contains content.")
        return

    # ------------------------------------------------------------------
    # Embed & upsert
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("PHASE 3: Embedding and upserting to Pinecone")
    print("-" * 70)

    result = embed_and_upsert(store, all_vectors, dry_run=args.dry_run)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  INGEST SUMMARY")
    print("=" * 70)
    print(f"  Facilities processed:     {len(facilities)}")
    print(f"  Facility chunks:          {len(facility_vectors)}")
    print(f"  External crawl files:     {len(crawls)}")
    print(f"  External pages processed: {ext_pages}")
    print(f"  External chunks:          {len(external_vectors)}")
    print(f"  Total chunks:             {len(all_vectors)}")
    print(f"  Vectors upserted:         {result['upserted']}")
    if result.get("errors"):
        print(f"  Errors:                   {len(result['errors'])}")
        for err in result["errors"]:
            print(f"    - Batch {err['batch']}: {err['error']}")
    else:
        print(f"  Errors:                   0")
    if not args.dry_run:
        print(f"  Elapsed time:             {result['elapsed_seconds']}s")
    print(f"  Namespace:                {SHARED_CTSI_NAMESPACE}")
    if args.dry_run:
        print(f"  Mode:                     DRY RUN (nothing was written)")
    print("=" * 70)

    # Final namespace stats (skip for dry run)
    if not args.dry_run and not result.get("errors"):
        time.sleep(2)  # Brief pause for Pinecone to update stats
        final_stats = store.get_stats()
        final_ns = final_stats.get("namespaces", {})
        final_count = final_ns.get(SHARED_CTSI_NAMESPACE, 0)
        print(f"\n[verify] Vectors in '{SHARED_CTSI_NAMESPACE}' after ingest: {final_count}")


if __name__ == "__main__":
    main()
