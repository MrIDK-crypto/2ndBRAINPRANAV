'use client'

import React, { useState } from 'react'

const t = {
  bg: '#f5f3f0', surface: '#fafaf9', border: '#e7e5e4', borderStrong: '#d6d3d1',
  text: '#1c1917', textSec: '#57534e', textMuted: '#a8a29e',
  accent: '#ea580c', accentBg: '#fff7ed', accentBorder: '#fed7aa',
  green: '#16a34a', greenBg: '#f0fdf4', greenBorder: '#bbf7d0',
  amber: '#d97706', amberBg: '#fffbeb', amberBorder: '#fde68a',
  red: '#dc2626', redBg: '#fef2f2', redBorder: '#fecaca',
  mono: "'JetBrains Mono', 'SF Mono', monospace",
}

interface LayerMapping {
  level: string
  source: string
  target: string
  confidence: number
  assumption: string
  breaks_if: string
}

interface Translation {
  title: string
  source_insight: string
  layers: LayerMapping[]
  overall_break_point: string
  what_to_test_first: string
  paper_name?: string
}

interface Verdict {
  agent_id: string
  agent_name: string
  agent_color: string
  agent_role: string
  verdict: 'survives' | 'vulnerable' | 'fatal'
  attack: string
  what_would_change_my_mind?: string
  [key: string]: any
}

interface AdversarialResult {
  survival_score: number
  has_fatal: boolean
  verdicts: Verdict[]
}

interface Props {
  translation: Translation
  adversarial: AdversarialResult
  rank: number
  isTop: boolean
}

export default function TranslationCard({ translation, adversarial, rank, isTop }: Props) {
  const [expanded, setExpanded] = useState(isTop)
  const [showVerdicts, setShowVerdicts] = useState(false)

  const score = adversarial.survival_score
  const shields = Array.from({ length: 4 }, (_, i) => {
    const verdict = adversarial.verdicts[i]
    if (!verdict) return 'missing'
    return verdict.verdict
  })

  const breakLayer = translation.overall_break_point?.match(/L[1-4]/)?.[0]

  return (
    <div style={{
      borderRadius: 14, overflow: 'hidden',
      background: t.surface, border: `1px solid ${t.border}`,
      borderLeft: isTop ? `3px solid ${t.accent}` : `3px solid ${t.border}`,
    }}>
      {/* Header — always visible */}
      <div
        style={{
          padding: '18px 22px', cursor: 'pointer',
          display: 'flex', alignItems: 'flex-start', gap: 12,
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{
          width: 28, height: 28, borderRadius: 8, flexShrink: 0,
          background: isTop ? t.accentBg : t.bg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: isTop ? t.accent : t.textMuted,
          fontSize: 13, fontWeight: 700, fontFamily: t.mono,
        }}>{rank}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: t.text, marginBottom: 4 }}>
            {translation.title}
          </div>
          <div style={{ fontSize: 12, color: t.textMuted }}>
            {translation.paper_name && <span>from {translation.paper_name} &middot; </span>}
            {translation.source_insight}
          </div>
        </div>

        {/* Survival shields */}
        <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
          {shields.map((s, i) => (
            <div key={i} style={{
              width: 22, height: 22, borderRadius: 6,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12,
              background: s === 'survives' ? t.greenBg : s === 'vulnerable' ? t.amberBg : s === 'fatal' ? t.redBg : t.bg,
              color: s === 'survives' ? t.green : s === 'vulnerable' ? t.amber : s === 'fatal' ? t.red : t.textMuted,
              border: `1px solid ${s === 'survives' ? t.greenBorder : s === 'vulnerable' ? t.amberBorder : s === 'fatal' ? t.redBorder : t.border}`,
            }}>
              {s === 'survives' ? '\u2713' : s === 'vulnerable' ? '!' : s === 'fatal' ? '\u2715' : '?'}
            </div>
          ))}
        </div>

        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke={t.textMuted} strokeWidth="2" strokeLinecap="round"
          style={{ flexShrink: 0, transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: '0 22px 22px' }}>
          {/* Layer breakdown */}
          <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
            {translation.layers.map(layer => {
              const isBreak = breakLayer === layer.level
              const confColor = layer.confidence >= 0.7 ? t.green : layer.confidence >= 0.4 ? t.amber : t.red
              return (
                <div key={layer.level} style={{
                  padding: '12px 14px', borderRadius: 10,
                  background: isBreak ? t.amberBg : t.bg,
                  border: `1px solid ${isBreak ? t.amberBorder : t.border}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{
                      fontFamily: t.mono, fontSize: 11, fontWeight: 700,
                      color: isBreak ? t.amber : t.textMuted,
                    }}>{layer.level}</span>
                    <div style={{
                      flex: 1, height: 3, borderRadius: 2, background: `${confColor}30`,
                    }}>
                      <div style={{
                        height: '100%', borderRadius: 2, background: confColor,
                        width: `${layer.confidence * 100}%`, transition: 'width 0.3s',
                      }} />
                    </div>
                    <span style={{
                      fontFamily: t.mono, fontSize: 11, fontWeight: 600, color: confColor,
                    }}>{(layer.confidence * 100).toFixed(0)}%</span>
                    {isBreak && (
                      <span style={{
                        fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
                        textTransform: 'uppercase', color: t.amber,
                      }}>BREAK POINT</span>
                    )}
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 24px 1fr', gap: 8, marginBottom: 8 }}>
                    <div style={{ fontSize: 12, color: t.textSec, lineHeight: 1.5 }}>
                      <span style={{ fontSize: 10, fontWeight: 600, color: t.textMuted, display: 'block', marginBottom: 2 }}>SOURCE</span>
                      {layer.source}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: t.textMuted }}>
                      &rarr;
                    </div>
                    <div style={{ fontSize: 12, color: t.text, lineHeight: 1.5 }}>
                      <span style={{ fontSize: 10, fontWeight: 600, color: t.accent, display: 'block', marginBottom: 2 }}>YOUR DOMAIN</span>
                      {layer.target}
                    </div>
                  </div>

                  {layer.assumption && (
                    <div style={{ fontSize: 11, color: t.textMuted, lineHeight: 1.4, marginBottom: 2 }}>
                      <strong>Assumes:</strong> {layer.assumption}
                    </div>
                  )}
                  {layer.breaks_if && (
                    <div style={{ fontSize: 11, color: isBreak ? t.amber : t.textMuted, lineHeight: 1.4 }}>
                      <strong>Breaks if:</strong> {layer.breaks_if}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* What to test first */}
          {translation.what_to_test_first && (
            <div style={{
              padding: '10px 14px', borderRadius: 8, marginBottom: 14,
              background: t.greenBg, border: `1px solid ${t.greenBorder}`,
            }}>
              <span style={{ color: t.green, fontWeight: 600, fontSize: 12 }}>Test first: </span>
              <span style={{ color: t.textSec, fontSize: 12, lineHeight: 1.5 }}>
                {translation.what_to_test_first}
              </span>
            </div>
          )}

          {/* Adversarial verdicts toggle */}
          <button
            onClick={() => setShowVerdicts(!showVerdicts)}
            style={{
              padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500,
              background: t.bg, border: `1px solid ${t.border}`,
              color: t.textSec, cursor: 'pointer', transition: 'all 0.15s',
              marginBottom: showVerdicts ? 10 : 0,
            }}
          >
            {showVerdicts ? 'Hide' : 'Show'} stress-test details ({score}/4 survived)
          </button>

          {showVerdicts && (
            <div style={{ display: 'grid', gap: 6 }}>
              {adversarial.verdicts.map(v => (
                <div key={v.agent_id} style={{
                  padding: '10px 14px', borderRadius: 8,
                  background: v.verdict === 'survives' ? t.greenBg : v.verdict === 'vulnerable' ? t.amberBg : t.redBg,
                  border: `1px solid ${v.verdict === 'survives' ? t.greenBorder : v.verdict === 'vulnerable' ? t.amberBorder : t.redBorder}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: v.agent_color }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: t.text }}>{v.agent_name}</span>
                    <span style={{ fontSize: 10, color: t.textMuted }}>{v.agent_role}</span>
                    <span style={{
                      marginLeft: 'auto', fontSize: 10, fontWeight: 700,
                      color: v.verdict === 'survives' ? t.green : v.verdict === 'vulnerable' ? t.amber : t.red,
                      textTransform: 'uppercase',
                    }}>{v.verdict}</span>
                  </div>
                  <div style={{ fontSize: 12, color: t.textSec, lineHeight: 1.5 }}>{v.attack}</div>
                  {v.what_would_change_my_mind && (
                    <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4, lineHeight: 1.4 }}>
                      <em>Would reconsider if: {v.what_would_change_my_mind}</em>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
