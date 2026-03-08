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

  // ── Auto-load most recent conversation on mount ──
  useEffect(() => {
    if (!token) return
    fetch(`${API_BASE}/chat/conversations?limit=1`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        if (data.success && data.conversations?.length > 0) {
          setActiveConversationId(data.conversations[0].id)
        }
      })
      .catch(() => {})
  }, [token])

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

      {/* 3-panel layout with history sidebar */}
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

        {/* Context panel */}
        <div style={{
          width: '25%',
          minWidth: '220px',
          height: '100%',
          overflow: 'hidden',
        }}>
          <CoWorkContext
            thinkingSteps={thinkingSteps}
            brief={researchBrief}
            sources={contextSources}
          />
        </div>

        {/* Plan panel */}
        <div style={{
          width: '25%',
          minWidth: '220px',
          height: '100%',
          overflow: 'hidden',
        }}>
          <CoWorkPlan steps={planSteps} />
        </div>
      </div>
    </div>
  )
}
