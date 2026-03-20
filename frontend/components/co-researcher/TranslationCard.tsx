'use client'

import React, { useState } from 'react'
import { theme, font } from './theme'

// Wellspring Warm Design System - matches 2nd Brain
const t = {
  bg: theme.pageBg,
  surface: theme.cardBg,
  border: theme.border,
  borderStrong: theme.borderDark,
  text: theme.textPrimary,
  textSec: theme.textSecondary,
  textMuted: theme.textMuted,
  accent: theme.primary,
  accentBg: theme.primaryLight,
  accentBorder: '#E8D5CF',
  green: theme.success,
  greenBg: '#F5FAF4',
  greenBorder: '#C5DBC1',
  amber: theme.amber,
  amberBg: theme.amberLight,
  amberBorder: '#F5D89A',
  red: '#D97B7B',
  redBg: '#FDF2F2',
  redBorder: '#F0C4C4',
  blue: theme.primary,
  blueBg: theme.primaryLight,
  blueBorder: '#E8D5CF',
  mono: "'JetBrains Mono', 'SF Mono', monospace",
  font,
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

// Convert layer level to readable step name
const levelToStep: Record<string, { name: string; desc: string }> = {
  L1: { name: 'Core Technique', desc: 'The fundamental method or protocol' },
  L2: { name: 'Apply to Your System', desc: 'How to adapt it to your specific context' },
  L3: { name: 'Experimental Design', desc: 'How to structure your experiments' },
  L4: { name: 'Broader Principle', desc: 'The underlying concept that makes this work' },
}

export default function TranslationCard({ translation, adversarial, rank, isTop }: Props) {
  const [showDetails, setShowDetails] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const score = adversarial.survival_score
  const hasFatal = adversarial.has_fatal

  // Sort layers by confidence to show most reliable first
  const sortedLayers = [...translation.layers].sort((a, b) => b.confidence - a.confidence)

  // Get overall confidence
  const avgConfidence = translation.layers.reduce((sum, l) => sum + l.confidence, 0) / translation.layers.length

  // Get reliability badge
  const getReliabilityBadge = () => {
    if (hasFatal) return { text: 'Needs Validation', color: t.red, bg: t.redBg, border: t.redBorder }
    if (score >= 3) return { text: 'High Confidence', color: t.green, bg: t.greenBg, border: t.greenBorder }
    if (score >= 2) return { text: 'Moderate Confidence', color: t.amber, bg: t.amberBg, border: t.amberBorder }
    return { text: 'Low Confidence', color: t.red, bg: t.redBg, border: t.redBorder }
  }
  const badge = getReliabilityBadge()

  return (
    <div style={{
      borderRadius: 16, overflow: 'hidden',
      background: t.surface, border: `1px solid ${t.border}`,
      borderLeft: isTop ? `4px solid ${t.accent}` : `4px solid ${t.border}`,
    }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: `1px solid ${t.border}` }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          {/* Rank badge */}
          <div style={{
            width: 36, height: 36, borderRadius: 10, flexShrink: 0,
            background: isTop ? t.accentBg : t.bg,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: isTop ? t.accent : t.textMuted,
            fontSize: 15, fontWeight: 700, fontFamily: t.mono,
          }}>#{rank}</div>

          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Title */}
            <h3 style={{
              fontSize: 17, fontWeight: 600, color: t.text, margin: '0 0 6px',
              lineHeight: 1.35,
            }}>
              {translation.title}
            </h3>

            {/* Source */}
            <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 10 }}>
              {translation.paper_name && <span>From: <strong style={{ color: t.textSec }}>{translation.paper_name}</strong></span>}
            </div>

            {/* Quick badges */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span style={{
                padding: '4px 10px', borderRadius: 6,
                background: badge.bg, border: `1px solid ${badge.border}`,
                fontSize: 11, fontWeight: 600, color: badge.color,
              }}>
                {badge.text}
              </span>
              {isTop && (
                <span style={{
                  padding: '4px 10px', borderRadius: 6,
                  background: t.accentBg, border: `1px solid ${t.accentBorder}`,
                  fontSize: 11, fontWeight: 600, color: t.accent,
                }}>
                  Best Match
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* The Key Idea - always visible */}
      <div style={{ padding: '16px 24px', background: t.blueBg, borderBottom: `1px solid ${t.blueBorder}` }}>
        <div style={{
          fontSize: 11, fontWeight: 600, color: t.blue, marginBottom: 6,
          textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>
          The Key Insight
        </div>
        <p style={{
          fontSize: 14, color: t.text, lineHeight: 1.6, margin: 0,
        }}>
          {translation.source_insight}
        </p>
      </div>

      {/* Implementation Guide - always visible */}
      <div style={{ padding: '20px 24px' }}>
        <div style={{
          fontSize: 13, fontWeight: 600, color: t.text, marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={t.accent} strokeWidth="2.5">
            <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          How to Implement This
        </div>

        {/* Step-by-step implementation */}
        <div style={{ display: 'grid', gap: 12 }}>
          {sortedLayers.map((layer, i) => {
            const stepInfo = levelToStep[layer.level] || { name: `Step ${i + 1}`, desc: '' }
            const confColor = layer.confidence >= 0.7 ? t.green : layer.confidence >= 0.4 ? t.amber : t.red

            return (
              <div key={layer.level} style={{
                padding: '14px 16px', borderRadius: 10,
                background: t.bg, border: `1px solid ${t.border}`,
              }}>
                {/* Step header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{
                    width: 22, height: 22, borderRadius: 6,
                    background: confColor + '20', color: confColor,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700, fontFamily: t.mono,
                  }}>{i + 1}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>
                    {stepInfo.name}
                  </span>
                  <span style={{
                    marginLeft: 'auto', fontSize: 11, fontWeight: 600,
                    color: confColor, fontFamily: t.mono,
                  }}>
                    {(layer.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>

                {/* What to do */}
                <div style={{
                  fontSize: 13, color: t.text, lineHeight: 1.55, marginBottom: 8,
                  paddingLeft: 30,
                }}>
                  {layer.target}
                </div>

                {/* Original approach (collapsed) */}
                <div style={{
                  fontSize: 11, color: t.textMuted, paddingLeft: 30,
                  display: 'flex', alignItems: 'flex-start', gap: 6,
                }}>
                  <span style={{ color: t.textMuted, flexShrink: 0 }}>Based on:</span>
                  <span>{layer.source}</span>
                </div>
              </div>
            )
          })}
        </div>

        {/* What to test first - highlighted */}
        {translation.what_to_test_first && (
          <div style={{
            marginTop: 16, padding: '14px 16px', borderRadius: 10,
            background: t.greenBg, border: `1px solid ${t.greenBorder}`,
          }}>
            <div style={{
              fontSize: 11, fontWeight: 600, color: t.green, marginBottom: 4,
              textTransform: 'uppercase', letterSpacing: '0.05em',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
              Start Here
            </div>
            <p style={{ fontSize: 13, color: t.text, lineHeight: 1.55, margin: 0 }}>
              {translation.what_to_test_first}
            </p>
          </div>
        )}

        {/* Important Considerations */}
        {translation.overall_break_point && (
          <div style={{
            marginTop: 12, padding: '14px 16px', borderRadius: 10,
            background: t.amberBg, border: `1px solid ${t.amberBorder}`,
          }}>
            <div style={{
              fontSize: 11, fontWeight: 600, color: t.amber, marginBottom: 4,
              textTransform: 'uppercase', letterSpacing: '0.05em',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              Watch Out For
            </div>
            <p style={{ fontSize: 13, color: t.text, lineHeight: 1.55, margin: 0 }}>
              {translation.overall_break_point}
            </p>
          </div>
        )}
      </div>

      {/* Show More Details Toggle */}
      <div style={{ padding: '0 24px 16px' }}>
        <button
          onClick={() => setShowDetails(!showDetails)}
          style={{
            width: '100%', padding: '10px 16px', borderRadius: 8,
            background: t.bg, border: `1px solid ${t.border}`,
            color: t.textSec, fontSize: 13, fontWeight: 500,
            cursor: 'pointer', transition: 'all 0.15s',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}
        >
          {showDetails ? 'Hide' : 'Show'} Assumptions & Validation Details
          <svg
            width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
            style={{ transform: showDetails ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      {/* Expanded Details */}
      {showDetails && (
        <div style={{
          padding: '0 24px 20px',
          animation: 'co-fadeIn 0.2s ease',
        }}>
          {/* Assumptions section */}
          <div style={{ marginBottom: 16 }}>
            <div style={{
              fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 10,
              textTransform: 'uppercase', letterSpacing: '0.05em',
            }}>
              Key Assumptions
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {translation.layers.filter(l => l.assumption).map((layer, i) => (
                <div key={i} style={{
                  padding: '10px 14px', borderRadius: 8,
                  background: t.bg, border: `1px solid ${t.border}`,
                }}>
                  <div style={{ fontSize: 12, color: t.textSec, lineHeight: 1.5 }}>
                    <strong style={{ color: t.text }}>Assumes:</strong> {layer.assumption}
                  </div>
                  {layer.breaks_if && (
                    <div style={{ fontSize: 12, color: t.amber, lineHeight: 1.5, marginTop: 4 }}>
                      <strong>Breaks if:</strong> {layer.breaks_if}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Stress Test Results */}
          <div>
            <div style={{
              fontSize: 12, fontWeight: 600, color: t.textMuted, marginBottom: 10,
              textTransform: 'uppercase', letterSpacing: '0.05em',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span>Stress Test Results</span>
              <span style={{
                fontFamily: t.mono, color: score >= 3 ? t.green : score >= 2 ? t.amber : t.red,
              }}>
                {score}/4 passed
              </span>
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {adversarial.verdicts.map((v, i) => (
                <div key={i} style={{
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
                      padding: '2px 8px', borderRadius: 4,
                      background: v.verdict === 'survives' ? t.green : v.verdict === 'vulnerable' ? t.amber : t.red,
                      color: '#fff', textTransform: 'uppercase',
                    }}>{v.verdict}</span>
                  </div>
                  <div style={{ fontSize: 12, color: t.textSec, lineHeight: 1.5 }}>{v.attack}</div>
                  {v.what_would_change_my_mind && (
                    <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4, fontStyle: 'italic' }}>
                      Would reconsider if: {v.what_would_change_my_mind}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
