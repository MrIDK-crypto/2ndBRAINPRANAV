'use client'

import React, { useState, useCallback } from 'react'
import UploadPanel from '@/components/co-researcher/UploadPanel'
import TranslationCard from '@/components/co-researcher/TranslationCard'
import ChatPanel from '@/components/co-researcher/ChatPanel'
import TopNav from '@/components/shared/TopNav'
import { useAuth } from '@/contexts/AuthContext'

// Co-researcher routes are now integrated into main backend on port 5002
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5002') + '/api/co-researcher'

// Context analysis type for enhanced mode
interface ContextAnalysis {
  has_context?: boolean
  no_context_reason?: string
  documents_searched?: number
  tip?: string
  domain_expertise_match?: { score: number; assessment: string; leverageable_expertise?: string[] }
  methodology_transferability?: { summary: string; relevant_methods?: string[] }
  equipment_compatibility?: { score: number; assessment: string; available_equipment?: string[]; may_need?: string[] }
  translation_advantages?: string[]
  potential_pitfalls?: string[]
  recommended_focus?: { area: string; rationale: string }
  sources?: Record<string, Array<{ title?: string; source_type?: string; excerpt?: string }>>
}

// Wellspring Warm theme - matching 2nd Brain design system
const t = {
  bg: '#FAF9F7', surface: '#FFFFFF', border: '#F0EEEC', borderStrong: '#E8E5E2',
  text: '#2D2D2D', textSec: '#6B6B6B', textMuted: '#9A9A9A',
  accent: '#C9A598', accentBg: '#FBF4F1', accentBorder: '#E8D5CF',
  green: '#9CB896', greenBg: '#F5FAF4', greenBorder: '#C5DBC1',
  amber: '#E2A336', amberBg: '#FEF7E8', amberBorder: '#F5D89A',
  red: '#D97B7B', redBg: '#FDF2F2', redBorder: '#F0C4C4',
  font: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', monospace",
}

type Phase = 'upload' | 'analyzing' | 'translating' | 'stress_testing' | 'results'

function Spinner({ size = 16, color = t.accent }: { size?: number; color?: string }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      border: `2px solid ${color}30`, borderTopColor: color,
      animation: 'co-spin 0.8s linear infinite', flexShrink: 0,
    }} />
  )
}

function Overline({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 600, letterSpacing: '0.1em',
      textTransform: 'uppercase' as const, color: t.textMuted, marginBottom: 6,
    }}>{children}</div>
  )
}

function ProgressBar({ value, color = t.accent }: { value: number; color?: string }) {
  return (
    <div style={{ height: 4, background: t.border, borderRadius: 2 }}>
      <div style={{
        height: '100%', borderRadius: 2, transition: 'width 0.4s ease',
        background: color, width: `${Math.min(value, 100)}%`,
      }} />
    </div>
  )
}

export default function ResearchReproducibilityPage() {
  const { user } = useAuth()
  const [phase, setPhase] = useState<Phase>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Parsing
  const [parseProgress, setParseProgress] = useState({ progress: 0, message: '' })

  // Context extraction
  const [targetContext, setTargetContext] = useState<any>(null)
  const [sourceContexts, setSourceContexts] = useState<any[]>([])

  // Decomposition
  const [decompositions, setDecompositions] = useState<any[]>([])
  const [decompStatus, setDecompStatus] = useState({ total: 0, done: 0 })

  // Translation
  const [translations, setTranslations] = useState<any[]>([])
  const [transStatus, setTransStatus] = useState({ total: 0, done: 0 })

  // Adversarial
  const [adversarialResults, setAdversarialResults] = useState<any[]>([])
  const [advStatus, setAdvStatus] = useState({ total: 0, done: 0 })
  const [liveVerdicts, setLiveVerdicts] = useState<any[]>([])

  // Results
  const [rankedTranslations, setRankedTranslations] = useState<any[]>([])
  const [rankedAdversarial, setRankedAdversarial] = useState<any[]>([])
  const [chatReady, setChatReady] = useState(false)

  // Context-aware mode
  const [contextAnalysis, setContextAnalysis] = useState<ContextAnalysis | null>(null)
  const [labProfileApplied, setLabProfileApplied] = useState(false)
  const [isContextEnhanced, setIsContextEnhanced] = useState(false)

  const startStream = (sid: string) => {
    const es = new EventSource(`${API_BASE}/stream/${sid}`)

    es.addEventListener('parsing_status', e => {
      const d = JSON.parse(e.data)
      setParseProgress({ progress: d.progress, message: d.message })
    })

    // Context-aware events
    es.addEventListener('context_analysis', e => {
      const d = JSON.parse(e.data)
      setContextAnalysis(d)
      setIsContextEnhanced(true)
    })

    es.addEventListener('lab_profile_applied', e => {
      const d = JSON.parse(e.data)
      setLabProfileApplied(true)
      setParseProgress(prev => ({ ...prev, message: d.message }))
    })

    es.addEventListener('context_extracting', e => {
      const d = JSON.parse(e.data)
      setParseProgress(prev => ({ ...prev, message: d.message }))
    })

    es.addEventListener('context_extracted', e => {
      const d = JSON.parse(e.data)
      if (d.role === 'target') {
        setTargetContext(d.context)
      } else {
        setSourceContexts(prev => {
          const next = [...prev]
          next[d.paper_index] = { ...d.context, paper_name: d.paper_name }
          return next
        })
      }
    })

    es.addEventListener('decomposition_started', e => {
      const d = JSON.parse(e.data)
      setDecompStatus(prev => ({ ...prev, total: prev.total + d.item_count }))
      setPhase('analyzing')
    })

    es.addEventListener('layer_extracted', e => {
      const d = JSON.parse(e.data)
      setDecompositions(prev => [...prev, d])
      setDecompStatus(prev => ({ ...prev, done: prev.done + 1 }))
    })

    es.addEventListener('decomposition_complete', () => {})

    es.addEventListener('translation_started', e => {
      const d = JSON.parse(e.data)
      setTransStatus({ total: d.total, done: 0 })
      setPhase('translating')
    })

    es.addEventListener('translating_insight', e => {
      const d = JSON.parse(e.data)
      setParseProgress(prev => ({ ...prev, message: `Translating: ${d.item_name}` }))
    })

    es.addEventListener('translation_complete', e => {
      const d = JSON.parse(e.data)
      setTranslations(prev => [...prev, d.translation])
      setTransStatus(prev => ({ ...prev, done: prev.done + 1 }))
    })

    es.addEventListener('adversarial_started', e => {
      const d = JSON.parse(e.data)
      setAdvStatus({ total: d.total_translations, done: 0 })
      setPhase('stress_testing')
    })

    es.addEventListener('adversarial_testing', e => {
      const d = JSON.parse(e.data)
      setParseProgress(prev => ({ ...prev, message: d.message }))
    })

    es.addEventListener('agent_verdict', e => {
      const d = JSON.parse(e.data)
      setLiveVerdicts(prev => [...prev, d])
    })

    es.addEventListener('adversarial_complete', e => {
      const d = JSON.parse(e.data)
      setAdversarialResults(prev => [...prev, d])
      setAdvStatus(prev => ({ ...prev, done: prev.done + 1 }))
    })

    es.addEventListener('results_ready', e => {
      const d = JSON.parse(e.data)
      setRankedTranslations(d.translations)
      setRankedAdversarial(d.adversarial)
      setPhase('results')
    })

    es.addEventListener('chat_ready', () => {
      setChatReady(true)
    })

    es.addEventListener('error', e => {
      if (es.readyState === EventSource.CLOSED) return
      try {
        const d = JSON.parse((e as any).data)
        setError(d.message)
      } catch {}
    })

    es.addEventListener('pipeline_complete', () => {
      es.close()
    })
  }

  const handleUpload = useCallback(async (myResearch: File | null, papers: File[], researchDescription?: string, paperUrls?: string[]) => {
    setError(null)
    const formData = new FormData()

    // Support both file upload and text description
    if (myResearch) {
      formData.append('my_research', myResearch)
    } else if (researchDescription) {
      formData.append('research_description', researchDescription)
    }

    papers.forEach(p => formData.append('papers', p))

    // Add paper URLs if provided
    if (paperUrls && paperUrls.length > 0) {
      formData.append('paper_urls', JSON.stringify(paperUrls))
    }

    try {
      // Use context-aware endpoint if user is logged in
      const token = localStorage.getItem('access_token')
      const endpoint = token ? `${API_BASE}/analyze-with-context` : `${API_BASE}/analyze`

      const headers: HeadersInit = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const resp = await fetch(endpoint, {
        method: 'POST',
        body: formData,
        headers,
      })

      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.error || 'Upload failed')
      }
      const data = await resp.json()
      setSessionId(data.session_id)
      setIsContextEnhanced(data.context_enhanced || false)
      setPhase('analyzing')
      startStream(data.session_id)
    } catch (e: any) {
      setError(e.message)
    }
  }, [])

  const handleReset = () => {
    setPhase('upload')
    setSessionId(null)
    setError(null)
    setParseProgress({ progress: 0, message: '' })
    setTargetContext(null)
    setSourceContexts([])
    setDecompositions([])
    setDecompStatus({ total: 0, done: 0 })
    setTranslations([])
    setTransStatus({ total: 0, done: 0 })
    setAdversarialResults([])
    setAdvStatus({ total: 0, done: 0 })
    setLiveVerdicts([])
    setRankedTranslations([])
    setRankedAdversarial([])
    setChatReady(false)
    setContextAnalysis(null)
    setLabProfileApplied(false)
    setIsContextEnhanced(false)
  }

  return (
    <>
      <style suppressHydrationWarning>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
        @keyframes co-spin { to { transform: rotate(360deg) } }
        @keyframes co-fadeIn { from { opacity: 0; transform: translateY(6px) } to { opacity: 1; transform: translateY(0) } }
        .co-markdown h1 { font-size: 18px; font-weight: 600; margin: 0 0 10px; color: ${t.text}; }
        .co-markdown h2 { font-size: 15px; font-weight: 600; margin: 18px 0 6px; color: ${t.text}; border-bottom: 1px solid ${t.border}; padding-bottom: 4px; }
        .co-markdown h3 { font-size: 13px; font-weight: 600; margin: 14px 0 4px; color: ${t.text}; }
        .co-markdown p { margin: 0 0 8px; line-height: 1.65; }
        .co-markdown ul, .co-markdown ol { margin: 0 0 10px; padding-left: 18px; }
        .co-markdown li { margin-bottom: 3px; line-height: 1.55; }
        .co-markdown strong { color: ${t.text}; font-weight: 600; }
        .co-markdown code { font-family: 'JetBrains Mono', monospace; font-size: 12px; background: ${t.bg}; padding: 1px 4px; border-radius: 3px; color: ${t.accent}; }
        .co-markdown blockquote { margin: 0 0 10px; padding: 6px 12px; border-left: 3px solid ${t.borderStrong}; background: ${t.bg}; border-radius: 0 6px 6px 0; color: ${t.textSec}; }
      `}</style>

      <div style={{ minHeight: '100vh', background: t.bg, fontFamily: t.font, color: t.text }}>
        {/* Top Navigation */}
        <TopNav userName={user?.full_name?.split(' ')[0] || 'Researcher'} />

        {/* Header */}
        <header style={{
          padding: '16px 32px', borderBottom: `1px solid ${t.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: t.surface,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8, background: t.accent,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
                <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600, color: t.text, letterSpacing: '-0.01em' }}>Research Translator</div>
              <div style={{ fontSize: 11, color: t.textMuted }}>Cross-Domain Idea Translation</div>
            </div>
          </div>
          {phase !== 'upload' && (
            <button onClick={handleReset} style={{
              padding: '6px 14px', borderRadius: 8,
              background: t.surface, border: `1px solid ${t.border}`,
              color: t.textSec, fontSize: 13, fontWeight: 500,
              cursor: 'pointer',
            }}>New Analysis</button>
          )}
        </header>

        {error && (
          <div style={{
            margin: '16px 32px 0', padding: '10px 16px', borderRadius: 10,
            background: t.redBg, border: `1px solid ${t.redBorder}`,
            color: t.red, fontSize: 13,
          }}>{error}</div>
        )}

        <main style={{ maxWidth: 900, margin: '0 auto', padding: '0 32px 64px' }}>

          {/* UPLOAD */}
          {phase === 'upload' && <UploadPanel onUpload={handleUpload} />}

          {/* ANALYZING */}
          {phase === 'analyzing' && (
            <div style={{ paddingTop: 40 }}>
              <h2 style={{ fontSize: 20, fontWeight: 500, margin: '0 0 6px' }}>Analyzing Papers</h2>
              <p style={{ color: t.textMuted, fontSize: 13, margin: '0 0 20px' }}>
                Extracting structured context and decomposing methods into abstraction layers
              </p>

              {parseProgress.progress < 50 && (
                <div style={{ marginBottom: 24 }}>
                  <div style={{ color: t.textSec, fontSize: 13, marginBottom: 8 }}>{parseProgress.message}</div>
                  <ProgressBar value={parseProgress.progress} />
                </div>
              )}

              {targetContext && (
                <div style={{
                  padding: 16, borderRadius: 12, marginBottom: 16,
                  background: t.accentBg, border: `1px solid ${t.accentBorder}`,
                }}>
                  <Overline>Your Research</Overline>
                  <div style={{ fontSize: 13, color: t.text, fontWeight: 500, marginBottom: 4 }}>
                    {targetContext.domain}
                  </div>
                  <div style={{ fontSize: 12, color: t.textSec }}>
                    Systems: {(targetContext.experimental_systems || []).join(', ')}
                  </div>
                  <div style={{ fontSize: 12, color: t.textSec }}>
                    Techniques: {(targetContext.available_techniques || []).join(', ')}
                  </div>
                </div>
              )}

              {sourceContexts.filter(Boolean).map((sc, i) => (
                <div key={i} style={{
                  padding: 16, borderRadius: 12, marginBottom: 12,
                  background: t.surface, border: `1px solid ${t.border}`,
                  animation: 'co-fadeIn 0.3s ease',
                }}>
                  <Overline>Paper {i + 1}: {sc.paper_name || 'Source'}</Overline>
                  <div style={{ fontSize: 13, color: t.text, fontWeight: 500, marginBottom: 6 }}>
                    {sc.domain}
                  </div>
                  {(sc.conceptual_principles || []).map((p: string, j: number) => (
                    <div key={j} style={{
                      padding: '6px 10px', marginBottom: 4, borderRadius: 6,
                      background: t.bg, fontSize: 12, color: t.textSec, lineHeight: 1.5,
                    }}>
                      L4: {p}
                    </div>
                  ))}
                </div>
              ))}

              {decompStatus.total > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <Spinner size={14} />
                    <span style={{ color: t.textSec, fontSize: 13 }}>
                      Decomposing methods: {decompStatus.done}/{decompStatus.total}
                    </span>
                  </div>
                  <ProgressBar value={(decompStatus.done / decompStatus.total) * 100} color={t.amber} />
                </div>
              )}

              <div style={{ display: 'grid', gap: 8, marginTop: 16 }}>
                {decompositions.slice(-4).map((d, i) => (
                  <div key={i} style={{
                    padding: '10px 14px', borderRadius: 8,
                    background: t.surface, border: `1px solid ${t.border}`,
                    animation: 'co-fadeIn 0.25s ease',
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 500, color: t.text, marginBottom: 4 }}>
                      {d.item_name}
                      <span style={{ color: t.textMuted, fontWeight: 400 }}> from {d.paper_name}</span>
                    </div>
                    {d.layers?.layers?.map((l: any) => (
                      <div key={l.level} style={{
                        fontSize: 11, color: t.textSec, lineHeight: 1.4,
                        padding: '2px 0',
                      }}>
                        <span style={{ fontFamily: t.mono, fontWeight: 600, color: t.textMuted }}>{l.level}</span>: {l.content?.slice(0, 100)}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TRANSLATING */}
          {phase === 'translating' && (
            <div style={{ paddingTop: 40 }}>
              <h2 style={{ fontSize: 20, fontWeight: 500, margin: '0 0 6px' }}>Translating Insights</h2>
              <p style={{ color: t.textMuted, fontSize: 13, margin: '0 0 20px' }}>
                Mapping each abstraction layer from source domain into your research context
              </p>

              <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Spinner size={14} />
                  <span style={{ color: t.textSec, fontSize: 13 }}>
                    {transStatus.done}/{transStatus.total} translations complete
                  </span>
                </div>
                <ProgressBar value={(transStatus.done / Math.max(transStatus.total, 1)) * 100} />
              </div>

              <div style={{ display: 'grid', gap: 10 }}>
                {translations.map((tr, i) => (
                  <div key={i} style={{
                    padding: '14px 18px', borderRadius: 10,
                    background: t.surface, border: `1px solid ${t.border}`,
                    animation: 'co-fadeIn 0.25s ease',
                  }}>
                    <div style={{ fontSize: 14, fontWeight: 500, color: t.text, marginBottom: 4 }}>
                      {tr.title}
                    </div>
                    <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 8 }}>
                      {tr.source_insight}
                    </div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {tr.layers?.map((l: any) => {
                        const c = l.confidence >= 0.7 ? t.green : l.confidence >= 0.4 ? t.amber : t.red
                        return (
                          <div key={l.level} style={{
                            padding: '2px 8px', borderRadius: 4,
                            background: `${c}15`, border: `1px solid ${c}30`,
                            fontSize: 11, fontFamily: t.mono, color: c, fontWeight: 600,
                          }}>
                            {l.level} {(l.confidence * 100).toFixed(0)}%
                          </div>
                        )
                      })}
                    </div>
                    {tr.overall_break_point && (
                      <div style={{
                        marginTop: 8, fontSize: 11, color: t.amber, lineHeight: 1.4,
                      }}>
                        Break point: {tr.overall_break_point}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STRESS TESTING */}
          {phase === 'stress_testing' && (
            <div style={{ paddingTop: 40 }}>
              <h2 style={{ fontSize: 20, fontWeight: 500, margin: '0 0 6px' }}>Stress-Testing Translations</h2>
              <p style={{ color: t.textMuted, fontSize: 13, margin: '0 0 20px' }}>
                4 adversarial agents are trying to break each translation
              </p>

              <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Spinner size={14} color={t.red} />
                  <span style={{ color: t.textSec, fontSize: 13 }}>
                    {advStatus.done}/{advStatus.total} translations tested
                  </span>
                </div>
                <ProgressBar value={(advStatus.done / Math.max(advStatus.total, 1)) * 100} color={t.red} />
              </div>

              <div style={{ display: 'grid', gap: 6 }}>
                {liveVerdicts.slice(-8).map((v, i) => (
                  <div key={i} style={{
                    padding: '8px 14px', borderRadius: 8,
                    background: v.verdict === 'survives' ? t.greenBg : v.verdict === 'vulnerable' ? t.amberBg : t.redBg,
                    border: `1px solid ${v.verdict === 'survives' ? t.greenBorder : v.verdict === 'vulnerable' ? t.amberBorder : t.redBorder}`,
                    animation: 'co-fadeIn 0.25s ease',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: v.agent_color }} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: t.text }}>{v.agent_name}</span>
                      <span style={{ fontSize: 10, color: t.textMuted }}>{v.translation_title}</span>
                      <span style={{
                        marginLeft: 'auto', fontSize: 10, fontWeight: 700,
                        color: v.verdict === 'survives' ? t.green : v.verdict === 'vulnerable' ? t.amber : t.red,
                        textTransform: 'uppercase',
                      }}>{v.verdict}</span>
                    </div>
                    <div style={{ fontSize: 11, color: t.textSec, lineHeight: 1.4 }}>{v.attack}</div>
                  </div>
                ))}
              </div>

              {adversarialResults.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <Overline>Completed</Overline>
                  {adversarialResults.map((ar, i) => (
                    <div key={i} style={{
                      padding: '8px 14px', marginBottom: 4, borderRadius: 8,
                      background: t.surface, border: `1px solid ${t.border}`,
                      display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                      <span style={{ flex: 1, fontSize: 13, color: t.text }}>{ar.title}</span>
                      <span style={{
                        fontFamily: t.mono, fontSize: 12, fontWeight: 700,
                        color: ar.survival_score >= 3 ? t.green : ar.survival_score >= 2 ? t.amber : t.red,
                      }}>{ar.survival_score}/4</span>
                      {ar.has_fatal && (
                        <span style={{ fontSize: 10, fontWeight: 700, color: t.red }}>FATAL</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* RESULTS */}
          {phase === 'results' && (
            <div style={{ paddingTop: 40 }}>
              <h2 style={{ fontSize: 24, fontWeight: 500, margin: '0 0 6px', letterSpacing: '-0.02em' }}>
                Translation Proposals
              </h2>
              <p style={{ color: t.textMuted, fontSize: 14, margin: '0 0 32px' }}>
                {rankedTranslations.length} translation{rankedTranslations.length !== 1 ? 's' : ''} ranked by stress-test survival.
                Each one maps a source insight into your research domain at 4 abstraction layers.
                {isContextEnhanced && <span style={{ color: t.accent }}> Enhanced with your lab profile.</span>}
              </p>

              {/* Context Analysis Card - NEW */}
              {contextAnalysis && (
                <div style={{
                  padding: 20, borderRadius: 14, marginBottom: 24,
                  background: `linear-gradient(135deg, ${t.accentBg} 0%, ${t.surface} 100%)`,
                  border: `1px solid ${t.accentBorder}`,
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
                  }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={t.accent} strokeWidth="2" strokeLinecap="round">
                      <path d="M12 2L2 7l10 5 10-5-10-5z" />
                      <path d="M2 17l10 5 10-5" />
                      <path d="M2 12l10 5 10-5" />
                    </svg>
                    <span style={{ fontSize: 15, fontWeight: 600, color: t.text }}>
                      Lab Context Analysis
                    </span>
                    <span style={{
                      marginLeft: 'auto',
                      padding: '3px 10px',
                      background: contextAnalysis.has_context === false ? t.amber : t.accent,
                      borderRadius: 12,
                      fontSize: 10,
                      fontWeight: 600,
                      color: '#fff',
                      letterSpacing: '0.03em',
                    }}>
                      {contextAnalysis.has_context === false ? 'LIMITED' : 'PERSONALIZED'}
                    </span>
                  </div>

                  {/* No Context Fallback */}
                  {contextAnalysis.has_context === false && (
                    <div style={{
                      padding: 14, borderRadius: 10, marginBottom: 14,
                      background: t.amberBg, border: `1px solid ${t.amberBorder}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={t.amber} strokeWidth="2" strokeLinecap="round">
                          <circle cx="12" cy="12" r="10" />
                          <path d="M12 16v-4M12 8h.01" />
                        </svg>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: '#6B5010', marginBottom: 4 }}>
                            Limited Personalization Available
                          </div>
                          <div style={{ fontSize: 12, color: '#6B5010', lineHeight: 1.5, marginBottom: 6 }}>
                            {contextAnalysis.no_context_reason || 'No relevant lab context found for this translation.'}
                          </div>
                          {contextAnalysis.tip && (
                            <div style={{ fontSize: 11, color: '#8B6914', fontStyle: 'italic' }}>
                              Tip: {contextAnalysis.tip}
                            </div>
                          )}
                          {contextAnalysis.documents_searched !== undefined && (
                            <div style={{ fontSize: 10, color: '#8B6914', marginTop: 4 }}>
                              Documents searched: {contextAnalysis.documents_searched}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Domain Expertise Match */}
                  {contextAnalysis.domain_expertise_match && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                      <div style={{
                        width: 44, height: 44, borderRadius: 22,
                        background: contextAnalysis.domain_expertise_match.score >= 70 ? t.greenBg :
                                   contextAnalysis.domain_expertise_match.score >= 40 ? t.amberBg : t.redBg,
                        border: `1px solid ${contextAnalysis.domain_expertise_match.score >= 70 ? t.greenBorder :
                                            contextAnalysis.domain_expertise_match.score >= 40 ? t.amberBorder : t.redBorder}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13, fontWeight: 700, fontFamily: t.mono,
                        color: contextAnalysis.domain_expertise_match.score >= 70 ? t.green :
                               contextAnalysis.domain_expertise_match.score >= 40 ? t.amber : t.red,
                      }}>
                        {contextAnalysis.domain_expertise_match.score}%
                      </div>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 600, color: t.textMuted, textTransform: 'uppercase' as const, letterSpacing: '0.05em', marginBottom: 2 }}>
                          Domain Expertise Match
                        </div>
                        <div style={{ fontSize: 13, color: t.text }}>
                          {contextAnalysis.domain_expertise_match.assessment}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Methodology Transferability */}
                  {contextAnalysis.methodology_transferability && (
                    <div style={{
                      padding: 12, borderRadius: 10, marginBottom: 14,
                      background: t.surface, border: `1px solid ${t.border}`,
                    }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: t.textMuted, textTransform: 'uppercase' as const, letterSpacing: '0.05em', marginBottom: 6 }}>
                        Methodology Transferability
                      </div>
                      <div style={{ fontSize: 13, color: t.text, lineHeight: 1.6 }}>
                        {contextAnalysis.methodology_transferability.summary}
                      </div>
                      {contextAnalysis.methodology_transferability.relevant_methods && contextAnalysis.methodology_transferability.relevant_methods.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, marginTop: 8 }}>
                          {contextAnalysis.methodology_transferability.relevant_methods.map((method, i) => (
                            <span key={i} style={{
                              padding: '3px 10px', borderRadius: 6,
                              background: t.greenBg, border: `1px solid ${t.greenBorder}`,
                              fontSize: 11, color: t.green, fontWeight: 500,
                            }}>
                              ✓ {method}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Equipment Compatibility */}
                  {contextAnalysis.equipment_compatibility && (
                    <div style={{
                      padding: 12, borderRadius: 10, marginBottom: 14,
                      background: t.surface, border: `1px solid ${t.border}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: t.textMuted, textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>
                          Equipment Compatibility
                        </span>
                        <span style={{
                          fontFamily: t.mono, fontSize: 12, fontWeight: 700,
                          color: contextAnalysis.equipment_compatibility.score >= 70 ? t.green :
                                 contextAnalysis.equipment_compatibility.score >= 40 ? t.amber : t.red,
                        }}>
                          {contextAnalysis.equipment_compatibility.score}%
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: t.text, marginBottom: 8 }}>
                        {contextAnalysis.equipment_compatibility.assessment}
                      </div>
                      {contextAnalysis.equipment_compatibility.may_need && contextAnalysis.equipment_compatibility.may_need.length > 0 && (
                        <div style={{ fontSize: 12, color: t.amber }}>
                          May need: {contextAnalysis.equipment_compatibility.may_need.join(', ')}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Translation Advantages */}
                  {contextAnalysis.translation_advantages && contextAnalysis.translation_advantages.length > 0 && (
                    <div style={{
                      padding: 12, borderRadius: 10, marginBottom: 14,
                      background: t.greenBg, border: `1px solid ${t.greenBorder}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={t.green} strokeWidth="2" strokeLinecap="round">
                          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                        </svg>
                        <span style={{ fontSize: 11, fontWeight: 600, color: t.green, textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>
                          Your Advantages
                        </span>
                      </div>
                      {contextAnalysis.translation_advantages.map((adv, i) => (
                        <div key={i} style={{ fontSize: 12.5, color: '#3D6B35', lineHeight: 1.5, marginBottom: 4 }}>
                          • {adv}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Potential Pitfalls */}
                  {contextAnalysis.potential_pitfalls && contextAnalysis.potential_pitfalls.length > 0 && (
                    <div style={{
                      padding: 12, borderRadius: 10, marginBottom: 14,
                      background: t.amberBg, border: `1px solid ${t.amberBorder}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={t.amber} strokeWidth="2" strokeLinecap="round">
                          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                          <line x1="12" y1="9" x2="12" y2="13" />
                          <line x1="12" y1="17" x2="12.01" y2="17" />
                        </svg>
                        <span style={{ fontSize: 11, fontWeight: 600, color: '#8B6914', textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>
                          Watch Out For
                        </span>
                      </div>
                      {contextAnalysis.potential_pitfalls.map((pit, i) => (
                        <div key={i} style={{ fontSize: 12.5, color: '#6B5010', lineHeight: 1.5, marginBottom: 4 }}>
                          • {pit}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Recommended Focus */}
                  {contextAnalysis.recommended_focus && (
                    <div style={{
                      padding: 12, borderRadius: 10,
                      background: `linear-gradient(135deg, ${t.accentBg} 0%, ${t.surface} 100%)`,
                      border: `1px solid ${t.accentBorder}`,
                    }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: t.accent, textTransform: 'uppercase' as const, letterSpacing: '0.05em', marginBottom: 6 }}>
                        Recommended Focus
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 4 }}>
                        {contextAnalysis.recommended_focus.area}
                      </div>
                      <div style={{ fontSize: 12.5, color: t.textSec, lineHeight: 1.5 }}>
                        {contextAnalysis.recommended_focus.rationale}
                      </div>
                    </div>
                  )}

                  {/* Source Citations */}
                  {contextAnalysis.sources && Object.keys(contextAnalysis.sources).length > 0 && (
                    <div style={{
                      marginTop: 16,
                      padding: 12,
                      borderRadius: 10,
                      background: t.bg,
                      border: `1px dashed ${t.border}`,
                    }}>
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: t.textMuted,
                        textTransform: 'uppercase' as const,
                        letterSpacing: '0.05em',
                      }}>
                        Sources Used
                      </span>
                      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, marginTop: 8 }}>
                        {Object.entries(contextAnalysis.sources).slice(0, 3).flatMap(([field, sources]) =>
                          (sources || []).slice(0, 2).map((src, i) => (
                            <span
                              key={`${field}-${i}`}
                              style={{
                                padding: '4px 10px',
                                borderRadius: 6,
                                background: t.surface,
                                border: `1px solid ${t.border}`,
                                fontSize: 11,
                                color: t.textSec,
                              }}
                            >
                              <span style={{ color: t.accent, fontWeight: 500 }}>
                                {src.source_type || 'doc'}:
                              </span>{' '}
                              {src.title?.slice(0, 30) || 'Unknown'}
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div style={{ display: 'grid', gap: 16, marginBottom: 36 }}>
                {rankedTranslations.map((tr, i) => (
                  <TranslationCard
                    key={i}
                    translation={tr}
                    adversarial={rankedAdversarial[i]}
                    rank={i + 1}
                    isTop={i === 0}
                  />
                ))}
              </div>

              {chatReady && sessionId && (
                <div style={{ marginBottom: 32 }}>
                  <ChatPanel sessionId={sessionId} />
                </div>
              )}

              <button onClick={handleReset} style={{
                marginTop: 8, padding: '10px 24px', borderRadius: 10,
                background: t.surface, border: `1px solid ${t.border}`,
                color: t.textSec, fontSize: 13, fontWeight: 500,
                cursor: 'pointer',
              }}>Start New Analysis</button>
            </div>
          )}
        </main>
      </div>
    </>
  )
}
