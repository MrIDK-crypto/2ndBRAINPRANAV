"""
Simple Project Mapping for Existing Data
Uses existing employee clusters to create project-employee mappings
"""

import json
from pathlib import Path
from collections import defaultdict
from config.config import Config


def create_simple_mappings():
    """Create simple project-employee mappings from existing data"""

    print("=" * 80)
    print("SIMPLE PROJECT-EMPLOYEE MAPPING")
    print("=" * 80)

    # Load from employee clusters
    employee_clusters_dir = Config.DATA_DIR / "employee_clusters"
    output_dir = Config.OUTPUT_DIR / "club_project_classification"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_documents = []
    employees = set()

    print("\n📂 Loading employee data...")

    # Load all employee files
    employee_files = list(employee_clusters_dir.glob("*.jsonl"))

    for emp_file in employee_files:
        if emp_file.stem == 'employee_statistics':
            continue

        employee = emp_file.stem
        employees.add(employee)

        with open(emp_file, 'r') as f:
            for line in f:
                doc = json.loads(line)
                doc['employee'] = employee
                all_documents.append(doc)

    print(f"✓ Loaded {len(all_documents):,} documents from {len(employees)} employees")

    # Extract project info from subject lines
    print("\n📊 Extracting projects from subject lines...")

    projects = defaultdict(lambda: {
        'employees': set(),
        'documents': [],
        'employee_contributions': defaultdict(int)
    })

    employee_projects = defaultdict(lambda: defaultdict(int))

    for doc in all_documents:
        subject = doc['metadata'].get('subject', 'General')
        employee = doc.get('employee', 'Unknown')

        # Simple project extraction from subject
        # Remove Re:, Fwd:, etc.
        clean_subject = subject.replace('Re:', '').replace('Fwd:', '').replace('RE:', '').replace('FW:', '').strip()

        # Take first 3-4 words as project name
        words = clean_subject.split()[:4]
        project_name = ' '.join(words) if words else 'General Communication'

        # Add to mappings
        projects[project_name]['employees'].add(employee)
        projects[project_name]['documents'].append(doc)
        projects[project_name]['employee_contributions'][employee] += 1

        employee_projects[employee][project_name] += 1

    print(f"✓ Identified {len(projects)} unique project topics")

    # Create project mapping
    print("\n🗺️  Creating project-employee mapping...")

    project_mapping = {}
    for proj_name, data in projects.items():
        project_mapping[proj_name] = {
            'project_name': proj_name,
            'total_documents': len(data['documents']),
            'num_employees': len(data['employees']),
            'employees': list(data['employees']),
            'employee_contributions': dict(data['employee_contributions']),
            'avg_confidence': 1.0  # Perfect confidence for exact matches
        }

    # Create employee mapping
    print("👥 Creating employee-project mapping...")

    employee_mapping = {}
    for emp_name, emp_projects in employee_projects.items():
        total_docs = sum(emp_projects.values())
        threshold = total_docs * 0.1

        primary_projects = {
            proj: count
            for proj, count in emp_projects.items()
            if count >= threshold
        }

        employee_mapping[emp_name] = {
            'employee': emp_name,
            'total_documents': total_docs,
            'num_projects': len(emp_projects),
            'all_projects': dict(emp_projects),
            'primary_projects': primary_projects
        }

    # Save results
    print("\n💾 Saving results...")

    # Save project mapping
    with open(output_dir / 'project_mapping.json', 'w') as f:
        json.dump(project_mapping, f, indent=2)
    print(f"✓ Saved project mapping")

    # Save employee mapping
    with open(output_dir / 'employee_mapping.json', 'w') as f:
        json.dump(employee_mapping, f, indent=2)
    print(f"✓ Saved employee mapping")

    # Save summary
    summary = {
        'total_projects': len(project_mapping),
        'total_employees': len(employee_mapping),
        'total_documents': len(all_documents),
        'avg_employees_per_project': sum(p['num_employees'] for p in project_mapping.values()) / len(project_mapping),
        'avg_projects_per_employee': sum(e['num_projects'] for e in employee_mapping.values()) / len(employee_mapping)
    }

    with open(output_dir / 'classification_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved summary")

    # Save documents by project
    projects_dir = output_dir / "projects"
    projects_dir.mkdir(exist_ok=True)

    for proj_name, data in projects.items():
        safe_name = proj_name.replace('/', '_').replace('\\', '_').replace(' ', '_')[:50]
        with open(projects_dir / f"{safe_name}.jsonl", 'w') as f:
            for doc in data['documents']:
                f.write(json.dumps(doc) + '\n')

    print(f"✓ Saved {len(projects)} project files")

    # Save documents by employee
    employees_dir = output_dir / "employees"
    employees_dir.mkdir(exist_ok=True)

    employee_docs = defaultdict(list)
    for doc in all_documents:
        employee_docs[doc['employee']].append(doc)

    for emp_name, docs in employee_docs.items():
        safe_name = emp_name.replace('/', '_').replace('\\', '_').replace('@', '_at_')
        with open(employees_dir / f"{safe_name}.jsonl", 'w') as f:
            for doc in docs:
                f.write(json.dumps(doc) + '\n')

    print(f"✓ Saved {len(employee_docs)} employee files")

    # Print summary
    print("\n" + "=" * 80)
    print("✅ MAPPING COMPLETE!")
    print("=" * 80)

    print(f"\n📊 Summary:")
    print(f"  • Total Projects: {summary['total_projects']:,}")
    print(f"  • Total Employees: {summary['total_employees']:,}")
    print(f"  • Total Documents: {summary['total_documents']:,}")
    print(f"  • Avg Employees/Project: {summary['avg_employees_per_project']:.1f}")
    print(f"  • Avg Projects/Employee: {summary['avg_projects_per_employee']:.1f}")

    print(f"\n📁 Results saved to: {output_dir}")

    # Show top projects
    print(f"\n🔝 Top 10 Projects by Document Count:")
    sorted_projects = sorted(
        project_mapping.items(),
        key=lambda x: x[1]['total_documents'],
        reverse=True
    )[:10]

    for i, (proj_name, data) in enumerate(sorted_projects, 1):
        print(f"  {i}. {proj_name}: {data['total_documents']} docs, {data['num_employees']} employees")

    print("\n🚀 Ready to view on frontend!")
    print("   Run: python app_project_classification.py")
    print("   Then open: http://localhost:5002")

    return project_mapping, employee_mapping


if __name__ == "__main__":
    create_simple_mappings()
