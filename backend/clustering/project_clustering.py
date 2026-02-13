"""
Project-Based Clustering Module using BERTopic or DistilBERT
Clusters employee documents into projects using semantic clustering
Optionally uses DistilBERT for supervised classification
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Try to import DistilBERT classifier
try:
    from classification.project_classifier import DistilBERTProjectClassifier
    HAS_DISTILBERT = True
except ImportError:
    HAS_DISTILBERT = False


class ProjectClusterer:
    """Cluster employee documents into projects using BERTopic or DistilBERT"""

    def __init__(self, config, use_distilbert=False, distilbert_model_path=None):
        """
        Initialize ProjectClusterer

        Args:
            config: Configuration object with clustering parameters
            use_distilbert: Whether to use DistilBERT for classification
            distilbert_model_path: Path to trained DistilBERT model (if using)
        """
        self.config = config
        self.embedding_model = None
        self.topic_model = None
        self.distilbert_classifier = None
        self.use_distilbert = use_distilbert and HAS_DISTILBERT
        self.employee_projects = {}

        # Initialize DistilBERT if requested
        if self.use_distilbert:
            if distilbert_model_path:
                print("Loading DistilBERT classifier for project classification...")
                self.distilbert_classifier = DistilBERTProjectClassifier(config)
                self.distilbert_classifier.load_model(distilbert_model_path)
                print("✓ Using DistilBERT for project classification")
            else:
                print("⚠ DistilBERT requested but no model path provided")
                print("  Falling back to BERTopic clustering")
                self.use_distilbert = False

    def _initialize_embedding_model(self):
        """Initialize sentence transformer embedding model"""
        print(f"Loading embedding model: {self.config.EMBEDDING_MODEL}...")
        self.embedding_model = SentenceTransformer(self.config.EMBEDDING_MODEL)
        print("✓ Embedding model loaded")

    def _initialize_topic_model(self):
        """Initialize BERTopic model with UMAP and HDBSCAN"""

        # UMAP for dimensionality reduction
        umap_model = UMAP(
            n_neighbors=self.config.UMAP_N_NEIGHBORS,
            n_components=self.config.UMAP_N_COMPONENTS,
            metric=self.config.UMAP_METRIC,
            random_state=42
        )

        # HDBSCAN for clustering
        hdbscan_model = HDBSCAN(
            min_cluster_size=self.config.MIN_CLUSTER_SIZE,
            min_samples=self.config.MIN_SAMPLES,
            metric='euclidean',
            prediction_data=True
        )

        # CountVectorizer for topic representation
        vectorizer_model = CountVectorizer(
            stop_words='english',
            min_df=2,
            ngram_range=(1, 2)
        )

        # Initialize BERTopic
        self.topic_model = BERTopic(
            embedding_model=self.embedding_model,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer_model,
            top_n_words=10,
            verbose=True,
            calculate_probabilities=False  # Faster without probabilities
        )

        print("✓ BERTopic model initialized")

    def prepare_documents_for_clustering(self, documents: List[Dict]) -> Tuple[List[str], List[Dict]]:
        """
        Prepare documents for clustering by creating text representations

        Args:
            documents: List of document dictionaries

        Returns:
            Tuple of (text_list, metadata_list)
        """
        texts = []
        metadata = []

        for doc in documents:
            # Combine subject and content for better clustering
            subject = doc['metadata'].get('subject', '')
            content = doc['content']

            # Create enriched text: weight subject more heavily
            enriched_text = f"{subject} {subject} {content}"

            texts.append(enriched_text)
            metadata.append(doc)

        return texts, metadata

    def cluster_employee_documents(
        self,
        employee: str,
        documents: List[Dict],
        min_docs_for_clustering: int = 10
    ) -> Dict:
        """
        Cluster documents for a single employee into projects
        Uses DistilBERT if available, otherwise BERTopic

        Args:
            employee: Employee name
            documents: List of employee's documents
            min_docs_for_clustering: Minimum documents needed for clustering

        Returns:
            Dictionary with clustering results
        """
        print(f"\nClustering documents for {employee} ({len(documents)} docs)...")

        # Check if enough documents for meaningful clustering
        if len(documents) < min_docs_for_clustering:
            print(f"  ⚠ Only {len(documents)} documents - creating single cluster")
            return self._create_single_cluster(employee, documents)

        # Use DistilBERT classifier if available
        if self.use_distilbert and self.distilbert_classifier:
            return self._classify_with_distilbert(employee, documents)

        # Otherwise use BERTopic clustering
        # Prepare documents
        texts, doc_metadata = self.prepare_documents_for_clustering(documents)

        # Initialize models if needed
        if self.embedding_model is None:
            self._initialize_embedding_model()
        if self.topic_model is None:
            self._initialize_topic_model()

        try:
            # Fit BERTopic model
            topics, probs = self.topic_model.fit_transform(texts)

            # Get topic info
            topic_info = self.topic_model.get_topic_info()

            # Organize documents by topic/project
            projects = defaultdict(list)
            topic_labels = {}

            for idx, (topic_id, doc) in enumerate(zip(topics, doc_metadata)):
                # Get topic label
                if topic_id not in topic_labels:
                    topic_label = self._generate_topic_label(topic_id, topic_info)
                    topic_labels[topic_id] = topic_label

                # Add cluster metadata to document
                doc['cluster_id'] = f"{employee}::project_{topic_id}"
                doc['cluster_label'] = topic_labels[topic_id]
                doc['cluster_type'] = 'project'

                projects[topic_id].append(doc)

            # Create result structure
            result = {
                'employee': employee,
                'total_documents': len(documents),
                'num_projects': len(projects) - (1 if -1 in projects else 0),  # Exclude outliers
                'projects': {},
                'outliers': [],
            }

            # Organize projects
            for topic_id, docs in projects.items():
                if topic_id == -1:
                    # Outliers (noise)
                    result['outliers'] = docs
                else:
                    project_name = topic_labels[topic_id]
                    result['projects'][project_name] = {
                        'cluster_id': f"{employee}::project_{topic_id}",
                        'topic_id': topic_id,
                        'document_count': len(docs),
                        'documents': docs,
                        'keywords': self._get_topic_keywords(topic_id),
                    }

            print(f"  ✓ Found {result['num_projects']} projects, {len(result['outliers'])} outliers")

            return result

        except Exception as e:
            print(f"  ✗ Clustering failed: {e}")
            return self._create_single_cluster(employee, documents)

    def _classify_with_distilbert(self, employee: str, documents: List[Dict]) -> Dict:
        """
        Classify documents using DistilBERT classifier

        Args:
            employee: Employee name
            documents: List of documents to classify

        Returns:
            Dictionary with classification results
        """
        print(f"  Using DistilBERT for classification...")

        # Classify documents
        classified_docs = self.distilbert_classifier.classify_batch(documents)

        # Organize by predicted project
        projects = defaultdict(list)

        for doc in classified_docs:
            project_label = doc.get('project_classification', 'unknown')
            confidence = doc.get('classification_confidence', 0.0)

            # Add cluster metadata
            doc['cluster_id'] = f"{employee}::{project_label}"
            doc['cluster_label'] = project_label
            doc['cluster_type'] = 'project_classified'
            doc['cluster_confidence'] = confidence

            projects[project_label].append(doc)

        # Create result structure
        result = {
            'employee': employee,
            'total_documents': len(documents),
            'num_projects': len(projects),
            'projects': {},
            'outliers': [],
        }

        # Organize projects
        for idx, (project_name, docs) in enumerate(projects.items()):
            result['projects'][project_name] = {
                'cluster_id': f"{employee}::{project_name}",
                'topic_id': idx,
                'document_count': len(docs),
                'documents': docs,
                'keywords': [],
                'avg_confidence': sum(d['cluster_confidence'] for d in docs) / len(docs)
            }

        print(f"  ✓ Classified into {result['num_projects']} projects (DistilBERT)")

        return result

    def _create_single_cluster(self, employee: str, documents: List[Dict]) -> Dict:
        """Create a single cluster for employees with few documents"""
        for doc in documents:
            doc['cluster_id'] = f"{employee}::project_0"
            doc['cluster_label'] = f"{employee}_general"
            doc['cluster_type'] = 'project'

        return {
            'employee': employee,
            'total_documents': len(documents),
            'num_projects': 1,
            'projects': {
                f"{employee}_general": {
                    'cluster_id': f"{employee}::project_0",
                    'topic_id': 0,
                    'document_count': len(documents),
                    'documents': documents,
                    'keywords': [],
                }
            },
            'outliers': [],
        }

    def _generate_topic_label(self, topic_id: int, topic_info: pd.DataFrame) -> str:
        """Generate human-readable label for topic/project"""
        if topic_id == -1:
            return "outliers"

        # Get topic keywords
        topic_row = topic_info[topic_info['Topic'] == topic_id]
        if not topic_row.empty:
            # Get top keywords and create label
            keywords = topic_row['Name'].values[0]
            # Remove topic number prefix from BERTopic
            label = keywords.split('_', 1)[1] if '_' in keywords else keywords
            # Clean up and limit length
            label = label.replace('_', ' ').strip()[:50]
            return f"project_{topic_id}_{label}"

        return f"project_{topic_id}"

    def _get_topic_keywords(self, topic_id: int) -> List[str]:
        """Get keywords for a topic"""
        if topic_id == -1:
            return []

        try:
            topic = self.topic_model.get_topic(topic_id)
            if topic:
                return [word for word, _ in topic[:10]]
        except:
            pass

        return []

    def cluster_all_employees(
        self,
        employee_clusters_dir: str,
        output_dir: str
    ) -> Dict[str, Dict]:
        """
        Cluster documents for all employees

        Args:
            employee_clusters_dir: Directory with employee JSONL files
            output_dir: Directory to save project clusters

        Returns:
            Dictionary with all employee project clusters
        """
        employee_dir = Path(employee_clusters_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        all_results = {}

        # Get all employee files
        employee_files = list(employee_dir.glob("*.jsonl"))
        print(f"\nFound {len(employee_files)} employee files")

        for emp_file in employee_files:
            employee = emp_file.stem

            # Skip statistics file
            if employee == 'employee_statistics':
                continue

            # Load employee documents
            documents = []
            with open(emp_file, 'r', encoding='utf-8') as f:
                for line in f:
                    documents.append(json.loads(line))

            # Cluster employee documents
            result = self.cluster_employee_documents(employee, documents)
            all_results[employee] = result

            # Save employee project clusters
            self._save_employee_projects(employee, result, output_path)

        # Save summary
        self._save_clustering_summary(all_results, output_path)

        print(f"\n✓ Completed project clustering for {len(all_results)} employees")
        return all_results

    def _save_employee_projects(self, employee: str, result: Dict, output_dir: Path):
        """Save employee project clusters to files"""
        employee_dir = output_dir / employee
        employee_dir.mkdir(parents=True, exist_ok=True)

        # Save each project
        for project_name, project_data in result['projects'].items():
            safe_name = project_name.replace('/', '_').replace('\\', '_')
            project_file = employee_dir / f"{safe_name}.jsonl"

            with open(project_file, 'w', encoding='utf-8') as f:
                for doc in project_data['documents']:
                    f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        # Save outliers if any
        if result['outliers']:
            outliers_file = employee_dir / "outliers.jsonl"
            with open(outliers_file, 'w', encoding='utf-8') as f:
                for doc in result['outliers']:
                    f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        # Save metadata
        metadata = {
            'employee': employee,
            'total_documents': result['total_documents'],
            'num_projects': result['num_projects'],
            'projects': {
                name: {
                    'cluster_id': data['cluster_id'],
                    'document_count': data['document_count'],
                    'keywords': data['keywords'],
                }
                for name, data in result['projects'].items()
            },
            'outlier_count': len(result['outliers']),
        }

        metadata_file = employee_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _save_clustering_summary(self, all_results: Dict, output_dir: Path):
        """Save overall clustering summary"""
        summary = {
            'total_employees': len(all_results),
            'total_projects': sum(r['num_projects'] for r in all_results.values()),
            'total_documents': sum(r['total_documents'] for r in all_results.values()),
            'employees': {}
        }

        for employee, result in all_results.items():
            summary['employees'][employee] = {
                'total_documents': result['total_documents'],
                'num_projects': result['num_projects'],
                'outlier_count': len(result['outliers']),
            }

        summary_file = output_dir / "project_clustering_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Saved clustering summary to {summary_file}")


if __name__ == "__main__":
    from config.config import Config

    clusterer = ProjectClusterer(Config)

    results = clusterer.cluster_all_employees(
        employee_clusters_dir=str(Config.DATA_DIR / "employee_clusters"),
        output_dir=str(Config.DATA_DIR / "project_clusters")
    )
