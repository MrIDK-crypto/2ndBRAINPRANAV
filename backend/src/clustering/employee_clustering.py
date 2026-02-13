"""
Employee-Based Clustering Module
Clusters documents by employee using metadata
"""

import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict
from datetime import datetime
import pandas as pd


class EmployeeClusterer:
    """Cluster documents by employee (metadata-based hard clustering)"""

    def __init__(self):
        self.employee_clusters = defaultdict(list)
        self.statistics = {}

    def load_documents(self, jsonl_path: str) -> List[Dict]:
        """Load documents from JSONL file"""
        documents = []
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                doc = json.loads(line)
                documents.append(doc)
        print(f"✓ Loaded {len(documents)} documents")
        return documents

    def cluster_by_employee(self, documents: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Cluster documents by employee

        Args:
            documents: List of document dictionaries

        Returns:
            Dictionary mapping employee names to their documents
        """
        print("Clustering documents by employee...")

        self.employee_clusters = defaultdict(list)

        for doc in documents:
            employee = doc['metadata'].get('employee', 'unknown')
            self.employee_clusters[employee].append(doc)

        print(f"✓ Created {len(self.employee_clusters)} employee clusters")
        return dict(self.employee_clusters)

    def save_employee_clusters(self, output_dir: str):
        """
        Save each employee's documents to separate JSONL files

        Args:
            output_dir: Directory to save employee cluster files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"Saving employee clusters to {output_dir}...")

        for employee, docs in self.employee_clusters.items():
            # Create safe filename
            safe_filename = employee.replace('/', '_').replace('\\', '_')
            employee_file = output_path / f"{safe_filename}.jsonl"

            with open(employee_file, 'w', encoding='utf-8') as f:
                for doc in docs:
                    f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        print(f"✓ Saved {len(self.employee_clusters)} employee cluster files")

    def generate_statistics(self) -> Dict:
        """Generate statistics about employee clusters"""
        stats = {
            'total_employees': len(self.employee_clusters),
            'total_documents': sum(len(docs) for docs in self.employee_clusters.values()),
            'employee_document_counts': {},
            'average_documents_per_employee': 0,
            'min_documents': float('inf'),
            'max_documents': 0,
        }

        for employee, docs in self.employee_clusters.items():
            doc_count = len(docs)
            stats['employee_document_counts'][employee] = doc_count
            stats['min_documents'] = min(stats['min_documents'], doc_count)
            stats['max_documents'] = max(stats['max_documents'], doc_count)

        if stats['total_employees'] > 0:
            stats['average_documents_per_employee'] = stats['total_documents'] / stats['total_employees']

        self.statistics = stats
        return stats

    def save_statistics(self, output_path: str):
        """Save statistics to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.statistics, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved statistics to {output_path}")

    def print_statistics(self):
        """Print employee clustering statistics"""
        if not self.statistics:
            self.generate_statistics()

        print("\n" + "="*60)
        print("EMPLOYEE CLUSTERING STATISTICS")
        print("="*60)
        print(f"Total employees: {self.statistics['total_employees']}")
        print(f"Total documents: {self.statistics['total_documents']}")
        print(f"Average documents per employee: {self.statistics['average_documents_per_employee']:.2f}")
        print(f"Min documents (single employee): {self.statistics['min_documents']}")
        print(f"Max documents (single employee): {self.statistics['max_documents']}")

        print(f"\nTop 15 employees by document count:")
        sorted_employees = sorted(
            self.statistics['employee_document_counts'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:15]

        for i, (emp, count) in enumerate(sorted_employees, 1):
            print(f"  {i:2d}. {emp:30s}: {count:5d} documents")

    def get_employee_timeline(self, employee: str) -> pd.DataFrame:
        """
        Get timeline of documents for a specific employee

        Args:
            employee: Employee name

        Returns:
            DataFrame with document timeline
        """
        if employee not in self.employee_clusters:
            return pd.DataFrame()

        docs = self.employee_clusters[employee]
        timeline_data = []

        for doc in docs:
            timestamp = doc['metadata'].get('timestamp')
            if timestamp:
                timeline_data.append({
                    'timestamp': timestamp,
                    'subject': doc['metadata'].get('subject', ''),
                    'folder': doc['metadata'].get('folder', ''),
                    'doc_id': doc['doc_id'],
                })

        df = pd.DataFrame(timeline_data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')

        return df

    def get_employee_metadata_summary(self, employee: str) -> Dict:
        """
        Get metadata summary for a specific employee

        Args:
            employee: Employee name

        Returns:
            Dictionary with metadata summaries
        """
        if employee not in self.employee_clusters:
            return {}

        docs = self.employee_clusters[employee]

        folders = defaultdict(int)
        subjects = []
        timestamps = []

        for doc in docs:
            metadata = doc['metadata']
            folders[metadata.get('folder', 'unknown')] += 1
            subjects.append(metadata.get('subject', ''))
            if metadata.get('timestamp'):
                timestamps.append(metadata['timestamp'])

        return {
            'employee': employee,
            'total_documents': len(docs),
            'folders': dict(folders),
            'unique_folders': len(folders),
            'date_range': {
                'earliest': min(timestamps) if timestamps else None,
                'latest': max(timestamps) if timestamps else None,
            },
            'sample_subjects': subjects[:10],
        }


def cluster_by_employee(input_jsonl: str, output_dir: str) -> EmployeeClusterer:
    """
    Main function to cluster documents by employee

    Args:
        input_jsonl: Path to unclustered JSONL file
        output_dir: Directory to save employee clusters

    Returns:
        EmployeeClusterer instance with results
    """
    clusterer = EmployeeClusterer()

    # Load documents
    documents = clusterer.load_documents(input_jsonl)

    # Cluster by employee
    clusterer.cluster_by_employee(documents)

    # Save clusters
    clusterer.save_employee_clusters(output_dir)

    # Generate and save statistics
    clusterer.generate_statistics()
    stats_path = Path(output_dir) / "employee_statistics.json"
    clusterer.save_statistics(str(stats_path))

    # Print statistics
    clusterer.print_statistics()

    return clusterer


if __name__ == "__main__":
    from config.config import Config

    # Test employee clustering
    input_file = Config.DATA_DIR / "unclustered" / "enron_emails.jsonl"
    output_dir = Config.DATA_DIR / "employee_clusters"

    clusterer = cluster_by_employee(
        input_jsonl=str(input_file),
        output_dir=str(output_dir)
    )

    # Show example employee summary
    if clusterer.employee_clusters:
        first_employee = list(clusterer.employee_clusters.keys())[0]
        summary = clusterer.get_employee_metadata_summary(first_employee)
        print(f"\nExample Employee Summary for {first_employee}:")
        print(json.dumps(summary, indent=2, default=str))
