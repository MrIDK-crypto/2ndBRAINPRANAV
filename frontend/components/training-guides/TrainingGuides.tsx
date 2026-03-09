'use client'

import React, { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'
import TopNav from '../shared/TopNav'
import { useAuth } from '@/contexts/AuthContext'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

const T = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  headerBg: '#F7F5F3',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
  error: '#D97B7B',
  amber: '#D4A853',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface TrainingGuide {
  id: string
  title: string
  description: string
  source_document_ids: string[]
  content_outline: string | null
  instructions: string | null
  video_style: string
  status: string
  progress_percent: number
  current_step: string | null
  error_message: string | null
  video_path: string | null
  slides_path: string | null
  slides_pdf_path: string | null
  created_at: string
  completed_at: string | null
}

interface Idea {
  title: string
  description: string
  document_ids: string[]
  documents: { id: string; title: string }[]
  suggested_outline: string
}

const VIDEO_STYLES = [
  { value: 'classic', label: 'Classic' },
  { value: 'whiteboard', label: 'Whiteboard' },
  { value: 'kawaii', label: 'Kawaii' },
  { value: 'anime', label: 'Anime' },
  { value: 'watercolor', label: 'Watercolor' },
  { value: 'retro_print', label: 'Retro Print' },
  { value: 'heritage', label: 'Heritage' },
  { value: 'paper_craft', label: 'Paper Craft' },
  { value: 'auto', label: 'Auto Select' },
]

type View = 'home' | 'edit-idea' | 'outline' | 'detail'

export default function TrainingGuides() {
  const { user, token } = useAuth()
  const [view, setView] = useState<View>('home')
  const [guides, setGuides] = useState<TrainingGuide[]>([])
  const [ideas, setIdeas] = useState<Idea[]>([])
  const [loading, setLoading] = useState(true)
  const [ideasLoading, setIdeasLoading] = useState(false)
  const [activeGuide, setActiveGuide] = useState<TrainingGuide | null>(null)

  // Edit idea state
  const [editIdea, setEditIdea] = useState<Idea | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editOutline, setEditOutline] = useState('')
  const [editDocIds, setEditDocIds] = useState<string[]>([])
  const [editDocs, setEditDocs] = useState<{ id: string; title: string }[]>([])
  const [videoStyle, setVideoStyle] = useState('classic')
  const [instructions, setInstructions] = useState('')
  const [creating, setCreating] = useState(false)
  const [confirming, setConfirming] = useState(false)

  // All KB docs for the doc editor
  const [allDocs, setAllDocs] = useState<{ id: string; title: string }[]>([])
  const [docSearch, setDocSearch] = useState('')
  const [showDocPicker, setShowDocPicker] = useState(false)

  const pollRef = useRef<NodeJS.Timeout | null>(null)
  const headers = { Authorization: `Bearer ${token}` }

  // ── Fetch guides ──
  const fetchGuides = useCallback(async () => {
    if (!token) return
    try {
      const res = await axios.get(`${API_BASE}/training-guides`, { headers })
      setGuides(res.data.guides || [])
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  useEffect(() => { fetchGuides() }, [fetchGuides])

  // ── Fetch ideas ──
  const fetchIdeas = useCallback(async () => {
    if (!token) return
    setIdeasLoading(true)
    try {
      const res = await axios.post(`${API_BASE}/training-guides/suggest-ideas`, {}, { headers })
      setIdeas(res.data.ideas || [])
    } catch (e) { console.error(e) }
    finally { setIdeasLoading(false) }
  }, [token])

  useEffect(() => { if (token) fetchIdeas() }, [token])

  // ── Fetch all KB docs ──
  const fetchAllDocs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/documents?limit=200&status=confirmed`, { headers })
      const docs = (res.data.documents || []).map((d: any) => ({ id: d.id, title: d.title || 'Untitled' }))
      setAllDocs(docs)
      // Also try classified if confirmed returns empty
      if (docs.length === 0) {
        const res2 = await axios.get(`${API_BASE}/documents?limit=200`, { headers })
        setAllDocs((res2.data.documents || []).map((d: any) => ({ id: d.id, title: d.title || 'Untitled' })))
      }
    } catch (e) { console.error(e) }
  }

  // ── Open idea for editing ──
  const openIdea = (idea: Idea) => {
    setEditIdea(idea)
    setEditTitle(idea.title)
    setEditDescription(idea.description)
    setEditOutline(idea.suggested_outline)
    setEditDocIds(idea.document_ids)
    setEditDocs(idea.documents)
    setVideoStyle('classic')
    setInstructions('')
    setShowDocPicker(false)
    setView('edit-idea')
    fetchAllDocs()
  }

  // ── Create guide from edited idea ──
  const handleCreateFromIdea = async () => {
    if (!editTitle.trim() || editDocIds.length === 0) return
    setCreating(true)
    try {
      const res = await axios.post(`${API_BASE}/training-guides/outline`, {
        title: editTitle.trim(),
        description: editDescription.trim(),
        source_document_ids: editDocIds,
        instructions: instructions.trim() || undefined,
        video_style: videoStyle,
      }, { headers })
      const guide = res.data.guide as TrainingGuide
      // Use the user's edited outline if they changed it, otherwise use LLM outline
      setActiveGuide(guide)
      setEditOutline(editOutline || guide.content_outline || '')
      setView('outline')
    } catch (e: any) {
      alert(e.response?.data?.error || 'Failed to generate outline')
    } finally { setCreating(false) }
  }

  // ── Confirm and generate ──
  const handleConfirmGenerate = async () => {
    if (!activeGuide) return
    setConfirming(true)
    try {
      const res = await axios.post(
        `${API_BASE}/training-guides/${activeGuide.id}/confirm`,
        { content_outline: editOutline, video_style: videoStyle },
        { headers }
      )
      setActiveGuide(res.data.guide)
      setView('detail')
      startPolling(res.data.guide.id)
      fetchGuides()
    } catch (e: any) {
      alert(e.response?.data?.error || 'Failed to start generation')
    } finally { setConfirming(false) }
  }

  // ── Polling ──
  const startPolling = (id: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const res = await axios.get(`${API_BASE}/training-guides/${id}/status`, { headers })
        setActiveGuide(prev => prev ? { ...prev, ...res.data } : prev)
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          clearInterval(pollRef.current!); pollRef.current = null; fetchGuides()
        }
      } catch (e) { console.error(e) }
    }, 5000)
  }
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  // ── View guide detail ──
  const viewGuide = (guide: TrainingGuide) => {
    setActiveGuide(guide)
    if (guide.status === 'draft') {
      setEditOutline(guide.content_outline || '')
      setView('outline')
    } else {
      setView('detail')
      if (guide.status === 'generating') startPolling(guide.id)
    }
  }

  const deleteGuide = async (id: string) => {
    if (!confirm('Delete this training guide?')) return
    try {
      await axios.delete(`${API_BASE}/training-guides/${id}`, { headers })
      setGuides(prev => prev.filter(g => g.id !== id))
      if (activeGuide?.id === id) { setActiveGuide(null); setView('home') }
    } catch (e) { console.error(e) }
  }

  // ── Toggle doc in selection ──
  const toggleDoc = (docId: string, docTitle: string) => {
    if (editDocIds.includes(docId)) {
      setEditDocIds(prev => prev.filter(id => id !== docId))
      setEditDocs(prev => prev.filter(d => d.id !== docId))
    } else {
      setEditDocIds(prev => [...prev, docId])
      setEditDocs(prev => [...prev, { id: docId, title: docTitle }])
    }
  }

  const filteredAllDocs = allDocs.filter(d =>
    !docSearch || d.title.toLowerCase().includes(docSearch.toLowerCase())
  )

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, { bg: string; text: string }> = {
      draft: { bg: `${T.amber}20`, text: T.amber },
      generating: { bg: `${T.primary}20`, text: T.primary },
      completed: { bg: `${T.success}20`, text: T.success },
      failed: { bg: `${T.error}20`, text: T.error },
    }
    const c = colors[status] || colors.draft
    return (
      <span style={{
        padding: '3px 10px', borderRadius: '6px', fontSize: '11px',
        fontWeight: 600, backgroundColor: c.bg, color: c.text, textTransform: 'capitalize',
      }}>{status}</span>
    )
  }

  const BackButton = ({ onClick }: { onClick: () => void }) => (
    <button onClick={onClick} style={{
      background: 'none', border: 'none', cursor: 'pointer', color: T.textSecondary,
      fontSize: '13px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '4px', fontFamily: FONT,
    }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
      Back
    </button>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: T.pageBg, fontFamily: FONT }}>
      <TopNav userName={user?.full_name?.split(' ')[0] || 'User'} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{
          padding: '24px 32px', borderBottom: `1px solid ${T.border}`, backgroundColor: T.headerBg,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: T.textPrimary, fontFamily: FONT }}>
              Training Guides
            </h1>
            <p style={{ fontSize: '14px', color: T.textSecondary, marginTop: '4px' }}>
              Auto-generated video and slide deck ideas from your knowledge base
            </p>
          </div>
          {view === 'home' && (
            <button onClick={() => { fetchIdeas() }} disabled={ideasLoading}
              style={{
                padding: '9px 18px', borderRadius: '10px', border: `1px solid ${T.border}`,
                backgroundColor: T.cardBg, color: T.textSecondary, fontSize: '13px', fontWeight: 500,
                cursor: 'pointer', fontFamily: FONT, display: 'flex', alignItems: 'center', gap: '6px',
                opacity: ideasLoading ? 0.5 : 1,
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
              {ideasLoading ? 'Analyzing...' : 'Refresh Ideas'}
            </button>
          )}
        </div>

        <div style={{ flex: 1, padding: '24px 32px', overflow: 'auto' }}>

          {/* ══ HOME VIEW ══ */}
          {view === 'home' && (
            <div>
              {/* Suggested Ideas */}
              <div style={{ marginBottom: '32px' }}>

                {ideasLoading ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '14px' }}>
                    {[1,2,3].map(i => (
                      <div key={i} style={{ height: '140px', borderRadius: '12px', backgroundColor: T.border, opacity: 0.5, animation: 'tg-pulse 1.5s ease-in-out infinite' }} />
                    ))}
                  </div>
                ) : ideas.length === 0 ? (
                  <div style={{ padding: '40px', textAlign: 'center', color: T.textMuted, fontSize: '14px' }}>
                    No ideas yet — upload some documents to your knowledge base first
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '14px' }}>
                    {ideas.map((idea, i) => (
                      <div
                        key={i}
                        onClick={() => openIdea(idea)}
                        style={{
                          padding: '20px', borderRadius: '12px', backgroundColor: T.cardBg,
                          border: `1px solid ${T.border}`, cursor: 'pointer',
                          transition: 'border-color 0.15s, box-shadow 0.15s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = T.primary; e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.05)' }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.boxShadow = 'none' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <div style={{
                            width: '32px', height: '32px', borderRadius: '8px', backgroundColor: T.primaryLight,
                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                          }}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={T.primary} strokeWidth="2">
                              <polygon points="5 3 19 12 5 21 5 3" />
                            </svg>
                          </div>
                          <h3 style={{ fontSize: '15px', fontWeight: 600, color: T.textPrimary, margin: 0 }}>{idea.title}</h3>
                        </div>
                        <p style={{ fontSize: '13px', color: T.textSecondary, lineHeight: '1.5', marginBottom: '10px' }}>
                          {idea.description}
                        </p>
                        <div style={{ fontSize: '12px', color: T.textMuted }}>
                          {idea.document_ids.length} documents
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Existing Guides */}
              {guides.length > 0 && (
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, color: T.textPrimary, marginBottom: '4px' }}>
                    Your Training Guides
                  </h2>
                  <p style={{ fontSize: '13px', color: T.textMuted, marginBottom: '16px' }}>
                    Previously created guides
                  </p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '14px' }}>
                    {guides.map(guide => (
                      <div
                        key={guide.id}
                        onClick={() => viewGuide(guide)}
                        style={{
                          padding: '18px', borderRadius: '12px', backgroundColor: T.cardBg,
                          border: `1px solid ${T.border}`, cursor: 'pointer',
                          transition: 'border-color 0.15s',
                        }}
                        onMouseEnter={e => e.currentTarget.style.borderColor = T.primary}
                        onMouseLeave={e => e.currentTarget.style.borderColor = T.border}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <StatusBadge status={guide.status} />
                          <button onClick={e => { e.stopPropagation(); deleteGuide(guide.id) }}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.textMuted, padding: '4px' }}>
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                          </button>
                        </div>
                        <h3 style={{ fontSize: '15px', fontWeight: 600, color: T.textPrimary, marginBottom: '4px' }}>{guide.title}</h3>
                        <div style={{ fontSize: '12px', color: T.textMuted }}>
                          {guide.source_document_ids?.length || 0} docs &middot; {new Date(guide.created_at).toLocaleDateString()}
                        </div>
                        {guide.status === 'generating' && (
                          <div style={{ marginTop: '8px' }}>
                            <div style={{ height: '3px', borderRadius: '2px', backgroundColor: T.border, overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${guide.progress_percent}%`, backgroundColor: T.primary, transition: 'width 0.5s' }} />
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══ EDIT IDEA VIEW ══ */}
          {view === 'edit-idea' && editIdea && (
            <div style={{ maxWidth: '720px', margin: '0 auto' }}>
              <BackButton onClick={() => { setView('home'); setEditIdea(null) }} />

              <div style={{ padding: '28px', borderRadius: '14px', backgroundColor: T.cardBg, border: `1px solid ${T.border}` }}>
                <h2 style={{ fontSize: '20px', fontWeight: 600, color: T.textPrimary, marginBottom: '20px' }}>
                  Customize Training Guide
                </h2>

                {/* Title */}
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: T.textPrimary, marginBottom: '6px' }}>Title</label>
                <input value={editTitle} onChange={e => setEditTitle(e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: `1px solid ${T.border}`, fontSize: '14px', fontFamily: FONT, marginBottom: '16px', outline: 'none', boxSizing: 'border-box' }}
                />

                {/* Description */}
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: T.textPrimary, marginBottom: '6px' }}>Description</label>
                <textarea value={editDescription} onChange={e => setEditDescription(e.target.value)} rows={2}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: `1px solid ${T.border}`, fontSize: '14px', fontFamily: FONT, marginBottom: '16px', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
                />

                {/* Documents */}
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: T.textPrimary, marginBottom: '6px' }}>
                  Source Documents ({editDocIds.length})
                </label>

                {/* Selected docs list */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '10px' }}>
                  {editDocs.map(doc => (
                    <div key={doc.id} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 12px', borderRadius: '8px', backgroundColor: T.primaryLight,
                      fontSize: '13px', color: T.textPrimary,
                    }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                        {doc.title}
                      </span>
                      <button onClick={() => toggleDoc(doc.id, doc.title)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.textMuted, padding: '2px 6px', fontSize: '16px' }}>
                        &times;
                      </button>
                    </div>
                  ))}
                </div>

                <button onClick={() => setShowDocPicker(!showDocPicker)}
                  style={{
                    padding: '8px 14px', borderRadius: '8px', border: `1px dashed ${T.border}`,
                    backgroundColor: 'transparent', color: T.textSecondary, fontSize: '13px',
                    cursor: 'pointer', fontFamily: FONT, marginBottom: showDocPicker ? '8px' : '16px',
                    width: '100%', textAlign: 'center',
                  }}>
                  {showDocPicker ? 'Hide document picker' : '+ Add or remove documents'}
                </button>

                {showDocPicker && (
                  <div style={{ marginBottom: '16px' }}>
                    <input value={docSearch} onChange={e => setDocSearch(e.target.value)} placeholder="Search documents..."
                      style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: `1px solid ${T.border}`, fontSize: '13px', fontFamily: FONT, marginBottom: '6px', outline: 'none', boxSizing: 'border-box' }}
                    />
                    <div style={{ maxHeight: '180px', overflowY: 'auto', border: `1px solid ${T.border}`, borderRadius: '8px' }}>
                      {filteredAllDocs.map(doc => {
                        const sel = editDocIds.includes(doc.id)
                        return (
                          <div key={doc.id} onClick={() => toggleDoc(doc.id, doc.title)}
                            style={{ padding: '9px 12px', borderBottom: `1px solid ${T.border}`, cursor: 'pointer', backgroundColor: sel ? T.primaryLight : 'transparent', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ width: '16px', height: '16px', borderRadius: '4px', flexShrink: 0, border: sel ? 'none' : `2px solid ${T.border}`, backgroundColor: sel ? T.primary : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              {sel && <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#FFF" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>}
                            </div>
                            <span style={{ fontSize: '13px', color: T.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.title}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Suggested outline */}
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: T.textPrimary, marginBottom: '6px' }}>Suggested Outline (editable)</label>
                <textarea value={editOutline} onChange={e => setEditOutline(e.target.value)} rows={6}
                  style={{ width: '100%', padding: '12px 14px', borderRadius: '8px', border: `1px solid ${T.border}`, fontSize: '14px', fontFamily: FONT, lineHeight: '1.6', marginBottom: '16px', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
                />

                {/* Video style */}
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: T.textPrimary, marginBottom: '6px' }}>Video Style</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
                  {VIDEO_STYLES.map(s => (
                    <button key={s.value} onClick={() => setVideoStyle(s.value)}
                      style={{
                        padding: '6px 14px', borderRadius: '8px', fontSize: '13px', fontFamily: FONT,
                        border: `1px solid ${videoStyle === s.value ? T.primary : T.border}`,
                        backgroundColor: videoStyle === s.value ? T.primaryLight : 'transparent',
                        color: videoStyle === s.value ? T.primary : T.textSecondary,
                        cursor: 'pointer', fontWeight: videoStyle === s.value ? 600 : 400,
                      }}>
                      {s.label}
                    </button>
                  ))}
                </div>

                {/* Instructions */}
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: T.textPrimary, marginBottom: '6px' }}>Custom Instructions (optional)</label>
                <textarea value={instructions} onChange={e => setInstructions(e.target.value)} rows={2} placeholder="e.g. Focus on key findings, keep it under 5 minutes"
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: `1px solid ${T.border}`, fontSize: '14px', fontFamily: FONT, marginBottom: '20px', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
                />

                <button onClick={handleCreateFromIdea} disabled={!editTitle.trim() || editDocIds.length === 0 || creating}
                  style={{
                    width: '100%', padding: '12px', borderRadius: '10px', backgroundColor: T.primary,
                    color: '#FFF', fontSize: '15px', fontWeight: 500, border: 'none', cursor: 'pointer', fontFamily: FONT,
                    opacity: (!editTitle.trim() || editDocIds.length === 0 || creating) ? 0.5 : 1,
                  }}>
                  {creating ? 'Generating outline...' : 'Generate & Review Outline'}
                </button>
              </div>
            </div>
          )}

          {/* ══ OUTLINE REVIEW ══ */}
          {view === 'outline' && activeGuide && (
            <div style={{ maxWidth: '720px', margin: '0 auto' }}>
              <BackButton onClick={() => { setView('home'); setActiveGuide(null) }} />

              <div style={{ padding: '28px', borderRadius: '14px', backgroundColor: T.cardBg, border: `1px solid ${T.border}` }}>
                <h2 style={{ fontSize: '20px', fontWeight: 600, color: T.textPrimary, marginBottom: '6px' }}>{activeGuide.title}</h2>
                <p style={{ fontSize: '13px', color: T.textMuted, marginBottom: '20px' }}>
                  Review the final outline, then confirm to start generating your video and slides.
                </p>

                <textarea value={editOutline} onChange={e => setEditOutline(e.target.value)} rows={16}
                  style={{ width: '100%', padding: '14px', borderRadius: '10px', border: `1px solid ${T.border}`, fontSize: '14px', fontFamily: FONT, lineHeight: '1.6', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
                />

                <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
                  <button onClick={handleConfirmGenerate} disabled={confirming}
                    style={{
                      flex: 1, padding: '12px', borderRadius: '10px', backgroundColor: T.primary,
                      color: '#FFF', fontSize: '15px', fontWeight: 500, border: 'none', cursor: 'pointer', fontFamily: FONT,
                      opacity: confirming ? 0.5 : 1,
                    }}>
                    {confirming ? 'Starting...' : 'Confirm & Generate Video + Slides'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ══ DETAIL VIEW ══ */}
          {view === 'detail' && activeGuide && (
            <div style={{ maxWidth: '720px', margin: '0 auto' }}>
              <BackButton onClick={() => { setView('home'); setActiveGuide(null); if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }} />

              <div style={{ padding: '28px', borderRadius: '14px', backgroundColor: T.cardBg, border: `1px solid ${T.border}` }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h2 style={{ fontSize: '20px', fontWeight: 600, color: T.textPrimary }}>{activeGuide.title}</h2>
                  <StatusBadge status={activeGuide.status} />
                </div>

                {activeGuide.status === 'generating' && (
                  <div style={{ marginBottom: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <div style={{ width: '14px', height: '14px', borderRadius: '50%', border: `2px solid ${T.border}`, borderTopColor: T.primary, animation: 'tg-spin 0.8s linear infinite' }} />
                      <span style={{ fontSize: '14px', color: T.textPrimary, fontWeight: 500 }}>
                        {activeGuide.current_step || 'Processing...'}
                      </span>
                    </div>
                    <div style={{ height: '6px', borderRadius: '3px', backgroundColor: T.border, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${activeGuide.progress_percent}%`, backgroundColor: T.primary, borderRadius: '3px', transition: 'width 0.5s' }} />
                    </div>
                    <p style={{ fontSize: '12px', color: T.textMuted, marginTop: '6px' }}>
                      {activeGuide.progress_percent}% — video generation can take 5-15 minutes
                    </p>
                  </div>
                )}

                {activeGuide.status === 'failed' && (
                  <div style={{ padding: '14px', borderRadius: '10px', backgroundColor: `${T.error}10`, border: `1px solid ${T.error}30`, marginBottom: '20px' }}>
                    <p style={{ fontSize: '13px', color: T.error, fontWeight: 500 }}>Generation Failed</p>
                    <p style={{ fontSize: '12px', color: T.textSecondary, marginTop: '4px' }}>{activeGuide.error_message}</p>
                  </div>
                )}

                {activeGuide.status === 'completed' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    {activeGuide.video_path && (
                      <div>
                        <h3 style={{ fontSize: '15px', fontWeight: 600, color: T.textPrimary, marginBottom: '10px' }}>Video Overview</h3>
                        <video controls style={{ width: '100%', borderRadius: '10px', backgroundColor: '#000' }} src={activeGuide.video_path} />
                        <a href={`${API_BASE}/training-guides/${activeGuide.id}/video`}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginTop: '8px', padding: '8px 16px', borderRadius: '8px', backgroundColor: T.primaryLight, color: T.primary, fontSize: '13px', fontWeight: 500, textDecoration: 'none' }}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                          Download Video
                        </a>
                      </div>
                    )}
                    {(activeGuide.slides_path || activeGuide.slides_pdf_path) && (
                      <div>
                        <h3 style={{ fontSize: '15px', fontWeight: 600, color: T.textPrimary, marginBottom: '10px' }}>Slide Deck</h3>
                        <div style={{ display: 'flex', gap: '10px' }}>
                          {activeGuide.slides_path && (
                            <a href={`${API_BASE}/training-guides/${activeGuide.id}/slides?format=pptx`}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '10px 18px', borderRadius: '8px', backgroundColor: T.primaryLight, color: T.primary, fontSize: '13px', fontWeight: 500, textDecoration: 'none' }}>
                              Download PPTX
                            </a>
                          )}
                          {activeGuide.slides_pdf_path && (
                            <a href={`${API_BASE}/training-guides/${activeGuide.id}/slides?format=pdf`}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '10px 18px', borderRadius: '8px', border: `1px solid ${T.border}`, color: T.textSecondary, fontSize: '13px', fontWeight: 500, textDecoration: 'none' }}>
                              Download PDF
                            </a>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div style={{ marginTop: '20px', paddingTop: '14px', borderTop: `1px solid ${T.border}`, fontSize: '12px', color: T.textMuted, display: 'flex', gap: '20px' }}>
                  <span>{activeGuide.source_document_ids?.length || 0} source docs</span>
                  <span>Style: {activeGuide.video_style}</span>
                  {activeGuide.completed_at && <span>Completed: {new Date(activeGuide.completed_at).toLocaleString()}</span>}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes tg-spin { to { transform: rotate(360deg); } }
        @keyframes tg-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.7; } }
      `}</style>
    </div>
  )
}
