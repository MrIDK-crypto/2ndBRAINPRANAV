"""
Build Knowledge Base for rishi2205
1. Filter all messages from rishi2205
2. Get all docs from spaces/groups rishi2205 is in
3. Build RAG index
4. Create gap analysis system
"""

import json
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import defaultdict
from config.config import Config

# Target user
TARGET_USER = "rishi2205"

def load_chat_messages():
    """Load all chat messages from Google Chat Takeout"""

    print("=" * 80)
    print(f"BUILDING KNOWLEDGE BASE FOR: {TARGET_USER}")
    print("=" * 80)

    takeout_path = Path("/Users/rishitjain/Downloads/Takeout/Google Chat/Groups")

    if not takeout_path.exists():
        print(f"❌ Takeout not found: {takeout_path}")
        return [], [], []

    # Store data
    user_messages = []  # Messages FROM rishi2205
    space_docs = []     # All docs in spaces rishi2205 is in
    user_spaces = []    # Spaces rishi2205 is a member of

    # Scan all spaces
    print(f"\n📂 Scanning Google Chat spaces...")

    for space_dir in takeout_path.iterdir():
        if not space_dir.is_dir():
            continue

        # Skip DMs for now
        if space_dir.name.startswith("DM "):
            continue

        # Read group info
        group_info_file = space_dir / "group_info.json"
        if not group_info_file.exists():
            continue

        with open(group_info_file, 'r') as f:
            group_info = json.load(f)

        space_name = group_info.get('name', space_dir.name)
        members = group_info.get('members', [])

        # Check if rishi2205 is in this space
        is_member = False
        for member in members:
            email = member.get('email', '')
            if TARGET_USER in email.lower():
                is_member = True
                break

        if not is_member:
            continue

        user_spaces.append({
            'space_id': space_dir.name,
            'space_name': space_name,
            'members': [m.get('email', '') for m in members],
            'member_count': len(members)
        })

        print(f"  ✓ Found space: {space_name} ({len(members)} members)")

        # Read messages from this space
        messages_file = space_dir / "messages.json"
        if messages_file.exists():
            with open(messages_file, 'r') as f:
                messages = json.load(f)

            messages_list = messages.get('messages', [])

            for msg in messages_list:
                creator = msg.get('creator', {})
                creator_email = creator.get('email', '')
                text = msg.get('text', '')

                if not text or len(text.strip()) < 5:
                    continue

                msg_data = {
                    'content': text,
                    'metadata': {
                        'space': space_name,
                        'space_id': space_dir.name,
                        'sender': creator_email,
                        'timestamp': msg.get('created_date', ''),
                        'type': 'message'
                    }
                }

                # If message is FROM rishi2205, add to user_messages
                if TARGET_USER in creator_email.lower():
                    user_messages.append(msg_data)

                # Add ALL messages from spaces rishi is in to space_docs
                space_docs.append(msg_data)

    print(f"\n✅ Found {len(user_spaces)} spaces with {TARGET_USER}")
    print(f"✅ Found {len(user_messages)} messages FROM {TARGET_USER}")
    print(f"✅ Found {len(space_docs)} total messages in those spaces")

    return user_messages, space_docs, user_spaces


def load_llamaparse_docs(user_spaces):
    """Load LlamaParse-parsed documents from spaces rishi2205 is in"""

    print("\n" + "=" * 80)
    print("LOADING LLAMAPARSE DOCUMENTS")
    print("=" * 80)

    # Map space names to project files
    club_dir = Config.OUTPUT_DIR / "club_project_classification" / "projects"

    llamaparse_docs = []

    # Space names to look for
    space_names = [s['space_name'] for s in user_spaces]

    print(f"\n📂 Looking for docs in {len(space_names)} spaces...")

    # Known project files for rishi2205's spaces
    project_files = [
        "Startup Team (Eric, Badri, Rishit).jsonl",
        "BEAT at UCLA.jsonl",
        "UCLA Health Project 2025.jsonl",
        "UCLA Health.jsonl",
        "Projects Summer.jsonl",
        "Vibio Health.jsonl",
        "BEAT Healthcare Consulting.jsonl",
        "Concierge Medicine + Addiction Medicine  (UCLA Health).jsonl",
    ]

    for pf in project_files:
        project_path = club_dir / pf
        if not project_path.exists():
            continue

        project_name = pf.replace('.jsonl', '')
        count = 0

        with open(project_path, 'r') as f:
            for line in f:
                doc = json.loads(line)

                # Only LlamaParse-parsed documents
                if doc.get('metadata', {}).get('parser') == 'llamaparse':
                    llamaparse_docs.append({
                        'content': doc.get('content', ''),
                        'metadata': {
                            'file_name': doc.get('metadata', {}).get('file_name', 'Unknown'),
                            'project': project_name,
                            'type': 'document',
                            'source': 'llamaparse'
                        }
                    })
                    count += 1

        if count > 0:
            print(f"  ✓ {project_name}: {count} docs")

    print(f"\n✅ Loaded {len(llamaparse_docs)} LlamaParse documents")
    return llamaparse_docs


def build_search_index(user_messages, space_docs, llamaparse_docs):
    """Build combined search index"""

    print("\n" + "=" * 80)
    print("BUILDING SEARCH INDEX")
    print("=" * 80)

    # Combine all documents
    all_docs = []
    doc_id = 0

    # Add LlamaParse docs (highest priority)
    for doc in llamaparse_docs:
        doc_id += 1
        all_docs.append({
            'doc_id': f"llamaparse_{doc_id}",
            'content': doc['content'],
            'metadata': doc['metadata'],
            'cluster_label': doc['metadata'].get('project', 'Unknown'),
            'priority': 1
        })

    # Add user messages
    for msg in user_messages:
        doc_id += 1
        all_docs.append({
            'doc_id': f"user_msg_{doc_id}",
            'content': msg['content'],
            'metadata': msg['metadata'],
            'cluster_label': msg['metadata'].get('space', 'Unknown'),
            'priority': 2
        })

    # Add space messages (lower priority)
    for msg in space_docs:
        doc_id += 1
        all_docs.append({
            'doc_id': f"space_msg_{doc_id}",
            'content': msg['content'],
            'metadata': msg['metadata'],
            'cluster_label': msg['metadata'].get('space', 'Unknown'),
            'priority': 3
        })

    print(f"\n📊 Building index for {len(all_docs)} total items:")
    print(f"   - {len(llamaparse_docs)} LlamaParse documents")
    print(f"   - {len(user_messages)} messages from {TARGET_USER}")
    print(f"   - {len(space_docs)} messages from team members")

    # Build TF-IDF
    doc_contents = [d['content'] for d in all_docs]
    doc_ids = [d['doc_id'] for d in all_docs]

    print("\n🔧 Creating TF-IDF vectorizer...")
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

    # Create document index
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
            'source': 'club_only'
        }
    }

    return search_index, all_docs


def create_gap_analysis_prompts(llamaparse_docs):
    """Create gap analysis system - identify missing information"""

    print("\n" + "=" * 80)
    print("CREATING GAP ANALYSIS SYSTEM")
    print("=" * 80)

    # Analyze documents for potential gaps
    gaps = []

    # Key metrics that should have specific values
    key_metrics = [
        ('NICU', 'cost per day', 'Cost per day in NICU'),
        ('NICU', 'market size', 'NICU market size'),
        ('OBED', 'revenue', 'OBED revenue projections'),
        ('ROI', 'percentage', 'Return on Investment'),
        ('beds', 'number', 'Number of beds'),
        ('patients', 'turned away', 'Patients turned away'),
        ('revenue', 'lost opportunity', 'Lost opportunity cost'),
        ('staff', 'nurses', 'Staffing requirements'),
    ]

    # Placeholders found in documents
    placeholder_patterns = ['$XXXX', '$XXxX', '$XxxX', 'TBD', '(TBD)']

    for doc in llamaparse_docs:
        content = doc.get('content', '')
        file_name = doc.get('metadata', {}).get('file_name', 'Unknown')
        project = doc.get('metadata', {}).get('project', 'Unknown')

        # Check for placeholder values
        for placeholder in placeholder_patterns:
            if placeholder in content:
                gaps.append({
                    'type': 'missing_value',
                    'description': f"Placeholder '{placeholder}' found - actual value needed",
                    'file': file_name,
                    'project': project,
                    'severity': 'high'
                })

        # Check for empty financial tables
        if '$ | $ | $' in content or '| $ |' in content:
            gaps.append({
                'type': 'incomplete_financials',
                'description': 'Financial table has empty cells - needs data',
                'file': file_name,
                'project': project,
                'severity': 'high'
            })

    # Add analytical gaps
    analytical_gaps = [
        {
            'type': 'analysis_question',
            'description': 'The NICU Step-Down TAM is $812M but SOM is only $47M (5.8%). Why such a conservative estimate?',
            'project': 'UCLA Health',
            'severity': 'medium'
        },
        {
            'type': 'analysis_question',
            'description': 'Lost opportunity cost per day mentioned as "$XXXX" - what is the actual calculation?',
            'project': 'UCLA Health',
            'severity': 'high'
        },
        {
            'type': 'analysis_question',
            'description': 'ROI stated as 154% for NICU Step-Down but OBED ROI is "(TBD)" - needs completion',
            'project': 'UCLA Health',
            'severity': 'high'
        },
        {
            'type': 'analysis_question',
            'description': '43 NICU patients turned away (10%) - what was the revenue impact?',
            'project': 'UCLA Health',
            'severity': 'medium'
        },
        {
            'type': 'comparison_gap',
            'description': 'Competitor analysis mentions Cedars-Sinai and CHLA have larger NICUs - specific capacity numbers missing',
            'project': 'UCLA Health',
            'severity': 'medium'
        }
    ]

    gaps.extend(analytical_gaps)

    print(f"\n✅ Identified {len(gaps)} potential gaps/questions:")
    for gap in gaps[:5]:
        print(f"   • [{gap['severity'].upper()}] {gap['description'][:60]}...")

    return gaps


def save_knowledge_base(search_index, user_spaces, gaps):
    """Save the knowledge base"""

    print("\n" + "=" * 80)
    print("SAVING KNOWLEDGE BASE")
    print("=" * 80)

    output_dir = Path('/Users/rishitjain/Downloads/knowledgevault_backend/club_data')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save search index
    index_file = output_dir / 'search_index.pkl'

    # Backup old
    if index_file.exists():
        backup = output_dir / 'search_index_backup.pkl'
        if not backup.exists():
            index_file.rename(backup)

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

    # Save metadata
    metadata = {
        'target_user': TARGET_USER,
        'total_docs': search_index['metadata']['total_documents'],
        'llamaparse_docs': search_index['metadata']['llamaparse_docs'],
        'user_messages': search_index['metadata']['user_messages'],
        'spaces': len(user_spaces),
        'gaps_identified': len(gaps),
        'source': 'club_only_no_enron'
    }

    with open(output_dir / 'knowledge_base_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata")

    print(f"\n📁 All files saved to: {output_dir}")


def main():
    """Main pipeline"""

    print("\n🎯 KNOWLEDGE BASE BUILDER FOR rishi2205")
    print("   Club data only - No Enron data\n")

    # Step 1: Load chat messages
    user_messages, space_docs, user_spaces = load_chat_messages()

    if not user_spaces:
        print("❌ No spaces found for user!")
        return

    # Step 2: Load LlamaParse documents
    llamaparse_docs = load_llamaparse_docs(user_spaces)

    # Step 3: Build search index
    search_index, all_docs = build_search_index(user_messages, space_docs, llamaparse_docs)

    # Step 4: Create gap analysis
    gaps = create_gap_analysis_prompts(llamaparse_docs)

    # Step 5: Save everything
    save_knowledge_base(search_index, user_spaces, gaps)

    print("\n" + "=" * 80)
    print("✅ KNOWLEDGE BASE COMPLETE!")
    print("=" * 80)

    print(f"\n📊 Summary:")
    print(f"   • User: {TARGET_USER}")
    print(f"   • Spaces: {len(user_spaces)}")
    print(f"   • LlamaParse Docs: {len(llamaparse_docs)}")
    print(f"   • User Messages: {len(user_messages)}")
    print(f"   • Team Messages: {len(space_docs)}")
    print(f"   • Knowledge Gaps: {len(gaps)}")

    print(f"\n🚀 Next: Restart the app and test!")


if __name__ == "__main__":
    main()
