"""
Build Deduplicated Knowledge Base for rishi2205
1. Load LlamaParse documents
2. Deduplicate to keep only most complete versions
3. Build RAG index from deduplicated docs
4. Generate project-based gap analysis and questions
"""

import json
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import defaultdict
from config.config import Config
from deduplicate_documents import deduplicate_documents, calculate_completeness_score, PLACEHOLDER_PATTERNS
import re

# Target user
TARGET_USER = "rishi2205"

# Projects (spaces)
PROJECTS = [
    "Vibio Health",
    "Startup Team (Eric, Badri, Rishit)",
    "Amgen Project Fall 2024",
    "BEAT at UCLA",
    "UCLA Health Project 2025",
    "Addiction Medicine - Data",
    "BEAT Healthcare Consulting",
    "Concierge Medicine + Addiction Medicine  (UCLA Health)",
    "UCLA Health",
    "Projects Summer"
]


def load_and_deduplicate_llamaparse_docs():
    """Load LlamaParse documents and deduplicate"""

    print("=" * 80)
    print("LOADING AND DEDUPLICATING LLAMAPARSE DOCUMENTS")
    print("=" * 80)

    club_dir = Config.OUTPUT_DIR / "club_project_classification" / "projects"

    project_files = [f"{p}.jsonl" for p in PROJECTS]

    all_docs = []
    project_doc_counts = defaultdict(int)

    for project_file in project_files:
        project_path = club_dir / project_file
        if not project_path.exists():
            continue

        project_name = project_file.replace('.jsonl', '')

        with open(project_path, 'r') as f:
            for line in f:
                doc = json.loads(line)
                if doc.get('metadata', {}).get('parser') == 'llamaparse':
                    # Add project info to metadata
                    doc['metadata']['project'] = project_name
                    all_docs.append(doc)
                    project_doc_counts[project_name] += 1

    print(f"\n📊 Loaded {len(all_docs)} LlamaParse documents from {len(project_doc_counts)} projects")

    # Deduplicate
    deduplicated_docs, dedup_info = deduplicate_documents(all_docs)

    return deduplicated_docs, dedup_info


def load_chat_messages():
    """Load chat messages from Google Chat Takeout"""

    print("\n" + "=" * 80)
    print("LOADING CHAT MESSAGES")
    print("=" * 80)

    takeout_path = Path("/Users/rishitjain/Downloads/Takeout/Google Chat/Groups")

    if not takeout_path.exists():
        print(f"❌ Takeout not found: {takeout_path}")
        return [], [], []

    user_messages = []
    space_docs = []
    user_spaces = []

    for space_dir in takeout_path.iterdir():
        if not space_dir.is_dir():
            continue
        if space_dir.name.startswith("DM "):
            continue

        group_info_file = space_dir / "group_info.json"
        if not group_info_file.exists():
            continue

        with open(group_info_file, 'r') as f:
            group_info = json.load(f)

        space_name = group_info.get('name', space_dir.name)
        members = group_info.get('members', [])

        # Check if rishi2205 is in this space
        is_member = any(TARGET_USER in m.get('email', '').lower() for m in members)

        if not is_member:
            continue

        user_spaces.append({
            'space_id': space_dir.name,
            'space_name': space_name,
            'members': [m.get('email', '') for m in members],
            'member_count': len(members)
        })

        # Read messages
        messages_file = space_dir / "messages.json"
        if messages_file.exists():
            with open(messages_file, 'r') as f:
                messages = json.load(f)

            for msg in messages.get('messages', []):
                creator_email = msg.get('creator', {}).get('email', '')
                text = msg.get('text', '')
                timestamp = msg.get('created_date', '')

                if not text or len(text.strip()) < 5:
                    continue

                msg_data = {
                    'content': text,
                    'metadata': {
                        'space': space_name,
                        'space_id': space_dir.name,
                        'sender': creator_email,
                        'timestamp': timestamp,
                        'type': 'message'
                    }
                }

                if TARGET_USER in creator_email.lower():
                    user_messages.append(msg_data)

                space_docs.append(msg_data)

    print(f"✅ Found {len(user_spaces)} spaces with {TARGET_USER}")
    print(f"✅ Found {len(user_messages)} messages FROM {TARGET_USER}")
    print(f"✅ Found {len(space_docs)} total messages in those spaces")

    return user_messages, space_docs, user_spaces


def build_search_index(llamaparse_docs, user_messages, space_docs):
    """Build combined search index with deduplicated docs"""

    print("\n" + "=" * 80)
    print("BUILDING SEARCH INDEX")
    print("=" * 80)

    all_docs = []
    doc_id = 0

    # Add deduplicated LlamaParse docs (highest priority)
    for doc in llamaparse_docs:
        doc_id += 1
        all_docs.append({
            'doc_id': f"llamaparse_{doc_id}",
            'content': doc['content'],
            'metadata': doc['metadata'],
            'cluster_label': doc['metadata'].get('project', 'Unknown'),
            'priority': 1,
            'is_latest': True  # Mark as deduplicated/latest version
        })

    # Add user messages
    for msg in user_messages:
        doc_id += 1
        all_docs.append({
            'doc_id': f"user_msg_{doc_id}",
            'content': msg['content'],
            'metadata': msg['metadata'],
            'cluster_label': msg['metadata'].get('space', 'Unknown'),
            'priority': 2,
            'is_latest': True
        })

    # Add space messages
    for msg in space_docs:
        doc_id += 1
        all_docs.append({
            'doc_id': f"space_msg_{doc_id}",
            'content': msg['content'],
            'metadata': msg['metadata'],
            'cluster_label': msg['metadata'].get('space', 'Unknown'),
            'priority': 3,
            'is_latest': True
        })

    print(f"\n📊 Building index for {len(all_docs)} total items:")
    print(f"   - {len(llamaparse_docs)} deduplicated LlamaParse documents")
    print(f"   - {len(user_messages)} messages from {TARGET_USER}")
    print(f"   - {len(space_docs)} messages from team members")

    # Build TF-IDF
    doc_contents = [d['content'] for d in all_docs]
    doc_ids = [d['doc_id'] for d in all_docs]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words='english',
        min_df=1,
        max_df=0.95
    )

    doc_vectors = vectorizer.fit_transform(doc_contents)

    print(f"  ✓ Created {doc_vectors.shape[0]} document vectors")
    print(f"  ✓ Feature dimensions: {doc_vectors.shape[1]}")

    doc_index = {d['doc_id']: d for d in all_docs}

    search_index = {
        'vectorizer': vectorizer,
        'doc_vectors': doc_vectors,
        'doc_ids': doc_ids,
        'doc_index': doc_index,
        'metadata': {
            'total_documents': len(all_docs),
            'llamaparse_docs': len(llamaparse_docs),
            'user_messages': len(user_messages),
            'space_messages': len(space_docs),
            'target_user': TARGET_USER,
            'source': 'club_deduplicated',
            'deduplicated': True
        }
    }

    return search_index, all_docs


def create_project_based_gaps(llamaparse_docs, user_spaces):
    """Create gap analysis organized by project with standard questions"""

    print("\n" + "=" * 80)
    print("CREATING PROJECT-BASED GAP ANALYSIS")
    print("=" * 80)

    # Organize docs by project
    docs_by_project = defaultdict(list)
    for doc in llamaparse_docs:
        project = doc.get('metadata', {}).get('project', 'Unknown')
        docs_by_project[project].append(doc)

    gaps = []

    # For each project, create standard questions + document-specific gaps
    for project_name in PROJECTS:
        project_docs = docs_by_project.get(project_name, [])

        # Standard questions for every project
        gaps.append({
            'type': 'project_goal',
            'description': f'What was the main goal of the {project_name} project?',
            'project': project_name,
            'severity': 'high',
            'is_standard': True
        })

        gaps.append({
            'type': 'success_criteria',
            'description': f'What were the success criteria for the {project_name} project?',
            'project': project_name,
            'severity': 'high',
            'is_standard': True
        })

        gaps.append({
            'type': 'project_outcome',
            'description': f'What was the final outcome/deliverable of the {project_name} project?',
            'project': project_name,
            'severity': 'medium',
            'is_standard': True
        })

        # Document-specific gaps (only from deduplicated docs)
        for doc in project_docs:
            content = doc.get('content', '')
            file_name = doc.get('metadata', {}).get('file_name', 'Unknown')

            # Check for placeholder values
            for pattern in PLACEHOLDER_PATTERNS[:7]:  # Main placeholder patterns
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    # Only add if we haven't already flagged this type
                    gap_desc = f"Document contains placeholder '{matches[0]}' - actual value needed"
                    if not any(g['description'] == gap_desc and g['project'] == project_name for g in gaps):
                        gaps.append({
                            'type': 'missing_value',
                            'description': gap_desc,
                            'file': file_name,
                            'project': project_name,
                            'severity': 'high',
                            'is_standard': False
                        })

            # Check for empty financial tables
            if '| $ |' in content or '| $\s*|' in content:
                gaps.append({
                    'type': 'incomplete_financials',
                    'description': 'Financial table has empty cells - needs data',
                    'file': file_name,
                    'project': project_name,
                    'severity': 'high',
                    'is_standard': False
                })

    # Deduplicate gaps
    seen = set()
    unique_gaps = []
    for gap in gaps:
        key = (gap['description'], gap['project'])
        if key not in seen:
            seen.add(key)
            unique_gaps.append(gap)

    print(f"\n✅ Created {len(unique_gaps)} knowledge gaps across {len(PROJECTS)} projects:")

    # Count by project
    gaps_by_project = defaultdict(int)
    for gap in unique_gaps:
        gaps_by_project[gap['project']] += 1

    for project, count in sorted(gaps_by_project.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {project}: {count} gaps")

    return unique_gaps


def save_knowledge_base(search_index, user_spaces, gaps, dedup_info):
    """Save the knowledge base"""

    print("\n" + "=" * 80)
    print("SAVING KNOWLEDGE BASE")
    print("=" * 80)

    output_dir = Path('/Users/rishitjain/Downloads/knowledgevault_backend/club_data')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Backup old index
    index_file = output_dir / 'search_index.pkl'
    if index_file.exists():
        backup = output_dir / 'search_index_pre_dedup_backup.pkl'
        if not backup.exists():
            index_file.rename(backup)
            print(f"✓ Backed up old index")

    # Save search index
    with open(index_file, 'wb') as f:
        pickle.dump(search_index, f)
    print(f"✓ Saved search index")

    # Save user spaces
    with open(output_dir / 'user_spaces.json', 'w') as f:
        json.dump(user_spaces, f, indent=2)
    print(f"✓ Saved user spaces")

    # Save gaps
    with open(output_dir / 'knowledge_gaps.json', 'w') as f:
        json.dump(gaps, f, indent=2)
    print(f"✓ Saved {len(gaps)} knowledge gaps")

    # Save deduplication info
    with open(output_dir / 'deduplication_info.json', 'w') as f:
        json.dump(dedup_info, f, indent=2)
    print(f"✓ Saved deduplication info")

    # Save metadata
    metadata = {
        'target_user': TARGET_USER,
        'total_docs': search_index['metadata']['total_documents'],
        'llamaparse_docs': search_index['metadata']['llamaparse_docs'],
        'user_messages': search_index['metadata']['user_messages'],
        'spaces': len(user_spaces),
        'gaps_identified': len(gaps),
        'source': 'club_deduplicated',
        'deduplicated': True,
        'original_doc_count': dedup_info['original_count'],
        'removed_duplicates': dedup_info['removed_count']
    }

    with open(output_dir / 'knowledge_base_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata")

    print(f"\n📁 All files saved to: {output_dir}")


def main():
    """Main pipeline"""

    print("\n🎯 DEDUPLICATED KNOWLEDGE BASE BUILDER")
    print("   For user: rishi2205")
    print("   With document deduplication and project-based gaps\n")

    # Step 1: Load and deduplicate LlamaParse documents
    llamaparse_docs, dedup_info = load_and_deduplicate_llamaparse_docs()

    if not llamaparse_docs:
        print("❌ No documents found!")
        return

    # Step 2: Load chat messages
    user_messages, space_docs, user_spaces = load_chat_messages()

    if not user_spaces:
        print("❌ No spaces found for user!")
        return

    # Step 3: Build search index
    search_index, all_docs = build_search_index(llamaparse_docs, user_messages, space_docs)

    # Step 4: Create project-based gap analysis
    gaps = create_project_based_gaps(llamaparse_docs, user_spaces)

    # Step 5: Save everything
    save_knowledge_base(search_index, user_spaces, gaps, dedup_info)

    print("\n" + "=" * 80)
    print("✅ DEDUPLICATED KNOWLEDGE BASE COMPLETE!")
    print("=" * 80)

    print(f"\n📊 Summary:")
    print(f"   • User: {TARGET_USER}")
    print(f"   • Original LlamaParse Docs: {dedup_info['original_count']}")
    print(f"   • After Deduplication: {dedup_info['deduplicated_count']}")
    print(f"   • Duplicates Removed: {dedup_info['removed_count']}")
    print(f"   • User Messages: {len(user_messages)}")
    print(f"   • Team Messages: {len(space_docs)}")
    print(f"   • Projects: {len(user_spaces)}")
    print(f"   • Knowledge Gaps: {len(gaps)}")

    print(f"\n🚀 Next: Restart app_universal.py and test!")


if __name__ == "__main__":
    main()
