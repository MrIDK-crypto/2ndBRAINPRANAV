"""
Rebuild Search Index for Club Data
Replace the 517K email index with the 117 LlamaParse-parsed documents
"""

import json
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from config.config import Config

def load_llamaparse_documents():
    """Load all LlamaParse-parsed documents from Google Chat projects"""

    print("=" * 80)
    print("LOADING LLAMAPARSE DOCUMENTS")
    print("=" * 80)

    club_dir = Config.OUTPUT_DIR / "club_project_classification"

    # The 10 Google Chat projects with LlamaParse-parsed docs
    google_chat_projects = [
        "Vibio Health.jsonl",
        "Startup Team (Eric, Badri, Rishit).jsonl",
        "Amgen Project Fall 2024.jsonl",
        "BEAT at UCLA.jsonl",
        "UCLA Health Project 2025.jsonl",
        "Addiction Medicine - Data.jsonl",
        "BEAT Healthcare Consulting.jsonl",
        "Concierge Medicine + Addiction Medicine  (UCLA Health).jsonl",
        "UCLA Health.jsonl",
        "Projects Summer.jsonl"
    ]

    projects_dir = club_dir / "projects"
    all_documents = []
    doc_count = 0

    print(f"\n📂 Loading from: {projects_dir}\n")

    for project_file in google_chat_projects:
        project_path = projects_dir / project_file

        if not project_path.exists():
            print(f"  ⚠️  Not found: {project_file}")
            continue

        project_name = project_file.replace('.jsonl', '')
        count = 0

        with open(project_path, 'r') as f:
            for line in f:
                doc = json.loads(line)

                # Only LlamaParse-parsed documents
                if doc.get('metadata', {}).get('parser') == 'llamaparse':
                    doc_count += 1
                    all_documents.append({
                        'doc_id': f"doc_{doc_count}",
                        'content': doc.get('content', ''),
                        'metadata': {
                            'file_name': doc.get('metadata', {}).get('file_name', 'Unknown'),
                            'file_type': doc.get('metadata', {}).get('file_type', 'unknown'),
                            'project': project_name,
                            'subject': doc.get('metadata', {}).get('file_name', '').replace('File-', ''),
                            'employee': 'Google Chat',
                            'group': project_name,
                            'source': 'llamaparse'
                        },
                        'cluster_label': project_name
                    })
                    count += 1

        if count > 0:
            print(f"  ✓ {project_name}: {count} docs")

    print(f"\n✅ Loaded {len(all_documents)} LlamaParse-parsed documents")
    return all_documents


def build_search_index(documents):
    """Build TF-IDF search index"""

    print("\n" + "=" * 80)
    print("BUILDING SEARCH INDEX")
    print("=" * 80)

    print(f"\n📊 Creating TF-IDF vectors for {len(documents)} documents...")

    # Extract content
    doc_contents = [doc['content'] for doc in documents]
    doc_ids = [doc['doc_id'] for doc in documents]

    # Build TF-IDF vectorizer
    print("  Creating TF-IDF vectorizer...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words='english',
        min_df=1,
        max_df=0.95
    )

    # Fit and transform
    print("  Fitting vectorizer...")
    doc_vectors = vectorizer.fit_transform(doc_contents)

    print(f"  ✓ Created {doc_vectors.shape[0]} document vectors")
    print(f"  ✓ Feature dimensions: {doc_vectors.shape[1]}")

    # Create document index
    doc_index = {doc['doc_id']: doc for doc in documents}

    # Package search index
    search_index = {
        'vectorizer': vectorizer,
        'doc_vectors': doc_vectors,
        'doc_ids': doc_ids,
        'doc_index': doc_index,
        'metadata': {
            'total_documents': len(documents),
            'source': 'llamaparse_google_chat',
            'feature_count': doc_vectors.shape[1]
        }
    }

    print(f"\n✅ Search index built!")
    return search_index


def save_search_index(search_index):
    """Save search index to club_data directory"""

    print("\n" + "=" * 80)
    print("SAVING SEARCH INDEX")
    print("=" * 80)

    # Save to club_data directory (where app_universal.py looks for it)
    output_dir = Path('/Users/rishitjain/Downloads/knowledgevault_backend/club_data')
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / 'search_index.pkl'

    print(f"\n💾 Saving to: {output_file}")

    # Backup old index
    if output_file.exists():
        backup_file = output_dir / 'search_index_OLD_BACKUP.pkl'
        output_file.rename(backup_file)
        print(f"  ✓ Backed up old index to: {backup_file.name}")

    # Save new index
    with open(output_file, 'wb') as f:
        pickle.dump(search_index, f)

    # Get file size
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"  ✓ Saved search index ({size_mb:.1f} MB)")

    print(f"\n✅ Search index saved!")


def test_search(search_index):
    """Test the search with sample queries"""

    print("\n" + "=" * 80)
    print("TESTING SEARCH")
    print("=" * 80)

    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    test_queries = [
        "NICU step down market size",
        "UCLA Health project",
        "BEAT Healthcare Consulting",
        "cardiology shadowing"
    ]

    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        print("-" * 80)

        # Search
        query_vector = search_index['vectorizer'].transform([query])
        similarities = cosine_similarity(query_vector, search_index['doc_vectors'])[0]
        top_indices = similarities.argsort()[-5:][::-1]

        print(f"Found {len([s for s in similarities if s > 0])} matching documents\n")

        for i, idx in enumerate(top_indices, 1):
            if similarities[idx] > 0:
                doc_id = search_index['doc_ids'][idx]
                doc = search_index['doc_index'][doc_id]
                print(f"[{i}] Score: {similarities[idx]:.2%}")
                print(f"    Project: {doc['metadata']['project']}")
                print(f"    File: {doc['metadata']['file_name']}")
                print(f"    Content: {doc['content'][:150]}...\n")

    print("✅ Search test complete!")


def main():
    """Main pipeline"""

    print("\n🎯 REBUILD CLUB SEARCH INDEX")
    print("   Replace 517K emails with 117 LlamaParse documents\n")

    # Step 1: Load LlamaParse documents
    documents = load_llamaparse_documents()

    if not documents:
        print("\n❌ No documents found!")
        return

    # Step 2: Build search index
    search_index = build_search_index(documents)

    # Step 3: Save index
    save_search_index(search_index)

    # Step 4: Test search
    test_search(search_index)

    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)

    print("\n🚀 Next steps:")
    print("   1. Restart app_universal.py")
    print("   2. Refresh browser")
    print("   3. Try query: 'NICU step down market size'")
    print("   4. You should now see parsed documents instead of chat fragments!")


if __name__ == "__main__":
    main()
