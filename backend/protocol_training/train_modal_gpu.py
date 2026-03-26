"""
Modal GPU Training for Protocol Classification
===============================================
Uses Modal.com's serverless GPUs to train BERT-based models.
Free tier includes GPU hours - no AWS/local GPU needed.

Usage:
    modal run protocol_training.train_modal_gpu
"""

import modal
import os

# Create Modal app
app = modal.App("protocol-classifier-training")

# Define the training image with all dependencies
training_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch",
    "transformers",
    "sentence-transformers",
    "scikit-learn",
    "numpy",
    "accelerate",
    "datasets"
)

# Volume to persist model artifacts
model_volume = modal.Volume.from_name("protocol-models", create_if_missing=True)


@app.function(
    image=training_image,
    gpu="T4",  # NVIDIA T4 GPU (free tier eligible)
    timeout=3600,  # 1 hour max
    volumes={"/models": model_volume}
)
def train_domain_classifier(training_data: list, validation_data: list):
    """Train BERT-based domain classifier on GPU."""
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer
    )
    from sklearn.metrics import accuracy_score
    import numpy as np
    import json

    print("=" * 60)
    print("TRAINING DOMAIN CLASSIFIER ON MODAL GPU")
    print("=" * 60)

    # Check GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # Domain mappings
    TARGET_DOMAINS = ['plant_biology', 'oncology', 'neurology', 'biology']
    DOMAIN_TO_ID = {d: i for i, d in enumerate(TARGET_DOMAINS)}
    ID_TO_DOMAIN = {i: d for d, i in DOMAIN_TO_ID.items()}

    # Load model
    model_name = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"
    print(f"Loading model: {model_name}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=len(TARGET_DOMAINS),
            id2label=ID_TO_DOMAIN,
            label2id=DOMAIN_TO_ID
        )
    except Exception as e:
        print(f"PubMedBERT failed, using distilbert: {e}")
        model_name = "distilbert-base-uncased"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=len(TARGET_DOMAINS),
            id2label=ID_TO_DOMAIN,
            label2id=DOMAIN_TO_ID
        )

    model.to(device)
    print(f"Model loaded: {model_name}")

    # Prepare datasets
    class ProtocolDataset(torch.utils.data.Dataset):
        def __init__(self, data, tokenizer, max_length=512):
            self.data = data
            self.tokenizer = tokenizer
            self.max_length = max_length

        def __len__(self):
            return len(self.data)

        def __getitem__(self, idx):
            item = self.data[idx]
            encoding = self.tokenizer(
                item['text'],
                truncation=True,
                padding='max_length',
                max_length=self.max_length,
                return_tensors='pt'
            )
            return {
                'input_ids': encoding['input_ids'].squeeze(),
                'attention_mask': encoding['attention_mask'].squeeze(),
                'labels': torch.tensor(item['label'])
            }

    train_dataset = ProtocolDataset(training_data, tokenizer)
    val_dataset = ProtocolDataset(validation_data, tokenizer)

    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples: {len(val_dataset)}")

    # Training arguments
    training_args = TrainingArguments(
        output_dir="/models/domain_classifier",
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        warmup_steps=100,
        weight_decay=0.01,
        logging_steps=50,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        report_to="none",
        fp16=True,  # Mixed precision for faster training
    )

    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        return {'accuracy': accuracy_score(labels, predictions)}

    # Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    print("Starting training...")
    trainer.train()

    # Evaluate
    eval_results = trainer.evaluate()
    print(f"Evaluation results: {eval_results}")

    # Save model
    model_path = "/models/domain_classifier_final"
    model.save_pretrained(model_path)
    tokenizer.save_pretrained(model_path)
    print(f"Model saved to {model_path}")

    # Commit the volume
    model_volume.commit()

    # Test predictions
    print("\nSample predictions:")
    test_texts = [
        "Arabidopsis thaliana transformation using floral dip method",
        "Tumor cell line culture and chemotherapy drug screening",
        "Neuroimaging fMRI preprocessing with FSL and FreeSurfer",
        "General PCR protocol for DNA amplification"
    ]

    model.eval()
    for text in test_texts:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=1).item()
        pred_domain = ID_TO_DOMAIN[pred_id]
        print(f"  '{text[:50]}...' -> {pred_domain}")

    return {
        "accuracy": eval_results.get("eval_accuracy", 0),
        "model_path": model_path,
        "samples_trained": len(training_data)
    }


@app.function(
    image=training_image,
    gpu="T4",
    timeout=3600,
    volumes={"/models": model_volume}
)
def train_protocol_embeddings(training_pairs: list):
    """Fine-tune sentence embeddings for protocol similarity."""
    import torch
    from sentence_transformers import SentenceTransformer, InputExample, losses, evaluation
    from torch.utils.data import DataLoader
    import numpy as np

    print("=" * 60)
    print("TRAINING PROTOCOL EMBEDDINGS ON MODAL GPU")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    # Load base model
    model_name = "all-MiniLM-L6-v2"
    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name, device=device)

    # Convert to InputExamples
    train_examples = []
    val_examples = []

    split_idx = int(len(training_pairs) * 0.9)

    for i, pair in enumerate(training_pairs):
        example = InputExample(
            texts=[pair['text1'], pair['text2']],
            label=pair['similarity']
        )
        if i < split_idx:
            train_examples.append(example)
        else:
            val_examples.append(example)

    print(f"Train examples: {len(train_examples)}")
    print(f"Val examples: {len(val_examples)}")

    # DataLoader
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=32)

    # Loss
    train_loss = losses.CosineSimilarityLoss(model)

    # Evaluator
    val_sentences1 = [ex.texts[0] for ex in val_examples]
    val_sentences2 = [ex.texts[1] for ex in val_examples]
    val_scores = [ex.label for ex in val_examples]

    evaluator = evaluation.EmbeddingSimilarityEvaluator(
        val_sentences1, val_sentences2, val_scores,
        name='protocol-similarity'
    )

    # Train
    output_path = "/models/protocol_embeddings"
    print("Starting embedding training...")

    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        evaluator=evaluator,
        epochs=2,
        warmup_steps=100,
        output_path=output_path,
        show_progress_bar=True
    )

    print(f"Embeddings model saved to {output_path}")

    # Commit volume
    model_volume.commit()

    # Test embeddings
    print("\nTesting embedding similarity:")
    test_pairs = [
        ("Arabidopsis transformation protocol", "Plant cell transformation method"),
        ("Cancer cell line drug screening", "Tumor chemotherapy assay"),
        ("Plant DNA extraction", "Neuroimaging MRI analysis"),
    ]

    for text1, text2 in test_pairs:
        emb1 = model.encode(text1)
        emb2 = model.encode(text2)
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        print(f"  '{text1}' <-> '{text2}': {similarity:.3f}")

    return {
        "model_path": output_path,
        "pairs_trained": len(train_examples)
    }


@app.local_entrypoint()
def main():
    """Main entry point - runs locally, training runs on Modal GPU."""
    import json
    import os
    import random
    from collections import Counter

    print("=" * 70)
    print("MODAL GPU TRAINING FOR PROTOCOL MODELS")
    print("=" * 70)

    # Load protocol data
    corpus_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'protocol_corpus')
    corpus_file = os.path.join(corpus_dir, 'unified_protocols.jsonl')

    if not os.path.exists(corpus_file):
        print(f"ERROR: Corpus file not found: {corpus_file}")
        return

    protocols = []
    with open(corpus_file, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    protocols.append(json.loads(line))
                except:
                    continue

    print(f"Loaded {len(protocols)} protocols")

    # Domain distribution
    TARGET_DOMAINS = ['plant_biology', 'oncology', 'neurology', 'biology']
    DOMAIN_TO_ID = {d: i for i, d in enumerate(TARGET_DOMAINS)}

    domain_counts = Counter(p.get('domain', 'unknown') for p in protocols)
    print("Domain distribution:")
    for domain, count in domain_counts.most_common(10):
        print(f"  {domain}: {count}")

    # Prepare classification data
    classification_data = []
    for p in protocols:
        domain = p.get('domain', 'biology')
        if domain not in TARGET_DOMAINS:
            domain = 'biology'

        text = ""
        if p.get('title'):
            text += p['title'] + " "
        if p.get('abstract'):
            text += p['abstract'][:500] + " "
        if p.get('raw_text'):
            text += p['raw_text'][:1000]

        text = text.strip()
        if len(text) > 50:
            classification_data.append({
                'text': text[:1500],
                'label': DOMAIN_TO_ID[domain]
            })

    random.shuffle(classification_data)
    split_idx = int(len(classification_data) * 0.9)
    train_data = classification_data[:split_idx]
    val_data = classification_data[split_idx:]

    print(f"\nClassification: {len(train_data)} train, {len(val_data)} val")

    # Prepare similarity data
    domain_protocols = {}
    for p in protocols:
        domain = p.get('domain', 'biology')
        if domain not in domain_protocols:
            domain_protocols[domain] = []

        text = ""
        if p.get('title'):
            text += p['title'] + " "
        if p.get('raw_text'):
            text += p['raw_text'][:1000]

        if len(text) > 50:
            domain_protocols[domain].append(text[:1500])

    similarity_pairs = []
    domains = list(domain_protocols.keys())

    for domain in domains:
        protos = domain_protocols[domain]
        if len(protos) < 2:
            continue

        # Positive pairs (same domain)
        for i in range(min(len(protos) - 1, 200)):
            idx1, idx2 = random.sample(range(len(protos)), 2)
            similarity_pairs.append({
                'text1': protos[idx1],
                'text2': protos[idx2],
                'similarity': 0.8
            })

        # Negative pairs (different domain)
        other_domains = [d for d in domains if d != domain]
        for other in other_domains:
            other_protos = domain_protocols[other]
            for i in range(min(20, len(protos), len(other_protos))):
                similarity_pairs.append({
                    'text1': random.choice(protos),
                    'text2': random.choice(other_protos),
                    'similarity': 0.3
                })

    random.shuffle(similarity_pairs)
    print(f"Similarity pairs: {len(similarity_pairs)}")

    # Run training on Modal GPU
    print("\n" + "=" * 60)
    print("LAUNCHING GPU TRAINING ON MODAL...")
    print("=" * 60)

    # Train classifier
    print("\n[1/2] Training domain classifier...")
    classifier_result = train_domain_classifier.remote(train_data, val_data)
    print(f"Classifier result: {classifier_result}")

    # Train embeddings
    print("\n[2/2] Training protocol embeddings...")
    embeddings_result = train_protocol_embeddings.remote(similarity_pairs)
    print(f"Embeddings result: {embeddings_result}")

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE!")
    print("=" * 70)
    print(f"Classifier accuracy: {classifier_result.get('accuracy', 'N/A')}")
    print(f"Models saved to Modal volume: protocol-models")
    print("\nTo download models, run:")
    print("  modal volume get protocol-models /models .")


if __name__ == "__main__":
    main()
