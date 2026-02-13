"""
Process Club Data from Google Chat Takeout
1. Parse all documents with LlamaParse
2. Identify real projects (Google Chat spaces)
3. Map employees to projects
4. Build RAG for each employee
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from config.config import Config
from parsers.document_parser import DocumentParser

def discover_projects_and_members(takeout_path: str):
    """
    Discover actual projects (Google Chat spaces) and their members

    Args:
        takeout_path: Path to Google Chat Takeout folder

    Returns:
        Dictionary of projects with members and files
    """
    print("=" * 80)
    print("DISCOVERING PROJECTS FROM GOOGLE CHAT")
    print("=" * 80)

    takeout = Path(takeout_path)
    groups_dir = takeout / "Google Chat" / "Groups"

    if not groups_dir.exists():
        print(f"❌ Groups directory not found: {groups_dir}")
        return {}

    projects = {}

    # Scan all spaces
    for space_dir in groups_dir.iterdir():
        if not space_dir.is_dir():
            continue

        # Skip DM conversations
        if space_dir.name.startswith("DM "):
            continue

        # Read group info
        group_info_file = space_dir / "group_info.json"
        if not group_info_file.exists():
            continue

        with open(group_info_file, 'r') as f:
            group_info = json.load(f)

        project_name = group_info.get('name', space_dir.name)
        members = group_info.get('members', [])

        # Get all files in this space
        files = []
        for file_path in space_dir.iterdir():
            if file_path.is_file() and not file_path.name.endswith('.json'):
                files.append(str(file_path))

        projects[project_name] = {
            'space_id': space_dir.name,
            'members': [
                {
                    'name': m.get('name', ''),
                    'email': m.get('email', '')
                }
                for m in members
            ],
            'files': files,
            'file_count': len(files)
        }

        print(f"\n✓ Found project: {project_name}")
        print(f"  Members: {len(members)}")
        print(f"  Files: {len(files)}")

    print(f"\n✅ Discovered {len(projects)} projects")
    return projects


def parse_all_documents(projects: dict, parser: DocumentParser):
    """
    Parse all documents in all projects using LlamaParse

    Args:
        projects: Dictionary of projects
        parser: DocumentParser instance

    Returns:
        Projects with parsed documents
    """
    print("\n" + "=" * 80)
    print("PARSING ALL DOCUMENTS WITH LLAMAPARSE")
    print("=" * 80)

    total_files = sum(p['file_count'] for p in projects.values())
    processed = 0

    for project_name, project_data in projects.items():
        print(f"\n📂 Processing: {project_name}")

        parsed_docs = []

        for file_path in project_data['files']:
            processed += 1
            file_name = Path(file_path).name

            # Skip very large files for testing
            file_size = Path(file_path).stat().st_size
            if file_size > 10 * 1024 * 1024:  # Skip files > 10MB
                print(f"  ⏭  Skipping large file: {file_name} ({file_size/1024/1024:.1f}MB)")
                continue

            print(f"  [{processed}/{total_files}] Parsing: {file_name[:50]}...")

            result = parser.parse(file_path)

            if result:
                parsed_docs.append({
                    'file_name': file_name,
                    'file_path': file_path,
                    'content': result['content'],
                    'metadata': result['metadata'],
                    'project': project_name
                })
                print(f"    ✓ Success: {result['metadata'].get('processed_chars', 0):,} chars")
            else:
                print(f"    ✗ Failed to parse")

        project_data['parsed_documents'] = parsed_docs
        print(f"  📊 Parsed {len(parsed_docs)}/{len(project_data['files'])} files")

    return projects


def create_employee_project_mapping(projects: dict):
    """
    Create mapping of employees to projects and vice versa

    Args:
        projects: Dictionary of projects with parsed documents

    Returns:
        Tuple of (project_mapping, employee_mapping)
    """
    print("\n" + "=" * 80)
    print("CREATING EMPLOYEE-PROJECT MAPPINGS")
    print("=" * 80)

    # Project → Employees mapping
    project_mapping = {}

    # Employee → Projects mapping
    employee_projects = defaultdict(list)
    employee_docs = defaultdict(list)

    for project_name, project_data in projects.items():
        members = project_data['members']
        docs = project_data.get('parsed_documents', [])

        project_mapping[project_name] = {
            'project_name': project_name,
            'space_id': project_data['space_id'],
            'members': [m['email'] for m in members],
            'member_names': [m['name'] for m in members],
            'total_documents': len(docs),
            'documents': docs
        }

        # Add to employee mapping
        for member in members:
            email = member['email']
            employee_projects[email].append(project_name)
            # All documents in this project are accessible by this employee
            employee_docs[email].extend(docs)

    # Create employee mapping
    employee_mapping = {}
    for email, proj_list in employee_projects.items():
        # Find member name
        member_name = email
        for project_data in projects.values():
            for m in project_data['members']:
                if m['email'] == email:
                    member_name = m['name']
                    break

        employee_mapping[email] = {
            'name': member_name,
            'email': email,
            'projects': proj_list,
            'num_projects': len(proj_list),
            'total_documents': len(employee_docs[email]),
            'documents': employee_docs[email]
        }

    print(f"\n✓ Created mapping for {len(project_mapping)} projects")
    print(f"✓ Created mapping for {len(employee_mapping)} employees")

    # Print summary
    print(f"\n📊 Project Summary:")
    for proj_name, proj_data in project_mapping.items():
        print(f"  • {proj_name}: {proj_data['total_documents']} docs, {len(proj_data['members'])} members")

    print(f"\n👥 Employee Summary:")
    for email, emp_data in employee_mapping.items():
        print(f"  • {emp_data['name']}: {emp_data['num_projects']} projects, {emp_data['total_documents']} docs")

    return project_mapping, employee_mapping


def save_results(project_mapping: dict, employee_mapping: dict, output_dir: str):
    """Save all results to output directory"""
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save project mapping
    with open(output_path / 'project_mapping.json', 'w') as f:
        # Remove documents for JSON size
        clean_projects = {}
        for proj, data in project_mapping.items():
            clean_projects[proj] = {
                'project_name': data['project_name'],
                'space_id': data['space_id'],
                'members': data['members'],
                'member_names': data['member_names'],
                'total_documents': data['total_documents']
            }
        json.dump(clean_projects, f, indent=2)
    print(f"✓ Saved project_mapping.json")

    # Save employee mapping
    with open(output_path / 'employee_mapping.json', 'w') as f:
        clean_employees = {}
        for email, data in employee_mapping.items():
            clean_employees[email] = {
                'name': data['name'],
                'email': data['email'],
                'projects': data['projects'],
                'num_projects': data['num_projects'],
                'total_documents': data['total_documents']
            }
        json.dump(clean_employees, f, indent=2)
    print(f"✓ Saved employee_mapping.json")

    # Save documents by project
    projects_dir = output_path / "projects"
    projects_dir.mkdir(exist_ok=True)

    for proj_name, proj_data in project_mapping.items():
        safe_name = proj_name.replace('/', '_').replace('\\', '_')[:50]
        with open(projects_dir / f"{safe_name}.jsonl", 'w') as f:
            for doc in proj_data['documents']:
                f.write(json.dumps(doc) + '\n')
    print(f"✓ Saved {len(project_mapping)} project document files")

    # Save documents by employee
    employees_dir = output_path / "employees"
    employees_dir.mkdir(exist_ok=True)

    for email, emp_data in employee_mapping.items():
        safe_name = email.replace('@', '_at_').replace('.', '_')
        with open(employees_dir / f"{safe_name}.jsonl", 'w') as f:
            for doc in emp_data['documents']:
                f.write(json.dumps(doc) + '\n')
    print(f"✓ Saved {len(employee_mapping)} employee document files")

    # Save summary
    summary = {
        'total_projects': len(project_mapping),
        'total_employees': len(employee_mapping),
        'total_documents': sum(p['total_documents'] for p in project_mapping.values())
    }

    with open(output_path / 'summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved summary.json")

    print(f"\n📁 All results saved to: {output_path}")


def main():
    """Main processing pipeline"""

    # Configuration
    TAKEOUT_PATH = "/Users/rishitjain/Downloads/Takeout"
    OUTPUT_DIR = str(Config.OUTPUT_DIR / "club_project_classification")

    print("\n🎯 CLUB DATA PROCESSING PIPELINE")
    print(f"   Takeout: {TAKEOUT_PATH}")
    print(f"   Output: {OUTPUT_DIR}\n")

    # Step 1: Discover projects
    projects = discover_projects_and_members(TAKEOUT_PATH)

    if not projects:
        print("\n❌ No projects found!")
        return

    # Step 2: Initialize LlamaParse parser
    print("\n" + "=" * 80)
    print("INITIALIZING LLAMAPARSE")
    print("=" * 80)

    parser = DocumentParser(config=Config, use_llamaparse=True)

    # Step 3: Parse all documents (this will take time!)
    print("\n⚠️  Parsing all documents with LlamaParse + GPT-4o-mini")
    print("   This may take 10-30 minutes depending on number of files\n")

    projects = parse_all_documents(projects, parser)

    # Step 4: Create mappings
    project_mapping, employee_mapping = create_employee_project_mapping(projects)

    # Step 5: Save results
    save_results(project_mapping, employee_mapping, OUTPUT_DIR)

    print("\n" + "=" * 80)
    print("✅ PROCESSING COMPLETE!")
    print("=" * 80)

    print("\n🚀 Next steps:")
    print("   1. Build RAG system: python build_club_rag.py")
    print("   2. Start web interface: python app_project_classification.py")
    print("   3. Open http://localhost:5002")


if __name__ == "__main__":
    main()
