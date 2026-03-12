'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ── Design tokens ──
const COLORS = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  success: '#9CB896',
  error: '#D97B7B',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

// ── Types ──
interface Message {
  id: string
  text: string
  isUser: boolean
  sources?: any[]
  sourceMap?: { [key: string]: { name: string; doc_id: string; source_url?: string } }
  attachments?: { name: string; type: string }[]
  confidence?: {
    confidence: number
    source_coverage: number
    source_quality: number
    query_alignment: number
    sources_used: number
    confidence_label: 'high' | 'medium' | 'low'
  }
}

export interface PlanStep {
  section: string
  text: string
  status: 'complete' | 'in_progress' | 'pending'
}

export interface ThinkingStep {
  type: string
  text: string
  status: 'active' | 'done'
}

export interface ContextData {
  documents?: any[]
  pubmed_papers?: any[]
  journals?: any[]
  experiments?: any[]
  experiment_suggestions?: any[]
  feasibility_check?: any
}

export interface ResearchBrief {
  heading: string
  description: string
  keyPoints: string[]
}

interface CoWorkChatProps {
  apiBase: string
  token: string | null
  onPlanUpdate: (steps: PlanStep[]) => void
  onThinkingStep: (step: ThinkingStep) => void
  onContextUpdate: (ctx: ContextData) => void
  onBriefUpdate: (brief: ResearchBrief) => void
  conversationId?: string | null
  onConversationChange?: (id: string) => void
  selectedSources?: string[]
}

export default function CoWorkChat({
  apiBase,
  token,
  onPlanUpdate,
  onThinkingStep,
  onContextUpdate,
  onBriefUpdate,
  conversationId: propConversationId,
  onConversationChange,
  selectedSources = [],
}: CoWorkChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [streamingSources, setStreamingSources] = useState<any[]>([])
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const [conversationId, setConversationId] = useState<string | null>(propConversationId || null)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Keep a ref of accumulated plan steps so we can update in-place during SSE
  const planStepsRef = useRef<PlanStep[]>([])
  const thinkingStepsRef = useRef<ThinkingStep[]>([])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingText, scrollToBottom])

  // ── Conversation persistence ──
  const loadConversation = useCallback(async (convId: string) => {
    if (!token) return
    setIsLoadingHistory(true)
    try {
      const res = await fetch(`${apiBase}/chat/conversations/${convId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.success && data.conversation?.messages) {
        const loaded: Message[] = data.conversation.messages.map((m: any) => ({
          id: m.id,
          text: m.content,
          isUser: m.role === 'user',
          sources: m.sources || [],
        }))
        setMessages(loaded)
      }
    } catch (e) {
      console.error('[Chat] Failed to load conversation:', e)
    } finally {
      setIsLoadingHistory(false)
    }
  }, [apiBase, token])

  // Load conversation when prop changes
  useEffect(() => {
    if (propConversationId && propConversationId !== conversationId) {
      setConversationId(propConversationId)
      loadConversation(propConversationId)
    } else if (propConversationId === null && conversationId !== null) {
      // New chat requested
      setConversationId(null)
      setMessages([])
    }
  }, [propConversationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleNewChat = useCallback(() => {
    setMessages([])
    setConversationId(null)
    onConversationChange?.('')
    planStepsRef.current = []
    thinkingStepsRef.current = []
    onPlanUpdate([])
    onContextUpdate({ documents: [], pubmed_papers: [], journals: [], experiments: [] })
  }, [onConversationChange, onPlanUpdate, onContextUpdate])

  // ── File handling ──
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    const newFiles = Array.from(files).slice(0, 5 - attachedFiles.length)
    setAttachedFiles(prev => [...prev, ...newFiles])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const removeAttachment = (idx: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== idx))
  }

  // ── Auto-resize textarea ──
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value)
    e.target.style.height = '24px'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  // ── Source citation rendering ──
  const renderMarkdownMessage = (text: string) => {
    const sourceToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
    const processedText = text.replace(
      /\[\[SOURCE:([^:]+):([^:\]]+):?([^\]]*)\]\]/g,
      (_match: string, name: string, docId: string, sourceUrl: string) => {
        if (sourceUrl) return `[${name}](${sourceUrl})`
        const hasValidDocId = docId && docId.length >= 32
        if (hasValidDocId && sourceToken) {
          return `[${name}](${apiBase}/documents/${encodeURIComponent(docId)}/view?token=${encodeURIComponent(sourceToken)})`
        } else if (hasValidDocId) {
          return `[${name}](${apiBase}/documents/${encodeURIComponent(docId)}/view)`
        }
        return `**${name}**`
      }
    )

    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: ({ className, children, ...props }: any) => {
            if (className) {
              return (
                <code style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '13px', lineHeight: '1.6' }} {...props}>
                  {children}
                </code>
              )
            }
            return (
              <code style={{ backgroundColor: '#E5E7EB', padding: '2px 6px', borderRadius: '4px', fontSize: '0.9em', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', color: '#374151' }} {...props}>
                {children}
              </code>
            )
          },
          pre: ({ children }: any) => (
            <pre style={{ backgroundColor: '#1E1E2E', color: '#CDD6F4', borderRadius: '12px', padding: '16px', overflow: 'auto', margin: '12px 0', fontSize: '13px', lineHeight: '1.6' }}>
              {children}
            </pre>
          ),
          p: ({ children }: any) => <p style={{ margin: '0 0 12px', lineHeight: '1.6' }}>{children}</p>,
          h1: ({ children }: any) => <h1 style={{ fontSize: '18px', fontWeight: 700, margin: '16px 0 8px' }}>{children}</h1>,
          h2: ({ children }: any) => <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '14px 0 6px' }}>{children}</h2>,
          h3: ({ children }: any) => <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '12px 0 4px' }}>{children}</h3>,
          ul: ({ children }: any) => <ul style={{ paddingLeft: '20px', margin: '0 0 12px', listStyleType: 'disc' }}>{children}</ul>,
          ol: ({ children }: any) => <ol style={{ paddingLeft: '20px', margin: '0 0 12px', listStyleType: 'decimal' }}>{children}</ol>,
          li: ({ children }: any) => <li style={{ marginBottom: '4px', lineHeight: '1.5' }}>{children}</li>,
          a: ({ href, children }: any) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: COLORS.primaryHover, fontWeight: 500, textDecoration: 'underline', textUnderlineOffset: '2px' }}
            >
              {children}
            </a>
          ),
          blockquote: ({ children }: any) => (
            <blockquote style={{ borderLeft: `3px solid ${COLORS.border}`, paddingLeft: '12px', margin: '12px 0', color: COLORS.textSecondary, fontStyle: 'italic' }}>
              {children}
            </blockquote>
          ),
          strong: ({ children }: any) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
          table: ({ children }: any) => (
            <div style={{ overflowX: 'auto', margin: '12px 0' }}>
              <table style={{ minWidth: '100%', borderCollapse: 'collapse', fontSize: '13px', border: '1px solid #D1D5DB', borderRadius: '8px' }}>
                {children}
              </table>
            </div>
          ),
          thead: ({ children }: any) => <thead style={{ backgroundColor: '#E5E7EB' }}>{children}</thead>,
          th: ({ children }: any) => <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#1F2937', border: '1px solid #D1D5DB' }}>{children}</th>,
          td: ({ children }: any) => <td style={{ padding: '10px 14px', color: '#374151', border: '1px solid #D1D5DB', backgroundColor: '#F9FAFB' }}>{children}</td>,
        }}
      >
        {processedText}
      </ReactMarkdown>
    )
  }

  // ── Send message ──
  const handleSend = async () => {
    if ((!inputValue.trim() && attachedFiles.length === 0) || isLoading || isStreaming) return

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputValue,
      isUser: true,
      attachments: attachedFiles.map(f => ({ name: f.name, type: f.type })),
    }

    setMessages(prev => [...prev, userMessage])
    const queryText = inputValue
    setInputValue('')
    setAttachedFiles([])
    if (textareaRef.current) textareaRef.current.style.height = '24px'
    setIsLoading(true)

    // Reset plan and thinking steps for this new query
    planStepsRef.current = []
    thinkingStepsRef.current = []

    // Build conversation history
    const history = messages.map(m => ({
      role: m.isUser ? 'user' : 'assistant',
      content: m.text,
    }))
    history.push({ role: 'user', content: queryText })

    // ── Persist: create conversation on first message ──
    let activeConvId = conversationId
    if (!activeConvId && token) {
      try {
        const res = await fetch(`${apiBase}/chat/conversations`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: queryText.slice(0, 100) })
        })
        const data = await res.json()
        if (data.success) {
          activeConvId = data.conversation.id
          setConversationId(activeConvId)
          onConversationChange?.(activeConvId!)
        }
      } catch (e) { console.error('[Chat] Failed to create conversation:', e) }
    }

    // Save user message
    if (activeConvId && token) {
      fetch(`${apiBase}/chat/conversations/${activeConvId}/messages`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: 'user', content: queryText })
      }).catch(e => console.error('[Chat] Failed to save user message:', e))
    }

    try {
      const aiMessageId = (Date.now() + 1).toString()
      let localSourceMap: { [key: string]: { name: string; doc_id: string; source_url: string } } = {}
      let localSources: any[] = []
      let accumulatedText = ''
      let streamDone = false

      setStreamingText('')
      setStreamingSources([])

      const fetchHeaders: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) fetchHeaders['Authorization'] = `Bearer ${token}`

      const streamResponse = await fetch(`${apiBase}/search/stream`, {
        method: 'POST',
        headers: fetchHeaders,
        body: JSON.stringify({
          query: queryText,
          conversation_history: history,
          top_k: 15,
          source_types: selectedSources.length > 0 ? selectedSources : undefined,
        }),
      })

      if (!streamResponse.ok) {
        throw new Error(`Search failed with status ${streamResponse.status}`)
      }

      const reader = streamResponse.body!.getReader()
      const decoder = new TextDecoder()
      let sseBuffer = ''

      while (true) {
        const { done: readerDone, value } = await reader.read()
        if (readerDone) break

        sseBuffer += decoder.decode(value, { stream: true })
        const sseEvents = sseBuffer.split('\n\n')
        sseBuffer = sseEvents.pop() || ''

        for (const eventStr of sseEvents) {
          if (!eventStr.trim()) continue

          let eventType = ''
          let eventData = ''

          for (const line of eventStr.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim()
            else if (line.startsWith('data: ')) eventData = line.slice(6)
          }

          if (!eventType || !eventData) continue

          try {
            const parsedData = JSON.parse(eventData)

            if (eventType === 'search_complete') {
              const sourcesData = parsedData.sources || []
              sourcesData.forEach((s: any, idx: number) => {
                const sourceName = s.title || `Source ${idx + 1}`
                const doc_id = s.doc_id || ''
                const source_url = s.source_url || ''
                const cleanName = (sourceName.split('/').pop()?.replace(/^(space_msg_|File-)/, '') || sourceName).replace(/:/g, ' -')
                localSourceMap[`Source ${idx + 1}`] = { name: cleanName, doc_id, source_url }
                localSourceMap[cleanName] = { name: cleanName, doc_id, source_url }
              })

              localSources = sourcesData.map((s: any, idx: number) => ({
                doc_id: s.doc_id,
                subject: s.title || `Source ${idx + 1}`,
                score: s.score,
                content: (s.content_preview || '').substring(0, 200) + '...',
                source_url: s.source_url || '',
                is_shared: s.is_shared || false,
                facility_name: s.facility_name || '',
                source_origin: s.source_origin || (s.is_shared ? 'ctsi' : 'user_kb'),
                source_origin_label: s.source_origin_label || (s.is_shared ? 'CTSI Research' : 'Your KB'),
              }))

              setStreamingSources(localSources)

              // Forward sources as context update, routed by origin
              const docSources = localSources.filter((s: any) => s.source_origin === 'user_kb')
              const ctsiSources = localSources.filter((s: any) => s.source_origin === 'ctsi')
              const pubmedSources = localSources.filter((s: any) => s.source_origin === 'pubmed')
              const openalexSources = localSources.filter((s: any) => s.source_origin === 'openalex')
              const journalSources = localSources.filter((s: any) => s.source_origin === 'journal')
              const reproSources = localSources.filter((s: any) => s.source_origin === 'reproducibility')
              onContextUpdate({
                documents: [...docSources, ...ctsiSources],
                pubmed_papers: [...pubmedSources, ...openalexSources],
                journals: journalSources,
                experiments: reproSources,
              })

            } else if (eventType === 'chunk') {
              accumulatedText += parsedData.content || ''
              setIsLoading(false)
              setIsStreaming(true)
              setStreamingText(accumulatedText)

            } else if (eventType === 'done') {
              streamDone = true

              if (parsedData.sources && parsedData.sources.length > 0) {
                localSources = parsedData.sources.map((s: any, idx: number) => ({
                  doc_id: s.doc_id,
                  subject: s.title || `Source ${idx + 1}`,
                  score: s.score,
                  content: (s.content_preview || '').substring(0, 200) + '...',
                  source_url: s.source_url || '',
                  is_shared: s.is_shared || false,
                  facility_name: s.facility_name || '',
                  source_origin: s.source_origin || (s.is_shared ? 'ctsi' : 'user_kb'),
                  source_origin_label: s.source_origin_label || (s.is_shared ? 'CTSI Research' : 'Your KB'),
                }))
              }

              // Clean up source citations in text
              let cleanedAnswer = accumulatedText
              // Remove "Sources Used" / "Sources" / "References" section and everything after it
              cleanedAnswer = cleanedAnswer.replace(/\n#{0,3}\s*\*{0,2}Sources?\s*(?:Used|Cited|Referenced)?\*{0,2}:?\s*(?:\n[\s\S]*$|\[[\d, ]+\].*$)/i, '')
              cleanedAnswer = cleanedAnswer.replace(/\n#{0,3}\s*\*{0,2}References?\*{0,2}:?\s*\n[\s\S]*$/i, '')
              // Remove inline "Sources Used: [1, 2, 3]" lines anywhere
              cleanedAnswer = cleanedAnswer.replace(/\**Sources?\s*(?:Used|Cited|Referenced)?\**:?\s*\[?[\d,\s]+\]?\.?\s*$/gmi, '')
              cleanedAnswer = cleanedAnswer.replace(/.*Citation Coverage:.*$/gm, '')
              // Remove standalone source list lines like "- [Source 1] Title" at the end
              cleanedAnswer = cleanedAnswer.replace(/(\n\s*[-•]\s*\[Source \d+\].*){2,}$/g, '')
              cleanedAnswer = cleanedAnswer.replace(/\n{3,}/g, '\n\n').trim()

              // Replace [Source X] with markers
              cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+)\]/g, (_m: string, num: string) => {
                const source = localSourceMap[`Source ${num}`]
                return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : ''
              })
              cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+(?:,\s*\d+)+)\]/g, (_m: string, nums: string) => {
                return nums.split(/,\s*/).map((n: string) => {
                  const source = localSourceMap[`Source ${n.trim()}`]
                  return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : null
                }).filter(Boolean).join(', ')
              })
              cleanedAnswer = cleanedAnswer.replace(/\[(\d+)\]/g, (_m: string, num: string) => {
                const source = localSourceMap[`Source ${num}`]
                return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : ''
              })
              cleanedAnswer = cleanedAnswer.replace(/\[Sources?\s*\d+(?:,\s*\d+)*\]/gi, '')
              cleanedAnswer = cleanedAnswer.replace(/\n{3,}/g, '\n\n')

              setMessages(prev => [...prev, {
                id: aiMessageId,
                text: cleanedAnswer,
                isUser: false,
                sources: localSources,
                sourceMap: localSourceMap,
                confidence: parsedData.answer_confidence || undefined,
              }])
              setIsStreaming(false)
              setStreamingText('')
              setStreamingSources([])

              // Mark all plan steps as complete
              if (planStepsRef.current.length > 0) {
                const completedSteps = planStepsRef.current.map(s => ({ ...s, status: 'complete' as const }))
                onPlanUpdate(completedSteps)
              }

              // Mark all thinking steps as done
              for (const step of thinkingStepsRef.current) {
                onThinkingStep({ ...step, status: 'done' })
              }

              // Persist assistant message
              if (activeConvId && token) {
                fetch(`${apiBase}/chat/conversations/${activeConvId}/messages`, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                  body: JSON.stringify({ role: 'assistant', content: cleanedAnswer, sources: localSources })
                }).catch(e => console.error('[Chat] Failed to save assistant message:', e))
              }

            } else if (eventType === 'thinking') {
              // Forward thinking events and track in ref
              const step: ThinkingStep = {
                type: parsedData.type || 'thinking',
                text: parsedData.text || parsedData.message || '',
                status: parsedData.status || 'active',
              }
              thinkingStepsRef.current = [...thinkingStepsRef.current, step]
              onThinkingStep(step)

            } else if (eventType === 'action') {
              // Forward plan/action events
              const newStep: PlanStep = {
                section: parsedData.section || 'Research',
                text: parsedData.text || parsedData.message || '',
                status: parsedData.status || 'in_progress',
              }
              planStepsRef.current = [...planStepsRef.current, newStep]
              onPlanUpdate([...planStepsRef.current])

            } else if (eventType === 'journal_analysis') {
              // Forward journal analysis results to the context panel
              const analysis = parsedData
              // Build a research brief from the journal analysis
              const keyPoints: string[] = []
              if (analysis.field_label) keyPoints.push(`Academic field: ${analysis.field_label}`)
              const gaps = analysis.methodology_gaps || []
              if (gaps.length > 0) keyPoints.push(`${gaps.length} methodology gaps detected`)
              const neighbors = analysis.citation_neighbor_journals || []
              const kwJournals = analysis.keyword_journals || []
              if (neighbors.length > 0) keyPoints.push(`${neighbors.length} journals from citation neighborhood`)
              if (kwJournals.length > 0) keyPoints.push(`${kwJournals.length} journals from keyword matching`)
              onBriefUpdate({
                heading: 'Journal Analysis',
                description: `Analyzed "${analysis.doc_title || 'document'}" for journal fit and methodology gaps.`,
                keyPoints,
              })
              // Also push journal data to context panel
              const journalSources = [
                ...neighbors.map((j: any) => ({
                  subject: j.journal_name,
                  source_origin: 'journal',
                  source_origin_label: 'Citation Neighborhood',
                  citation_overlap: j.citation_overlap,
                })),
                ...kwJournals.map((j: any) => ({
                  subject: j.name,
                  source_origin: 'journal',
                  source_origin_label: j.category === 'primary' ? 'Target Journal' : j.category === 'stretch' ? 'Stretch Journal' : 'Safe Journal',
                })),
              ]
              if (journalSources.length > 0) {
                onContextUpdate({ journals: journalSources })
              }

            } else if (eventType === 'experiment_suggestions') {
              const suggestions = parsedData.suggestions || []
              // Pass to context panel
              onContextUpdate({
                experiment_suggestions: suggestions,
              })
              // The LLM answer will follow — this just pre-loads the context panel

            } else if (eventType === 'feasibility_check') {
              const feasibility = parsedData.feasibility || parsedData
              onContextUpdate({
                feasibility_check: feasibility,
              })

            } else if (eventType === 'context_update') {
              onContextUpdate(parsedData)

            } else if (eventType === 'brief') {
              onBriefUpdate({
                heading: parsedData.heading || '',
                description: parsedData.description || '',
                keyPoints: parsedData.keyPoints || parsedData.key_points || [],
              })

            } else if (eventType === 'error') {
              throw new Error(parsedData.error || 'Search failed')
            }
            // Gracefully ignore unknown event types
          } catch (parseErr: any) {
            if (parseErr.message?.startsWith('Search failed')) throw parseErr
            console.error('Error parsing SSE event:', parseErr)
          }
        }
      }

      // Handle stream ending without a done event
      if (accumulatedText && !streamDone) {
        setMessages(prev => [...prev, {
          id: aiMessageId,
          text: accumulatedText,
          isUser: false,
          sources: localSources,
          sourceMap: localSourceMap,
        }])
        setIsStreaming(false)
        setStreamingText('')
        setStreamingSources([])
      }
    } catch (error: any) {
      console.error('CoWorkChat error:', error)
      let errorText = 'Sorry, I encountered an error.'
      if (error.message) errorText += ` ${error.message}`
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        text: errorText,
        isUser: false,
      }])
    } finally {
      setIsLoading(false)
      setIsStreaming(false)
      setStreamingText('')
      setStreamingSources([])
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ── Render ──
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: COLORS.cardBg,
      fontFamily: FONT,
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: `1px solid ${COLORS.border}`,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexShrink: 0,
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
        </svg>
        <span style={{ fontSize: '15px', fontWeight: 600, color: COLORS.textPrimary, flex: 1 }}>Chat</span>
        <button
          onClick={handleNewChat}
          style={{
            padding: '6px 14px',
            borderRadius: '8px',
            border: 'none',
            backgroundColor: COLORS.primary,
            color: '#FFFFFF',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: FONT,
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            transition: 'background-color 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#B8948A' }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = COLORS.primary }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Messages area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px 20px',
      }}>
        {messages.length === 0 && !isLoading && !isStreaming ? (
          // Welcome state
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            textAlign: 'center',
            gap: '12px',
          }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '16px',
              backgroundColor: COLORS.primaryLight,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
              </svg>
            </div>
            <div>
              <h3 style={{
                fontSize: '18px',
                fontWeight: 700,
                color: COLORS.textPrimary,
                marginBottom: '6px',
                fontFamily: FONT,
                letterSpacing: '-0.01em',
              }}>
                Start a conversation
              </h3>
              <p style={{ fontSize: '13px', color: COLORS.textMuted, lineHeight: '1.5', maxWidth: '280px' }}>
                Ask questions about your knowledge base. I will search across all your documents and provide sourced answers.
              </p>
            </div>
            {/* Quick prompts */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px', width: '100%', maxWidth: '300px' }}>
              {[
                'What do we know about...',
                'Summarize the key points from...',
                'Find documents related to...',
              ].map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => setInputValue(prompt)}
                  style={{
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: `1px solid ${COLORS.border}`,
                    backgroundColor: COLORS.cardBg,
                    fontSize: '13px',
                    color: COLORS.textSecondary,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                    fontFamily: FONT,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = COLORS.primary
                    e.currentTarget.style.backgroundColor = COLORS.primaryLight
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = COLORS.border
                    e.currentTarget.style.backgroundColor = COLORS.cardBg
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                style={{
                  display: 'flex',
                  justifyContent: message.isUser ? 'flex-end' : 'flex-start',
                  marginBottom: '12px',
                }}
              >
                <div style={{
                  padding: '12px 16px',
                  borderRadius: '14px',
                  maxWidth: message.isUser ? '85%' : '100%',
                  backgroundColor: message.isUser ? COLORS.primaryLight : COLORS.cardBg,
                  border: message.isUser ? 'none' : `1px solid ${COLORS.border}`,
                }}>
                  <div style={{
                    fontSize: '14px',
                    lineHeight: '1.6',
                    color: COLORS.textPrimary,
                  }}>
                    {message.isUser ? message.text : renderMarkdownMessage(message.text)}
                  </div>

                  {/* Attachments */}
                  {message.isUser && message.attachments && message.attachments.length > 0 && (
                    <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {message.attachments.map((att, idx) => (
                        <span key={idx} style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '2px 8px',
                          backgroundColor: COLORS.primaryLight,
                          borderRadius: '12px',
                          fontSize: '11px',
                          color: COLORS.primary,
                        }}>
                          <svg width="10" height="10" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z" clipRule="evenodd" />
                          </svg>
                          {att.name}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Confidence indicator — only show for high confidence */}
                  {!message.isUser && message.confidence && message.confidence.confidence_label === 'high' && (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      marginTop: '8px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      backgroundColor: '#F0FDF4',
                      fontSize: '11.5px',
                      color: '#6B6B6B',
                      fontFamily: FONT,
                    }}>
                      <span style={{
                        width: '6px', height: '6px', borderRadius: '50%',
                        backgroundColor: '#22C55E',
                      }} />
                      <span>
                        High confidence
                        {message.confidence.sources_used > 0 && ` · ${message.confidence.sources_used} sources`}
                      </span>
                    </div>
                  )}

                  {/* Sources */}
                  {!message.isUser && message.sources && message.sources.length > 0 && (
                    <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {message.sources
                        .filter((source, idx, arr) => arr.findIndex(s =>
                          (s.subject || '').toLowerCase().trim() === (source.subject || '').toLowerCase().trim()
                        ) === idx)
                        .slice(0, 5)
                        .map((source, idx) => {
                          const sourceViewUrl = source.source_url || null
                          return (
                            <a
                              key={idx}
                              href={sourceViewUrl || '#'}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '3px 8px',
                                borderRadius: '10px',
                                backgroundColor: COLORS.primaryLight,
                                fontSize: '11px',
                                color: COLORS.primary,
                                textDecoration: 'none',
                                transition: 'background 0.15s',
                              }}
                              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F0E8E4' }}
                              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = COLORS.primaryLight }}
                            >
                              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                              <span style={{ maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {source.subject?.split('/').pop() || source.subject || `Source ${idx + 1}`}
                              </span>
                              {source.source_origin_label && (
                                <span style={{
                                  fontSize: '9px',
                                  padding: '1px 5px',
                                  borderRadius: '4px',
                                  backgroundColor: {
                                    user_kb: '#9CB896',
                                    ctsi: '#7BA7C9',
                                    pubmed: COLORS.primary,
                                    journal: '#B39DDB',
                                    reproducibility: '#FFB74D',
                                    openalex: '#F59E0B',
                                  }[source.source_origin as string] || '#E0E0E0',
                                  color: '#FFFFFF',
                                  fontWeight: 600,
                                }}>
                                  {source.source_origin_label}
                                </span>
                              )}
                            </a>
                          )
                        })}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Loading / Thinking indicator */}
            {isLoading && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '12px' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '12px 16px',
                  backgroundColor: COLORS.primaryLight,
                  borderRadius: '14px',
                }}>
                  <div style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    border: `2px solid ${COLORS.border}`,
                    borderTopColor: COLORS.primary,
                    animation: 'cowork-spin 0.8s linear infinite',
                  }} />
                  <span style={{ fontSize: '13px', color: COLORS.textSecondary }}>Thinking...</span>
                </div>
              </div>
            )}

            {/* Streaming message */}
            {isStreaming && streamingText && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '12px' }}>
                <div style={{
                  padding: '12px 16px',
                  borderRadius: '14px',
                  maxWidth: '100%',
                  backgroundColor: COLORS.cardBg,
                  border: `1px solid ${COLORS.border}`,
                }}>
                  <div style={{ fontSize: '14px', lineHeight: '1.6', color: COLORS.textPrimary }}>
                    {renderMarkdownMessage(streamingText)}
                  </div>
                  {/* Streaming cursor */}
                  <span style={{
                    display: 'inline-block',
                    width: '2px',
                    height: '16px',
                    backgroundColor: COLORS.primary,
                    animation: 'cowork-blink 1s step-end infinite',
                    verticalAlign: 'text-bottom',
                    marginLeft: '2px',
                  }} />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input area */}
      <div style={{
        borderTop: `1px solid ${COLORS.border}`,
        padding: '12px 16px',
        flexShrink: 0,
      }}>
        {/* Attached files preview */}
        {attachedFiles.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
            {attachedFiles.map((file, idx) => (
              <span key={idx} style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                backgroundColor: COLORS.primaryLight,
                borderRadius: '8px',
                fontSize: '11px',
                color: COLORS.primary,
              }}>
                {file.name}
                <button
                  onClick={() => removeAttachment(idx)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: COLORS.textMuted,
                    padding: '0 2px',
                    fontSize: '14px',
                    lineHeight: 1,
                  }}
                >
                  x
                </button>
              </span>
            ))}
          </div>
        )}

        <div style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
          backgroundColor: COLORS.pageBg,
          borderRadius: '12px',
          border: `1px solid ${COLORS.border}`,
          padding: '8px 12px',
        }}>
          {/* File attachment button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '4px',
              color: COLORS.textMuted,
              display: 'flex',
              alignItems: 'center',
              flexShrink: 0,
              transition: 'color 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = COLORS.primary }}
            onMouseLeave={(e) => { e.currentTarget.style.color = COLORS.textMuted }}
            title="Attach files"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            style={{ display: 'none' }}
            accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.pptx,.md"
          />

          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            rows={1}
            style={{
              flex: 1,
              resize: 'none',
              border: 'none',
              outline: 'none',
              backgroundColor: 'transparent',
              fontSize: '14px',
              lineHeight: '1.5',
              color: COLORS.textPrimary,
              fontFamily: FONT,
              height: '24px',
              maxHeight: '120px',
            }}
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={isLoading || isStreaming || (!inputValue.trim() && attachedFiles.length === 0)}
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: (isLoading || isStreaming || (!inputValue.trim() && attachedFiles.length === 0))
                ? COLORS.border
                : COLORS.primary,
              cursor: (isLoading || isStreaming) ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              transition: 'background-color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!isLoading && !isStreaming && (inputValue.trim() || attachedFiles.length > 0)) {
                e.currentTarget.style.backgroundColor = COLORS.primaryHover
              }
            }}
            onMouseLeave={(e) => {
              if (!isLoading && !isStreaming && (inputValue.trim() || attachedFiles.length > 0)) {
                e.currentTarget.style.backgroundColor = COLORS.primary
              }
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>

      {/* Keyframe animations */}
      <style>{`
        @keyframes cowork-spin { to { transform: rotate(360deg); } }
        @keyframes cowork-blink { 50% { opacity: 0; } }
      `}</style>
    </div>
  )
}
