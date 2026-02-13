"""
Classify Club Data as Work vs Personal
Run on sample of documents to demonstrate classification
"""

import json
from pathlib import Path
from classification.work_personal_classifier import WorkPersonalClassifier
from tqdm import tqdm

# Paths
CLUB_DATA_DIR = Path("/Users/rishitjain/Downloads/knowledgevault_backend/club_data")
OUTPUT_DIR = CLUB_DATA_DIR / "classified"
OPENAI_API_KEY = "os.getenv("OPENAI_API_KEY", "")"

def classify_club_documents():
    """Classify club documents and save results by employee"""

    print("="*80)
    print("WORK/PERSONAL CLASSIFICATION - CLUB DATA")
    print("="*80)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize classifier
    classifier = WorkPersonalClassifier(api_key=OPENAI_API_KEY)

    # Get top employees
    employee_clusters = CLUB_DATA_DIR / "employee_clusters"

    # Process top 3 employees (most active)
    employees_to_process = [
        ("rishi2205", 50),  # Sample 50 messages
        ("trsericyucla", 50),
        ("badrimishra7", 50)
    ]

    all_results = {}

    for employee, sample_size in employees_to_process:
        print(f"\n{'='*80}")
        print(f"Processing: {employee}")
        print("-"*80)

        employee_file = employee_clusters / f"{employee}.jsonl"

        if not employee_file.exists():
            print(f"  ⚠ File not found: {employee_file}")
            continue

        # Load documents (sample)
        documents = []
        with open(employee_file, 'r') as f:
            for i, line in enumerate(f):
                if i >= sample_size:
                    break
                doc = json.loads(line)
                # Only classify messages (not empty)
                if len(doc['content'].strip()) >= 30:
                    documents.append(doc)

        print(f"Loaded {len(documents)} documents for classification")

        if not documents:
            print(f"  ⚠ No documents to classify")
            continue

        # Classify
        classified_docs = classifier.classify_batch(documents, batch_delay=0.2)

        # Filter results
        keep_docs, remove_docs, review_docs = classifier.filter_documents(classified_docs)

        # Save employee-specific results
        employee_output = OUTPUT_DIR / employee
        employee_output.mkdir(parents=True, exist_ok=True)

        # Save categorized documents
        if keep_docs:
            with open(employee_output / "work.jsonl", 'w') as f:
                for doc in keep_docs:
                    f.write(json.dumps(doc) + '\n')

        if remove_docs:
            with open(employee_output / "personal.jsonl", 'w') as f:
                for doc in remove_docs:
                    f.write(json.dumps(doc) + '\n')

        if review_docs:
            with open(employee_output / "review.jsonl", 'w') as f:
                for doc in review_docs:
                    f.write(json.dumps(doc) + '\n')

        # Save summary
        summary = {
            'employee': employee,
            'total': len(documents),
            'work': len(keep_docs),
            'personal': len(remove_docs),
            'review': len(review_docs),
            'work_percentage': round(len(keep_docs) / len(documents) * 100, 1),
            'personal_percentage': round(len(remove_docs) / len(documents) * 100, 1)
        }

        all_results[employee] = summary

        with open(employee_output / "summary.json", 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n✓ Saved to {employee_output}")
        print(f"  Work: {len(keep_docs)} ({summary['work_percentage']}%)")
        print(f"  Personal: {len(remove_docs)} ({summary['personal_percentage']}%)")
        print(f"  Review: {len(review_docs)}")

    # Save overall summary
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print("-"*80)

    total_work = sum(r['work'] for r in all_results.values())
    total_personal = sum(r['personal'] for r in all_results.values())
    total_review = sum(r['review'] for r in all_results.values())
    total_all = sum(r['total'] for r in all_results.values())

    overall_summary = {
        'employees_processed': list(all_results.keys()),
        'total_documents': total_all,
        'work_documents': total_work,
        'personal_documents': total_personal,
        'review_documents': total_review,
        'work_percentage': round(total_work / total_all * 100, 1) if total_all > 0 else 0,
        'personal_percentage': round(total_personal / total_all * 100, 1) if total_all > 0 else 0,
        'employee_results': all_results
    }

    with open(OUTPUT_DIR / "overall_summary.json", 'w') as f:
        json.dump(overall_summary, f, indent=2)

    print(f"Total Documents: {total_all}")
    print(f"  Work: {total_work} ({overall_summary['work_percentage']}%)")
    print(f"  Personal: {total_personal} ({overall_summary['personal_percentage']}%)")
    print(f"  Review: {total_review}")

    print(f"\n✓ Classification complete!")
    print(f"✓ Results saved to: {OUTPUT_DIR}")

    return overall_summary


if __name__ == "__main__":
    classify_club_documents()
