"""
Rebuild club search index with better quality
Filter out short messages, prioritize substantive content
"""

import json
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer

CLUB_DATA_DIR = Path("/Users/rishitjain/Downloads/knowledgevault_backend/club_data")

# Load all messages
unclustered_file = CLUB_DATA_DIR / "unclustered" / "all_messages.jsonl"

all_documents = []
with open(unclustered_file, 'r') as f:
    for line in f:
        doc = json.loads(line)
        # FILTER: Only include messages with at least 20 characters
        if len(doc['content'].strip()) >= 20:
            all_documents.append(doc)

print(f"Total messages: {len(all_documents)} (filtered from short ones)")

# Build better TF-IDF
texts = [doc['content'] for doc in all_documents]

vectorizer = TfidfVectorizer(
    max_features=10000,  # Increased from 5000
    stop_words='english',
    ngram_range=(1, 3),  # Include trigrams
    max_df=0.7,  # More restrictive
    min_df=1,  # Keep rare terms
    sublinear_tf=True  # Use sublinear tf scaling
)

print("Building TF-IDF vectors...")
doc_vectors = vectorizer.fit_transform(texts)

# Create index
doc_index = {doc['doc_id']: doc for doc in all_documents}

index_data = {
    'vectorizer': vectorizer,
    'doc_vectors': doc_vectors,
    'doc_ids': [doc['doc_id'] for doc in all_documents],
    'doc_index': doc_index
}

# Save
output_file = CLUB_DATA_DIR / "search_index.pkl"
with open(output_file, 'wb') as f:
    pickle.dump(index_data, f)

print(f"✓ Rebuilt index with {len(all_documents)} quality documents")
print(f"✓ Saved to {output_file}")
