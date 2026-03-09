'use client'

import React, { useState, useRef, useEffect } from 'react'

// ── Design tokens ──
const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  cardBg: '#FFFFFF',
  pageBg: '#FAF9F7',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
  error: '#D97B7B',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

// Source type badge colors — keyed by source_origin and display labels
const SOURCE_BADGE_COLORS: Record<string, string> = {
  'Your KB': '#9CB896',
  'CTSI Research': '#7BA7C9',
  'PubMed': '#93C5FD',
  'Journal DB': '#A5B4FC',
  'Repro Archive': '#FFB74D',
  'Knowledge Base': '#C9A598',
  'Reproducibility': '#FCA5A5',
  'OpenAlex': '#F59E0B',
  // Also keyed by source_origin codes
  'user_kb': '#9CB896',
  'ctsi': '#7BA7C9',
  'pubmed': '#93C5FD',
  'journal': '#A5B4FC',
  'reproducibility': '#FFB74D',
  'openalex': '#F59E0B',
}

// ── Types ──
export interface ThinkingStep {
  type: string
  text: string
  status: 'active' | 'done'
}

export interface ResearchBrief {
  heading: string
  description: string
  keyPoints: string[]
}

export interface ContextData {
  documents?: any[]
  pubmed_papers?: any[]
  journals?: any[]
  experiments?: any[]
  experiment_suggestions?: any[]
  feasibility_check?: any
}

interface CoWorkContextProps {
  thinkingSteps: ThinkingStep[]
  brief: ResearchBrief | null
  sources: ContextData | null
}

// Map thinking step types to display labels
const THINKING_LABELS: Record<string, string> = {
  searching_kb: 'Knowledge Base',
  searching_pubmed: 'PubMed',
  searching_journals: 'Journal DB',
  searching_experiments: 'Reproducibility Archive',
  reranking: 'Re-ranking results',
  thinking: 'Processing',
}

export default function CoWorkContext({ thinkingSteps, brief, sources }: CoWorkContextProps) {
  const [briefCollapsed, setBriefCollapsed] = useState(false)
  const [expandedSource, setExpandedSource] = useState<number | null>(null)
  const thinkingEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll thinking steps
  useEffect(() => {
    thinkingEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [thinkingSteps])

  // Combine all sources from ContextData into a flat list
  // Use source_origin_label from each item (set by backend) with fallback to array-based type
  const allSources: { item: any; type: string }[] = []
  if (sources?.documents) {
    sources.documents.forEach(d => allSources.push({
      item: d,
      type: d.source_origin_label || (d.is_shared ? 'CTSI Research' : 'Your KB'),
    }))
  }
  if (sources?.pubmed_papers) {
    sources.pubmed_papers.forEach(d => allSources.push({
      item: d,
      type: d.source_origin_label || 'PubMed',
    }))
  }
  if (sources?.journals) {
    sources.journals.forEach(d => allSources.push({
      item: d,
      type: d.source_origin_label || 'Journal DB',
    }))
  }
  if (sources?.experiments) {
    sources.experiments.forEach(d => allSources.push({
      item: d,
      type: d.source_origin_label || 'Repro Archive',
    }))
  }

  // Deduplicate sources by title (same document may appear as multiple chunks)
  const seen = new Set<string>()
  const dedupedSources = allSources.filter(({ item }) => {
    const title = (item.subject || item.title || item.name || '').toLowerCase().trim()
    if (!title || seen.has(title)) return false
    seen.add(title)
    return true
  })

  // Extract experiment suggestions and feasibility from sources prop
  const experimentSuggestions = sources?.experiment_suggestions || []
  const feasibilityResult = sources?.feasibility_check || null

  const hasContent = brief || thinkingSteps.length > 0 || dedupedSources.length > 0 || experimentSuggestions.length > 0 || feasibilityResult

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: COLORS.cardBg,
      /* borderLeft handled by parent layout */
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
          <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
          <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
        </svg>
        <span style={{ fontSize: '14px', fontWeight: 600, color: COLORS.textPrimary }}>
          Context
        </span>
      </div>

      {/* Scrollable content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
      }}>
        {!hasContent ? (
          // Empty state
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
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              backgroundColor: COLORS.primaryLight,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={COLORS.textMuted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
                <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
              </svg>
            </div>
            <p style={{
              fontSize: '13px',
              color: COLORS.textMuted,
              lineHeight: '1.5',
              maxWidth: '200px',
            }}>
              Context, sources, and thinking steps will appear here as you chat
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* ── Research Brief ── */}
            {brief && (
              <div>
                <button
                  onClick={() => setBriefCollapsed(!briefCollapsed)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0 0 8px',
                    fontFamily: FONT,
                    width: '100%',
                  }}
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={COLORS.textMuted}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{
                      transform: briefCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
                      transition: 'transform 0.15s ease',
                    }}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                  </svg>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: COLORS.textPrimary }}>
                    Research brief
                  </span>
                </button>

                {!briefCollapsed && (
                  <div style={{
                    padding: '12px 14px',
                    backgroundColor: COLORS.pageBg,
                    borderRadius: '10px',
                    border: `1px solid ${COLORS.border}`,
                  }}>
                    {brief.heading && (
                      <div style={{
                        fontSize: '14px',
                        fontWeight: 600,
                        color: COLORS.textPrimary,
                        marginBottom: '6px',
                      }}>
                        {brief.heading}
                      </div>
                    )}
                    {brief.description && (
                      <p style={{
                        fontSize: '13px',
                        color: COLORS.textSecondary,
                        lineHeight: '1.5',
                        margin: '0 0 8px',
                      }}>
                        {brief.description}
                      </p>
                    )}
                    {brief.keyPoints && brief.keyPoints.length > 0 && (
                      <ul style={{
                        margin: 0,
                        padding: '0 0 0 16px',
                        listStyleType: 'disc',
                      }}>
                        {brief.keyPoints.map((point, i) => (
                          <li key={i} style={{
                            fontSize: '12px',
                            color: COLORS.textSecondary,
                            lineHeight: '1.5',
                            marginBottom: '3px',
                          }}>
                            {point}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── RAG Thinking ── */}
            {thinkingSteps.length > 0 && (
              <div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginBottom: '10px',
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: COLORS.textPrimary }}>
                    Thinking
                  </span>
                </div>

                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  position: 'relative',
                  paddingLeft: '14px',
                }}>
                  {/* Vertical connector line */}
                  <div style={{
                    position: 'absolute',
                    left: '5px',
                    top: '6px',
                    bottom: '6px',
                    width: '1px',
                    backgroundColor: COLORS.border,
                  }} />

                  {thinkingSteps.map((step, i) => {
                    const isDone = step.status === 'done'
                    const label = THINKING_LABELS[step.type] || step.type

                    return (
                      <div
                        key={i}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '4px 0',
                          position: 'relative',
                        }}
                      >
                        {/* Node dot */}
                        <div style={{
                          position: 'absolute',
                          left: '-14px',
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          backgroundColor: isDone ? COLORS.success : COLORS.cardBg,
                          border: isDone ? 'none' : `2px solid ${COLORS.primary}`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}>
                          {isDone && (
                            <svg width="7" height="7" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </div>

                        {/* Spinner for active steps */}
                        {!isDone && (
                          <div style={{
                            width: '12px',
                            height: '12px',
                            borderRadius: '50%',
                            border: `2px solid ${COLORS.border}`,
                            borderTopColor: COLORS.primary,
                            animation: 'cowork-ctx-spin 0.8s linear infinite',
                            flexShrink: 0,
                          }} />
                        )}

                        <span style={{
                          fontSize: '12px',
                          color: isDone ? COLORS.textMuted : COLORS.textPrimary,
                          fontWeight: isDone ? 400 : 500,
                        }}>
                          {step.text || label}
                        </span>

                        {/* Type label */}
                        {step.type && step.text && (
                          <span style={{
                            fontSize: '10px',
                            color: COLORS.textMuted,
                            backgroundColor: COLORS.pageBg,
                            padding: '1px 6px',
                            borderRadius: '4px',
                            marginLeft: 'auto',
                            flexShrink: 0,
                          }}>
                            {label}
                          </span>
                        )}
                      </div>
                    )
                  })}
                  <div ref={thinkingEndRef} />
                </div>
              </div>
            )}

            {/* ── Sources ── */}
            {dedupedSources.length > 0 && (
              <div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginBottom: '10px',
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
                  </svg>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: COLORS.textPrimary }}>
                    Sources
                  </span>
                  <span style={{
                    fontSize: '11px',
                    color: COLORS.textMuted,
                    backgroundColor: COLORS.pageBg,
                    padding: '1px 6px',
                    borderRadius: '8px',
                    marginLeft: '4px',
                  }}>
                    {dedupedSources.length}
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {dedupedSources.map(({ item, type }, idx) => {
                    const isExpanded = expandedSource === idx
                    const title = item.subject || item.title || item.name || `Source ${idx + 1}`
                    // Only show score as percentage if it's a valid 0-1 similarity score
                    // Cross-encoder rerank scores can be negative logits — hide those
                    const rawScore = item.score
                    const score = (rawScore != null && rawScore >= 0 && rawScore <= 1)
                      ? Math.round(rawScore * 100)
                      : null
                    const preview = item.content || item.abstract || item.content_preview || ''
                    const badgeColor = SOURCE_BADGE_COLORS[type] || COLORS.primary

                    return (
                      <div
                        key={idx}
                        onClick={() => setExpandedSource(isExpanded ? null : idx)}
                        style={{
                          padding: '10px 12px',
                          borderRadius: '8px',
                          border: `1px solid ${COLORS.border}`,
                          backgroundColor: isExpanded ? COLORS.pageBg : COLORS.cardBg,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          if (!isExpanded) e.currentTarget.style.backgroundColor = COLORS.pageBg
                        }}
                        onMouseLeave={(e) => {
                          if (!isExpanded) e.currentTarget.style.backgroundColor = COLORS.cardBg
                        }}
                      >
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}>
                          {/* Type badge */}
                          <span style={{
                            padding: '1px 6px',
                            borderRadius: '4px',
                            backgroundColor: `${badgeColor}20`,
                            color: badgeColor,
                            fontSize: '10px',
                            fontWeight: 600,
                            flexShrink: 0,
                            letterSpacing: '0.02em',
                          }}>
                            {type}
                          </span>

                          {/* Title */}
                          <span style={{
                            fontSize: '12px',
                            fontWeight: 500,
                            color: COLORS.textPrimary,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            flex: 1,
                          }}>
                            {typeof title === 'string' ? title.split('/').pop() : title}
                          </span>

                          {/* Score */}
                          {score !== null && (
                            <span style={{
                              fontSize: '10px',
                              color: COLORS.textMuted,
                              flexShrink: 0,
                            }}>
                              {score}%
                            </span>
                          )}
                        </div>

                        {/* Expanded preview */}
                        {isExpanded && preview && (
                          <div style={{
                            marginTop: '8px',
                            paddingTop: '8px',
                            borderTop: `1px solid ${COLORS.border}`,
                            fontSize: '12px',
                            lineHeight: '1.5',
                            color: COLORS.textSecondary,
                            maxHeight: '120px',
                            overflow: 'hidden',
                          }}>
                            {typeof preview === 'string' ? preview.slice(0, 300) : ''}
                            {typeof preview === 'string' && preview.length > 300 && '...'}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* ── Experiment Suggestions ── */}
            {experimentSuggestions.length > 0 && (
              <div>
                <div style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: COLORS.textSecondary,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  marginBottom: '8px',
                }}>
                  Experiment Suggestions
                </div>
                {experimentSuggestions.map((s: any, i: number) => {
                  const score = s.deep_feasibility?.score ?? s.feasibility?.overall ?? 0
                  const tier = s.deep_feasibility?.tier ?? s.feasibility?.feasibility_tier ?? 'unknown'
                  const tierColor = tier === 'high' ? '#9CB896' : tier === 'medium' ? '#D4A853' : '#D97B7B'

                  return (
                    <div key={i} style={{
                      padding: '10px 12px',
                      marginBottom: '6px',
                      borderRadius: '8px',
                      backgroundColor: COLORS.cardBg,
                      border: `1px solid ${COLORS.border}`,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: COLORS.textPrimary }}>{s.title}</span>
                        <span style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          color: tierColor,
                          backgroundColor: `${tierColor}15`,
                          textTransform: 'uppercase',
                          flexShrink: 0,
                          marginLeft: '8px',
                        }}>
                          {tier} ({Math.round(score * 100)}%)
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', color: COLORS.textSecondary, marginBottom: '4px' }}>
                        {s.hypothesis || s.methodology?.slice(0, 100) || ''}
                      </div>
                      {s.deep_feasibility?.issues?.length > 0 && (
                        <div style={{ fontSize: '11px', color: '#D97B7B', marginTop: '4px' }}>
                          {s.deep_feasibility.issues.map((issue: any, j: number) => (
                            <div key={j}>&#x26A0; {issue.description}</div>
                          ))}
                        </div>
                      )}
                      {s.deep_feasibility?.modifications?.length > 0 && (
                        <div style={{ fontSize: '11px', color: '#9CB896', marginTop: '4px' }}>
                          {s.deep_feasibility.modifications.map((mod: any, j: number) => (
                            <div key={j}>{'\u2192'} {mod.suggested}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* ── Feasibility Assessment ── */}
            {feasibilityResult && (
              <div>
                <div style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: COLORS.textSecondary,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  marginBottom: '8px',
                }}>
                  Feasibility Assessment
                </div>
                <div style={{
                  padding: '12px',
                  borderRadius: '8px',
                  backgroundColor: COLORS.cardBg,
                  border: `1px solid ${COLORS.border}`,
                }}>
                  {/* Score bar */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <div style={{
                      flex: 1, height: '6px', borderRadius: '3px', backgroundColor: COLORS.border,
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${Math.round((feasibilityResult.score || 0) * 100)}%`,
                        height: '100%',
                        borderRadius: '3px',
                        backgroundColor: feasibilityResult.tier === 'high' ? '#9CB896' :
                                       feasibilityResult.tier === 'medium' ? '#D4A853' : '#D97B7B',
                      }} />
                    </div>
                    <span style={{
                      fontSize: '12px', fontWeight: 600,
                      color: feasibilityResult.tier === 'high' ? '#9CB896' :
                             feasibilityResult.tier === 'medium' ? '#D4A853' : '#D97B7B',
                    }}>
                      {Math.round((feasibilityResult.score || 0) * 100)}%
                    </span>
                  </div>

                  {/* Reasoning */}
                  {feasibilityResult.reasoning && (
                    <div style={{ fontSize: '12px', color: COLORS.textPrimary, marginBottom: '8px' }}>
                      {feasibilityResult.reasoning}
                    </div>
                  )}

                  {/* Evidence summary */}
                  <div style={{ fontSize: '11px', color: COLORS.textMuted }}>
                    {feasibilityResult.evidence?.cooccurrence_hits > 0 && (
                      <span>{feasibilityResult.evidence.cooccurrence_hits} validated pairs &middot; </span>
                    )}
                    {feasibilityResult.evidence?.corpus_matches > 0 && (
                      <span>{feasibilityResult.evidence.corpus_matches} similar protocols &middot; </span>
                    )}
                    {feasibilityResult.evidence?.unsupported_pairs > 0 && (
                      <span style={{ color: '#D97B7B' }}>{feasibilityResult.evidence.unsupported_pairs} unsupported</span>
                    )}
                  </div>

                  {/* Issues */}
                  {feasibilityResult.issues?.length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      {feasibilityResult.issues.map((issue: any, i: number) => (
                        <div key={i} style={{
                          fontSize: '11px',
                          color: issue.severity === 'critical' ? '#D97B7B' : '#D4A853',
                          padding: '4px 0',
                        }}>
                          {issue.severity === 'critical' ? '\u2715' : '\u26A0'} {issue.description}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Modifications */}
                  {feasibilityResult.modifications?.length > 0 && (
                    <div style={{ marginTop: '8px', padding: '8px', borderRadius: '6px', backgroundColor: '#F7FAF7' }}>
                      <div style={{ fontSize: '11px', fontWeight: 600, color: '#9CB896', marginBottom: '4px' }}>
                        Suggested Modifications
                      </div>
                      {feasibilityResult.modifications.map((mod: any, i: number) => (
                        <div key={i} style={{ fontSize: '11px', color: COLORS.textSecondary, padding: '2px 0' }}>
                          <span style={{ textDecoration: 'line-through', color: COLORS.textMuted }}>{mod.original}</span>
                          {' \u2192 '}
                          <span style={{ color: '#9CB896' }}>{mod.suggested}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Keyframe animations */}
      <style>{`
        @keyframes cowork-ctx-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
