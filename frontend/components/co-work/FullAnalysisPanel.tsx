'use client'

import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const COLORS = {
  primary: '#C9A598', primaryLight: '#FBF4F1', cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D', textSecondary: '#6B6B6B', textMuted: '#9A9A9A',
  border: '#F0EEEC', success: '#9CB896',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface FullAnalysisPanelProps {
  label: string
  fullResults: any
  onClose: () => void
}

export default function FullAnalysisPanel({ label, fullResults, onClose }: FullAnalysisPanelProps) {
  if (!fullResults) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: COLORS.cardBg, fontFamily: FONT }}>
      <div style={{ padding: '14px 20px', borderBottom: `1px solid ${COLORS.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
          <span style={{ fontSize: '14px', fontWeight: 600, color: COLORS.textPrimary }}>{label} — Full Analysis</span>
        </div>
        <button onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', color: COLORS.textSecondary, fontSize: '18px', padding: '4px' }}>✕</button>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
        {renderResults(fullResults)}
      </div>
    </div>
  )
}

function renderResults(results: any): React.ReactNode {
  if (!results) return <p style={{ color: '#9A9A9A' }}>No detailed results available.</p>

  return (
    <div style={{ fontSize: '13px', lineHeight: '1.7', color: '#2D2D2D' }}>
      {Object.entries(results).map(([key, value]) => {
        if (key === 'raw_events') return null
        return (
          <div key={key} style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#6B6B6B', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
              {key.replace(/_/g, ' ')}
            </div>
            <div style={{ padding: '12px', backgroundColor: '#FAFAF9', borderRadius: '8px', border: '1px solid #F0EEEC' }}>
              {typeof value === 'string' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
              ) : Array.isArray(value) ? (
                <ul style={{ margin: 0, paddingLeft: '16px' }}>
                  {(value as any[]).map((item: any, i: number) => (
                    <li key={i} style={{ marginBottom: '4px' }}>
                      {typeof item === 'object' ? (
                        <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap' }}>{JSON.stringify(item, null, 2)}</pre>
                      ) : String(item)}
                    </li>
                  ))}
                </ul>
              ) : typeof value === 'object' && value !== null ? (
                <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap' }}>{JSON.stringify(value, null, 2)}</pre>
              ) : (
                <span>{String(value)}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
