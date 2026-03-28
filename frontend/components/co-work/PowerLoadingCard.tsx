'use client'

import React from 'react'

const COLORS = {
  primary: '#C9A598', cardBg: '#FFFFFF', textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B', border: '#F0EEEC', success: '#9CB896',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

const SERVICE_LABELS: Record<string, string> = {
  hij: 'Scoring manuscript', competitor_finder: 'Finding competitors',
  idea_reality: 'Validating idea', co_researcher: 'Generating hypotheses',
}

interface PowerLoadingCardProps {
  services: string[]
  completedServices: Record<string, string>
  thinkingStep?: string
}

export default function PowerLoadingCard({ services, completedServices, thinkingStep }: PowerLoadingCardProps) {
  return (
    <div style={{ backgroundColor: COLORS.cardBg, borderRadius: '14px', border: `1px solid ${COLORS.border}`, padding: '16px 20px', fontFamily: FONT, maxWidth: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
        <div className="power-loading-spinner" style={{ width: '16px', height: '16px', border: `2px solid ${COLORS.border}`, borderTopColor: COLORS.primary, borderRadius: '50%' }} />
        <span style={{ fontSize: '13px', fontWeight: 500, color: COLORS.textPrimary }}>Running analysis...</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {services.map((service) => {
          const completed = service in completedServices
          const status = completedServices[service]
          const isError = status === 'error' || status === 'timeout'
          return (
            <div key={service} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: completed ? (isError ? '#D97B7B' : COLORS.success) : COLORS.textSecondary }}>
              {completed ? (isError ? <span style={{ fontSize: '14px' }}>✗</span> : <span style={{ fontSize: '14px' }}>✓</span>) : (
                <div className="power-loading-dot" style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: COLORS.primary }} />
              )}
              <span>{SERVICE_LABELS[service] || service}...</span>
            </div>
          )
        })}
      </div>
      {thinkingStep && <div style={{ marginTop: '12px', fontSize: '12px', color: COLORS.textSecondary, fontStyle: 'italic' }}>{thinkingStep}</div>}
      <style>{`
        @keyframes power-spin { to { transform: rotate(360deg); } }
        .power-loading-spinner { animation: power-spin 0.8s linear infinite; }
        @keyframes power-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .power-loading-dot { animation: power-pulse 1.5s ease-in-out infinite; }
      `}</style>
    </div>
  )
}
