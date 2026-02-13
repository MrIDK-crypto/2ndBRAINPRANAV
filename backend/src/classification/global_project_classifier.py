"""
Global Project Classification using DistilBERT
Classifies projects across the entire dataset, then maps employees to projects
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
from transformers import (
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    pipeline
)
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')


class GlobalProjectClassifier:
    """
    Classify projects globally across all employees using DistilBERT
    Uses zero-shot classification with predefined project categories
    """

    def __init__(self, config):
        """
        Initialize Global Project Classifier

        Args:
            config: Configuration object
        """
        self.config = config
        self.classifier = None
        self.project_categories = []

        print("Initializing Global Project Classifier with DistilBERT...")
        self._initialize_classifier()

    def _initialize_classifier(self):
        """Initialize zero-shot classification pipeline"""
        try:
            # Use zero-shot classification pipeline with DistilBERT
            self.classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",  # Best for zero-shot
                device=0 if torch.cuda.is_available() else -1
            )
            print("✓ Zero-shot classifier initialized")
        except Exception as e:
            print(f"⚠ Failed to initialize zero-shot classifier: {e}")
            print("  Falling back to simple DistilBERT classification")
            self.classifier = None

    def set_project_categories(self, categories: List[str]):
        """
        Set the project categories to classify into

        Args:
            categories: List of project category names
        """
        self.project_categories = categories
        print(f"✓ Set {len(categories)} project categories")

    def auto_detect_project_categories(
        self,
        documents: List[Dict],
        max_categories: int = 20
    ) -> List[str]:
        """
        Auto-detect project categories from documents using keywords

        Args:
            documents: All documents from all employees
            max_categories: Maximum number of categories to detect

        Returns:
            List of detected project categories
        """
        print(f"\n🔍 Auto-detecting project categories from {len(documents)} documents...")

        # Extract common themes from subjects
        subjects = []
        for doc in documents:
            subject = doc['metadata'].get('subject', '')
            if subject:
                subjects.append(subject.lower())

        # Simple keyword extraction (you can enhance this)
        from collections import Counter

        # Common project-related keywords
        common_words = set(['re:', 'fwd:', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'])

        # Extract significant words
        word_freq = Counter()
        for subject in subjects:
            words = subject.split()
            for word in words:
                word = word.strip('.,!?:;')
                if len(word) > 3 and word not in common_words:
                    word_freq[word] += 1

        # Get top keywords as categories
        top_keywords = [word for word, _ in word_freq.most_common(max_categories)]

        # Create meaningful category names
        categories = []
        for keyword in top_keywords:
            category = keyword.replace('_', ' ').title()
            categories.append(category)

        # Add some default categories
        default_categories = [
            "General Communication",
            "Project Planning",
            "Technical Discussion",
            "Meeting Notes",
            "Status Update",
            "Client Communication"
        ]

        # Combine and deduplicate
        all_categories = list(set(categories + default_categories))[:max_categories]

        self.project_categories = all_categories
        print(f"✓ Detected {len(all_categories)} project categories:")
        for i, cat in enumerate(all_categories[:10], 1):
            print(f"  {i}. {cat}")
        if len(all_categories) > 10:
            print(f"  ... and {len(all_categories) - 10} more")

        return all_categories

    def classify_document(self, document: Dict) -> Tuple[str, float]:
        """
        Classify a single document into a project category

        Args:
            document: Document dictionary

        Returns:
            Tuple of (project_category, confidence)
        """
        if not self.project_categories:
            raise ValueError("No project categories set. Call set_project_categories() first.")

        # Prepare text for classification
        subject = document['metadata'].get('subject', '')
        content = document['content'][:500]  # First 500 chars
        text = f"{subject}. {content}"

        if self.classifier:
            # Use zero-shot classification
            result = self.classifier(
                text,
                candidate_labels=self.project_categories,
                multi_label=False
            )

            return result['labels'][0], result['scores'][0]
        else:
            # Fallback: simple keyword matching
            text_lower = text.lower()
            best_match = self.project_categories[0]
            best_score = 0.5

            for category in self.project_categories:
                if category.lower() in text_lower:
                    return category, 0.8

            return best_match, best_score

    def classify_all_documents(
        self,
        documents: List[Dict],
        batch_size: int = 16
    ) -> List[Dict]:
        """
        Classify all documents into project categories

        Args:
            documents: List of all documents
            batch_size: Batch size for processing

        Returns:
            Documents with project classification added
        """
        print(f"\n📊 Classifying {len(documents)} documents into projects...")

        classified_docs = []

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            for doc in batch:
                project, confidence = self.classify_document(doc)

                doc['project_category'] = project
                doc['project_confidence'] = confidence

                classified_docs.append(doc)

            if (i + batch_size) % 100 == 0:
                print(f"  Processed {min(i + batch_size, len(documents))}/{len(documents)} documents...")

        print(f"✓ Classified all documents")
        return classified_docs

    def create_project_employee_mapping(
        self,
        classified_documents: List[Dict]
    ) -> Dict[str, Dict]:
        """
        Create mapping of projects to employees

        Args:
            classified_documents: Documents with project classifications

        Returns:
            Dictionary mapping project -> employee data
        """
        print("\n🗺️  Creating project-employee mapping...")

        # Group by project
        projects = defaultdict(lambda: {
            'employees': set(),
            'documents': [],
            'total_docs': 0,
            'avg_confidence': []
        })

        for doc in classified_documents:
            project = doc.get('project_category', 'Unknown')
            employee = doc['metadata'].get('from', 'Unknown')
            confidence = doc.get('project_confidence', 0.0)

            projects[project]['employees'].add(employee)
            projects[project]['documents'].append(doc)
            projects[project]['total_docs'] += 1
            projects[project]['avg_confidence'].append(confidence)

        # Create final mapping
        project_mapping = {}

        for project, data in projects.items():
            employee_list = list(data['employees'])
            avg_conf = sum(data['avg_confidence']) / len(data['avg_confidence']) if data['avg_confidence'] else 0.0

            # Count docs per employee in this project
            employee_doc_counts = defaultdict(int)
            for doc in data['documents']:
                emp = doc['metadata'].get('from', 'Unknown')
                employee_doc_counts[emp] += 1

            project_mapping[project] = {
                'project_name': project,
                'total_documents': data['total_docs'],
                'num_employees': len(employee_list),
                'employees': employee_list,
                'employee_contributions': dict(employee_doc_counts),
                'avg_confidence': avg_conf,
                'documents': data['documents']
            }

        print(f"✓ Created mapping for {len(project_mapping)} projects")

        # Print summary
        print("\n📋 Project Summary:")
        for project, info in sorted(project_mapping.items(), key=lambda x: x[1]['total_documents'], reverse=True)[:10]:
            print(f"  • {project}: {info['total_documents']} docs, {info['num_employees']} employees")

        return project_mapping

    def create_employee_project_mapping(
        self,
        classified_documents: List[Dict]
    ) -> Dict[str, Dict]:
        """
        Create mapping of employees to projects

        Args:
            classified_documents: Documents with project classifications

        Returns:
            Dictionary mapping employee -> project data
        """
        print("\n👥 Creating employee-project mapping...")

        # Group by employee
        employees = defaultdict(lambda: {
            'projects': defaultdict(int),
            'total_docs': 0,
            'documents': []
        })

        for doc in classified_documents:
            employee = doc['metadata'].get('from', 'Unknown')
            project = doc.get('project_category', 'Unknown')

            employees[employee]['projects'][project] += 1
            employees[employee]['total_docs'] += 1
            employees[employee]['documents'].append(doc)

        # Create final mapping
        employee_mapping = {}

        for employee, data in employees.items():
            # Get primary projects (>10% of docs)
            threshold = data['total_docs'] * 0.1
            primary_projects = {
                proj: count
                for proj, count in data['projects'].items()
                if count >= threshold
            }

            employee_mapping[employee] = {
                'employee': employee,
                'total_documents': data['total_docs'],
                'num_projects': len(data['projects']),
                'all_projects': dict(data['projects']),
                'primary_projects': primary_projects,
                'documents': data['documents']
            }

        print(f"✓ Created mapping for {len(employee_mapping)} employees")

        return employee_mapping

    def save_results(
        self,
        project_mapping: Dict,
        employee_mapping: Dict,
        output_dir: str
    ):
        """
        Save classification results

        Args:
            project_mapping: Project to employee mapping
            employee_mapping: Employee to project mapping
            output_dir: Directory to save results
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save project mapping
        project_file = output_path / "project_mapping.json"
        with open(project_file, 'w', encoding='utf-8') as f:
            # Convert for JSON serialization
            serializable_projects = {}
            for proj, data in project_mapping.items():
                serializable_projects[proj] = {
                    'project_name': data['project_name'],
                    'total_documents': data['total_documents'],
                    'num_employees': data['num_employees'],
                    'employees': data['employees'],
                    'employee_contributions': data['employee_contributions'],
                    'avg_confidence': data['avg_confidence']
                }
            json.dump(serializable_projects, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved project mapping to {project_file}")

        # Save employee mapping
        employee_file = output_path / "employee_mapping.json"
        with open(employee_file, 'w', encoding='utf-8') as f:
            serializable_employees = {}
            for emp, data in employee_mapping.items():
                serializable_employees[emp] = {
                    'employee': data['employee'],
                    'total_documents': data['total_documents'],
                    'num_projects': data['num_projects'],
                    'all_projects': data['all_projects'],
                    'primary_projects': data['primary_projects']
                }
            json.dump(serializable_employees, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved employee mapping to {employee_file}")

        # Save summary
        summary = {
            'total_projects': len(project_mapping),
            'total_employees': len(employee_mapping),
            'total_documents': sum(p['total_documents'] for p in project_mapping.values()),
            'avg_employees_per_project': sum(p['num_employees'] for p in project_mapping.values()) / len(project_mapping),
            'avg_projects_per_employee': sum(e['num_projects'] for e in employee_mapping.values()) / len(employee_mapping)
        }

        summary_file = output_path / "classification_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

        print(f"✓ Saved summary to {summary_file}")
        print(f"\n📊 Classification Summary:")
        print(f"  • Total Projects: {summary['total_projects']}")
        print(f"  • Total Employees: {summary['total_employees']}")
        print(f"  • Total Documents: {summary['total_documents']}")
        print(f"  • Avg Employees/Project: {summary['avg_employees_per_project']:.1f}")
        print(f"  • Avg Projects/Employee: {summary['avg_projects_per_employee']:.1f}")


if __name__ == "__main__":
    from config.config import Config

    # Example usage
    classifier = GlobalProjectClassifier(Config)

    # Load some documents (replace with actual data)
    # documents = load_all_documents()

    # Auto-detect categories
    # categories = classifier.auto_detect_project_categories(documents)

    # Classify all documents
    # classified_docs = classifier.classify_all_documents(documents)

    # Create mappings
    # project_mapping = classifier.create_project_employee_mapping(classified_docs)
    # employee_mapping = classifier.create_employee_project_mapping(classified_docs)

    # Save results
    # classifier.save_results(project_mapping, employee_mapping, str(Config.OUTPUT_DIR / "project_classification"))

    print("✓ Global Project Classifier initialized")
