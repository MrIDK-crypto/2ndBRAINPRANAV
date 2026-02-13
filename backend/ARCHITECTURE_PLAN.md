# Knowledge Vault - Architecture & Implementation Plan

**Date:** November 25, 2025
**Status:** Production Readiness Assessment

---

## Executive Summary

**Current State:** Individual components working, need integration into cohesive workflow
**Goal:** Scalable, sellable product with complete user workflow
**Timeline:** 2-3 weeks for MVP completion

---

## Target Workflow (What We're Building)

```
1. Login Page
   ↓
2. Integrations Page (Connect Gmail + Manual Upload)
   ↓
3. Document Classification (4 Categories: Work, Personal, Uncertain, Spam)
   ↓
4. User Deletes Personal Docs → Parse Remaining with LlamaParse
   ↓
5. Cluster Documents into Projects (LLM-First Clustering)
   ↓
6. Build RAG + Chatbot from Parsed Data
   ↓
7. Auto-Generate 10-Min Presentation per Project (Gamma + OpenAI Voiceover)
```

---

## Current Architecture

### Production Stack

**Backend:** Flask API (`app_universal.py` - 2,340 lines)
**Frontend:** Next.js 14 + React + TypeScript
**Database:** File-based + ChromaDB/Pinecone vector store
**ML Models:** OpenAI GPT-4o/4o-mini, Sentence Transformers, LlamaParse
**Hosting:** Local (ready for cloud deployment)

### Key Components Status

| Component | Status | Notes |
|-----------|--------|-------|
| Gmail Connector | ✅ Working | OAuth flow complete, sync functional |
| Manual Upload | ❌ Missing | Need `/api/upload` endpoint |
| Classification | 🔧 Partial | 2 categories (need 4) |
| LlamaParse | ✅ Working | Not integrated into pipeline |
| Project Clustering | ✅ Working | LLM-first clusterer production-ready |
| RAG + Chatbot | ✅ Working | Enhanced RAG v2 with reranking |
| Gamma Presentations | 🔧 Partial | Creates slides, missing voiceover |
| Authentication | 🔧 Partial | Auth0 setup, not enforced |

---

## What We Have (Inventory)

### ✅ FULLY WORKING (Production-Ready)

#### Backend Core
- **`app_universal.py`** - Main Flask API (50+ endpoints)
- **Gmail Connector** - Full OAuth, email sync, auto-clustering
- **LLM-First Clusterer** - 842 lines, 5-phase clustering algorithm
- **Enhanced RAG v2** - 1,248 lines, semantic search, reranking
- **Work/Personal Classifier** - GPT-4o-mini based (85% confidence threshold)
- **LlamaParse Integration** - Supports PDF, DOCX, PPTX, XLSX, TXT, HTML
- **Stakeholder Graph** - "Who" question answering system
- **Knowledge Gap System** - Question generation and answer collection
- **Gamma API Integration** - Slide generation from templates

#### Frontend Components
- All pages created (Login, Integrations, Projects, Documents, Gaps, Training)
- All UI components built
- Sidebar navigation working
- Project cards with expand/collapse
- Document viewer
- Chat interface

#### APIs (50+ Endpoints)
- `/api/connectors/*` - Integration management
- `/api/projects/*` - Project CRUD and clustering
- `/api/search` - RAG search
- `/api/questions/*` - Knowledge gap management
- `/api/stakeholders/*` - Person queries
- `/api/gamma/*` - Presentation generation
- `/api/documents/*` - Document management

### 🔧 PARTIALLY WORKING (Needs Fixes)

1. **Authentication** - Auth0 handler exists but not integrated into app_universal.py
2. **Classification** - Only 2 categories (work/personal), need 4
3. **Presentations** - Gamma creates slides, missing OpenAI voiceover + video
4. **Slack/GitHub Connectors** - Basic implementation, needs testing
5. **Frontend Integration** - Components exist but API calls need wiring

### ❌ MISSING (Critical Gaps)

1. **Manual File Upload** - No endpoint for user file uploads
2. **4-Category Classification** - Only work/personal, need uncertain/spam
3. **LlamaParse Pipeline Integration** - Parser works standalone, not in workflow
4. **Presentation Voiceover** - No OpenAI TTS integration
5. **Video Generation** - No slide + voiceover → video pipeline
6. **Automated Presentation per Project** - Manual trigger only, not automated
7. **User Data Isolation** - No multi-user support yet

---

## Implementation Plan

### Phase 1: Core Workflow (Week 1)
**Goal:** Complete end-to-end workflow for single user

#### Task 1.1: Manual File Upload (4 hours)
- Add `/api/upload` endpoint to app_universal.py
- Accept multipart/form-data
- Save to temporary directory
- Route to LlamaParse for processing
- Return document ID

**Files to modify:**
- `app_universal.py` - Add upload endpoint
- `parsers/llamaparse_parser.py` - Already works, just call it

**Code snippet:**
```python
@app.route('/api/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    # Parse with LlamaParse
    from parsers.llamaparse_parser import LlamaParseParser
    parser = LlamaParseParser()
    result = parser.parse(filepath)

    # Add to knowledge base
    doc_id = add_to_knowledge_base(result)

    return jsonify({"success": True, "doc_id": doc_id})
```

#### Task 1.2: 4-Category Classification (6 hours)
- Extend `work_personal_classifier.py` to 4 categories
- Categories: `work`, `personal`, `uncertain`, `spam`
- Add confidence scores for each
- Update classification prompt

**Files to modify:**
- `classification/work_personal_classifier.py`

**Updated prompt:**
```python
classification_prompt = """
Classify this document into ONE category:

1. WORK - Professional emails, work documents, client communications
2. PERSONAL - Personal emails, casual conversations, non-work content
3. UNCERTAIN - Could be either work or personal, needs human review
4. SPAM - Promotional emails, newsletters, automated messages

Return JSON:
{
  "category": "work|personal|uncertain|spam",
  "confidence": 0.0-1.0,
  "reasoning": "Why this classification"
}
"""
```

#### Task 1.3: Integrate LlamaParse into Pipeline (4 hours)
- Wire LlamaParse after classification
- Only parse documents classified as "work" or "uncertain"
- Skip "personal" and "spam"
- Update ingestion flow

**Files to modify:**
- `app_universal.py` - Update Gmail sync workflow
- Create new `pipelines/ingestion_pipeline.py`

**Workflow:**
```python
# In Gmail sync or upload endpoint
def process_document(doc):
    # 1. Classify
    category = classifier.classify(doc)

    if category in ['personal', 'spam']:
        # User can delete these later
        save_to_review_queue(doc, category)
        return

    # 2. Parse with LlamaParse
    if category in ['work', 'uncertain']:
        parsed_content = llamaparse_parser.parse(doc)

        # 3. Add to vector store
        add_to_vector_store(parsed_content)

        # 4. Cluster into projects (done by /api/projects/reprocess)
```

#### Task 1.4: Document Review & Deletion UI (6 hours)
- Frontend: Add "Review Documents" page
- Show documents by category
- Allow user to delete personal/spam
- Bulk actions (delete all personal, etc.)

**Files to create:**
- `frontend/app/review/page.tsx`
- `frontend/components/DocumentReview.tsx`

**API endpoint:**
```python
@app.route('/api/documents/review', methods=['GET'])
def get_documents_for_review():
    return jsonify({
        "personal": get_docs_by_category("personal"),
        "spam": get_docs_by_category("spam"),
        "uncertain": get_docs_by_category("uncertain")
    })

@app.route('/api/documents/delete', methods=['POST'])
def delete_documents():
    doc_ids = request.json.get('doc_ids', [])
    for doc_id in doc_ids:
        delete_document(doc_id)
    return jsonify({"success": True})
```

### Phase 2: Presentation Generation (Week 2)
**Goal:** Auto-generate 10-min presentations with voiceover

#### Task 2.1: OpenAI TTS Integration (4 hours)
- Use OpenAI `tts-1` model
- Generate narration for each slide
- Save audio files

**Files to create:**
- `content_generation/voice_generator.py`

**Code:**
```python
from openai import OpenAI

class VoiceGenerator:
    def __init__(self):
        self.client = OpenAI()

    def generate_narration(self, slide_text, output_path):
        """Generate audio narration for slide"""
        response = self.client.audio.speech.create(
            model="tts-1",
            voice="alloy",  # or nova, shimmer
            input=slide_text,
            speed=1.0
        )
        response.stream_to_file(output_path)
        return output_path
```

#### Task 2.2: Video Generation (6 hours)
- Combine Gamma slides (export as images) with voiceover
- Use moviepy or similar to create video
- Target 10-minute duration

**Files to modify:**
- `content_generation/video_generator.py` (already exists, update it)

**Workflow:**
```python
def generate_presentation_video(project_id):
    # 1. Generate slides with Gamma
    gamma_result = gamma_api.generate(project_data)
    slides = gamma_result['slides']

    # 2. For each slide, generate narration
    audio_files = []
    for i, slide in enumerate(slides):
        narration = voice_gen.generate_narration(
            slide['content'],
            f"audio_{i}.mp3"
        )
        audio_files.append(narration)

    # 3. Export Gamma slides as images
    slide_images = gamma_api.export_images(gamma_result['id'])

    # 4. Combine into video
    video = create_video(slide_images, audio_files)

    return video_url
```

#### Task 2.3: Automated Presentation per Project (4 hours)
- Trigger presentation generation when project is created
- Add to project clustering workflow
- Store presentation link in project metadata

**Files to modify:**
- `app_universal.py` - Add to `/api/projects/reprocess`
- `clustering/llm_first_clusterer.py` - Call presentation generation

**Code:**
```python
# After clustering completes
for project in canonical_projects:
    # Generate presentation asynchronously
    task_id = generate_presentation_async(project)
    project['presentation_task_id'] = task_id
```

### Phase 3: Authentication & Multi-User (Week 2-3)
**Goal:** Secure, multi-user system

#### Task 3.1: Integrate Auth0 (6 hours)
- Add authentication middleware to app_universal.py
- Protect all API endpoints
- Extract user ID from JWT token

**Files to modify:**
- `app_universal.py` - Add auth decorator
- `auth/auth0_handler.py` - Already exists, use it

**Code:**
```python
from auth.auth0_handler import requires_auth

@app.route('/api/projects')
@requires_auth
def get_projects():
    user_id = get_user_id_from_token()
    projects = load_user_projects(user_id)
    return jsonify(projects)
```

#### Task 3.2: User Data Isolation (8 hours)
- Change file structure: `club_data/{user_id}/`
- Update all data loading to be user-specific
- Migrate existing data to new structure

**Files to modify:**
- All data loading/saving code
- `app_universal.py` - Add user context

**New structure:**
```
club_data/
├── user_abc123/
│   ├── documents/
│   ├── projects/
│   ├── embeddings/
│   └── presentations/
├── user_def456/
│   └── ...
```

#### Task 3.3: Frontend Auth Integration (4 hours)
- Add Auth0 React SDK
- Protect routes
- Add login/logout flow

**Files to modify:**
- `frontend/app/layout.tsx` - Add Auth0Provider
- `frontend/app/login/page.tsx` - Use Auth0 login
- All pages - Add authentication checks

### Phase 4: Polish & Production (Week 3)
**Goal:** Deploy-ready product

#### Task 4.1: Error Handling & Loading States (8 hours)
- Add error boundaries
- Loading spinners
- Toast notifications
- Retry logic

#### Task 4.2: Performance Optimization (8 hours)
- Cache API responses
- Lazy load components
- Optimize vector search
- Add pagination

#### Task 4.3: Testing (8 hours)
- End-to-end workflow testing
- Edge case handling
- Load testing
- Bug fixes

#### Task 4.4: Documentation (6 hours)
- API documentation
- User guide
- Deployment guide
- Architecture diagrams

---

## Files to Delete/Archive

### Safe to Delete (73 files, ~15MB)

Create archive directory first:
```bash
mkdir /Users/rishitjain/Downloads/knowledgevault_backend/archive
mv [files below] archive/
```

#### Backend Scripts (Development/Testing - 45 files)
```
app.py
app_complete.py
app_project_classification.py
main.py
demo_simple.py
test_*.py (7 files)
run_*.py (7 files)
build_*.py (7 files)
classify_all_employees.py
classify_club_data.py
parser_comparison_*.py (2 files)
generate_all_summaries.py
generate_llamaparse_report.py
show_methodology_results.py
process_club_data.py
project_clusterer.py
deduplicate_documents.py
message_filter*.py (2 files)
rebuild_*.py (2 files)
watch_progress.sh
```

#### Old Clustering/Classification (5 files)
```
clustering/project_clustering.py
clustering/employee_clustering.py
clustering/intelligent_project_clustering.py
classification/project_classifier.py
classification/global_project_classifier.py
```

#### Old RAG Implementation (1 file)
```
rag/hierarchical_rag.py
```

#### Frontend Duplicate (1 file)
```
components/ChatInterface-old.tsx
```

#### Log Files (18 files)
```
*.log files
```

#### Report Files (3 files)
```
*.html report files
```

**Command to archive:**
```bash
cd /Users/rishitjain/Downloads/knowledgevault_backend
mkdir -p archive/{scripts,old_clustering,old_classification,old_rag,logs}

# Archive test/demo scripts
mv app.py app_complete.py app_project_classification.py main.py demo_simple.py archive/scripts/
mv test_*.py run_*.py build_*.py archive/scripts/
mv classify_*.py parser_comparison_*.py generate_*.py show_*.py archive/scripts/
mv process_club_data.py project_clusterer.py deduplicate_documents.py archive/scripts/
mv message_filter*.py rebuild_*.py watch_progress.sh archive/scripts/

# Archive old implementations
mv clustering/project_clustering.py clustering/employee_clustering.py archive/old_clustering/
mv clustering/intelligent_project_clustering.py archive/old_clustering/
mv classification/project_classifier.py classification/global_project_classifier.py archive/old_classification/
mv rag/hierarchical_rag.py archive/old_rag/

# Archive logs
mv *.log *.html archive/logs/ 2>/dev/null || true

# Frontend
cd /Users/rishitjain/Downloads/knowledge-vault-frontend
rm components/ChatInterface-old.tsx
```

### Keep Everything Else (Production Code)

**Backend Core:**
- `app_universal.py` ← Main API
- `gamma_presentation.py` ← Standalone presenter
- All `/connectors/`
- All `/parsers/`
- `classification/work_personal_classifier.py`
- `clustering/llm_first_clusterer.py`
- `rag/enhanced_rag_v2.py`
- `rag/enhanced_rag.py` (fallback)
- `rag/stakeholder_graph.py`
- Everything in: `/auth/`, `/vector_stores/`, `/indexing/`, `/gap_analysis/`, `/content_generation/`, `/training_generator/`, `/config/`, `/utils/`, `/scripts/`

**Frontend:**
- All pages and components (except ChatInterface-old.tsx)

---

## Critical Implementation Priorities

### Must Have (Blocking Launch)
1. ❌ Manual file upload endpoint
2. ❌ 4-category classification
3. ❌ LlamaParse integration into pipeline
4. ❌ Document review & deletion UI
5. ❌ Authentication enforcement
6. ❌ User data isolation

### Should Have (Launch v1.1)
7. ❌ OpenAI TTS voiceover
8. ❌ Video generation
9. ❌ Automated presentation per project

### Nice to Have (Future)
10. 🔧 Slack/GitHub connectors completion
11. 🔧 Advanced permissions
12. 🔧 Export functionality
13. 🔧 Analytics dashboard

---

## Technology Stack

### Backend
- **Framework:** Flask 3.0
- **Language:** Python 3.12
- **ML Models:** OpenAI GPT-4o/4o-mini, Sentence Transformers
- **Vector DB:** ChromaDB (local) or Pinecone (cloud)
- **Graph DB:** Neo4j (optional)
- **Parsing:** LlamaParse
- **Auth:** Auth0

### Frontend
- **Framework:** Next.js 14
- **Language:** TypeScript
- **UI:** React 18, Tailwind CSS
- **State:** React hooks
- **HTTP:** Fetch API

### Infrastructure
- **Storage:** File-based + vector stores
- **Deployment:** Docker (ready)
- **CI/CD:** GitHub Actions (can add)

---

## Deployment Checklist

### Pre-Deployment
- [ ] Archive unused code
- [ ] Add `.gitignore` for sensitive files
- [ ] Environment variables in `.env`
- [ ] Update README with setup instructions
- [ ] Add Docker Compose for easy deployment

### Production Prep
- [ ] Set up production Auth0 tenant
- [ ] Get production Gamma API key
- [ ] Configure production vector store (Pinecone)
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Add rate limiting
- [ ] Enable CORS properly
- [ ] Add request logging

### Launch
- [ ] Deploy backend to cloud (Heroku, Railway, or AWS)
- [ ] Deploy frontend to Vercel/Netlify
- [ ] Set up custom domain
- [ ] Configure SSL certificates
- [ ] Test end-to-end workflow
- [ ] Create demo account
- [ ] Write user documentation

---

## Estimated Timeline

| Phase | Duration | Completion Date |
|-------|----------|-----------------|
| Phase 1: Core Workflow | 1 week | Dec 2, 2025 |
| Phase 2: Presentations | 1 week | Dec 9, 2025 |
| Phase 3: Auth & Multi-User | 1 week | Dec 16, 2025 |
| Phase 4: Polish & Production | 1 week | Dec 23, 2025 |
| **Total** | **4 weeks** | **MVP Launch** |

---

## Next Steps (This Week)

1. **Archive unused code** (1 hour) - Clean up repository
2. **Implement manual upload** (4 hours) - Core feature
3. **Extend to 4-category classification** (6 hours) - Workflow requirement
4. **Build document review UI** (6 hours) - User interaction
5. **Integrate LlamaParse** (4 hours) - Complete pipeline

**Total:** ~21 hours (3 days of focused work)

---

## Questions for Product Owner

1. **Presentation Duration:** Confirm 10 minutes is the target?
2. **Voice:** Which OpenAI voice? (alloy, echo, fable, onyx, nova, shimmer)
3. **Gamma Template:** Use existing template or create custom?
4. **User Tiers:** Free vs paid features? Usage limits?
5. **Data Retention:** How long to keep deleted documents?
6. **Export:** Should users be able to export their data?

---

**Document Version:** 1.0
**Last Updated:** November 25, 2025
**Author:** Architecture Analysis Agent
