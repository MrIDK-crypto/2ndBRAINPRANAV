"""
Test Global Project Classification on Club Dataset
"""

import sys
from pathlib import Path
from config.config import Config
from run_global_project_classification import run_global_classification


def test_club_classification():
    """Test project classification on club dataset"""

    print("=" * 80)
    print("TESTING GLOBAL PROJECT CLASSIFICATION ON CLUB DATASET")
    print("=" * 80)

    # Check if club data exists
    club_data_dir = Config.DATA_DIR
    employee_clusters_dir = club_data_dir / "employee_clusters"

    if not employee_clusters_dir.exists():
        print("\n❌ Club employee clusters not found!")
        print(f"   Looking in: {employee_clusters_dir}")
        print("\n💡 Please run the employee clustering first:")
        print("   python run_club_pipeline_with_docs.py")
        return False

    # Count employee files
    employee_files = list(employee_clusters_dir.glob("*.jsonl"))
    if len(employee_files) <= 1:  # Only stats file
        print("\n❌ No employee data found in clusters!")
        print("   Please run the employee clustering pipeline first.")
        return False

    print(f"\n✅ Found {len(employee_files)} employee files")

    # Run classification
    output_dir = str(Config.OUTPUT_DIR / "club_project_classification")

    print(f"\n📍 Output will be saved to: {output_dir}")
    print("\nPress ENTER to continue or Ctrl+C to cancel...")
    input()

    try:
        project_mapping, employee_mapping = run_global_classification(
            data_dir=str(club_data_dir),
            output_dir=output_dir
        )

        print("\n" + "=" * 80)
        print("✅ CLASSIFICATION COMPLETE!")
        print("=" * 80)

        # Show some sample results
        print("\n📊 Sample Projects:")
        for i, (proj_name, proj_data) in enumerate(list(project_mapping.items())[:5], 1):
            print(f"\n{i}. {proj_name}")
            print(f"   Documents: {proj_data['total_documents']}")
            print(f"   Employees: {proj_data['num_employees']}")
            print(f"   Confidence: {proj_data['avg_confidence']:.2%}")
            print(f"   Top contributors: {', '.join(list(proj_data['employees'])[:3])}")

        print("\n👥 Sample Employees:")
        for i, (emp_name, emp_data) in enumerate(list(employee_mapping.items())[:5], 1):
            print(f"\n{i}. {emp_name}")
            print(f"   Documents: {emp_data['total_documents']}")
            print(f"   Projects: {emp_data['num_projects']}")
            top_projects = sorted(
                emp_data['all_projects'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            print(f"   Top projects: {', '.join([p[0] for p in top_projects])}")

        print("\n" + "=" * 80)
        print("🚀 READY TO VIEW ON FRONTEND!")
        print("=" * 80)

        print("\nTo start the web interface:")
        print("   python app_project_classification.py")
        print("\nThen open your browser to:")
        print("   http://localhost:5002")

        return True

    except Exception as e:
        print(f"\n❌ Error during classification: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_club_classification()

    if success:
        print("\n✅ Test completed successfully!")
        print("\n💡 Next steps:")
        print("   1. python app_project_classification.py")
        print("   2. Open http://localhost:5002 in your browser")
        print("   3. Explore projects and employees!")
    else:
        print("\n❌ Test failed. Please check the error messages above.")
        sys.exit(1)
