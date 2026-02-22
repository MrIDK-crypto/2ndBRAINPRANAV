# Smart Folders Design

## Summary
When a user creates a folder (name + description), the system embeds that text via OpenAI, queries Pinecone for semantically similar documents, and shows a preview of matched docs. The user selects which docs to include, and the folder is persisted in the backend via the existing `Project` table.

## Approach
- **Matching:** Semantic similarity via Pinecone (embed folder name+description, vector search)
- **Behavior:** One-time populate at creation. User can manually add/remove later.
- **Storage:** Backend `Project` table (replaces localStorage custom folders)
- **UX:** Preview matched docs with scores before confirming

## Data Flow
1. User enters folder name + description + color
2. `POST /api/projects/smart-create` → embed text → query Pinecone (top 30) → deduplicate to documents → return candidates with scores
3. Frontend shows preview modal with checkboxes
4. User confirms → `POST /api/projects/{id}/confirm` with selected doc IDs
5. Backend sets `Document.project_id` for selected docs
6. Folder appears in sidebar

## Database Changes
- Add `color` column to `Project` table (String, nullable)
- No other schema changes needed

## New API Endpoints (`backend/api/project_routes.py`)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/projects` | GET | List user's folders |
| `/api/projects/smart-create` | POST | Create folder + return matched docs |
| `/api/projects/{id}/confirm` | POST | Assign selected docs to folder |
| `/api/projects/{id}` | DELETE | Delete folder |
| `/api/projects/{id}/documents/{doc_id}` | DELETE | Remove doc from folder |

## Frontend Changes
- Replace localStorage custom folders with backend-fetched projects
- New `SmartFolderModal` with Step 1 (name/desc/color) → Step 2 (preview candidates) → confirm
- Load folders via `GET /api/projects` on component mount
- Filter documents by `project_id` when folder is selected
