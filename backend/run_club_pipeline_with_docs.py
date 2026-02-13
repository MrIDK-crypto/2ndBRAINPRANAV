"""
Enhanced Club Pipeline with Document Parsing
Processes both chat messages AND attached documents (PDF, PPTX, XLSX, DOCX)
"""

import json
import os
from pathlib import Path
from tqdm import tqdm
from parsers.document_parser import DocumentParser
from run_club_pipeline import (
    parse_google_chat_messages,
    cluster_by_employee,
    cluster_projects_simple,
    build_search_index,
    generate_employee_summaries
)

# Paths
TAKEOUT_DIR = Path("/Users/rishitjain/Downloads/Takeout/Google Chat/Groups")
CLUB_DATA_DIR = Path("/Users/rishitjain/Downloads/knowledgevault_backend/club_data")

def find_and_parse_documents():
    """
    Find all Office documents in the Takeout and parse them
    Returns list of parsed documents
    """
    print("="*80)
    print("STEP 1A: Parsing Office Documents (PDF, PPTX, XLSX, DOCX)")
    print("-"*80)

    parser = DocumentParser()
    print(f"Supported formats: {parser.supported_formats}")

    # Find all documents
    all_docs = []
    for ext in ['.pdf', '.pptx', '.xlsx', '.docx']:
        found = list(TAKEOUT_DIR.rglob(f"*{ext}"))
        all_docs.extend(found)

    print(f"Found {len(all_docs)} documents to parse")

    parsed_documents = []

    for doc_path in tqdm(all_docs, desc="Parsing documents"):
        # Parse the document
        result = parser.parse(str(doc_path))

        if not result or len(result['content'].strip()) < 50:
            continue  # Skip empty or very short documents

        # Determine employee from path
        # Path structure: .../Groups/[GROUP_NAME]/File-[FILENAME]
        parts = doc_path.parts
        group_idx = parts.index('Groups') if 'Groups' in parts else -1

        if group_idx >= 0 and group_idx + 1 < len(parts):
            group_name = parts[group_idx + 1]
        else:
            group_name = "Unknown"

        # Create document structure
        doc_id = f"doc_{doc_path.stem}_{hash(str(doc_path)) % 1000000}"

        parsed_doc = {
            'doc_id': doc_id,
            'content': result['content'],
            'metadata': {
                'filename': doc_path.name,
                'file_path': str(doc_path),
                'group': group_name,
                'file_type': result['metadata']['file_type'],
                'source_type': 'document',
                **result['metadata']
            },
            'source_hyperlink': f"File: {doc_path.name}"
        }

        parsed_documents.append(parsed_doc)

    print(f"✓ Successfully parsed {len(parsed_documents)} documents")
    print(f"✓ Total content: {sum(len(d['content']) for d in parsed_documents):,} characters")

    return parsed_documents


def combine_messages_and_documents(messages_file, documents):
    """
    Combine chat messages with parsed documents
    """
    print("="*80)
    print("STEP 1B: Combining Messages and Documents")
    print("-"*80)

    # Load existing messages
    all_messages = []
    with open(messages_file, 'r') as f:
        for line in f:
            all_messages.append(json.loads(line))

    print(f"Loaded {len(all_messages)} chat messages")
    print(f"Adding {len(documents)} parsed documents")

    # Combine
    combined = all_messages + documents

    # Save combined
    combined_file = CLUB_DATA_DIR / "unclustered" / "all_messages_with_docs.jsonl"
    with open(combined_file, 'w') as f:
        for doc in combined:
            f.write(json.dumps(doc) + '\n')

    print(f"✓ Combined total: {len(combined)} items")
    print(f"✓ Saved to {combined_file}")

    return combined_file, combined


def main():
    print("="*80)
    print("ENHANCED CLUB PIPELINE - WITH DOCUMENT PARSING")
    print("="*80)

    # Ensure directories exist
    (CLUB_DATA_DIR / "unclustered").mkdir(parents=True, exist_ok=True)
    (CLUB_DATA_DIR / "employee_clusters").mkdir(parents=True, exist_ok=True)
    (CLUB_DATA_DIR / "project_clusters").mkdir(parents=True, exist_ok=True)

    # Step 1A: Parse documents
    parsed_docs = find_and_parse_documents()

    # Step 1B: Combine with messages
    messages_file = CLUB_DATA_DIR / "unclustered" / "all_messages.jsonl"
    combined_file, all_data = combine_messages_and_documents(messages_file, parsed_docs)

    # Step 2: Cluster by employee (using combined data)
    print("\n" + "="*80)
    print("STEP 2: Clustering by Employee (Messages + Documents)")
    print("-"*80)

    employee_data = {}
    for item in all_data:
        if item['metadata'].get('source_type') == 'google_chat':
            employee = item['metadata']['employee']
        else:
            # For documents, we'll assign to a special "documents" category for now
            # In a real system, you'd want to link documents to employees
            employee = item['metadata'].get('employee', 'shared_documents')

        if employee not in employee_data:
            employee_data[employee] = []
        employee_data[employee].append(item)

    # Save employee clusters
    for employee, items in employee_data.items():
        employee_file = CLUB_DATA_DIR / "employee_clusters" / f"{employee}.jsonl"
        with open(employee_file, 'w') as f:
            for item in items:
                f.write(json.dumps(item) + '\n')
        print(f"  {employee}: {len(items)} items")

    print(f"\n✓ Created {len(employee_data)} employee clusters")

    # Step 3: Build search index with combined data
    print("\n" + "="*80)
    print("STEP 3: Building Search Index (Messages + Documents)")
    print("-"*80)

    # Filter for quality content
    quality_items = []
    for item in all_data:
        if item['metadata'].get('source_type') == 'document':
            # Always include documents
            quality_items.append(item)
        else:
            # For messages, filter short ones
            if len(item['content'].strip()) >= 20:
                quality_items.append(item)

    print(f"Quality items for indexing: {len(quality_items)}")
    print(f"  - Chat messages: {sum(1 for i in quality_items if i['metadata'].get('source_type') == 'google_chat')}")
    print(f"  - Documents: {sum(1 for i in quality_items if i['metadata'].get('source_type') == 'document')}")

    # Build index
    from sklearn.feature_extraction.text import TfidfVectorizer
    import pickle

    texts = [item['content'] for item in quality_items]

    vectorizer = TfidfVectorizer(
        max_features=15000,  # Increased for documents
        stop_words='english',
        ngram_range=(1, 3),
        max_df=0.7,
        min_df=1,
        sublinear_tf=True
    )

    print("Building TF-IDF vectors...")
    doc_vectors = vectorizer.fit_transform(texts)

    doc_index = {item['doc_id']: item for item in quality_items}

    index_data = {
        'vectorizer': vectorizer,
        'doc_vectors': doc_vectors,
        'doc_ids': [item['doc_id'] for item in quality_items],
        'doc_index': doc_index
    }

    output_file = CLUB_DATA_DIR / "search_index.pkl"
    with open(output_file, 'wb') as f:
        pickle.dump(index_data, f)

    print(f"✓ Indexed {len(quality_items)} items")
    print(f"✓ Saved to {output_file}")

    # Step 4: Project clustering (skip for now, we can use existing)
    print("\n" + "="*80)
    print("STEP 4: Project Clustering (Using Existing)")
    print("-"*80)
    print("Keeping existing project clusters...")

    # Step 5: Employee summaries (skip, we can use existing)
    print("\n" + "="*80)
    print("STEP 5: Employee Summaries (Using Existing)")
    print("-"*80)
    print("Keeping existing employee summaries...")

    print("\n" + "="*80)
    print("PIPELINE COMPLETE!")
    print("="*80)

    print(f"\nTotal Items: {len(all_data):,}")
    print(f"  - Chat Messages: {len(all_data) - len(parsed_docs):,}")
    print(f"  - Documents: {len(parsed_docs):,}")
    print(f"Quality Items Indexed: {len(quality_items):,}")
    print(f"\nData saved to: {CLUB_DATA_DIR}")
    print("\n🌐 Restart the web app to use the new index with documents!")
    print("   python3 app_universal.py")


if __name__ == "__main__":
    main()
