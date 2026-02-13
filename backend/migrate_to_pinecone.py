"""
Migrate existing pickle-based embeddings to Pinecone for scalability.
This script will:
1. Load existing embedding index from pickle
2. Batch upsert all vectors to Pinecone
3. Organize by namespace (project/user)
"""

import os
import pickle
import time
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment
load_dotenv("/Users/rishitjain/Downloads/knowledgevault_backend/.env")

from pinecone import Pinecone

# Configuration
PICKLE_PATH = "/Users/rishitjain/Downloads/knowledgevault_backend/club_data/embedding_index.pkl"
BATCH_SIZE = 100  # Pinecone recommends batches of 100

def load_pickle_embeddings() -> Dict:
    """Load existing embeddings from pickle file"""
    print(f"Loading embeddings from {PICKLE_PATH}...")

    if not os.path.exists(PICKLE_PATH):
        print(f"❌ Pickle file not found: {PICKLE_PATH}")
        return {}

    with open(PICKLE_PATH, "rb") as f:
        data = pickle.load(f)

    print(f"✅ Loaded pickle data with {len(data)} top-level keys")
    return data

def extract_vectors(data: Dict) -> List[Dict]:
    """Extract vectors and metadata from pickle structure"""
    import numpy as np
    vectors = []

    # Handle different pickle structures
    if "chunks" in data and "embeddings" in data:
        # Structure: {chunks: [...], embeddings: [...]}
        chunks = data["chunks"]
        embeddings = data["embeddings"]

        print(f"Found {len(chunks)} chunks with embeddings")
        print(f"Embeddings type: {type(embeddings)}, shape: {embeddings.shape if hasattr(embeddings, 'shape') else 'N/A'}")

        for i, chunk in enumerate(chunks):
            # Get embedding for this chunk
            embedding = embeddings[i]

            # Extract metadata
            if isinstance(chunk, dict):
                chunk_id = chunk.get("chunk_id", f"chunk_{i}")
                content = chunk.get("content", "")
                meta = chunk.get("metadata", {})
                metadata = {
                    "doc_id": chunk.get("doc_id", "unknown"),
                    "chunk_id": chunk_id,
                    "project": meta.get("project", "enron") if isinstance(meta, dict) else "enron",
                    "file_name": meta.get("file_name", "") if isinstance(meta, dict) else "",
                    "chunk_index": chunk.get("chunk_index", i),
                    "content_preview": content[:450] if content else ""  # Pinecone metadata limit
                }
            else:
                chunk_id = f"chunk_{i}"
                metadata = {
                    "doc_id": f"doc_{i}",
                    "chunk_id": chunk_id,
                    "project": "enron",
                    "content_preview": str(chunk)[:450] if chunk else ""
                }

            # Convert numpy array to list
            if isinstance(embedding, np.ndarray):
                embedding_list = embedding.tolist()
            elif isinstance(embedding, list):
                embedding_list = embedding
            else:
                embedding_list = list(embedding)

            vectors.append({
                "id": chunk_id,
                "values": embedding_list,
                "metadata": metadata
            })

    elif isinstance(data, list):
        # Structure: [{chunk_id, embedding, ...}, ...]
        print(f"Found list structure with {len(data)} items")

        for i, item in enumerate(data):
            if isinstance(item, dict) and "embedding" in item:
                chunk_id = item.get("chunk_id", f"chunk_{i}")
                vectors.append({
                    "id": chunk_id,
                    "values": item["embedding"] if isinstance(item["embedding"], list) else item["embedding"].tolist(),
                    "metadata": {
                        "doc_id": item.get("doc_id", "unknown"),
                        "chunk_id": chunk_id,
                        "project": item.get("project", "default"),
                        "content_preview": item.get("content", "")[:500]
                    }
                })

    else:
        # Try to iterate through keys
        print(f"Exploring data structure: {type(data)}")
        for key in list(data.keys())[:5]:
            print(f"  Key '{key}': {type(data[key])}")

    return vectors

def migrate_to_pinecone(vectors: List[Dict], namespace: str = "default"):
    """Migrate vectors to Pinecone in batches"""

    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX", "knowledgevault")

    if not api_key:
        print("❌ PINECONE_API_KEY not set")
        return False

    print(f"\nConnecting to Pinecone index: {index_name}")
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)

    # Get current stats
    stats = index.describe_index_stats()
    print(f"Current index stats: {stats.total_vector_count} vectors")

    # Batch upsert
    total_vectors = len(vectors)
    print(f"\nMigrating {total_vectors} vectors in batches of {BATCH_SIZE}...")

    success_count = 0
    error_count = 0

    for i in range(0, total_vectors, BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]

        try:
            # Upsert batch
            index.upsert(
                vectors=[(v["id"], v["values"], v["metadata"]) for v in batch],
                namespace=namespace
            )
            success_count += len(batch)

            # Progress
            progress = (i + len(batch)) / total_vectors * 100
            print(f"  Progress: {progress:.1f}% ({success_count}/{total_vectors})")

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            error_count += len(batch)
            print(f"  ❌ Batch error at {i}: {str(e)[:50]}")

    # Final stats
    time.sleep(1)
    final_stats = index.describe_index_stats()

    print(f"\n{'='*50}")
    print(f"MIGRATION COMPLETE")
    print(f"{'='*50}")
    print(f"  Vectors migrated: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total in Pinecone: {final_stats.total_vector_count}")
    print(f"  Namespaces: {list(final_stats.namespaces.keys()) if final_stats.namespaces else ['default']}")

    return error_count == 0

def main():
    print("="*50)
    print("KNOWLEDGEVAULT - PINECONE MIGRATION")
    print("="*50)

    # Load existing data
    data = load_pickle_embeddings()

    if not data:
        print("\n❌ No data to migrate")
        return 1

    # Extract vectors
    vectors = extract_vectors(data)

    if not vectors:
        print("\n❌ Could not extract vectors from pickle data")
        print("Please check the pickle structure manually")
        return 1

    print(f"\n✅ Extracted {len(vectors)} vectors for migration")

    # Show sample
    if vectors:
        sample = vectors[0]
        print(f"\nSample vector:")
        print(f"  ID: {sample['id']}")
        print(f"  Dimension: {len(sample['values'])}")
        print(f"  Metadata: {list(sample['metadata'].keys())}")

    # Confirm migration
    print(f"\nReady to migrate {len(vectors)} vectors to Pinecone.")
    print("This will add vectors to the 'knowledgevault' index.")

    # Migrate
    success = migrate_to_pinecone(vectors, namespace="enron")  # Use project as namespace

    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
