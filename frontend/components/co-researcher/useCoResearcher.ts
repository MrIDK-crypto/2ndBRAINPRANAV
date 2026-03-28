import { useState, useCallback, useRef } from 'react'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'
import type {
  ResearchSession, ResearchMessage, Hypothesis, PlanPhase,
  ResearchBrief, ActionDetail, ContextData,
} from './types'

// Co-researcher routes are now integrated into main backend on port 5002
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5002') + '/api/co-researcher'

export function useCoResearcher() {
  const { token } = useAuth()

  // State
  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [activeSession, setActiveSession] = useState<ResearchSession | null>(null)
  const [messages, setMessages] = useState<ResearchMessage[]>([])
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([])
  const [plan, setPlan] = useState<PlanPhase[]>([])
  const [brief, setBrief] = useState<ResearchBrief>({})
  const [context, setContext] = useState<ContextData>({ documents: [], pubmed_papers: [], gaps: [] })

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [streamingActions, setStreamingActions] = useState<ActionDetail[]>([])

  const abortRef = useRef<AbortController | null>(null)

  const headers = useCallback(() => {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) h['Authorization'] = `Bearer ${token}`
    return h
  }, [token])

  // =========================================================================
  // SESSION MANAGEMENT
  // =========================================================================

  const listSessions = useCallback(async () => {
    try {
      const resp = await axios.get(`${API_BASE}/sessions`, { headers: headers() })
      if (resp.data.success) setSessions(resp.data.sessions)
    } catch (e) {
      console.error('[CoResearcher] listSessions error:', e)
    }
  }, [headers])

  const createSession = useCallback(async (firstMessage: string): Promise<ResearchSession | null> => {
    try {
      const resp = await axios.post(`${API_BASE}/sessions`, { initial_message: firstMessage }, { headers: headers() })
      if (resp.data.success) {
        const session = resp.data.session
        setActiveSession(session)
        setMessages(session.messages || [])
        setHypotheses(session.hypotheses || [])
        setPlan(session.research_plan || [])
        setBrief(session.research_brief || {})
        setContext({ documents: [], pubmed_papers: [], gaps: [] })
        return session
      }
    } catch (e) {
      console.error('[CoResearcher] createSession error:', e)
    }
    return null
  }, [headers])

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const resp = await axios.get(`${API_BASE}/sessions/${sessionId}`, { headers: headers() })
      if (resp.data.success) {
        const session = resp.data.session
        setActiveSession(session)
        setMessages(session.messages || [])
        setHypotheses(session.hypotheses || [])
        setPlan(session.research_plan || [])
        setBrief(session.research_brief || {})
        setContext({ documents: [], pubmed_papers: [], gaps: [] })
      }
    } catch (e) {
      console.error('[CoResearcher] loadSession error:', e)
    }
  }, [headers])

  const closeSession = useCallback(() => {
    setActiveSession(null)
    setMessages([])
    setHypotheses([])
    setPlan([])
    setBrief({})
    setContext({ documents: [], pubmed_papers: [], gaps: [] })
    setStreamingText('')
    setStreamingActions([])
  }, [])

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await axios.delete(`${API_BASE}/sessions/${sessionId}`, { headers: headers() })
      setSessions(prev => prev.filter(s => s.id !== sessionId))
      if (activeSession?.id === sessionId) closeSession()
    } catch (e) {
      console.error('[CoResearcher] deleteSession error:', e)
    }
  }, [headers, activeSession, closeSession])

  // =========================================================================
  // SEND MESSAGE (SSE STREAMING)
  // =========================================================================

  const sendMessage = useCallback(async (message: string, options?: { sessionId?: string; skipUserMsg?: boolean }) => {
    const sid = options?.sessionId || activeSession?.id
    if (!sid || isStreaming) return

    // Add user message to UI immediately (skip if initial message already added by createSession)
    if (!options?.skipUserMsg) {
      const userMsg: ResearchMessage = {
        id: Date.now().toString(),
        session_id: sid,
        role: 'user',
        content: message,
        actions: [],
        sources: [],
        extra_data: {},
        created_at: new Date().toISOString(),
      }
      setMessages(prev => [...prev, userMsg])
    }
    setIsStreaming(true)
    setStreamingText('')
    setStreamingActions([])

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const fetchHeaders: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) fetchHeaders['Authorization'] = `Bearer ${token}`

      const body: Record<string, any> = { message }
      if (options?.skipUserMsg) body.skip_user_save = true

      const response = await fetch(`${API_BASE}/sessions/${sid}/messages/stream`, {
        method: 'POST',
        headers: fetchHeaders,
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!response.ok) throw new Error(`Stream failed: ${response.status}`)

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let sseBuffer = ''
      let accumulatedText = ''
      let finalActions: ActionDetail[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        sseBuffer += decoder.decode(value, { stream: true })
        const events = sseBuffer.split('\n\n')
        sseBuffer = events.pop() || ''

        for (const eventStr of events) {
          if (!eventStr.trim()) continue

          let eventType = ''
          let eventData = ''

          for (const line of eventStr.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim()
            else if (line.startsWith('data: ')) eventData = line.slice(6)
          }

          if (!eventType || !eventData) continue

          try {
            const data = JSON.parse(eventData)

            switch (eventType) {
              case 'action':
                setStreamingActions(prev => [...prev, { icon: data.type === 'searching_pubmed' || data.type === 'pubmed_done' ? 'search' : data.type === 'searching_kb' ? 'search' : 'plan', text: data.text }])
                finalActions.push({ icon: 'search', text: data.text })
                break

              case 'chunk':
                accumulatedText += data.content
                setStreamingText(accumulatedText)
                break

              case 'plan_update':
                setPlan(data.plan)
                break

              case 'brief_update':
                setBrief(data.brief)
                break

              case 'context_update':
                setContext(data)
                break

              case 'hypothesis_update':
                setHypotheses(prev => {
                  const idx = prev.findIndex(h => h.id === data.id)
                  if (idx >= 0) {
                    const updated = [...prev]
                    updated[idx] = data
                    return updated
                  }
                  return [...prev, data]
                })
                break

              case 'done':
                // Add the complete assistant message
                const assistantMsg: ResearchMessage = {
                  id: data.message_id || (Date.now() + 1).toString(),
                  session_id: sid,
                  role: 'assistant',
                  content: accumulatedText,
                  actions: data.actions || finalActions,
                  sources: data.sources || [],
                  extra_data: {},
                  created_at: new Date().toISOString(),
                }
                setMessages(prev => [...prev, assistantMsg])
                setStreamingText('')
                setStreamingActions([])
                break

              case 'error':
                console.error('[CoResearcher] Stream error:', data.error)
                break
            }
          } catch {
            // Skip malformed events
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        console.error('[CoResearcher] sendMessage error:', e)
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [activeSession, isStreaming, token])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return {
    // State
    sessions, activeSession, messages, hypotheses, plan, brief, context,
    isStreaming, streamingText, streamingActions,
    // Actions
    listSessions, createSession, loadSession, closeSession, deleteSession,
    sendMessage, stopStreaming,
  }
}
