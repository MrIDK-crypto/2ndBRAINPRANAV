# Navigation Redesign + Co-Work + Uploads Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the top navigation with dropdown menus, create a full-screen drag-and-drop upload page, merge chatbot + co-researcher into a 3-panel "Co-Work" page, make the research translator public at `/research-reproducibility`, and remove landing page dropdown emoji icons.

**Architecture:** The nav gets dropdown hover menus (Uploads → Drag & Drop / Integrations; More → Training Videos / Knowledge Gaps / Analytics / Inventory). The Co-Work page is a 3-panel layout (Chat | Plan | Context) that replaces `/chat`, using SSE streaming from `/api/search/stream` and `/api/co-researcher/sessions/{id}/messages/stream`. The backend RAG is extended to also search JournalProfile and FailedExperiment tables and stream "thinking" events. Old routes (`/chat`, `/co-researcher`) redirect to `/co-work`.

**Tech Stack:** Next.js 14 (App Router), React, TypeScript, inline styles (existing pattern), Flask SSE streaming, SQLAlchemy

---

## Task 1: Remove Emoji Icons from Landing Page Dropdown

**Files:**
- Modify: `frontend/app/landing/page.tsx:62-82`
- Modify: `frontend/app/landing/landing.css:177-194`

**Step 1: Remove the three `<span className="nav-dropdown-icon">` elements**

In `frontend/app/landing/page.tsx`, replace lines 62-82:

```tsx
              <Link href="/high-impact-journal" className="nav-dropdown-item">
                <span className="nav-dropdown-icon">📊</span>
                <div>
                  <span className="nav-dropdown-label">High Impact Journals</span>
                  <span className="nav-dropdown-desc">AI-powered manuscript scoring & journal matching</span>
                </div>
              </Link>
              <Link href="/reproducibility-archive" className="nav-dropdown-item">
                <span className="nav-dropdown-icon">🔬</span>
                <div>
                  <span className="nav-dropdown-label">Reproducibility Archive</span>
                  <span className="nav-dropdown-desc">Track and verify experimental reproducibility</span>
                </div>
              </Link>
              <Link href="/reproducibility-archive/submit" className="nav-dropdown-item">
                <span className="nav-dropdown-icon">🧪</span>
                <div>
                  <span className="nav-dropdown-label">Anonymous Failed Experiments</span>
                  <span className="nav-dropdown-desc">Share negative results anonymously to advance science</span>
                </div>
              </Link>
```

With (icons removed):

```tsx
              <Link href="/high-impact-journal" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">High Impact Journals</span>
                  <span className="nav-dropdown-desc">AI-powered manuscript scoring & journal matching</span>
                </div>
              </Link>
              <Link href="/reproducibility-archive" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Reproducibility Archive</span>
                  <span className="nav-dropdown-desc">Track and verify experimental reproducibility</span>
                </div>
              </Link>
              <Link href="/reproducibility-archive/submit" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Anonymous Failed Experiments</span>
                  <span className="nav-dropdown-desc">Share negative results anonymously to advance science</span>
                </div>
              </Link>
```

**Step 2: Remove the gap from `.nav-dropdown-item` since there's no icon**

In `frontend/app/landing/landing.css`, change `.nav-dropdown-item` gap from `12px` to `0`:

```css
.nav-dropdown-item {
  display: flex;
  align-items: flex-start;
  gap: 0;
  padding: 10px 12px;
  border-radius: 8px;
  text-decoration: none !important;
  transition: background 0.15s;
}
```

And remove the `.nav-dropdown-icon` rule (lines 189-194).

**Step 3: Verify landing page loads correctly**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds, no errors

**Step 4: Commit**

```bash
git add frontend/app/landing/page.tsx frontend/app/landing/landing.css
git commit -m "fix: remove emoji icons from landing page dropdown"
```

---

## Task 2: Redesign TopNav with Dropdown Menus

**Files:**
- Modify: `frontend/components/shared/TopNav.tsx`

**Step 1: Replace the entire TopNav component**

The current TopNav renders flat links from a `navItems` array. Replace with a new structure that has:
- **Uploads** dropdown (Drag & Drop → `/uploads/drag-drop`, Integrations → `/integrations`)
- **Documents** direct link → `/documents`
- **Co-Work** direct link → `/co-work`
- **More** dropdown (Training Videos (Coming Soon) → `/training-guides`, Knowledge Gaps → `/knowledge-gaps`, Analytics → `/analytics` (admin), Inventory → `/inventory`)

```tsx
'use client'

import React, { useState, useRef, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

interface TopNavProps {
  userName?: string
  onNewChat?: () => void
}

interface DropdownItem {
  label: string
  href: string
  description?: string
  adminOnly?: boolean
  comingSoon?: boolean
}

interface NavItem {
  id: string
  label: string
  href?: string
  adminOnly?: boolean
  dropdown?: DropdownItem[]
}

const font = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

export default function TopNav({ userName = 'User', onNewChat }: TopNavProps) {
  const pathname = usePathname()
  const { user: authUser, logout } = useAuth()
  const isAdmin = authUser?.role === 'admin'
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)
  const dropdownTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const navItems: NavItem[] = [
    {
      id: 'Uploads',
      label: 'uploads',
      dropdown: [
        { label: 'Drag & Drop', href: '/uploads/drag-drop', description: 'Upload files directly to your knowledge base' },
        { label: 'Integrations', href: '/integrations', description: 'Connect tools and services', adminOnly: true },
      ],
    },
    { id: 'Documents', label: 'documents', href: '/documents' },
    { id: 'Co-Work', label: 'co-work', href: '/co-work' },
    {
      id: 'More',
      label: 'more',
      dropdown: [
        { label: 'Training Videos', href: '/training-guides', description: 'Learn how to use 2nd Brain', comingSoon: true },
        { label: 'Knowledge Gaps', href: '/knowledge-gaps', description: 'Identify missing knowledge' },
        { label: 'Analytics', href: '/analytics', description: 'Usage and insights', adminOnly: true },
        { label: 'Inventory', href: '/inventory', description: 'Data inventory overview' },
      ],
    },
  ]

  const isActive = (item: NavItem) => {
    if (item.href) {
      if (item.href === '/co-work') return pathname === '/co-work'
      return pathname?.startsWith(item.href)
    }
    if (item.dropdown) {
      return item.dropdown.some(d => pathname?.startsWith(d.href))
    }
    return false
  }

  const handleDropdownEnter = (id: string) => {
    if (dropdownTimeoutRef.current) clearTimeout(dropdownTimeoutRef.current)
    setOpenDropdown(id)
  }

  const handleDropdownLeave = () => {
    dropdownTimeoutRef.current = setTimeout(() => setOpenDropdown(null), 150)
  }

  useEffect(() => {
    return () => {
      if (dropdownTimeoutRef.current) clearTimeout(dropdownTimeoutRef.current)
    }
  }, [])

  const filterDropdown = (items: DropdownItem[]) =>
    isAdmin ? items : items.filter(i => !i.adminOnly)

  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 32px',
      height: '60px',
      backgroundColor: '#FFFFFF',
      borderBottom: '1px solid #F0EEEC',
      fontFamily: font,
    }}>
      {/* Left: Logo */}
      <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
        <Image src="/owl.png" alt="2nd Brain" width={42} height={42} style={{ objectFit: 'contain' }} />
        <span style={{ fontWeight: 700, fontSize: '17px', color: '#2D2D2D', letterSpacing: '-0.3px' }}>
          2nd Brain
        </span>
      </Link>

      {/* Center: Nav */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {navItems.map((item) => {
          const active = isActive(item)

          if (item.dropdown) {
            const visibleDropdown = filterDropdown(item.dropdown)
            if (visibleDropdown.length === 0) return null

            return (
              <div
                key={item.id}
                style={{ position: 'relative' }}
                onMouseEnter={() => handleDropdownEnter(item.id)}
                onMouseLeave={handleDropdownLeave}
              >
                <button
                  style={{
                    padding: '7px 16px',
                    borderRadius: '8px',
                    fontSize: '14.5px',
                    fontWeight: active ? 600 : 400,
                    color: active ? '#C9A598' : '#6B6B6B',
                    backgroundColor: active ? '#FBF4F1' : 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    textTransform: 'lowercase' as const,
                    fontFamily: font,
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      e.currentTarget.style.backgroundColor = '#F7F5F3'
                      e.currentTarget.style.color = '#2D2D2D'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      e.currentTarget.style.backgroundColor = 'transparent'
                      e.currentTarget.style.color = '#6B6B6B'
                    }
                  }}
                >
                  {item.label}
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {openDropdown === item.id && (
                  <div style={{
                    position: 'absolute',
                    top: '100%',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    marginTop: '4px',
                    minWidth: '240px',
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #F0EEEC',
                    borderRadius: '12px',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04)',
                    padding: '6px',
                    zIndex: 200,
                  }}>
                    {visibleDropdown.map((dropItem) => (
                      <Link
                        key={dropItem.href}
                        href={dropItem.comingSoon ? '#' : dropItem.href}
                        onClick={(e) => {
                          if (dropItem.comingSoon) e.preventDefault()
                          else setOpenDropdown(null)
                        }}
                        style={{
                          display: 'block',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          textDecoration: 'none',
                          transition: 'background 0.15s',
                          opacity: dropItem.comingSoon ? 0.5 : 1,
                          cursor: dropItem.comingSoon ? 'default' : 'pointer',
                        }}
                        onMouseEnter={(e) => { if (!dropItem.comingSoon) e.currentTarget.style.backgroundColor = '#F7F5F3' }}
                        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
                      >
                        <div style={{ fontSize: '13.5px', fontWeight: 500, color: '#2D2D2D', marginBottom: '2px' }}>
                          {dropItem.label}
                          {dropItem.comingSoon && (
                            <span style={{
                              fontSize: '10px',
                              fontWeight: 600,
                              color: '#C9A598',
                              backgroundColor: '#FBF4F1',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              marginLeft: '8px',
                              textTransform: 'uppercase',
                              letterSpacing: '0.5px',
                            }}>
                              coming soon
                            </span>
                          )}
                        </div>
                        {dropItem.description && (
                          <div style={{ fontSize: '12px', color: '#9A9A9A', lineHeight: 1.4 }}>
                            {dropItem.description}
                          </div>
                        )}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )
          }

          // Direct link
          return (
            <Link
              key={item.id}
              href={item.href!}
              style={{
                padding: '7px 16px',
                borderRadius: '8px',
                fontSize: '14.5px',
                fontWeight: active ? 600 : 400,
                color: active ? '#C9A598' : '#6B6B6B',
                backgroundColor: active ? '#FBF4F1' : 'transparent',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
                textTransform: 'lowercase' as const,
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = '#F7F5F3'
                  e.currentTarget.style.color = '#2D2D2D'
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = '#6B6B6B'
                }
              }}
            >
              {item.label}
            </Link>
          )
        })}
      </div>

      {/* Right: User menu (unchanged) */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            border: '1px solid #F0EEEC',
            borderRadius: '8px',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            transition: 'all 0.15s',
            fontFamily: font,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#FAF9F7' }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
        >
          <div style={{ width: '28px', height: '28px', borderRadius: '50%', overflow: 'hidden', border: '1.5px solid #F0EEEC' }}>
            <Image src="/Maya.png" alt="User" width={28} height={28} />
          </div>
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#2D2D2D' }}>
            {userName}
          </span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#9A9A9A" strokeWidth="2" strokeLinecap="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {showUserMenu && (
          <>
            <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setShowUserMenu(false)} />
            <div style={{
              position: 'absolute',
              right: 0,
              top: '100%',
              marginTop: '6px',
              width: '180px',
              backgroundColor: '#FFFFFF',
              border: '1px solid #F0EEEC',
              borderRadius: '10px',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
              padding: '4px',
              zIndex: 100,
            }}>
              <Link
                href="/settings"
                onClick={() => setShowUserMenu(false)}
                style={{
                  display: 'block',
                  padding: '10px 12px',
                  fontSize: '13px',
                  color: '#2D2D2D',
                  textDecoration: 'none',
                  borderRadius: '8px',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F7F5F3' }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
              >
                settings
              </Link>
              <div style={{ height: '1px', backgroundColor: '#F0EEEC', margin: '4px 0' }} />
              <button
                onClick={() => { setShowUserMenu(false); logout() }}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px 12px',
                  fontSize: '13px',
                  color: '#D97B7B',
                  textAlign: 'left',
                  border: 'none',
                  backgroundColor: 'transparent',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                  fontFamily: font,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#FDF2F2' }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
              >
                log out
              </button>
            </div>
          </>
        )}
      </div>
    </nav>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/components/shared/TopNav.tsx
git commit -m "feat: redesign top nav with dropdown menus (Uploads, More)"
```

---

## Task 3: Redesign Sidebar to Match New Nav

**Files:**
- Modify: `frontend/components/shared/Sidebar.tsx`

**Step 1: Update the Sidebar menu items and structure**

The sidebar needs to match the new nav structure:
- **Uploads** section (expandable): Drag & Drop, Integrations
- **Documents** link
- **Co-Work** link (with chat history below it)
- **More** section (expandable): Training Videos (coming soon), Knowledge Gaps, Analytics, Inventory

Key changes:
1. Replace `allMenuItems` array with new grouped structure
2. Add collapsible section headers for "Uploads" and "More"
3. Move chat history to show under "Co-Work" instead of "ChatBot"
4. Update `getActiveItem()` to recognize new routes (`/co-work`, `/uploads/drag-drop`)
5. Change logo link from `/chat` to `/co-work`
6. Add new SVG icon for "Co-Work" (combination of chat + research):
   ```tsx
   case 'cowork':
     return (
       <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
         <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
         <circle cx="12" cy="10" r="1" />
         <circle cx="8" cy="10" r="1" />
         <circle cx="16" cy="10" r="1" />
       </svg>
     )
   ```
7. Add new SVG icon for "Upload" (upload arrow):
   ```tsx
   case 'upload':
     return (
       <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
         <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
         <polyline points="17 8 12 3 7 8" />
         <line x1="12" y1="3" x2="12" y2="15" />
       </svg>
     )
   ```

**Step 2: Update chat history condition**

Change from:
```tsx
const showChatHistory = currentActive === 'ChatBot' && (conversations.length > 0 || onNewChat)
```
To:
```tsx
const showChatHistory = currentActive === 'Co-Work' && (conversations.length > 0 || onNewChat)
```

**Step 3: Commit**

```bash
git add frontend/components/shared/Sidebar.tsx
git commit -m "feat: update sidebar to match new nav structure"
```

---

## Task 4: Create Full-Screen Drag & Drop Upload Page

**Files:**
- Create: `frontend/app/uploads/drag-drop/page.tsx`

**Step 1: Create the upload page**

This page needs:
1. Full-screen drag-drop zone with dashed border
2. Click-to-upload alternative (hidden file input)
3. File list with upload progress per file
4. Calls `POST /api/documents` with multipart/form-data
5. Toast notification on completion
6. Post-upload: "Add More" button (resets state) + "Go to Documents" button (navigates)
7. Uses warm design language (#C9A598 accent, Avenir font, #FAF9F7 bg)
8. Supported file types: PDF, DOC, DOCX, TXT, CSV, TSV, XLSX, XLS, PPTX, PPT, RTF, JSON, XML, HTML, MD, PNG, JPG, JPEG, GIF, MP4, MOV, WAV, MP3, M4A, WEBM, ZIP

Key UI structure:
```
┌──────────────────────────────────────────┐
│  TopNav                                   │
├──────────────────────────────────────────┤
│                                           │
│   ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐   │
│   │                                   │   │
│   │     ↑  Upload icon               │   │
│   │     Drag & drop files here       │   │
│   │     or click to browse           │   │
│   │     Supported: PDF, DOCX, ...    │   │
│   │                                   │   │
│   └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘   │
│                                           │
│   [File list with progress bars]          │
│                                           │
│   [Add More]  [Go to Documents →]         │
│                                           │
└──────────────────────────────────────────┘
```

The page should:
- Use `useAuth()` for auth token
- Use `axios.post` to `${API_BASE}/documents` with FormData
- Track upload state: `idle` → `uploading` → `complete` → `idle`
- Show a success toast/banner on completion
- Accept multiple files at once
- Show individual file progress (name, size, status icon)

**Step 2: Create directory and verify**

Run: `mkdir -p frontend/app/uploads/drag-drop`
Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/app/uploads/drag-drop/page.tsx
git commit -m "feat: add full-screen drag-and-drop upload page"
```

---

## Task 5: Create Co-Work Page (3-Panel Layout)

**Files:**
- Create: `frontend/app/co-work/page.tsx`
- Create: `frontend/components/co-work/CoWorkChat.tsx`
- Create: `frontend/components/co-work/CoWorkPlan.tsx`
- Create: `frontend/components/co-work/CoWorkContext.tsx`

This is the largest task. The 3-panel layout:

```
┌──────────────────────────────────────────────────────────┐
│  TopNav                                                   │
├────────────────┬──────────────────┬───────────────────────┤
│  Chat (~40%)   │  Plan (~30%)     │  Context (~30%)       │
│                │                  │                       │
│  [Messages]    │  Initial context │  Research Brief       │
│                │    ● Step 1 ✓    │  ─────────────────    │
│                │    ● Step 2 ✓    │  Key findings...      │
│                │    ● Step 3 ◐    │                       │
│                │                  │  RAG Thinking         │
│                │  Deep analysis   │  ─────────────────    │
│                │    ● Step 4      │  Searching KB...      │
│                │    ● Step 5      │  Found 5 sources      │
│                │                  │  Checking journals... │
│                │  Follow-up       │  Querying repro...    │
│                │    ○ Step 6      │                       │
│                │    ○ Step 7      │  Sources              │
│  ┌──────────┐ │                  │  ─────────────────    │
│  │ Reply... │ │                  │  [Source cards]        │
│  └──────────┘ │                  │                       │
└────────────────┴──────────────────┴───────────────────────┘
```

### Task 5a: Co-Work Page Shell (`co-work/page.tsx`)

Main page that:
1. Manages session state (create/load research sessions via `/api/co-researcher/sessions`)
2. Manages conversation state (create/load via `/api/chat/conversations`)
3. Renders 3 panels side by side with `display: flex`
4. Passes state/callbacks to each panel
5. Has session list in a collapsible left drawer

### Task 5b: Chat Panel (`CoWorkChat.tsx`)

Port from `ChatInterface.tsx` — extract the chat functionality:
1. Message list with markdown rendering (ReactMarkdown + remarkGfm)
2. SSE streaming via `fetch` to `/api/search/stream`
3. Also integrate `/api/co-researcher/sessions/{id}/messages/stream` for research queries
4. File attachment support (hidden input, drag-drop on message area)
5. Conversation history sidebar (collapsible)
6. Source citation rendering (`[[SOURCE:name:id:url]]` pattern)
7. Welcome cards for empty state
8. Voice input (optional, from existing ChatInterface)

The chat panel decides routing:
- If a research session is active → use co-researcher stream endpoint
- If in general chat mode → use search/stream endpoint

### Task 5c: Plan Panel (`CoWorkPlan.tsx`)

Shows research plan from the active session:
1. Reads `research_plan` JSON from session data
2. Groups steps into sections (from SSE `action` events)
3. Status dots:
   - Green filled circle: complete
   - Yellow/amber half circle: in-progress
   - Gray empty circle: pending
4. Updates in real-time from SSE `action` events
5. Empty state: "Start a conversation to generate a research plan"
6. Clicking a step scrolls the chat to the relevant message

Plan structure mirrors image reference:
```json
{
  "sections": [
    {
      "title": "Initial context gathering",
      "steps": [
        { "text": "Review submitted items", "status": "complete" },
        { "text": "Search knowledge base", "status": "complete" },
        { "text": "Cross-reference data", "status": "in_progress" }
      ]
    },
    {
      "title": "Deep analysis",
      "steps": [...]
    }
  ]
}
```

### Task 5d: Context Panel (`CoWorkContext.tsx`)

Right panel with two collapsible sections:

**1. Research Brief** (top):
- Heading + description from `research_brief` JSON
- Key points as bullet list
- Source counts
- Updated after each assistant response

**2. RAG Thinking** (bottom, auto-scrolling):
- Shows each retrieval step as it happens via SSE:
  - `action: searching_kb` → "Searching knowledge base..."
  - `action: searching_pubmed` → "Searching PubMed..."
  - `action: searching_journals` → "Querying journal database..."
  - `action: searching_experiments` → "Checking reproducibility archive..."
  - `context_update` → Show found sources count
- Each step has a status indicator (spinner → checkmark)
- Source cards at the bottom (document title, score, preview)
- Indicates data source clearly: "From: Knowledge Base", "From: Journal DB", "From: Reproducibility Archive", "From: PubMed"

**Step: Create directories, write all 4 files, verify build**

```bash
mkdir -p frontend/components/co-work
# Write all files
cd frontend && npm run build 2>&1 | tail -20
```

**Step: Commit**

```bash
git add frontend/app/co-work/ frontend/components/co-work/
git commit -m "feat: add co-work page with 3-panel layout (chat, plan, context)"
```

---

## Task 6: Backend — Extend RAG to Search Journal + Reproducibility Data

**Files:**
- Modify: `backend/services/co_researcher_service.py`
- Modify: `backend/app_v2.py` (search/stream endpoint)

**Step 1: Add journal and reproducibility search to co-researcher service**

In `co_researcher_service.py`, add two new helper methods:

```python
def _search_journals(self, query: str, db, limit=5) -> List[Dict]:
    """Search JournalProfile table for relevant journals."""
    from database.models import JournalProfile
    from sqlalchemy import or_

    journals = db.query(JournalProfile).filter(
        or_(
            JournalProfile.name.ilike(f'%{query}%'),
            JournalProfile.primary_field.ilike(f'%{query}%'),
            JournalProfile.primary_subfield.ilike(f'%{query}%'),
        )
    ).order_by(JournalProfile.composite_score.desc()).limit(limit).all()

    return [{
        'source_type': 'journal_database',
        'title': j.name,
        'field': j.primary_field,
        'subfield': j.primary_subfield,
        'h_index': j.h_index,
        'impact_factor': j.impact_factor,
        'tier': j.computed_tier,
        'sjr_quartile': j.sjr_quartile,
    } for j in journals]

def _search_experiments(self, query: str, db, limit=5) -> List[Dict]:
    """Search FailedExperiment table for relevant experiments."""
    from database.models import FailedExperiment
    from sqlalchemy import or_

    experiments = db.query(FailedExperiment).filter(
        or_(
            FailedExperiment.title.ilike(f'%{query}%'),
            FailedExperiment.hypothesis.ilike(f'%{query}%'),
            FailedExperiment.what_failed.ilike(f'%{query}%'),
            FailedExperiment.field.ilike(f'%{query}%'),
        )
    ).order_by(FailedExperiment.upvotes.desc()).limit(limit).all()

    return [{
        'source_type': 'reproducibility_archive',
        'title': e.title,
        'field': e.field,
        'category': e.category,
        'hypothesis': e.hypothesis,
        'what_failed': e.what_failed,
        'lessons_learned': e.lessons_learned,
        'upvotes': e.upvotes,
    } for e in experiments]
```

**Step 2: Integrate into the streaming message handler**

In the `handle_message_stream()` method, after the KB search and PubMed search, add:

```python
# Search journal database
yield f"event: action\ndata: {json.dumps({'type': 'searching_journals', 'text': 'Querying journal database...'})}\n\n"
journal_results = self._search_journals(query, db)

# Search reproducibility archive
yield f"event: action\ndata: {json.dumps({'type': 'searching_experiments', 'text': 'Checking reproducibility archive...'})}\n\n"
experiment_results = self._search_experiments(query, db)

# Include in context_update
yield f"event: context_update\ndata: {json.dumps({'documents': kb_results, 'pubmed_papers': pubmed_results, 'journals': journal_results, 'experiments': experiment_results})}\n\n"
```

**Step 3: Add "thinking" events to the search/stream endpoint in app_v2.py**

In the streaming search handler, add SSE events before each major step:

```python
yield f"event: thinking\ndata: {json.dumps({'step': 'expanding_query', 'text': 'Expanding query...'})}\n\n"
# ... query expansion ...

yield f"event: thinking\ndata: {json.dumps({'step': 'searching_kb', 'text': 'Searching knowledge base...', 'detail': f'Found {len(results)} sources'})}\n\n"

yield f"event: thinking\ndata: {json.dumps({'step': 'reranking', 'text': 'Reranking results...'})}\n\n"
```

**Step 4: Add journal/experiment context to the GPT prompt**

When building the context for the LLM response, append journal and experiment data:

```python
if journal_results:
    context += "\n\n--- JOURNAL DATABASE ---\n"
    for j in journal_results:
        context += f"Journal: {j['title']} (Field: {j['field']}, Impact Factor: {j['impact_factor']}, Tier: {j['tier']})\n"

if experiment_results:
    context += "\n\n--- REPRODUCIBILITY ARCHIVE ---\n"
    for e in experiment_results:
        context += f"Experiment: {e['title']}\nHypothesis: {e['hypothesis']}\nWhat Failed: {e['what_failed']}\nLessons: {e['lessons_learned']}\n\n"
```

**Step 5: Update the system prompt to explain source attribution**

Add to the system prompt:
```
When citing information, ALWAYS indicate the source:
- [KB] for knowledge base documents
- [PubMed] for academic papers
- [Journal DB] for journal database entries
- [Repro Archive] for reproducibility archive experiments
```

**Step 6: Commit**

```bash
git add backend/services/co_researcher_service.py backend/app_v2.py
git commit -m "feat: extend RAG to search journal profiles and failed experiments"
```

---

## Task 7: Add Redirects for Old Routes

**Files:**
- Create: `frontend/app/chat/page.tsx` (overwrite)
- Create: `frontend/app/co-researcher/page.tsx` (overwrite — keep backup for public route)

**Step 1: Replace /chat page with redirect**

```tsx
import { redirect } from 'next/navigation'

export default function ChatPage() {
  redirect('/co-work')
}
```

**Step 2: Replace /co-researcher page with redirect**

The current co-researcher code needs to be preserved for the public `/research-reproducibility` route (Task 8). So:
1. Copy `frontend/app/co-researcher/page.tsx` → keep content for Task 8
2. Replace with redirect:

```tsx
import { redirect } from 'next/navigation'

export default function CoResearcherPage() {
  redirect('/co-work')
}
```

**Step 3: Commit**

```bash
git add frontend/app/chat/page.tsx frontend/app/co-researcher/page.tsx
git commit -m "feat: redirect /chat and /co-researcher to /co-work"
```

---

## Task 8: Public Research-Reproducibility Route

**Files:**
- Create: `frontend/app/research-reproducibility/page.tsx`
- Modify: `frontend/contexts/AuthContext.tsx:50`

**Step 1: Create the public page**

Copy the original co-researcher page content to `frontend/app/research-reproducibility/page.tsx`. This is the existing research translator pipeline (upload → analyze → translate → stress test → results).

**Step 2: Add to public routes in AuthContext**

In `frontend/contexts/AuthContext.tsx` line 50, the `PUBLIC_ROUTES` array already includes `/co-researcher`. Add `/research-reproducibility`:

```tsx
const PUBLIC_ROUTES = ['/', '/login', '/signup', '/forgot-password', '/reset-password', '/verify-email', '/verification-pending', '/terms', '/privacy', '/landing', '/product', '/high-impact-journal', '/co-researcher', '/reproducibility-archive', '/research-reproducibility']
```

**Step 3: Commit**

```bash
git add frontend/app/research-reproducibility/page.tsx frontend/contexts/AuthContext.tsx
git commit -m "feat: add public research-reproducibility route (no login required)"
```

---

## Task 9: Final Verification & Cleanup

**Step 1: Full build check**

```bash
cd frontend && npm run build 2>&1 | tail -30
```

Expected: Build succeeds with no errors.

**Step 2: Manual smoke test checklist**

- [ ] Landing page: "other domains" dropdown has no emoji icons
- [ ] Login → TopNav shows: Uploads (hover: Drag & Drop, Integrations), Documents, Co-Work, More (hover: Training Videos, Knowledge Gaps, Analytics, Inventory)
- [ ] Sidebar matches TopNav structure
- [ ] `/uploads/drag-drop` loads full-screen upload zone
- [ ] Upload a file → notification appears → "Add More" and "Go to Documents" buttons work
- [ ] `/co-work` loads 3-panel layout
- [ ] Chat panel: can send message, streaming works, sources show
- [ ] Plan panel: shows research plan steps with status dots
- [ ] Context panel: shows RAG thinking steps + research brief
- [ ] `/chat` redirects to `/co-work`
- [ ] `/co-researcher` redirects to `/co-work`
- [ ] `/research-reproducibility` loads without login
- [ ] Admin user sees "Integrations" under Uploads and "Analytics" under More
- [ ] Non-admin user doesn't see admin-only items

**Step 3: Final commit with all fixes**

```bash
git add -A
git commit -m "chore: cleanup and verify nav redesign + co-work"
```

---

## Execution Order

| # | Task | Dependencies | Estimated Complexity |
|---|------|-------------|---------------------|
| 1 | Landing page icon removal | None | Small |
| 2 | TopNav redesign | None | Medium |
| 3 | Sidebar redesign | Task 2 (same nav structure) | Medium |
| 4 | Drag & Drop upload page | Task 2 (nav links to it) | Medium |
| 5 | Co-Work 3-panel page | Task 2, 3 (nav links to it) | Large |
| 6 | Backend RAG extension | Task 5 (co-work consumes it) | Medium |
| 7 | Route redirects | Task 5, 8 (need co-work + public route first) | Small |
| 8 | Public research-reproducibility | Task 7 (redirects reference it) | Small |
| 9 | Final verification | All tasks | Small |

Tasks 1, 2, 4, 6 can run in parallel. Tasks 3 depends on 2. Task 5 depends on 2+3. Tasks 7+8 depend on 5.
