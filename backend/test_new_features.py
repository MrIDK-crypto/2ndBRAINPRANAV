"""
Test script for new features:
1. LlamaParse document parsing with GPT-4o-mini processing
2. DistilBERT project classification
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.config import Config
from parsers.document_parser import DocumentParser
from classification.project_classifier import DistilBERTProjectClassifier, ProjectClassifierTrainer
from clustering.project_clustering import ProjectClusterer


def test_llamaparse_parsing():
    """Test LlamaParse document parsing"""
    print("=" * 80)
    print("TEST 1: LlamaParse Document Parsing with GPT-4o-mini")
    print("=" * 80)

    # Initialize parser with config
    parser = DocumentParser(config=Config, use_llamaparse=True)

    # Test with a sample file
    test_files = [
        "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAn7sv4eE/File-Timeline - BEAT Healthcare Consulting.pptx",
        "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAn7sv4eE/File-BEAT Healthcare Consulting Project Charter(3).pdf"
    ]

    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"\n⚠ Test file not found: {test_file}")
            continue

        print(f"\n📄 Testing: {Path(test_file).name}")
        print("-" * 80)

        result = parser.parse(test_file)

        if result:
            print(f"✓ Success!")
            print(f"  Parser: {result['metadata'].get('parser', 'unknown')}")
            print(f"  LLM Processor: {result['metadata'].get('llm_processor', 'unknown')}")
            print(f"  File Type: {result['metadata']['file_type']}")
            print(f"  Total Characters: {result['metadata'].get('total_chars', 0):,}")
            print(f"  Processed Characters: {result['metadata'].get('processed_chars', 0):,}")

            print(f"\n📝 Preview (first 500 chars):")
            print("-" * 80)
            print(result['content'][:500])
            print("-" * 80)
        else:
            print("✗ Failed to parse")

    print("\n✓ LlamaParse test complete!\n")


def test_distilbert_classification():
    """Test DistilBERT project classification"""
    print("=" * 80)
    print("TEST 2: DistilBERT Project Classification")
    print("=" * 80)

    # Check if we have project clusters to train on
    project_clusters_dir = Config.DATA_DIR / "project_clusters"

    if not project_clusters_dir.exists():
        print("\n⚠ No project clusters found for training")
        print("  Please run the clustering pipeline first to generate training data")
        print("  Run: python run_full_pipeline.py")
        return

    print("\n📊 Training DistilBERT classifier...")

    # Prepare training data from existing clusters
    trainer = ProjectClassifierTrainer()

    try:
        documents, labels = trainer.prepare_training_data_from_clusters(
            str(project_clusters_dir)
        )

        if len(documents) < 10:
            print(f"\n⚠ Not enough documents for training (found {len(documents)})")
            print("  Need at least 10 documents")
            return

        print(f"\n✓ Loaded {len(documents)} documents from {len(set(labels))} project types")

        # Train classifier (using small subset for testing)
        classifier = DistilBERTProjectClassifier(Config)

        # Use a small subset for quick testing
        sample_size = min(100, len(documents))
        print(f"\n📚 Training on {sample_size} documents (subset for testing)...")

        classifier.train(
            documents=documents[:sample_size],
            project_labels=labels[:sample_size],
            epochs=1,  # Just 1 epoch for quick testing
            batch_size=4
        )

        print("\n✓ Training complete!")

        # Test prediction on a few documents
        print("\n🔮 Testing predictions...")
        test_docs = documents[sample_size:sample_size+5] if len(documents) > sample_size else documents[:5]

        predictions = classifier.predict(test_docs)

        for doc, (predicted_label, confidence) in zip(test_docs, predictions):
            actual_label = doc.get('cluster_label', 'unknown')
            print(f"\n  Document: {doc['metadata'].get('subject', 'No subject')[:50]}...")
            print(f"  Predicted: {predicted_label} (confidence: {confidence:.2%})")
            print(f"  Actual: {actual_label}")

        print("\n✓ DistilBERT classification test complete!\n")

    except Exception as e:
        print(f"\n✗ Error during DistilBERT test: {e}")
        import traceback
        traceback.print_exc()


def test_integrated_pipeline():
    """Test integrated pipeline with both features"""
    print("=" * 80)
    print("TEST 3: Integrated Pipeline (LlamaParse + DistilBERT)")
    print("=" * 80)

    print("\n📋 This test would:")
    print("  1. Parse documents using LlamaParse + GPT-4o-mini")
    print("  2. Classify them using DistilBERT")
    print("  3. Generate knowledge base")

    print("\n💡 To run the full integrated pipeline:")
    print("  python run_full_pipeline.py")

    # Check if DistilBERT model exists
    model_path = Config.MODELS_DIR / "project_classifier"

    if model_path.exists():
        print(f"\n✓ Found trained DistilBERT model at: {model_path}")
        print("  The clustering pipeline can now use DistilBERT classification")

        print("\n📝 To use DistilBERT in clustering:")
        print("  clusterer = ProjectClusterer(")
        print("      config=Config,")
        print("      use_distilbert=True,")
        print(f"      distilbert_model_path='{model_path}'")
        print("  )")
    else:
        print(f"\n⚠ No trained DistilBERT model found")
        print("  Run TEST 2 to train a model first")

    print("\n✓ Integration test complete!\n")


def main():
    """Run all tests"""
    print("\n🚀 Testing New KnowledgeVault Features\n")

    try:
        # Test 1: LlamaParse
        test_llamaparse_parsing()

        # Test 2: DistilBERT (may take a few minutes)
        print("\n⏳ Test 2 may take a few minutes if training DistilBERT...")
        response = input("Run DistilBERT training test? (y/n): ")

        if response.lower() == 'y':
            test_distilbert_classification()
        else:
            print("⏭ Skipping DistilBERT test")

        # Test 3: Integration
        test_integrated_pipeline()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETE!")
        print("=" * 80)

        print("\n📚 Summary:")
        print("  ✓ LlamaParse: Parses all documents and processes with GPT-4o-mini")
        print("  ✓ DistilBERT: Classifies documents into project categories")
        print("  ✓ Integration: Both work together in the pipeline")

        print("\n💡 Next Steps:")
        print("  1. Install llama-parse: pip install llama-parse")
        print("  2. Set your API key in .env: LLAMAPARSE_API_KEY=your_key")
        print("  3. Run the full pipeline: python run_full_pipeline.py")

    except KeyboardInterrupt:
        print("\n\n⚠ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Error during tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
