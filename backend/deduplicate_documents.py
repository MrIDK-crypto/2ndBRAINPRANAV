"""
Document Deduplication Module
Identifies duplicate/versioned documents and keeps only the most complete version.

Strategy:
1. Group documents by content similarity (>70% TF-IDF cosine similarity)
2. Score each document by "completeness" (fewer placeholders = better)
3. Use timestamps as tiebreaker when available
4. Keep only the best version from each group
"""

import json
import re
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from collections import defaultdict

# Placeholder patterns that indicate incomplete data
PLACEHOLDER_PATTERNS = [
    r'\$XXXX',
    r'\$XXxX',
    r'\$XxxX',
    r'\$X+',
    r'\(TBD\)',
    r'\bTBD\b',
    r'TODO',
    r'\[INSERT\]',
    r'\[PLACEHOLDER\]',
    r'\| \$ \|',  # Empty dollar cells in tables
    r'\| \$\s*\|',
]

def calculate_completeness_score(content):
    """
    Calculate how "complete" a document is.
    Higher score = more complete (fewer placeholders, more actual data)
    """
    score = 100  # Start with perfect score

    # Penalize for each placeholder found
    for pattern in PLACEHOLDER_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        score -= len(matches) * 10  # -10 points per placeholder

    # Bonus for actual dollar values (real data)
    real_dollar_pattern = r'\$[\d,]+(?:\.\d+)?[MBK]?(?:illion)?'
    real_values = re.findall(real_dollar_pattern, content)
    score += len(real_values) * 2  # +2 points per real value

    # Bonus for percentages (indicates analysis)
    percentage_pattern = r'\d+(?:\.\d+)?%'
    percentages = re.findall(percentage_pattern, content)
    score += len(percentages) * 1  # +1 point per percentage

    # Bonus for content length (more complete docs tend to be longer)
    score += min(len(content) / 1000, 20)  # Up to +20 for length

    return score


def extract_timestamp_from_metadata(metadata):
    """Extract timestamp from document metadata if available"""
    timestamp = metadata.get('timestamp', '')
    if not timestamp:
        timestamp = metadata.get('created_date', '')
    if not timestamp:
        timestamp = metadata.get('date', '')
    return timestamp


def find_similar_document_groups(documents, similarity_threshold=0.70):
    """
    Group documents by content similarity using TF-IDF cosine similarity.
    Returns groups of similar documents.
    """
    if len(documents) < 2:
        return [[0]] if documents else []

    print(f"\n🔍 Finding similar document groups (threshold: {similarity_threshold})...")

    # Extract content
    contents = [doc.get('content', '')[:5000] for doc in documents]  # Use first 5000 chars

    # Build TF-IDF vectors
    vectorizer = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        stop_words='english',
        min_df=1
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(contents)
    except ValueError:
        # If all docs are too similar or empty
        return [[i] for i in range(len(documents))]

    # Calculate pairwise similarities
    similarity_matrix = cosine_similarity(tfidf_matrix)

    # Group similar documents using union-find approach
    n = len(documents)
    parent = list(range(n))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Union similar documents
    for i in range(n):
        for j in range(i + 1, n):
            if similarity_matrix[i][j] >= similarity_threshold:
                union(i, j)

    # Collect groups
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    group_list = list(groups.values())

    # Stats
    duplicate_groups = [g for g in group_list if len(g) > 1]
    print(f"  ✓ Found {len(group_list)} unique document groups")
    print(f"  ✓ {len(duplicate_groups)} groups have multiple versions")

    return group_list


def select_best_document(documents, indices):
    """
    From a group of similar documents, select the best (most complete) one.
    """
    if len(indices) == 1:
        return indices[0], None

    best_idx = None
    best_score = -float('inf')
    scores = []

    for idx in indices:
        doc = documents[idx]
        content = doc.get('content', '')
        metadata = doc.get('metadata', {})

        # Calculate completeness score
        completeness = calculate_completeness_score(content)

        # Timestamp bonus (newer is better)
        timestamp = extract_timestamp_from_metadata(metadata)
        timestamp_bonus = 0
        if timestamp:
            # Simple heuristic: later dates get small bonus
            try:
                # Try to extract year/month
                if '2024' in timestamp:
                    timestamp_bonus = 5
                if '2025' in timestamp:
                    timestamp_bonus = 10
            except:
                pass

        total_score = completeness + timestamp_bonus
        scores.append((idx, total_score, completeness))

        if total_score > best_score:
            best_score = total_score
            best_idx = idx

    # Return best and info about rejected docs
    rejected = [idx for idx in indices if idx != best_idx]
    return best_idx, rejected


def deduplicate_documents(documents):
    """
    Main deduplication function.
    Returns: (deduplicated_docs, dedup_info)
    """
    print("\n" + "=" * 80)
    print("DOCUMENT DEDUPLICATION")
    print("=" * 80)

    print(f"\n📊 Input: {len(documents)} documents")

    # Find similar document groups
    groups = find_similar_document_groups(documents)

    # Select best from each group
    kept_indices = []
    rejected_indices = []
    dedup_log = []

    for group in groups:
        best_idx, rejected = select_best_document(documents, group)
        kept_indices.append(best_idx)

        if rejected:
            rejected_indices.extend(rejected)
            # Log the deduplication decision
            best_doc = documents[best_idx]
            best_name = best_doc.get('metadata', {}).get('file_name', f'doc_{best_idx}')

            for rej_idx in rejected:
                rej_doc = documents[rej_idx]
                rej_name = rej_doc.get('metadata', {}).get('file_name', f'doc_{rej_idx}')
                dedup_log.append({
                    'kept': best_name,
                    'rejected': rej_name,
                    'reason': 'Less complete version'
                })

    # Build deduplicated document list
    deduplicated = [documents[i] for i in sorted(kept_indices)]

    print(f"\n✅ Deduplication Results:")
    print(f"   • Original documents: {len(documents)}")
    print(f"   • After deduplication: {len(deduplicated)}")
    print(f"   • Removed duplicates: {len(rejected_indices)}")

    if dedup_log:
        print(f"\n📋 Deduplication Decisions (showing first 10):")
        for entry in dedup_log[:10]:
            print(f"   ✓ Kept: {entry['kept'][:50]}")
            print(f"     Rejected: {entry['rejected'][:50]}")

    return deduplicated, {
        'original_count': len(documents),
        'deduplicated_count': len(deduplicated),
        'removed_count': len(rejected_indices),
        'log': dedup_log
    }


def analyze_document_versions(documents):
    """
    Analyze and report on document versions without modifying.
    Useful for understanding the data before deduplication.
    """
    print("\n" + "=" * 80)
    print("DOCUMENT VERSION ANALYSIS")
    print("=" * 80)

    # Group by similarity
    groups = find_similar_document_groups(documents, similarity_threshold=0.70)

    # Analyze each group
    version_groups = []
    for group in groups:
        if len(group) > 1:
            group_info = {
                'count': len(group),
                'documents': []
            }
            for idx in group:
                doc = documents[idx]
                content = doc.get('content', '')
                metadata = doc.get('metadata', {})

                # Count placeholders
                placeholder_count = 0
                for pattern in PLACEHOLDER_PATTERNS:
                    placeholder_count += len(re.findall(pattern, content, re.IGNORECASE))

                group_info['documents'].append({
                    'file_name': metadata.get('file_name', f'doc_{idx}'),
                    'project': metadata.get('project', 'Unknown'),
                    'completeness_score': calculate_completeness_score(content),
                    'placeholder_count': placeholder_count,
                    'content_length': len(content)
                })

            # Sort by completeness
            group_info['documents'].sort(key=lambda x: x['completeness_score'], reverse=True)
            version_groups.append(group_info)

    # Report
    print(f"\n📊 Found {len(version_groups)} groups of similar documents:\n")

    for i, group in enumerate(version_groups[:10], 1):
        print(f"Group {i} ({group['count']} versions):")
        for doc in group['documents']:
            marker = "✓ BEST" if doc == group['documents'][0] else "  "
            print(f"  {marker} {doc['file_name'][:60]}")
            print(f"       Score: {doc['completeness_score']:.0f}, Placeholders: {doc['placeholder_count']}, Length: {doc['content_length']}")
        print()

    return version_groups


if __name__ == "__main__":
    # Test with current LlamaParse documents
    from config.config import Config

    print("\n🎯 DOCUMENT DEDUPLICATION TEST")
    print("   Loading LlamaParse documents...\n")

    # Load documents
    club_dir = Config.OUTPUT_DIR / "club_project_classification" / "projects"

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

    all_docs = []
    for project_file in google_chat_projects:
        project_path = club_dir / project_file
        if not project_path.exists():
            continue

        with open(project_path, 'r') as f:
            for line in f:
                doc = json.loads(line)
                if doc.get('metadata', {}).get('parser') == 'llamaparse':
                    all_docs.append(doc)

    print(f"Loaded {len(all_docs)} LlamaParse documents")

    # Analyze versions
    analyze_document_versions(all_docs)

    # Deduplicate
    deduped, info = deduplicate_documents(all_docs)

    print("\n" + "=" * 80)
    print("✅ DEDUPLICATION COMPLETE")
    print("=" * 80)
