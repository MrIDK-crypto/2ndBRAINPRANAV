"""
Project Classification Module using DistilBERT
Classifies documents into project categories using DistilBERT
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
from transformers import (
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    Trainer,
    TrainingArguments
)
from torch.utils.data import Dataset
import warnings
warnings.filterwarnings('ignore')


class ProjectDataset(Dataset):
    """Custom dataset for project classification"""

    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors='pt'
        )
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item


class DistilBERTProjectClassifier:
    """Classify documents into projects using DistilBERT"""

    def __init__(self, config):
        """
        Initialize DistilBERT classifier

        Args:
            config: Configuration object
        """
        self.config = config
        self.tokenizer = None
        self.model = None
        self.label_to_id = {}
        self.id_to_label = {}
        self.is_trained = False

        print("Initializing DistilBERT Project Classifier...")
        self._initialize_model()

    def _initialize_model(self):
        """Initialize DistilBERT model and tokenizer"""
        print("Loading DistilBERT tokenizer and model...")

        # Load tokenizer
        self.tokenizer = DistilBertTokenizer.from_pretrained(
            self.config.CLASSIFICATION_MODEL
        )

        # Model will be initialized when we know number of classes
        print("✓ Tokenizer loaded")

    def _create_model(self, num_labels: int):
        """Create classification model with specified number of labels"""
        self.model = DistilBertForSequenceClassification.from_pretrained(
            self.config.CLASSIFICATION_MODEL,
            num_labels=num_labels
        )
        print(f"✓ Model created with {num_labels} labels")

    def prepare_training_data(
        self,
        documents: List[Dict],
        project_labels: List[str]
    ) -> Tuple[List[str], List[int]]:
        """
        Prepare documents for training

        Args:
            documents: List of document dictionaries
            project_labels: List of project labels for each document

        Returns:
            Tuple of (texts, encoded_labels)
        """
        # Extract texts
        texts = []
        for doc in documents:
            subject = doc['metadata'].get('subject', '')
            content = doc['content'][:1000]  # Limit content length
            # Combine subject and content
            text = f"{subject} {content}"
            texts.append(text)

        # Create label mappings
        unique_labels = sorted(set(project_labels))
        self.label_to_id = {label: idx for idx, label in enumerate(unique_labels)}
        self.id_to_label = {idx: label for label, idx in self.label_to_id.items()}

        # Encode labels
        encoded_labels = [self.label_to_id[label] for label in project_labels]

        return texts, encoded_labels

    def train(
        self,
        documents: List[Dict],
        project_labels: List[str],
        output_dir: Optional[str] = None,
        epochs: int = 3,
        batch_size: int = 8
    ):
        """
        Train the classifier on labeled documents

        Args:
            documents: List of document dictionaries
            project_labels: List of project labels for each document
            output_dir: Directory to save trained model
            epochs: Number of training epochs
            batch_size: Training batch size
        """
        print(f"\nTraining DistilBERT classifier on {len(documents)} documents...")

        # Prepare data
        texts, encoded_labels = self.prepare_training_data(documents, project_labels)

        # Create model with correct number of labels
        num_labels = len(self.label_to_id)
        self._create_model(num_labels)

        # Create dataset
        dataset = ProjectDataset(texts, encoded_labels, self.tokenizer)

        # Set up training arguments
        if output_dir is None:
            output_dir = str(self.config.MODELS_DIR / "project_classifier")

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            warmup_steps=100,
            weight_decay=0.01,
            logging_dir=f"{output_dir}/logs",
            logging_steps=10,
            save_strategy="epoch",
            evaluation_strategy="no",
            load_best_model_at_end=False,
        )

        # Create trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset,
        )

        # Train
        print("Training...")
        trainer.train()

        # Save model and mappings
        self.save_model(output_dir)

        self.is_trained = True
        print(f"✓ Training complete! Model saved to {output_dir}")

    def predict(self, documents: List[Dict]) -> List[Tuple[str, float]]:
        """
        Predict project labels for documents

        Args:
            documents: List of document dictionaries

        Returns:
            List of (predicted_label, confidence) tuples
        """
        if not self.is_trained and self.model is None:
            raise ValueError("Model not trained. Call train() first or load a trained model.")

        # Prepare texts
        texts = []
        for doc in documents:
            subject = doc['metadata'].get('subject', '')
            content = doc['content'][:1000]
            text = f"{subject} {content}"
            texts.append(text)

        # Tokenize
        encodings = self.tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors='pt'
        )

        # Predict
        self.model.eval()
        with torch.no_grad():
            outputs = self.model(**encodings)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)
            predicted_classes = torch.argmax(probs, dim=-1)
            confidences = torch.max(probs, dim=-1).values

        # Convert to labels
        results = []
        for pred_class, confidence in zip(predicted_classes, confidences):
            label = self.id_to_label[pred_class.item()]
            results.append((label, confidence.item()))

        return results

    def classify_batch(self, documents: List[Dict]) -> List[Dict]:
        """
        Classify a batch of documents and add classification to metadata

        Args:
            documents: List of document dictionaries

        Returns:
            Documents with classification added
        """
        predictions = self.predict(documents)

        for doc, (label, confidence) in zip(documents, predictions):
            doc['project_classification'] = label
            doc['classification_confidence'] = confidence

        return documents

    def save_model(self, output_dir: str):
        """Save model and label mappings"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save model and tokenizer
        self.model.save_pretrained(str(output_path))
        self.tokenizer.save_pretrained(str(output_path))

        # Save label mappings
        mappings = {
            'label_to_id': self.label_to_id,
            'id_to_label': self.id_to_label
        }

        with open(output_path / 'label_mappings.json', 'w') as f:
            json.dump(mappings, f, indent=2)

        print(f"✓ Model saved to {output_path}")

    def load_model(self, model_dir: str):
        """Load trained model and label mappings"""
        model_path = Path(model_dir)

        if not model_path.exists():
            raise ValueError(f"Model directory not found: {model_dir}")

        print(f"Loading model from {model_path}...")

        # Load tokenizer
        self.tokenizer = DistilBertTokenizer.from_pretrained(str(model_path))

        # Load model
        self.model = DistilBertForSequenceClassification.from_pretrained(str(model_path))

        # Load label mappings
        with open(model_path / 'label_mappings.json', 'r') as f:
            mappings = json.load(f)
            self.label_to_id = mappings['label_to_id']
            # Convert string keys back to integers
            self.id_to_label = {int(k): v for k, v in mappings['id_to_label'].items()}

        self.is_trained = True
        print(f"✓ Model loaded with {len(self.label_to_id)} labels")


class ProjectClassifierTrainer:
    """Helper class to train project classifier from clustered data"""

    @staticmethod
    def prepare_training_data_from_clusters(
        project_clusters_dir: str
    ) -> Tuple[List[Dict], List[str]]:
        """
        Prepare training data from project cluster directories

        Args:
            project_clusters_dir: Directory with employee project clusters

        Returns:
            Tuple of (documents, labels)
        """
        clusters_path = Path(project_clusters_dir)
        documents = []
        labels = []

        print(f"Loading training data from {clusters_path}...")

        # Iterate through employee directories
        for employee_dir in clusters_path.iterdir():
            if not employee_dir.is_dir():
                continue

            employee = employee_dir.name
            print(f"  Loading {employee}...")

            # Iterate through project files
            for project_file in employee_dir.glob("*.jsonl"):
                if project_file.name == "outliers.jsonl":
                    continue

                project_name = project_file.stem

                # Load documents
                with open(project_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        doc = json.loads(line)
                        documents.append(doc)
                        labels.append(project_name)

        print(f"✓ Loaded {len(documents)} documents from {len(set(labels))} projects")
        return documents, labels


if __name__ == "__main__":
    from config.config import Config

    # Example: Train classifier from existing clusters
    trainer = ProjectClassifierTrainer()
    documents, labels = trainer.prepare_training_data_from_clusters(
        str(Config.DATA_DIR / "project_clusters")
    )

    # Train classifier
    classifier = DistilBERTProjectClassifier(Config)
    classifier.train(
        documents=documents,
        project_labels=labels,
        epochs=3,
        batch_size=8
    )

    print("\n✓ Project classifier trained and saved!")
