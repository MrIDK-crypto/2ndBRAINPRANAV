'use client'

import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api/shared'

// Warm coral theme (matches main app)
const theme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFE',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  statusSuccess: '#9CB896',
}

interface SharedPortalProps {
  token: string
}

interface PortalInfo {
  organization_name: string
  permissions: { documents?: boolean; chatbot?: boolean; knowledge_gaps?: boolean }
  document_count: number
  gap_count: number
}

interface SharedDocument {
  id: string
  title: string
  summary: string | null
  source_type: string
  created_at: string | null
}

interface ChatMessage {
  id: string
  text: string
  isUser: boolean
  sources?: { title: string; content_preview: string; score: number }[]
}

interface KnowledgeGap {
  id: string
  title: string
  description: string
  category: string
  status: string
  questions: { question: string; priority: string }[]
  answers: { id: string; question_index: number; answer_text: string; created_at: string }[]
  context_summary?: string
}

// Shared API helper
function sharedApi(token: string) {
  const headers: Record<string, string> = {
    'X-Share-Token': token,
    'Content-Type': 'application/json',
  }

  return {
    async get(endpoint: string) {
      const res = await fetch(`${API_BASE}${endpoint}`, { headers })
      return res.json()
    },
    async post(endpoint: string, body: Record<string, unknown>) {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      })
      return res.json()
    },
  }
}

export default function SharedPortal({ token }: SharedPortalProps) {
  const [portalInfo, setPortalInfo] = useState<PortalInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'documents' | 'chatbot' | 'knowledge-gaps'>('documents')

  const api = sharedApi(token)

  useEffect(() => {
    const loadPortal = async () => {
      try {
        const data = await api.get('/portal')
        if (data.success) {
          setPortalInfo(data.portal)
        } else {
          setError(data.error || 'Invalid or expired share link')
        }
      } catch {
        setError('Failed to load portal. The link may be invalid or expired.')
      } finally {
        setLoading(false)
      }
    }
    loadPortal()
  }, [token])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: theme.pageBg }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 40, height: 40, border: `3px solid ${theme.border}`, borderTopColor: theme.primary, borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }} />
          <p style={{ color: theme.textSecondary, fontSize: 14 }}>Loading portal...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: theme.pageBg }}>
        <div style={{ textAlign: 'center', maxWidth: 400, padding: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔗</div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: theme.textPrimary, marginBottom: 8 }}>Link Unavailable</h1>
          <p style={{ color: theme.textSecondary, fontSize: 14, lineHeight: 1.6 }}>{error}</p>
        </div>
      </div>
    )
  }

  const permissions = portalInfo?.permissions || {}
  const tabs = [
    { id: 'documents' as const, label: 'Documents', icon: '📄', enabled: permissions.documents !== false, count: portalInfo?.document_count },
    { id: 'chatbot' as const, label: 'Chatbot', icon: '💬', enabled: permissions.chatbot !== false },
    { id: 'knowledge-gaps' as const, label: 'Knowledge Gaps', icon: '🔍', enabled: permissions.knowledge_gaps !== false, count: portalInfo?.gap_count },
  ].filter(t => t.enabled)

  return (
    <div style={{ minHeight: '100vh', backgroundColor: theme.pageBg }}>
      {/* Header */}
      <div style={{ backgroundColor: theme.cardBg, borderBottom: `1px solid ${theme.border}`, padding: '16px 24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.textPrimary, margin: 0 }}>
              {portalInfo?.organization_name || 'Knowledge Portal'}
            </h1>
            <p style={{ fontSize: 13, color: theme.textMuted, margin: '4px 0 0' }}>
              Shared Knowledge Portal — Powered by 2nd Brain
            </p>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {portalInfo?.document_count !== undefined && (
              <span style={{ fontSize: 12, color: theme.textMuted, backgroundColor: theme.primaryLight, padding: '4px 10px', borderRadius: 12 }}>
                {portalInfo.document_count} documents
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ backgroundColor: theme.cardBg, borderBottom: `1px solid ${theme.border}` }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', gap: 0 }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '14px 24px',
                fontSize: 14,
                fontWeight: activeTab === tab.id ? 600 : 400,
                color: activeTab === tab.id ? theme.primary : theme.textSecondary,
                backgroundColor: 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.id ? `2px solid ${theme.primary}` : '2px solid transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                transition: 'all 0.15s ease',
              }}
            >
              <span>{tab.icon}</span>
              {tab.label}
              {tab.count !== undefined && (
                <span style={{ fontSize: 11, backgroundColor: theme.primaryLight, color: theme.primary, padding: '2px 6px', borderRadius: 8, fontWeight: 500 }}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 24px' }}>
        {activeTab === 'documents' && <DocumentsTab api={api} />}
        {activeTab === 'chatbot' && <ChatbotTab api={api} />}
        {activeTab === 'knowledge-gaps' && <KnowledgeGapsTab api={api} />}
      </div>
    </div>
  )
}


// ============================================================================
// DOCUMENTS TAB
// ============================================================================

function DocumentsTab({ api }: { api: ReturnType<typeof sharedApi> }) {
  const [documents, setDocuments] = useState<SharedDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null)
  const [docContent, setDocContent] = useState<Record<string, string>>({})

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.get('/documents?limit=100')
        if (data.success) setDocuments(data.documents || [])
      } catch { /* ignore */ }
      setLoading(false)
    }
    load()
  }, [])

  const loadDocContent = async (docId: string) => {
    if (docContent[docId]) {
      setExpandedDoc(expandedDoc === docId ? null : docId)
      return
    }
    try {
      const data = await api.get(`/documents/${docId}`)
      if (data.success) {
        setDocContent(prev => ({ ...prev, [docId]: data.document.content || 'No content available.' }))
        setExpandedDoc(docId)
      }
    } catch { /* ignore */ }
  }

  if (loading) {
    return <LoadingSpinner text="Loading documents..." />
  }

  if (documents.length === 0) {
    return <EmptyState icon="📄" title="No documents yet" description="Documents will appear here once they've been added to the knowledge base." />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {documents.map(doc => (
        <div key={doc.id} style={{ backgroundColor: theme.cardBg, border: `1px solid ${theme.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div
            onClick={() => loadDocContent(doc.id)}
            style={{ padding: '16px 20px', cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 12 }}
          >
            <div style={{ width: 36, height: 36, borderRadius: 8, backgroundColor: theme.primaryLight, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>
              {doc.source_type === 'email' ? '✉️' : doc.source_type === 'message' ? '💬' : '📄'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: theme.textPrimary, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {doc.title}
              </h3>
              {doc.summary && (
                <p style={{ fontSize: 13, color: theme.textSecondary, margin: '4px 0 0', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {doc.summary}
                </p>
              )}
              <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <span style={{ fontSize: 11, color: theme.textMuted, backgroundColor: theme.primaryLight, padding: '2px 8px', borderRadius: 6 }}>
                  {doc.source_type || 'document'}
                </span>
                {doc.created_at && (
                  <span style={{ fontSize: 11, color: theme.textMuted }}>
                    {new Date(doc.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
            <span style={{ color: theme.textMuted, fontSize: 12, transform: expandedDoc === doc.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
              ▼
            </span>
          </div>
          {expandedDoc === doc.id && docContent[doc.id] && (
            <div style={{ padding: '0 20px 16px', borderTop: `1px solid ${theme.border}` }}>
              <div style={{ marginTop: 12, fontSize: 13, color: theme.textPrimary, lineHeight: 1.7, whiteSpace: 'pre-wrap', maxHeight: 400, overflowY: 'auto' }}>
                {docContent[doc.id]}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}


// ============================================================================
// CHATBOT TAB
// ============================================================================

function ChatbotTab({ api }: { api: ReturnType<typeof sharedApi> }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const query = input.trim()
    if (!query || isSearching) return

    const userMsg: ChatMessage = { id: Date.now().toString(), text: query, isUser: true }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsSearching(true)

    try {
      const data = await api.post('/search', { query })
      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: data.answer || 'No answer found.',
        isUser: false,
        sources: data.sources,
      }
      setMessages(prev => [...prev, aiMsg])
    } catch {
      setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), text: 'Sorry, something went wrong. Please try again.', isUser: false }])
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)', backgroundColor: theme.cardBg, borderRadius: 16, border: `1px solid ${theme.border}`, overflow: 'hidden' }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div style={{ fontSize: 40, marginBottom: 16 }}>💬</div>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: theme.textPrimary, marginBottom: 8 }}>Ask anything</h3>
            <p style={{ fontSize: 13, color: theme.textSecondary, maxWidth: 400, margin: '0 auto' }}>
              Search this organization's knowledge base. Try asking about processes, decisions, or specific topics.
            </p>
          </div>
        )}
        {messages.map(msg => (
          <div key={msg.id} style={{ marginBottom: 16, display: 'flex', justifyContent: msg.isUser ? 'flex-end' : 'flex-start' }}>
            <div style={{
              maxWidth: '75%',
              padding: '12px 16px',
              borderRadius: msg.isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              backgroundColor: msg.isUser ? theme.primary : theme.primaryLight,
              color: msg.isUser ? '#fff' : theme.textPrimary,
              fontSize: 14,
              lineHeight: 1.6,
            }}>
              {msg.isUser ? msg.text : (
                <div className="shared-markdown">
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                </div>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <div style={{ marginTop: 12, paddingTop: 8, borderTop: `1px solid ${theme.border}` }}>
                  <p style={{ fontSize: 11, color: theme.textMuted, marginBottom: 4, fontWeight: 600 }}>Sources:</p>
                  {msg.sources.slice(0, 3).map((src, i) => (
                    <p key={i} style={{ fontSize: 11, color: theme.textSecondary, margin: '2px 0' }}>
                      [{i + 1}] {src.title}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {isSearching && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
            <div style={{ padding: '12px 16px', borderRadius: '16px 16px 16px 4px', backgroundColor: theme.primaryLight, fontSize: 14, color: theme.textSecondary }}>
              Searching...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '16px 24px', borderTop: `1px solid ${theme.border}`, display: 'flex', gap: 12 }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Ask a question..."
          style={{
            flex: 1,
            padding: '12px 16px',
            fontSize: 14,
            border: `1px solid ${theme.border}`,
            borderRadius: 12,
            outline: 'none',
            backgroundColor: theme.pageBg,
          }}
          disabled={isSearching}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isSearching}
          style={{
            padding: '12px 24px',
            fontSize: 14,
            fontWeight: 600,
            backgroundColor: !input.trim() || isSearching ? theme.textMuted : theme.primary,
            color: '#fff',
            border: 'none',
            borderRadius: 12,
            cursor: !input.trim() || isSearching ? 'not-allowed' : 'pointer',
          }}
        >
          Send
        </button>
      </div>
    </div>
  )
}


// ============================================================================
// KNOWLEDGE GAPS TAB
// ============================================================================

function KnowledgeGapsTab({ api }: { api: ReturnType<typeof sharedApi> }) {
  const [gaps, setGaps] = useState<KnowledgeGap[]>([])
  const [loading, setLoading] = useState(true)
  const [answerInputs, setAnswerInputs] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({})
  const [submitResult, setSubmitResult] = useState<Record<string, { success: boolean; message: string }>>({})

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.get('/knowledge/gaps?limit=100')
        if (data.success) setGaps(data.gaps || [])
      } catch { /* ignore */ }
      setLoading(false)
    }
    load()
  }, [])

  const handleSubmitAnswer = async (gapId: string, questionIndex: number) => {
    const key = `${gapId}-${questionIndex}`
    const text = answerInputs[key]?.trim()
    if (!text) return

    setSubmitting(prev => ({ ...prev, [key]: true }))

    try {
      const data = await api.post(`/knowledge/gaps/${gapId}/answers`, {
        question_index: questionIndex,
        answer_text: text,
      })

      if (data.success) {
        setSubmitResult(prev => ({ ...prev, [key]: { success: true, message: 'Answer submitted!' } }))
        setAnswerInputs(prev => ({ ...prev, [key]: '' }))
        // Refresh gaps to show new answer
        const refreshed = await api.get('/knowledge/gaps?limit=100')
        if (refreshed.success) setGaps(refreshed.gaps || [])
      } else {
        setSubmitResult(prev => ({ ...prev, [key]: { success: false, message: data.error || 'Failed to submit' } }))
      }
    } catch {
      setSubmitResult(prev => ({ ...prev, [key]: { success: false, message: 'Network error' } }))
    } finally {
      setSubmitting(prev => ({ ...prev, [key]: false }))
      setTimeout(() => setSubmitResult(prev => { const n = { ...prev }; delete n[key]; return n }), 3000)
    }
  }

  if (loading) {
    return <LoadingSpinner text="Loading knowledge gaps..." />
  }

  if (gaps.length === 0) {
    return <EmptyState icon="🔍" title="No knowledge gaps" description="Knowledge gaps will appear here once the team has analyzed their documents." />
  }

  const categoryColors: Record<string, string> = {
    decision: '#E8D5B7',
    technical: '#D5E0E8',
    process: '#D8E8D5',
    context: '#E8D5E0',
    relationship: '#E0D5E8',
    timeline: '#E8E0D5',
    outcome: '#D5E8E0',
    rationale: '#E5D5E8',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {gaps.map(gap => (
        <div key={gap.id} style={{ backgroundColor: theme.cardBg, border: `1px solid ${theme.border}`, borderRadius: 12, padding: 20 }}>
          {/* Gap Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{
              fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
              backgroundColor: categoryColors[gap.category] || theme.primaryLight,
              color: theme.textPrimary, padding: '3px 8px', borderRadius: 6
            }}>
              {gap.category}
            </span>
            <span style={{ fontSize: 11, color: theme.textMuted }}>
              {gap.status}
            </span>
          </div>

          <h3 style={{ fontSize: 15, fontWeight: 600, color: theme.textPrimary, margin: '0 0 8px' }}>
            {gap.title}
          </h3>

          {gap.context_summary && (
            <p style={{ fontSize: 13, color: theme.textSecondary, lineHeight: 1.5, margin: '0 0 16px' }}>
              {gap.context_summary}
            </p>
          )}

          {/* Questions */}
          {gap.questions && gap.questions.map((q, qIdx) => {
            const key = `${gap.id}-${qIdx}`
            const existingAnswer = gap.answers?.find(a => a.question_index === qIdx)

            return (
              <div key={qIdx} style={{ marginTop: 12, padding: 12, backgroundColor: theme.pageBg, borderRadius: 8 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: theme.textPrimary, margin: '0 0 8px' }}>
                  Q{qIdx + 1}: {q.question}
                </p>

                {existingAnswer ? (
                  <div style={{ fontSize: 13, color: theme.textSecondary, lineHeight: 1.5, padding: '8px 12px', backgroundColor: theme.cardBg, borderRadius: 6, border: `1px solid ${theme.border}` }}>
                    <span style={{ fontSize: 11, color: theme.statusSuccess, fontWeight: 600 }}>Answered: </span>
                    {existingAnswer.answer_text}
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      type="text"
                      value={answerInputs[key] || ''}
                      onChange={e => setAnswerInputs(prev => ({ ...prev, [key]: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && handleSubmitAnswer(gap.id, qIdx)}
                      placeholder="Type your answer..."
                      style={{
                        flex: 1, padding: '8px 12px', fontSize: 13,
                        border: `1px solid ${theme.border}`, borderRadius: 8, outline: 'none',
                      }}
                      disabled={submitting[key]}
                    />
                    <button
                      onClick={() => handleSubmitAnswer(gap.id, qIdx)}
                      disabled={!answerInputs[key]?.trim() || submitting[key]}
                      style={{
                        padding: '8px 16px', fontSize: 13, fontWeight: 500,
                        backgroundColor: !answerInputs[key]?.trim() || submitting[key] ? theme.textMuted : theme.primary,
                        color: '#fff', border: 'none', borderRadius: 8,
                        cursor: !answerInputs[key]?.trim() || submitting[key] ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {submitting[key] ? '...' : 'Submit'}
                    </button>
                  </div>
                )}

                {submitResult[key] && (
                  <p style={{ fontSize: 12, marginTop: 4, color: submitResult[key].success ? theme.statusSuccess : '#E57373' }}>
                    {submitResult[key].message}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}


// ============================================================================
// SHARED COMPONENTS
// ============================================================================

function LoadingSpinner({ text }: { text: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '60px 20px' }}>
      <div style={{ width: 32, height: 32, border: `3px solid ${theme.border}`, borderTopColor: theme.primary, borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
      <p style={{ color: theme.textSecondary, fontSize: 13 }}>{text}</p>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function EmptyState({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '60px 20px' }}>
      <div style={{ fontSize: 40, marginBottom: 16 }}>{icon}</div>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: theme.textPrimary, marginBottom: 8 }}>{title}</h3>
      <p style={{ fontSize: 13, color: theme.textSecondary, maxWidth: 400, margin: '0 auto' }}>{description}</p>
    </div>
  )
}
