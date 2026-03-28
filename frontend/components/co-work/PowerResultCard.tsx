'use client'

import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const COLORS = {
  primary: '#C9A598', primaryLight: '#FBF4F1', cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D', textSecondary: '#6B6B6B', textMuted: '#9A9A9A',
  border: '#F0EEEC', success: '#9CB896', error: '#D97B7B',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface Tab {
  label: string; icon: string; status: 'success' | 'error' | 'timeout'
  summary: string; full_results: any | null
}

interface PowerResultCardProps {
  tabs: Tab[]; followup_suggestions: string[]
  onViewFullAnalysis?: (tab: Tab) => void
  onFollowupClick?: (suggestion: string) => void
}

export default function PowerResultCard({ tabs, followup_suggestions, onViewFullAnalysis, onFollowupClick }: PowerResultCardProps) {
  const [activeTab, setActiveTab] = useState(0)
  if (!tabs || tabs.length === 0) return null
  const currentTab = tabs[activeTab]
  const isError = currentTab.status === 'error' || currentTab.status === 'timeout'

  return (
    <div style={{ backgroundColor: COLORS.cardBg, borderRadius: '14px', border: `1px solid ${COLORS.border}`, overflow: 'hidden', fontFamily: FONT, maxWidth: '100%' }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${COLORS.border}`, backgroundColor: '#FAFAF9' }}>
        {tabs.map((tab, idx) => (
          <button key={idx} onClick={() => setActiveTab(idx)} style={{
            flex: 1, padding: '10px 16px', border: 'none',
            backgroundColor: idx === activeTab ? COLORS.cardBg : 'transparent',
            borderBottom: idx === activeTab ? `2px solid ${COLORS.primary}` : '2px solid transparent',
            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
            fontSize: '12px', fontWeight: idx === activeTab ? 600 : 400,
            color: idx === activeTab ? COLORS.textPrimary : COLORS.textSecondary,
            fontFamily: FONT, transition: 'all 0.15s ease',
          }}>
            {(tab.status === 'error' || tab.status === 'timeout') && <span style={{ color: COLORS.error }}>⚠</span>}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ padding: '16px 20px', fontSize: '14px', lineHeight: '1.6', color: isError ? COLORS.error : COLORS.textPrimary, minHeight: '80px' }}>
        {isError ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>⚠️</span><span>{currentTab.summary}</span></div>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{currentTab.summary || 'Analysis complete.'}</ReactMarkdown>
        )}
      </div>

      {/* View full analysis button */}
      {currentTab.status === 'success' && currentTab.full_results && onViewFullAnalysis && (
        <div style={{ padding: '0 20px 12px' }}>
          <button onClick={() => onViewFullAnalysis(currentTab)} style={{
            padding: '8px 16px', borderRadius: '8px', border: `1px solid ${COLORS.primary}`,
            backgroundColor: 'transparent', color: COLORS.primary, fontSize: '12px', fontWeight: 500,
            cursor: 'pointer', fontFamily: FONT, transition: 'all 0.15s ease',
          }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = COLORS.primaryLight }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
          >View full analysis →</button>
        </div>
      )}

      {/* Followup suggestions */}
      {followup_suggestions && followup_suggestions.length > 0 && (
        <div style={{ padding: '10px 20px 14px', borderTop: `1px solid ${COLORS.border}`, display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {followup_suggestions.map((suggestion, idx) => (
            <button key={idx} onClick={() => onFollowupClick?.(suggestion)} style={{
              padding: '5px 12px', borderRadius: '20px', border: `1px solid ${COLORS.border}`,
              backgroundColor: COLORS.cardBg, color: COLORS.textSecondary, fontSize: '11px',
              cursor: 'pointer', fontFamily: FONT, transition: 'all 0.15s ease',
            }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = COLORS.primary; e.currentTarget.style.color = COLORS.primary }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = COLORS.border; e.currentTarget.style.color = COLORS.textSecondary }}
            >{suggestion}</button>
          ))}
        </div>
      )}
    </div>
  )
}
