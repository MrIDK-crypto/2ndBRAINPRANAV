"""
Build RAG Index from LlamaParse-parsed Club Documents
Uses only the 117 documents parsed from Google Chat projects
"""

import json
from pathlib import Path
from collections import defaultdict
from config.config import Config
from rag.rag_engine import RAGEngine

def load_llamaparse_documents():
    """Load all LlamaParse-parsed documents from club projects"""

    print("=" * 80)
    print("LOADING LLAMAPARSE-PARSED DOCUMENTS")
    print("=" * 80)

    club_dir = Config.OUTPUT_DIR / "club_project_classification"

    # Load summary to verify
    summary_file = club_dir / "summary.json"
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        print(f"\n📊 Dataset Summary:")
        print(f"  • Projects: {summary['total_projects']}")
        print(f"  • Employees: {summary['total_employees']}")
        print(f"  • Documents: {summary['total_documents']}")

    # Find the 10 Google Chat project files
    projects_dir = club_dir / "projects"

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

    print(f"\n📂 Loading documents from {len(google_chat_projects)} Google Chat projects...")

    all_documents = []
    project_counts = {}

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

                # Only include documents that were successfully parsed with LlamaParse
                if doc.get('metadata', {}).get('parser') == 'llamaparse':
                    all_documents.append(doc)
                    count += 1

        project_counts[project_name] = count
        print(f"  ✓ {project_name}: {count} docs")

    print(f"\n✅ Loaded {len(all_documents)} LlamaParse-parsed documents")

    # Show top projects by document count
    sorted_projects = sorted(project_counts.items(), key=lambda x: x[1], reverse=True)
    print(f"\n📊 Documents by Project:")
    for proj, count in sorted_projects[:10]:
        if count > 0:
            print(f"  {count:3d} docs - {proj}")

    return all_documents


def build_rag_index(documents):
    """Build RAG index from documents"""

    print("\n" + "=" * 80)
    print("BUILDING RAG INDEX")
    print("=" * 80)

    # Initialize RAG engine
    print("\n🔧 Initializing RAG engine...")
    rag = RAGEngine(config=Config)

    # Prepare documents for indexing
    print(f"\n📝 Preparing {len(documents)} documents...")

    rag_docs = []
    for i, doc in enumerate(documents, 1):
        # Extract key fields
        content = doc.get('content', '')
        metadata = doc.get('metadata', {})
        project = doc.get('project', 'Unknown')

        # Create document for RAG
        rag_doc = {
            'content': content,
            'metadata': {
                'file_name': metadata.get('file_name', 'Unknown'),
                'file_type': metadata.get('file_type', 'unknown'),
                'project': project,
                'parser': metadata.get('parser', 'unknown'),
                'source': 'club_google_chat',
                'doc_id': f"club_{i}"
            }
        }
        rag_docs.append(rag_doc)

        if i % 10 == 0:
            print(f"  Prepared {i}/{len(documents)} documents...")

    print(f"✓ Prepared {len(rag_docs)} documents")

    # Build index
    print(f"\n🔨 Building vector index...")
    print(f"   This may take 2-5 minutes for {len(rag_docs)} documents...")

    rag.build_index(rag_docs)

    print(f"\n✅ RAG index built successfully!")

    return rag


def test_rag_search(rag):
    """Test the RAG search with sample queries"""

    print("\n" + "=" * 80)
    print("TESTING RAG SEARCH")
    print("=" * 80)

    test_queries = [
        "NICU step down market size",
        "UCLA Health project",
        "BEAT Healthcare Consulting",
        "cardiology shadowing proposal"
    ]

    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        print("-" * 80)

        results = rag.search(query, top_k=5)

        print(f"Found {len(results)} results:")
        for i, result in enumerate(results[:3], 1):
            print(f"\n[{i}] Score: {result['score']:.2f}")
            print(f"    Project: {result['metadata'].get('project', 'Unknown')}")
            print(f"    File: {result['metadata'].get('file_name', 'Unknown')}")
            print(f"    Content: {result['content'][:200]}...")

    print("\n✅ RAG search test complete!")


def save_rag_index(rag):
    """Save RAG index to disk"""

    print("\n" + "=" * 80)
    print("SAVING RAG INDEX")
    print("=" * 80)

    output_dir = Config.OUTPUT_DIR / "club_rag_index"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Saving to: {output_dir}")

    rag.save_index(str(output_dir))

    print(f"✅ RAG index saved!")

    # Save metadata
    metadata = {
        'source': 'club_google_chat',
        'parser': 'llamaparse',
        'total_documents': len(rag.documents) if hasattr(rag, 'documents') else 0,
        'index_type': 'llamaindex',
        'created': 'November 2025'
    }

    with open(output_dir / 'index_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ Saved metadata")


def main():
    """Main pipeline"""

    print("\n🎯 CLUB RAG INDEX BUILDER")
    print("   Build RAG from LlamaParse-parsed Google Chat documents\n")

    # Step 1: Load documents
    documents = load_llamaparse_documents()

    if not documents:
        print("\n❌ No documents found!")
        return

    # Step 2: Build RAG index
    rag = build_rag_index(documents)

    # Step 3: Test search
    test_rag_search(rag)

    # Step 4: Save index
    save_rag_index(rag)

    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)

    print("\n🚀 Next steps:")
    print("   1. RAG index is ready at: output/club_rag_index/")
    print("   2. Update frontend to use this index")
    print("   3. Test search queries on frontend")
    print("   4. Open http://localhost:5002")


if __name__ == "__main__":
    main()
