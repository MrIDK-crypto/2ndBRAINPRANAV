# 🚀 Complete 2ndBrain Localhost Setup

**Date:** February 1, 2026
**Status:** ✅ FULLY RUNNING - NO LOGIN REQUIRED

---

## 🌐 LOCALHOST URLs

### **Frontend (Next.js - Port 3002)**
- **Home:** http://localhost:3002
- **Integrations:** http://localhost:3002/integrations
- **Documents:** http://localhost:3002/documents
- **Knowledge Gaps:** http://localhost:3002/knowledge-gaps
- **Projects:** http://localhost:3002/projects
- **Training Guides:** http://localhost:3002/training-guides
- **Settings:** http://localhost:3002/settings

### **Backend (Flask - Port 5003)**
- **Health Check:** http://localhost:5003/api/health
- **Email Status:** http://localhost:5003/api/email-forwarding/status-public
- **Fetch Emails:** POST http://localhost:5003/api/email-forwarding/fetch-public
- **Get Documents:** http://localhost:5003/api/email-forwarding/documents

---

## 📂 Complete Backend Structure

**Location:** `/Users/badri/2ndBrainFINAL/backend/`

### Main App Files:
```
app_v2.py              # Full backend with all features (DB required)
app_minimal.py         # ✅ CURRENTLY RUNNING - Minimal backend (no DB)
app.py                 # Legacy backend
main.py                # Alternative entry point
```

### API Routes (`./api/`):
```
auth_routes.py                 # User authentication & JWT
chat_routes.py                 # Chatbot endpoints
document_routes.py             # Document management
email_forwarding_routes.py     # Email forwarding (with auth)
email_forwarding_simple.py     # ✅ Email forwarding (no auth) - ACTIVE
github_routes.py               # GitHub integration
integration_routes.py          # Integration management
jobs_routes.py                 # Background jobs
knowledge_routes.py            # Knowledge gap detection
profile_routes.py              # User profiles
slack_bot_routes.py            # Slack bot
video_routes.py                # Video generation
```

### Services (`./services/`):
```
auth_service.py                    # Authentication logic
classification_service.py          # AI document classification
code_analysis_service.py           # Code analysis
document_parser.py                 # Document parsing
email_forwarding_service.py        # Email IMAP service
embedding_service.py               # Vector embeddings
enhanced_search_service.py         # RAG search
extraction_service.py              # Data extraction
gamma_service.py                   # Gamma integration
goal_first_analyzer.py             # Goal analysis
intelligent_gap_detector.py        # Gap detection
knowledge_service.py               # Knowledge management
multistage_gap_analyzer.py         # Multi-stage analysis
openai_client.py                   # Azure OpenAI client
s3_service.py                      # AWS S3 storage
slack_bot_service.py               # Slack bot logic
validators.py                      # Input validation
video_service.py                   # Video generation
```

### Knowledge Gap V3 (`./services/knowledge_gap_v3/`):
```
deep_extractor.py              # Deep knowledge extraction
feedback_loop.py               # Learning feedback
gap_analyzers.py               # Gap analysis algorithms
knowledge_graph.py             # Knowledge graph builder
orchestrator.py                # Gap detection orchestrator
prioritization.py              # Priority ranking
question_generator.py          # Question generation
```

### Database (`./database/`):
```
models.py                      # SQLAlchemy models
config.py                      # Database configuration
```

### Other Backend Directories:
```
./connectors/          # Integration connectors (Gmail, Slack, Box, etc.)
./indexing/            # Vector database & indexing
./parsers/             # Document parsers
./scripts/             # Utility scripts
./static/              # Static files
./uploads/             # File uploads directory
```

---

## 📂 Complete Frontend Structure

**Location:** `/Users/badri/2ndBrainFINAL/frontend/`

### App Pages (`./app/`):
```
page.tsx                       # Home (redirects to integrations)
layout.tsx                     # Root layout
login/page.tsx                 # Login page
integrations/page.tsx          # ✅ Integrations page (PUBLIC)
documents/page.tsx             # ✅ Documents page (PUBLIC)
knowledge-gaps/page.tsx        # Knowledge gaps page
projects/page.tsx              # Projects page
training-guides/page.tsx       # Training guides page
settings/page.tsx              # Settings page
```

### Components (`./components/`):

#### Documents (`./components/documents/`):
```
Documents.tsx                  # Original documents component (with auth)
DocumentsSimple.tsx            # ✅ ACTIVE - Simple documents (no auth)
DocumentViewer.tsx             # Document detail viewer
```

#### Integrations (`./components/integrations/`):
```
Integrations.tsx               # Main integrations grid
EmailForwardingCard.tsx        # ✅ Email forwarding card (no auth)
```

#### Knowledge Gaps (`./components/knowledge-gaps/`):
```
KnowledgeGaps.tsx              # Main knowledge gaps component
GapCard.tsx                    # Individual gap card
GapFilters.tsx                 # Filtering UI
GapStats.tsx                   # Statistics display
GapAnswerPanel.tsx             # Answer submission panel
AnalysisModeSelector.tsx       # Analysis mode selector
VoiceRecorder.tsx              # Voice input recorder
```

#### Other Components:
```
./components/auth/Login.tsx                   # Login form
./components/chat/ChatInterface.tsx           # Chat interface
./components/projects/Projects.tsx            # Projects component
./components/settings/Settings.tsx            # Settings component
./components/training-guides/TrainingGuides.tsx  # Training guides
./components/shared/Sidebar.tsx               # Main sidebar navigation
./components/providers/Providers.tsx          # Context providers
```

### Contexts (`./contexts/`):
```
AuthContext.tsx                # ✅ MODIFIED - Auth disabled for public pages
```

---

## 🔧 Current Configuration

### Backend (.env):
```
JWT_SECRET_KEY=test_secret_key_12345
FLASK_SECRET_KEY=test_flask_secret_12345
PORT=5003

# Email Forwarding
FORWARD_EMAIL_ADDRESS=beatatucla@gmail.com
FORWARD_EMAIL_PASSWORD=ekxvjoipvimekmnz
```

### Frontend:
```
NEXT_PUBLIC_API_URL=http://localhost:5003
```

---

## 🎯 What's Running

### Backend Process:
```bash
# Running from: /Users/badri/2ndBrainFINAL/backend/
./venv_fixed/bin/python3 app_minimal.py
```

**Features Enabled:**
- ✅ Email forwarding (no auth)
- ✅ CORS enabled
- ✅ JSON file storage (no database)
- ✅ Health check endpoint

### Frontend Process:
```bash
# Running from: /Users/badri/2ndBrainFINAL/frontend/
npm run dev
```

**Features Enabled:**
- ✅ All pages accessible
- ✅ Integrations page (public)
- ✅ Documents page (public)
- ✅ Sidebar navigation
- ✅ Email forwarding integration

---

## 🔥 Key Features

### Email Integration:
1. **Fetch Emails:**
   - Goes to http://localhost:3002/integrations
   - Click "Email Forwarding" card
   - Click "Connect" → "FETCH EMAILS"
   - Fetches from beatatucla@gmail.com
   - Max 10 emails per fetch
   - Stores in JSON file

2. **View Emails:**
   - Go to http://localhost:3002/documents
   - Auto-refreshes every 10 seconds
   - Shows all fetched emails
   - Clean, modern interface
   - Manual refresh button

### Authentication:
- **Modified:** `/contexts/AuthContext.tsx`
- **Public Pages:** `/integrations`, `/documents`
- **No login required** for email functionality

---

## 📊 Data Storage

### Backend Data:
```
/Users/badri/2ndBrainFINAL/backend/
├── fetched_emails.json          # Email storage (currently 20 emails)
├── 2nd_brain.db                 # SQLite database (not used by minimal app)
└── knowledge_vault.db           # Knowledge database (not used by minimal app)
```

---

## 🚀 Quick Start Guide

### To Make Changes:

1. **Backend Changes:**
   ```bash
   cd /Users/badri/2ndBrainFINAL/backend

   # Edit files in:
   - api/email_forwarding_simple.py    # Email API
   - app_minimal.py                    # Main app
   - services/                         # Business logic

   # Restart backend (kill current process and restart)
   ```

2. **Frontend Changes:**
   ```bash
   cd /Users/badri/2ndBrainFINAL/frontend

   # Edit files in:
   - components/integrations/EmailForwardingCard.tsx
   - components/documents/DocumentsSimple.tsx
   - app/integrations/page.tsx
   - app/documents/page.tsx

   # Hot reload is enabled - changes reflect automatically
   ```

3. **Database (if needed):**
   ```bash
   cd /Users/badri/2ndBrainFINAL/backend

   # Use full backend:
   ./venv_fixed/bin/python3 app_v2.py

   # Note: Requires fixing SQLAlchemy compatibility
   ```

---

## 🛠️ Common Tasks

### Restart Backend:
```bash
# Find and kill process
lsof -ti:5003 | xargs kill

# Start minimal backend
cd /Users/badri/2ndBrainFINAL/backend
./venv_fixed/bin/python3 app_minimal.py
```

### Restart Frontend:
```bash
# Find and kill process
lsof -ti:3002 | xargs kill

# Start frontend
cd /Users/badri/2ndBrainFINAL/frontend
npm run dev
```

### Fetch More Emails:
```bash
# Via API
curl -X POST http://localhost:5003/api/email-forwarding/fetch-public

# Via UI
# Go to http://localhost:3002/integrations
# Click Email Forwarding → Fetch Emails
```

### View All Emails:
```bash
# Via API
curl http://localhost:5003/api/email-forwarding/documents

# Via UI
# Go to http://localhost:3002/documents
```

---

## 📝 Important Notes

1. **No Database:** Current minimal backend uses JSON file storage
2. **Public Access:** Integrations and Documents pages are public (no login)
3. **Email Limit:** Fetches max 10 emails per request
4. **Auto-refresh:** Documents page auto-refreshes every 10 seconds
5. **Gmail Credentials:** Hardcoded in backend .env file

---

## 🎉 Ready for Changes!

Everything is running and accessible at:
- **Frontend:** http://localhost:3002
- **Backend:** http://localhost:5003

You can now make any changes you need! The frontend has hot reload enabled, so changes will reflect immediately. For backend changes, you'll need to restart the server.

---

**Last Updated:** February 1, 2026
**Status:** ✅ FULLY OPERATIONAL
**Authentication:** DISABLED for public pages
**Email Fetching:** WORKING
