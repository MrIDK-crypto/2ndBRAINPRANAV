"""Setup Pinecone index for KnowledgeVault"""
import os
from dotenv import load_dotenv

# Load environment
load_dotenv("/Users/rishitjain/Downloads/knowledgevault_backend/.env")

from pinecone import Pinecone, ServerlessSpec

# Initialize Pinecone
api_key = os.getenv("PINECONE_API_KEY")
print(f"API Key loaded: {api_key[:20]}...")

pc = Pinecone(api_key=api_key)

# List existing indexes
existing = [idx.name for idx in pc.list_indexes()]
print(f"Existing indexes: {existing}")

# Create index if it doesn't exist
index_name = "knowledgevault"
if index_name not in existing:
    print(f"Creating index '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=1536,  # text-embedding-3-small dimension
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    print("Index created successfully!")
else:
    print(f"Index '{index_name}' already exists")

# Get index stats
import time
time.sleep(2)  # Wait for index to be ready
index = pc.Index(index_name)
stats = index.describe_index_stats()
print(f"\nIndex stats:")
print(f"  Total vectors: {stats.total_vector_count}")
print(f"  Dimension: {stats.dimension}")
print(f"  Namespaces: {list(stats.namespaces.keys()) if stats.namespaces else 'none'}")
print("\nPinecone setup complete!")
