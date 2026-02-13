"""
Global Project Classification Pipeline
1. Identify all employees in dataset
2. Classify projects globally across all documents
3. Map which employees worked on which projects
"""

import json
from pathlib import Path
from config.config import Config
from classification.global_project_classifier import GlobalProjectClassifier


def load_all_documents(data_dir: str) -> list:
    """
    Load all documents from employee clusters

    Args:
        data_dir: Directory containing employee JSONL files

    Returns:
        List of all documents with employee info
    """
    print("📂 Loading all documents from employee clusters...")

    data_path = Path(data_dir)
    all_documents = []
    employee_count = 0

    # Load from employee_clusters directory
    employee_clusters_dir = data_path / "employee_clusters"

    if not employee_clusters_dir.exists():
        print(f"⚠ Employee clusters directory not found: {employee_clusters_dir}")
        return []

    # Get all employee files
    employee_files = list(employee_clusters_dir.glob("*.jsonl"))
    print(f"Found {len(employee_files)} employee files")

    for emp_file in employee_files:
        employee = emp_file.stem

        # Skip statistics file
        if employee == 'employee_statistics':
            continue

        employee_count += 1

        # Load employee documents
        with open(emp_file, 'r', encoding='utf-8') as f:
            for line in f:
                doc = json.loads(line)
                # Ensure employee info is in metadata
                if 'from' not in doc['metadata']:
                    doc['metadata']['from'] = employee
                all_documents.append(doc)

    print(f"✓ Loaded {len(all_documents)} documents from {employee_count} employees")
    return all_documents


def run_global_classification(data_dir: str, output_dir: str):
    """
    Run complete global project classification pipeline

    Args:
        data_dir: Directory with employee data
        output_dir: Directory to save results
    """
    print("=" * 80)
    print("GLOBAL PROJECT CLASSIFICATION PIPELINE")
    print("=" * 80)

    # Step 1: Load all documents
    print("\n" + "=" * 80)
    print("STEP 1: Loading Documents")
    print("=" * 80)

    all_documents = load_all_documents(data_dir)

    if not all_documents:
        print("❌ No documents found. Please run the employee clustering first.")
        return

    # Get unique employees
    employees = set()
    for doc in all_documents:
        emp = doc['metadata'].get('from', 'Unknown')
        if emp != 'Unknown':
            employees.add(emp)

    print(f"\n✅ Dataset Overview:")
    print(f"   • Total Documents: {len(all_documents)}")
    print(f"   • Total Employees: {len(employees)}")
    print(f"   • Avg Docs/Employee: {len(all_documents) / len(employees):.1f}")

    # Step 2: Initialize classifier and detect project categories
    print("\n" + "=" * 80)
    print("STEP 2: Initializing Global Project Classifier")
    print("=" * 80)

    classifier = GlobalProjectClassifier(Config)

    # Auto-detect project categories from all documents
    print("\nAuto-detecting project categories...")
    categories = classifier.auto_detect_project_categories(
        all_documents,
        max_categories=15  # Adjust based on your needs
    )

    # Step 3: Classify all documents into projects
    print("\n" + "=" * 80)
    print("STEP 3: Classifying Documents into Projects")
    print("=" * 80)

    classified_documents = classifier.classify_all_documents(all_documents)

    # Step 4: Create project-employee mapping
    print("\n" + "=" * 80)
    print("STEP 4: Creating Project-Employee Mapping")
    print("=" * 80)

    project_mapping = classifier.create_project_employee_mapping(classified_documents)

    # Step 5: Create employee-project mapping
    print("\n" + "=" * 80)
    print("STEP 5: Creating Employee-Project Mapping")
    print("=" * 80)

    employee_mapping = classifier.create_employee_project_mapping(classified_documents)

    # Step 6: Save results
    print("\n" + "=" * 80)
    print("STEP 6: Saving Results")
    print("=" * 80)

    classifier.save_results(project_mapping, employee_mapping, output_dir)

    # Save classified documents
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save by project
    projects_dir = output_path / "projects"
    projects_dir.mkdir(exist_ok=True)

    for project_name, project_data in project_mapping.items():
        safe_name = project_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        project_file = projects_dir / f"{safe_name}.jsonl"

        with open(project_file, 'w', encoding='utf-8') as f:
            for doc in project_data['documents']:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        print(f"  ✓ Saved {project_name}: {len(project_data['documents'])} docs")

    # Save by employee
    employees_dir = output_path / "employees"
    employees_dir.mkdir(exist_ok=True)

    for employee_name, employee_data in employee_mapping.items():
        safe_name = employee_name.replace('/', '_').replace('\\', '_').replace('@', '_at_')
        employee_file = employees_dir / f"{safe_name}.jsonl"

        with open(employee_file, 'w', encoding='utf-8') as f:
            for doc in employee_data['documents']:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

    print(f"\n✓ Saved employee files to {employees_dir}")

    # Print final summary
    print("\n" + "=" * 80)
    print("✅ CLASSIFICATION COMPLETE!")
    print("=" * 80)

    print(f"\n📊 Results saved to: {output_path}")
    print(f"\n📁 Directory structure:")
    print(f"   {output_path}/")
    print(f"   ├── project_mapping.json       # Projects → Employees")
    print(f"   ├── employee_mapping.json      # Employees → Projects")
    print(f"   ├── classification_summary.json")
    print(f"   ├── projects/                  # Documents by project")
    print(f"   │   ├── project_1.jsonl")
    print(f"   │   └── ...")
    print(f"   └── employees/                 # Documents by employee")
    print(f"       ├── employee_1.jsonl")
    print(f"       └── ...")

    print("\n💡 Next Steps:")
    print("   1. Review project_mapping.json to see all projects and their employees")
    print("   2. Review employee_mapping.json to see which projects each employee worked on")
    print("   3. Use the frontend to visualize the results")

    return project_mapping, employee_mapping


if __name__ == "__main__":
    import sys

    # Determine which dataset to use
    if len(sys.argv) > 1 and sys.argv[1] == "club":
        print("🎯 Using CLUB dataset")
        data_dir = str(Config.DATA_DIR)
        output_dir = str(Config.OUTPUT_DIR / "club_project_classification")
    else:
        print("🎯 Using default dataset")
        data_dir = str(Config.DATA_DIR)
        output_dir = str(Config.OUTPUT_DIR / "global_project_classification")

    # Run the pipeline
    run_global_classification(data_dir, output_dir)
