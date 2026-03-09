'use client'

import React, { useState, useCallback, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import TopNav from '@/components/shared/TopNav'
import CoWorkChat from '@/components/co-work/CoWorkChat'
import CoWorkPlan from '@/components/co-work/CoWorkPlan'
import CoWorkContext from '@/components/co-work/CoWorkContext'
import CoWorkHistory from '@/components/co-work/CoWorkHistory'

import type { PlanStep, ThinkingStep, ContextData, ResearchBrief } from '@/components/co-work/CoWorkChat'

// ── Design tokens ──
const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

export default function CoWorkPage() {
  const { user, token, isLoading: authLoading } = useAuth()

  // ── State ──
  const [planSteps, setPlanSteps] = useState<PlanStep[]>([])
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([])
  const [contextSources, setContextSources] = useState<ContextData | null>(null)
  const [researchBrief, setResearchBrief] = useState<ResearchBrief | null>(null)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)

  // ── Right columns resize ──
  const [contextWidth, setContextWidth] = useState(280)
  const [planWidth, setPlanWidth] = useState(280)
  const [resizingCol, setResizingCol] = useState<'context' | 'plan' | null>(null)
  // Store the starting X and starting width when drag begins
  const dragRef = React.useRef<{ startX: number; startW: number }>({ startX: 0, startW: 0 })

  const handleContextResizeDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startW: contextWidth }
    setResizingCol('context')
  }, [contextWidth])

  const handlePlanResizeDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startW: planWidth }
    setResizingCol('plan')
  }, [planWidth])

  useEffect(() => {
    if (!resizingCol) return
    const handleMouseMove = (e: MouseEvent) => {
      const dx = dragRef.current.startX - e.clientX // positive = dragging left = wider
      const newW = Math.max(200, Math.min(500, dragRef.current.startW + dx))
      if (resizingCol === 'context') setContextWidth(newW)
      else setPlanWidth(newW)
    }
    const handleMouseUp = () => setResizingCol(null)
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [resizingCol])

  // ── Load conversation on mount ──
  // Fresh login → new chat (null). Navigate away & back → restore last chat.
  useEffect(() => {
    if (!token) return

    // Check if we've already visited co-work this session
    const lastChatId = sessionStorage.getItem('cowork_last_chat')
    if (lastChatId) {
      // Returning to page — restore last conversation
      setActiveConversationId(lastChatId)
    }
    // else: fresh login session — start with new chat (null)
  }, [token])

  // Persist active conversation to sessionStorage
  useEffect(() => {
    if (activeConversationId) {
      sessionStorage.setItem('cowork_last_chat', activeConversationId)
    }
  }, [activeConversationId])

  // ── Callbacks from chat panel ──
  const handlePlanUpdate = useCallback((steps: PlanStep[]) => {
    setPlanSteps(steps)
  }, [])

  const handleThinkingStep = useCallback((step: ThinkingStep) => {
    setThinkingSteps(prev => {
      const existingIdx = prev.findIndex(s => s.type === step.type && s.text === step.text)
      if (existingIdx >= 0) {
        const updated = [...prev]
        updated[existingIdx] = step
        return updated
      }
      return [...prev, step]
    })
  }, [])

  const handleContextUpdate = useCallback((ctx: ContextData) => {
    setContextSources(prev => {
      if (!prev) return ctx
      return {
        documents: [...(prev.documents || []), ...(ctx.documents || [])],
        pubmed_papers: [...(prev.pubmed_papers || []), ...(ctx.pubmed_papers || [])],
        journals: [...(prev.journals || []), ...(ctx.journals || [])],
        experiments: [...(prev.experiments || []), ...(ctx.experiments || [])],
        // Replace (not merge) for experiment suggestions and feasibility — latest result wins
        experiment_suggestions: ctx.experiment_suggestions || prev.experiment_suggestions,
        feasibility_check: ctx.feasibility_check || prev.feasibility_check,
      }
    })
  }, [])

  const handleBriefUpdate = useCallback((brief: ResearchBrief) => {
    setResearchBrief(brief)
  }, [])

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id)
    // Reset side panels when switching conversations
    setPlanSteps([])
    setThinkingSteps([])
    setContextSources(null)
    setResearchBrief(null)
  }, [])

  const handleNewChat = useCallback(() => {
    setActiveConversationId(null)
    setPlanSteps([])
    setThinkingSteps([])
    setContextSources(null)
    setResearchBrief(null)
  }, [])

  // ── Loading state ──
  if (authLoading) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: COLORS.pageBg,
        fontFamily: FONT,
      }}>
        <TopNav userName="User" />
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              width: '28px',
              height: '28px',
              border: `2px solid ${COLORS.border}`,
              borderTopColor: COLORS.primary,
              borderRadius: '50%',
              animation: 'cowork-page-spin 0.8s linear infinite',
              margin: '0 auto 12px',
            }} />
            <p style={{ color: COLORS.textMuted, fontSize: '13px' }}>Loading...</p>
          </div>
          <style>{`@keyframes cowork-page-spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  // ── Not authenticated ──
  if (!user) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: COLORS.pageBg,
        fontFamily: FONT,
      }}>
        <TopNav userName="Guest" />
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <div style={{
            textAlign: 'center',
            padding: '40px',
            backgroundColor: COLORS.cardBg,
            borderRadius: '16px',
            border: `1px solid ${COLORS.border}`,
            maxWidth: '400px',
          }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '16px',
              backgroundColor: COLORS.primaryLight,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
            }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0110 0v4" />
              </svg>
            </div>
            <h2 style={{
              fontSize: '18px',
              fontWeight: 600,
              color: COLORS.textPrimary,
              marginBottom: '8px',
              fontFamily: "'Instrument Serif', Georgia, serif",
            }}>
              Sign in to use Co-Work
            </h2>
            <p style={{ fontSize: '14px', color: COLORS.textSecondary, lineHeight: '1.5', marginBottom: '20px' }}>
              Log in to access your knowledge base and start collaborating with AI.
            </p>
            <a
              href="/login"
              style={{
                display: 'inline-block',
                padding: '10px 28px',
                borderRadius: '10px',
                backgroundColor: COLORS.primary,
                color: '#FFFFFF',
                fontSize: '14px',
                fontWeight: 500,
                textDecoration: 'none',
                transition: 'background-color 0.15s',
                fontFamily: FONT,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#B8948A' }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = COLORS.primary }}
            >
              Sign in
            </a>
          </div>
        </div>
      </div>
    )
  }

  // ── Main layout ──
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      overflow: 'hidden',
      backgroundColor: COLORS.pageBg,
      fontFamily: FONT,
    }}>
      {/* Top navigation */}
      <TopNav userName={user?.full_name?.split(' ')[0] || 'User'} />

      {/* Layout: History sidebar + Chat + Right panel (Context + Plan stacked) */}
      <div style={{
        display: 'flex',
        flex: 1,
        height: 'calc(100vh - 60px)',
        overflow: 'hidden',
      }}>
        {/* History sidebar */}
        <CoWorkHistory
          apiBase={API_BASE}
          token={token}
          activeConversationId={activeConversationId}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
        />

        {/* Chat panel */}
        <div style={{
          flex: 1,
          minWidth: '300px',
          height: '100%',
          overflow: 'hidden',
        }}>
          <CoWorkChat
            apiBase={API_BASE}
            token={token}
            conversationId={activeConversationId}
            onConversationChange={(id) => setActiveConversationId(id || null)}
            onPlanUpdate={handlePlanUpdate}
            onThinkingStep={handleThinkingStep}
            onContextUpdate={handleContextUpdate}
            onBriefUpdate={handleBriefUpdate}
          />
        </div>

        {/* Context column resize handle */}
        <div
          onMouseDown={handleContextResizeDown}
          style={{
            width: '4px',
            cursor: 'col-resize',
            backgroundColor: resizingCol === 'context' ? COLORS.primary : 'transparent',
            transition: resizingCol ? 'none' : 'background-color 0.15s',
            flexShrink: 0,
          }}
          onMouseEnter={(e) => { if (!resizingCol) e.currentTarget.style.backgroundColor = COLORS.border }}
          onMouseLeave={(e) => { if (!resizingCol) e.currentTarget.style.backgroundColor = 'transparent' }}
        />

        {/* Context column */}
        <div style={{
          width: `${contextWidth}px`,
          minWidth: '200px',
          height: '100%',
          overflow: 'hidden',
          borderLeft: `1px solid ${COLORS.border}`,
        }}>
          <CoWorkContext
            thinkingSteps={thinkingSteps}
            brief={researchBrief}
            sources={contextSources}
          />
        </div>

        {/* Plan column resize handle */}
        <div
          onMouseDown={handlePlanResizeDown}
          style={{
            width: '4px',
            cursor: 'col-resize',
            backgroundColor: resizingCol === 'plan' ? COLORS.primary : 'transparent',
            transition: resizingCol ? 'none' : 'background-color 0.15s',
            flexShrink: 0,
          }}
          onMouseEnter={(e) => { if (!resizingCol) e.currentTarget.style.backgroundColor = COLORS.border }}
          onMouseLeave={(e) => { if (!resizingCol) e.currentTarget.style.backgroundColor = 'transparent' }}
        />

        {/* Plan column */}
        <div style={{
          width: `${planWidth}px`,
          minWidth: '200px',
          height: '100%',
          overflow: 'hidden',
          borderLeft: `1px solid ${COLORS.border}`,
        }}>
          <CoWorkPlan steps={planSteps} />
        </div>
      </div>
    </div>
  )
}
