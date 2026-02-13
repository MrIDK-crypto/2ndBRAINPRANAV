# Quick Start: Global Project Classification

## What This Does

1. **Identifies** all employees in your dataset
2. **Classifies** projects globally across all documents using DistilBERT
3. **Maps** which employees worked on which projects
4. **Visualizes** results in a beautiful web dashboard

---

## Run It Now (3 Commands)

### Step 1: Test on Club Data
```bash
python test_club_classification.py
```

**What happens:**
- ✅ Checks club data exists
- ✅ Runs global classification
- ✅ Creates employee-project mappings
- ✅ Saves to `output/club_project_classification/`

**Time:** 5-15 minutes depending on data size

---

### Step 2: Start Web Server
```bash
python app_project_classification.py
```

**What happens:**
- ✅ Loads classification results
- ✅ Starts Flask server on port 5002
- ✅ Serves web dashboard

---

### Step 3: View in Browser
```
http://localhost:5002
```

**What you'll see:**
- 📊 Project statistics
- 👥 Employee statistics
- 🔍 Interactive search
- 📈 Detailed mappings
- 💡 Beautiful UI

---

## What You Get

### Project → Employee Mapping
**Question**: *Who worked on Project X?*
```json
{
  "Project Name": {
    "employees": ["emp1", "emp2", "emp3"],
    "employee_contributions": {
      "emp1": 50,  // 50 documents
      "emp2": 30,  // 30 documents
      "emp3": 20   // 20 documents
    }
  }
}
```

### Employee → Project Mapping
**Question**: *What projects did Employee Y work on?*
```json
{
  "employee@example.com": {
    "all_projects": {
      "Project A": 50,
      "Project B": 30,
      "Project C": 20
    },
    "primary_projects": {
      "Project A": 50,
      "Project B": 30
    }
  }
}
```

---

## Files You'll Get

```
output/club_project_classification/
├── project_mapping.json          ← All projects
├── employee_mapping.json         ← All employees
├── classification_summary.json   ← Statistics
├── projects/                     ← Docs by project
│   ├── Project_A.jsonl
│   └── ...
└── employees/                    ← Docs by employee
    ├── employee_1.jsonl
    └── ...
```

---

## Dashboard Features

### 📊 Projects Tab
- View all projects
- See employee contributions
- Click for detailed breakdowns
- Search by project name

### 👥 Employees Tab
- View all employees
- See project assignments
- Primary vs. secondary projects
- Search by employee name

### 🔍 Search
- Real-time filtering
- Search projects and employees
- Instant results

### 📈 Statistics
- Total projects
- Total employees
- Total documents
- Average projects per employee

---

## API Endpoints

Once the server is running:

```bash
# List all projects
curl http://localhost:5002/projects

# Get project details
curl http://localhost:5002/project/Project%20Name

# List all employees
curl http://localhost:5002/employees

# Get employee details
curl http://localhost:5002/employee/employee@example.com

# Get statistics
curl http://localhost:5002/summary
```

---

## Troubleshooting

### ❌ "Club employee clusters not found"
**Solution:**
```bash
# Run the club pipeline first
python run_club_pipeline_with_docs.py
```

### ❌ Web dashboard shows no data
**Solution:**
- Ensure Step 1 completed successfully
- Check `output/club_project_classification/` exists
- Verify JSON files are present

### ❌ Classification is slow
**Normal behavior:**
- 1,000 docs = 2-5 minutes
- 10,000 docs = 15-30 minutes
- Be patient, it's working!

---

## Customization

### Change Number of Projects
Edit in `run_global_project_classification.py`:
```python
categories = classifier.auto_detect_project_categories(
    all_documents,
    max_categories=20  # Change this number
)
```

### Manual Project Categories
Instead of auto-detection:
```python
classifier.set_project_categories([
    "Marketing",
    "Development",
    "Research",
    "Operations"
])
```

### Adjust Confidence Threshold
Filter low-confidence predictions:
```python
high_conf = [
    doc for doc in classified_docs
    if doc['project_confidence'] > 0.8
]
```

---

## Complete Documentation

- **Full Guide**: `GLOBAL_PROJECT_CLASSIFICATION.md`
- **Implementation Details**: `FINAL_IMPLEMENTATION_SUMMARY.md`
- **Original Features**: `NEW_FEATURES_IMPLEMENTATION.md`

---

## That's It!

Three commands, beautiful results:

```bash
python test_club_classification.py
python app_project_classification.py
# Open http://localhost:5002
```

🚀 **Ready to explore your data!**
