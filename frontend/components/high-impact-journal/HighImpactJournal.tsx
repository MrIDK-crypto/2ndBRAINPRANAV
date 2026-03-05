'use client'

import React, { useState, useRef, useCallback } from 'react'
import { theme, font, fontDisplay, fontMono, tierColors, fieldColors, severityColors } from './theme'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006'

// ── Types ──────────────────────────────────────────────────────────────────

interface FieldInfo {
  field: string
  field_label: string
  confidence: number
  subfield: string
  reasoning: string
}

interface Citation {
  text: string
  section: string
}

interface SuggestedReference {
  title: string
  authors: string
  year: string
  url: string
  relevance: string
}

interface Feature {
  score: number
  weight: number
  label: string
  details: string
  citations?: Citation[]
  suggested_references?: SuggestedReference[]
}

interface ScoreInfo {
  overall_score: number
  tier: number
  tier_label: string
  score_breakdown: { feature: string; score: number; weight: number; weighted: number }[]
  penalty_applied?: number
  original_score?: number
}

interface JournalMatch {
  name: string
  url?: string
  homepage_url?: string
  h_index?: number
  impact_factor?: number
  sjr_score?: number
  sjr_quartile?: string
  composite_score?: number
  citedness_2yr?: number
  publisher?: string
}

interface JournalsInfo {
  primary_matches: JournalMatch[]
  stretch_matches: JournalMatch[]
  safe_matches: JournalMatch[]
}

interface RedFlag {
  severity: string
  issue: string
  penalty: number
  fix: string
}

interface RedFlagsInfo {
  flags: RedFlag[]
  total_penalty: number
}

interface FeaturesInfo {
  features: Record<string, Feature>
  word_count: number
  reference_count: number
  has_abstract: boolean
  has_tables: boolean
}

interface ConsistencyInfo {
  scores_by_run: Record<string, number>[]
  averaged_scores: Record<string, number>
  high_variance_features: { feature: string; label: string; std: number; scores: number[] }[]
  num_runs: number
}

interface LandscapeInfo {
  field: string
  total_journals: number
  percentile: number
  tier1_count?: number
  tier2_count?: number
  tier3_count?: number
  tier1_threshold: number
  tier2_threshold?: number
  median_composite: number
  median_h_index?: number
  median_impact_factor?: number
  max_h_index?: number
  max_impact_factor?: number
}

interface VerifiedCitation {
  doi: string
  valid: boolean
  title?: string
  year?: number
  citations?: number
  journal?: string
  error?: string
}

interface CitationVerificationInfo {
  verified: VerifiedCitation[]
  unverified: VerifiedCitation[]
  verification_rate: number
  total_dois_found: number
}

type AppState = 'idle' | 'analyzing' | 'results'

// ── Main Component ─────────────────────────────────────────────────────────

export default function HighImpactJournal() {
  const [state, setState] = useState<AppState>('idle')
  const [dragOver, setDragOver] = useState(false)
  const [progress, setProgress] = useState({ step: 0, message: '', percent: 0 })
  const [fieldInfo, setFieldInfo] = useState<FieldInfo | null>(null)
  const [featuresInfo, setFeaturesInfo] = useState<FeaturesInfo | null>(null)
  const [scoreInfo, setScoreInfo] = useState<ScoreInfo | null>(null)
  const [journalsInfo, setJournalsInfo] = useState<JournalsInfo | null>(null)
  const [redFlags, setRedFlags] = useState<RedFlagsInfo | null>(null)
  const [recommendations, setRecommendations] = useState('')
  const [consistencyInfo, setConsistencyInfo] = useState<ConsistencyInfo | null>(null)
  const [landscapeInfo, setLandscapeInfo] = useState<LandscapeInfo | null>(null)
  const [citationInfo, setCitationInfo] = useState<CitationVerificationInfo | null>(null)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const reset = useCallback(() => {
    setState('idle')
    setProgress({ step: 0, message: '', percent: 0 })
    setFieldInfo(null)
    setFeaturesInfo(null)
    setScoreInfo(null)
    setJournalsInfo(null)
    setRedFlags(null)
    setRecommendations('')
    setConsistencyInfo(null)
    setLandscapeInfo(null)
    setCitationInfo(null)
    setError('')
  }, [])

  const handleFile = useCallback(async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['pdf', 'docx'].includes(ext)) {
      setError('Please upload a PDF or DOCX file.')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('File too large. Maximum size is 50MB.')
      return
    }

    setError('')
    setState('analyzing')
    setProgress({ step: 1, message: 'Uploading...', percent: 2 })

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_URL}/api/journal/analyze`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok || !response.body) {
        setError('Server error. Please try again.')
        setState('idle')
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ') && eventType) {
            try {
              const data = JSON.parse(line.slice(6))
              switch (eventType) {
                case 'progress':
                  setProgress(data)
                  break
                case 'field_detected':
                  setFieldInfo(data)
                  break
                case 'features_extracted':
                  setFeaturesInfo(data)
                  break
                case 'score':
                  setScoreInfo(data)
                  break
                case 'journals':
                  setJournalsInfo(data)
                  break
                case 'red_flags':
                  setRedFlags(data)
                  break
                case 'consistency':
                  setConsistencyInfo(data)
                  break
                case 'landscape':
                  setLandscapeInfo(data)
                  break
                case 'citation_verification':
                  setCitationInfo(data)
                  break
                case 'recommendations':
                  setRecommendations(prev => prev + data.content)
                  break
                case 'done':
                  setState('results')
                  break
                case 'error':
                  setError(data.error)
                  setState('idle')
                  break
              }
            } catch {
              // skip unparseable lines
            }
            eventType = ''
          }
        }
      }
    } catch (e) {
      setError('Connection failed. Please check your network and try again.')
      setState('idle')
    }
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }, [handleFile])

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: theme.pageBg,
      fontFamily: font,
      color: theme.textPrimary,
    }}>
      <main style={{ maxWidth: 900, margin: '0 auto', padding: '40px 24px' }}>
        {error && (
          <div style={{
            padding: '12px 16px',
            borderRadius: 8,
            backgroundColor: '#FDF2F2',
            border: '1px solid #D97B7B',
            color: '#9B4D4D',
            marginBottom: 24,
            fontSize: 14,
          }}>
            {error}
          </div>
        )}

        {/* ── IDLE STATE ─────────────────────────────────────── */}
        {state === 'idle' && (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <p style={{
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: '1.5px',
              textTransform: 'uppercase',
              color: theme.primary,
              marginBottom: 16,
            }}>
              Manuscript Analysis
            </p>
            <h1 style={{
              fontFamily: fontDisplay,
              fontSize: 42,
              fontWeight: 400,
              marginBottom: 16,
              color: theme.textPrimary,
              lineHeight: 1.15,
            }}>
              Where can you publish?
            </h1>
            <p style={{
              color: theme.textSecondary,
              fontSize: 17,
              lineHeight: 1.6,
              maxWidth: 480,
              margin: '0 auto 48px',
            }}>
              Upload your manuscript for instant field detection, quality scoring, journal tier predictions, and actionable recommendations.
            </p>

            {/* Upload Zone */}
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? theme.primary : theme.borderDark}`,
                borderRadius: 16,
                padding: '60px 40px',
                backgroundColor: dragOver ? theme.primaryLight : theme.cardBg,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                maxWidth: 520,
                margin: '0 auto',
              }}
            >
              <div style={{
                width: 56, height: 56, borderRadius: 14,
                backgroundColor: theme.primaryLight,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 20px',
                fontSize: 24,
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <p style={{ fontWeight: 600, fontSize: 16, marginBottom: 8, color: theme.textPrimary }}>
                Drop your manuscript here
              </p>
              <p style={{ color: theme.textMuted, fontSize: 14 }}>
                or click to browse — PDF or DOCX up to 50MB
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              onChange={onFileSelect}
              style={{ display: 'none' }}
            />

            {/* Features Row */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
              marginTop: 56,
            }}>
              {[
                { icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z', title: 'Field Detection', desc: '18 academic disciplines' },
                { icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', title: 'Quality Score', desc: 'Weighted 0-100 scoring' },
                { icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253', title: 'Journal Match', desc: 'Tier 1 / 2 / 3 targets' },
                { icon: 'M13 10V3L4 14h7v7l9-11h-7z', title: 'Recommendations', desc: 'Actionable next steps' },
              ].map(f => (
                <div key={f.title} style={{
                  padding: '20px 16px',
                  borderRadius: 12,
                  backgroundColor: theme.cardBg,
                  border: `1px solid ${theme.border}`,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                }}>
                  <div style={{ width: 20, height: 20, marginBottom: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d={f.icon}/>
                    </svg>
                  </div>
                  <p style={{ fontWeight: 600, fontSize: 13, marginBottom: 3, color: theme.textPrimary, textAlign: 'center' }}>{f.title}</p>
                  <p style={{ color: theme.textMuted, fontSize: 12, lineHeight: 1.4, textAlign: 'center' }}>{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── ANALYZING STATE ────────────────────────────────── */}
        {state === 'analyzing' && (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <h2 style={{ fontFamily: fontDisplay, fontSize: 28, marginBottom: 24 }}>
              Analyzing your manuscript...
            </h2>

            {/* Progress Bar */}
            <div style={{
              maxWidth: 480,
              margin: '0 auto 24px',
              backgroundColor: theme.border,
              borderRadius: 8,
              height: 8,
              overflow: 'hidden',
            }}>
              <div style={{
                width: `${progress.percent}%`,
                height: '100%',
                backgroundColor: theme.primary,
                borderRadius: 8,
                transition: 'width 0.5s ease',
              }} />
            </div>
            <p style={{ color: theme.textSecondary, fontSize: 14 }}>
              Step {progress.step}/10 — {progress.message}
            </p>

            {/* Pulse indicator */}
            <div style={{
              width: 12, height: 12,
              borderRadius: '50%',
              backgroundColor: theme.primary,
              margin: '32px auto 0',
              animation: 'pulse 1.5s ease-in-out infinite',
            }} />
            <style>{`@keyframes pulse { 0%, 100% { opacity: 0.4; transform: scale(1); } 50% { opacity: 1; transform: scale(1.3); } }`}</style>

            {/* Live feed of detected info */}
            {fieldInfo && (
              <div style={{
                marginTop: 32,
                padding: '16px 20px',
                borderRadius: 12,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                maxWidth: 480,
                margin: '32px auto 0',
                textAlign: 'left',
              }}>
                <FieldBadge field={fieldInfo.field} label={fieldInfo.field_label} subfield={fieldInfo.subfield} confidence={fieldInfo.confidence} />
              </div>
            )}
          </div>
        )}

        {/* ── RESULTS STATE ──────────────────────────────────── */}
        {state === 'results' && scoreInfo && (
          <div>
            {/* Top summary row */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '280px 1fr',
              gap: 20,
              marginBottom: 24,
              alignItems: 'stretch',
            }}>
              {/* Score Gauge */}
              <div style={{
                padding: '28px 24px',
                borderRadius: 16,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <ScoreGauge score={scoreInfo.overall_score} tier={scoreInfo.tier} />
                <p style={{
                  marginTop: 14,
                  fontWeight: 600,
                  fontSize: 15,
                  color: tierColors[scoreInfo.tier as keyof typeof tierColors]?.text || theme.textPrimary,
                  textAlign: 'center',
                }}>
                  {scoreInfo.tier_label}
                </p>
                {scoreInfo.penalty_applied && (
                  <p style={{ fontSize: 12, color: theme.error, marginTop: 6, textAlign: 'center' }}>
                    {scoreInfo.penalty_applied} penalty applied (original: {scoreInfo.original_score})
                  </p>
                )}
              </div>

              {/* Field & Meta */}
              <div style={{
                padding: '24px 28px',
                borderRadius: 16,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
              }}>
                {fieldInfo && (
                  <>
                    <FieldBadge field={fieldInfo.field} label={fieldInfo.field_label} subfield={fieldInfo.subfield} confidence={fieldInfo.confidence} />
                    <p style={{ color: theme.textSecondary, fontSize: 13, marginTop: 12, lineHeight: 1.6 }}>
                      {fieldInfo.reasoning}
                    </p>
                  </>
                )}
                {featuresInfo && (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: 8,
                    marginTop: 16,
                    fontSize: 13,
                  }}>
                    <MetaStat label="Words" value={featuresInfo.word_count.toLocaleString()} />
                    <MetaStat label="References" value={String(featuresInfo.reference_count)} />
                    <MetaStat label="Abstract" value={featuresInfo.has_abstract ? 'Yes' : 'Missing'} warn={!featuresInfo.has_abstract} />
                    <MetaStat label="Tables" value={featuresInfo.has_tables ? 'Yes' : 'None'} />
                  </div>
                )}
              </div>
            </div>

            {/* Feature Breakdown */}
            {scoreInfo.score_breakdown && featuresInfo && (
              <div style={{
                padding: 24,
                borderRadius: 16,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                marginBottom: 24,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <h3 style={{ fontSize: 17, fontWeight: 600, color: theme.textPrimary }}>Feature Breakdown</h3>
                  {consistencyInfo && (
                    <span style={{ fontSize: 11, color: theme.textMuted, fontFamily: fontMono }}>
                      Averaged over {consistencyInfo.num_runs} runs
                    </span>
                  )}
                </div>
                {scoreInfo.score_breakdown.map(b => {
                  const featureKey = Object.keys(featuresInfo.features).find(
                    k => featuresInfo.features[k].label === b.feature
                  )
                  const feat = featureKey ? featuresInfo.features[featureKey] : null
                  const varianceItem = consistencyInfo?.high_variance_features?.find(
                    v => v.label === b.feature
                  )

                  return (
                    <div key={b.feature} style={{ marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${theme.border}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4, alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                          {b.feature}
                          {varianceItem && (
                            <span style={{
                              fontSize: 10,
                              padding: '1px 6px',
                              borderRadius: 4,
                              backgroundColor: '#FEF7E8',
                              color: '#8B6914',
                              fontWeight: 500,
                            }} title={`Scores varied: ${varianceItem.scores.join(', ')}`}>
                              ±{varianceItem.std}
                            </span>
                          )}
                        </span>
                        <span style={{ fontFamily: fontMono, color: theme.textSecondary }}>
                          {b.score}/100 <span style={{ color: theme.textMuted }}>({(b.weight * 100).toFixed(0)}%)</span>
                        </span>
                      </div>
                      <div style={{ height: 6, borderRadius: 3, backgroundColor: theme.border, marginBottom: 8 }}>
                        <div style={{
                          height: '100%',
                          borderRadius: 3,
                          width: `${b.score}%`,
                          backgroundColor: b.score >= 85 ? theme.success : b.score >= 65 ? theme.amber : theme.error,
                          transition: 'width 0.6s ease',
                        }} />
                      </div>

                      {/* Details */}
                      {feat?.details && (
                        <p style={{ fontSize: 13, color: theme.textSecondary, lineHeight: 1.5, marginBottom: 8 }}>
                          {feat.details}
                        </p>
                      )}

                      {/* Manuscript Citations */}
                      {feat?.citations && feat.citations.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                          {feat.citations.map((c, i) => (
                            <div key={i} style={{
                              padding: '8px 12px',
                              borderRadius: 6,
                              backgroundColor: theme.primaryLight,
                              borderLeft: `3px solid ${theme.primary}`,
                              marginBottom: 4,
                              fontSize: 12,
                            }}>
                              <span style={{ fontStyle: 'italic', color: theme.textSecondary }}>"{c.text}"</span>
                              {c.section && (
                                <span style={{ color: theme.textMuted, marginLeft: 8 }}>— {c.section}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Suggested References */}
                      {feat?.suggested_references && feat.suggested_references.length > 0 && (
                        <div>
                          <span style={{ fontSize: 11, fontWeight: 600, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            Key References
                          </span>
                          {feat.suggested_references.map((r, i) => (
                            <div key={i} style={{ fontSize: 12, marginTop: 4, lineHeight: 1.5 }}>
                              {r.url ? (
                                <a
                                  href={r.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{ color: '#4338CA', textDecoration: 'none' }}
                                >
                                  {r.authors} ({r.year}) — {r.title}
                                </a>
                              ) : (
                                <span style={{ color: theme.textSecondary }}>
                                  {r.authors} ({r.year}) — {r.title}
                                </span>
                              )}
                              {r.relevance && (
                                <span style={{ color: theme.textMuted, display: 'block', fontSize: 11, marginLeft: 12 }}>
                                  {r.relevance}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* Journal Matches */}
            {journalsInfo && (() => {
              const columns = [
                { title: 'Target Journals', journals: journalsInfo.primary_matches, accent: tierColors[scoreInfo.tier as keyof typeof tierColors]?.border || theme.primary },
                { title: 'Stretch Goals', journals: journalsInfo.stretch_matches, accent: theme.amber },
                { title: 'Safe Options', journals: journalsInfo.safe_matches, accent: theme.success },
              ].filter(c => c.journals && c.journals.length > 0)

              return (
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: `repeat(${columns.length}, 1fr)`,
                  gap: 16,
                  marginBottom: 24,
                }}>
                  {columns.map(c => (
                    <JournalColumn key={c.title} title={c.title} journals={c.journals} accent={c.accent} />
                  ))}
                </div>
              )
            })()}

            {/* Landscape Position */}
            {landscapeInfo && landscapeInfo.total_journals > 0 && (
              <div style={{
                padding: 24,
                borderRadius: 16,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                marginBottom: 24,
              }}>
                <h3 style={{ fontSize: 17, fontWeight: 600, marginBottom: 16, color: theme.textPrimary }}>Journal Landscape Position</h3>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                    <span style={{ color: theme.textSecondary }}>Your percentile rank</span>
                    <span style={{ fontFamily: fontMono, fontWeight: 600, color: theme.textPrimary }}>
                      {landscapeInfo.percentile}th percentile
                    </span>
                  </div>
                  <div style={{ height: 10, borderRadius: 5, backgroundColor: theme.border, position: 'relative' }}>
                    <div style={{
                      height: '100%',
                      borderRadius: 5,
                      width: `${landscapeInfo.percentile}%`,
                      backgroundColor: landscapeInfo.percentile >= 85 ? theme.success : landscapeInfo.percentile >= 50 ? theme.amber : theme.error,
                      transition: 'width 0.8s ease',
                    }} />
                    <div style={{
                      position: 'absolute',
                      top: -4,
                      left: `${landscapeInfo.percentile}%`,
                      transform: 'translateX(-50%)',
                      width: 18,
                      height: 18,
                      borderRadius: '50%',
                      backgroundColor: '#fff',
                      border: `2px solid ${theme.primary}`,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                    }} />
                  </div>
                </div>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: 8,
                  marginTop: 16,
                }}>
                  <MetaStat label="Total Journals" value={String(landscapeInfo.total_journals)} />
                  <MetaStat label="Tier 1 Threshold" value={String(Math.round(landscapeInfo.tier1_threshold))} />
                  <MetaStat label="Median Score" value={String(Math.round(landscapeInfo.median_composite))} />
                  {landscapeInfo.median_h_index ? (
                    <MetaStat label="Median h-index" value={String(landscapeInfo.median_h_index)} />
                  ) : (
                    <MetaStat label="Tier 1 Count" value={String(landscapeInfo.tier1_count || 0)} />
                  )}
                </div>
              </div>
            )}

            {/* Citation Verification */}
            {citationInfo && citationInfo.total_dois_found > 0 && (
              <div style={{
                padding: 24,
                borderRadius: 16,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                marginBottom: 24,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <h3 style={{ fontSize: 17, fontWeight: 600, color: theme.textPrimary }}>Citation Verification</h3>
                  <span style={{
                    padding: '4px 10px',
                    borderRadius: 12,
                    fontSize: 12,
                    fontWeight: 600,
                    fontFamily: fontMono,
                    backgroundColor: citationInfo.verification_rate >= 80 ? '#F0F7EE' : citationInfo.verification_rate >= 50 ? '#FEF7E8' : '#FDF2F2',
                    color: citationInfo.verification_rate >= 80 ? '#3D6B35' : citationInfo.verification_rate >= 50 ? '#8B6914' : '#9B4D4D',
                  }}>
                    {citationInfo.verification_rate}% verified
                  </span>
                </div>
                <p style={{ fontSize: 13, color: theme.textSecondary, marginBottom: 12 }}>
                  {citationInfo.verified.length} of {citationInfo.total_dois_found} DOIs confirmed via CrossRef
                </p>
                {citationInfo.verified.length > 0 && (
                  <div style={{ marginBottom: citationInfo.unverified.length > 0 ? 16 : 0 }}>
                    {citationInfo.verified.map((c, i) => (
                      <div key={i} style={{
                        padding: '8px 12px',
                        borderRadius: 6,
                        backgroundColor: '#F0F7EE',
                        borderLeft: '3px solid #9CB896',
                        marginBottom: 4,
                        fontSize: 12,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        gap: 8,
                      }}>
                        <div style={{ flex: 1 }}>
                          <a
                            href={`https://doi.org/${c.doi}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: '#4338CA', textDecoration: 'none', fontWeight: 500 }}
                          >
                            {c.title || c.doi}
                          </a>
                          {c.journal && <span style={{ color: theme.textMuted, marginLeft: 6 }}>— {c.journal}</span>}
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexShrink: 0, fontFamily: fontMono, color: theme.textMuted }}>
                          {c.year && <span>{c.year}</span>}
                          {c.citations !== undefined && <span>{c.citations} cites</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {citationInfo.unverified.length > 0 && (
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 600, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      Unverified DOIs
                    </span>
                    {citationInfo.unverified.map((c, i) => (
                      <div key={i} style={{
                        padding: '6px 12px',
                        borderRadius: 6,
                        backgroundColor: '#FEF7E8',
                        borderLeft: '3px solid #E2A336',
                        marginTop: 4,
                        fontSize: 12,
                        color: theme.textSecondary,
                      }}>
                        {c.doi} {c.error && <span style={{ color: theme.textMuted }}>— {c.error}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Red Flags */}
            {redFlags && redFlags.flags.length > 0 && (
              <div style={{
                padding: 24,
                borderRadius: 16,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                marginBottom: 24,
              }}>
                <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Red Flags</h3>
                {redFlags.flags.map((f, i) => {
                  const sc = severityColors[f.severity as keyof typeof severityColors] || severityColors.info
                  return (
                    <div key={i} style={{
                      padding: '12px 16px',
                      borderRadius: 8,
                      backgroundColor: sc.bg,
                      border: `1px solid ${sc.border}`,
                      marginBottom: 8,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      gap: 12,
                    }}>
                      <div>
                        <span style={{
                          display: 'inline-block',
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          color: sc.text,
                          marginBottom: 4,
                        }}>
                          {f.severity}
                        </span>
                        <p style={{ fontSize: 14, fontWeight: 500, marginBottom: 2 }}>{f.issue}</p>
                        <p style={{ fontSize: 13, color: theme.textSecondary }}>{f.fix}</p>
                      </div>
                      <span style={{
                        fontFamily: fontMono,
                        fontSize: 13,
                        color: sc.text,
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                      }}>
                        {f.penalty}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Recommendations */}
            {recommendations && (
              <div style={{
                padding: 24,
                borderRadius: 16,
                backgroundColor: theme.cardBg,
                border: `1px solid ${theme.border}`,
                marginBottom: 24,
              }}>
                <h3 style={{ fontSize: 17, fontWeight: 600, marginBottom: 16, color: theme.textPrimary }}>Recommendations</h3>
                <div
                  style={{
                    fontSize: 14,
                    lineHeight: 1.7,
                    color: theme.textSecondary,
                    overflowX: 'auto',
                  }}
                  dangerouslySetInnerHTML={{ __html: markdownToHtml(recommendations) }}
                />
              </div>
            )}

            {/* Analyze Another */}
            <div style={{ textAlign: 'center', paddingTop: 8, paddingBottom: 40 }}>
              <button
                onClick={reset}
                style={{
                  padding: '12px 32px',
                  borderRadius: 10,
                  border: 'none',
                  backgroundColor: theme.primary,
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: 15,
                  cursor: 'pointer',
                  fontFamily: font,
                }}
              >
                Analyze Another Manuscript
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function FieldBadge({ field, label, subfield, confidence }: { field: string; label: string; subfield: string; confidence: number }) {
  const fc = fieldColors[field] || fieldColors.economics
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 12px',
        borderRadius: 20,
        backgroundColor: fc.bg,
        color: fc.text,
        fontSize: 13,
        fontWeight: 600,
      }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: fc.dot }} />
        {label}
      </span>
      <span style={{ fontSize: 13, color: theme.textSecondary }}>{subfield}</span>
      <span style={{ fontSize: 12, color: theme.textMuted, fontFamily: fontMono }}>
        {(confidence * 100).toFixed(0)}% confidence
      </span>
    </div>
  )
}

function MetaStat({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: theme.pageBg }}>
      <div style={{ fontSize: 11, color: theme.textMuted, marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: 14, color: warn ? theme.error : theme.textPrimary }}>{value}</div>
    </div>
  )
}

function ScoreGauge({ score, tier }: { score: number; tier: number }) {
  const tc = tierColors[tier as keyof typeof tierColors] || tierColors[3]
  const radius = 70
  const circumference = Math.PI * radius
  const offset = circumference - (score / 100) * circumference

  return (
    <svg width="200" height="120" viewBox="0 0 200 120">
      {/* Background arc */}
      <path
        d="M 25 105 A 70 70 0 0 1 175 105"
        fill="none"
        stroke={theme.border}
        strokeWidth="12"
        strokeLinecap="round"
      />
      {/* Score arc */}
      <path
        d="M 25 105 A 70 70 0 0 1 175 105"
        fill="none"
        stroke={tc.border}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={`${circumference}`}
        strokeDashoffset={`${offset}`}
        style={{ transition: 'stroke-dashoffset 1s ease' }}
      />
      {/* Score text */}
      <text x="100" y="85" textAnchor="middle" fontFamily={fontMono} fontSize="36" fontWeight="700" fill={tc.text}>
        {score}
      </text>
      <text x="100" y="108" textAnchor="middle" fontFamily={font} fontSize="13" fill={theme.textMuted}>
        out of 100
      </text>
    </svg>
  )
}

function JournalColumn({ title, journals, accent }: { title: string; journals: JournalMatch[]; accent: string }) {
  if (!journals || journals.length === 0) return null
  const hasMetrics = journals.some(j => j.h_index || j.impact_factor || j.sjr_quartile)
  return (
    <div style={{
      padding: 20,
      borderRadius: 16,
      backgroundColor: theme.cardBg,
      border: `1px solid ${theme.border}`,
      borderTop: `3px solid ${accent}`,
    }}>
      <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>{title}</h4>
      {journals.map((j, i) => {
        const url = j.homepage_url || j.url
        const content = (
          <div style={{
            padding: '10px 0',
            borderBottom: i < journals.length - 1 ? `1px solid ${theme.border}` : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ fontSize: 13, color: url ? '#4338CA' : theme.textPrimary, fontWeight: 500 }}>{j.name}</span>
              {url && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4338CA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, opacity: 0.5 }}>
                  <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                  <polyline points="15 3 21 3 21 9"/>
                  <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              )}
            </div>
            {hasMetrics && (
              <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                {j.h_index !== undefined && j.h_index > 0 && (
                  <MetricPill label="h-index" value={String(j.h_index)} />
                )}
                {j.impact_factor !== undefined && j.impact_factor > 0 && (
                  <MetricPill label="IF" value={j.impact_factor.toFixed(1)} />
                )}
                {j.sjr_quartile && (
                  <MetricPill label="" value={j.sjr_quartile} color={
                    j.sjr_quartile === 'Q1' ? '#3D6B35' : j.sjr_quartile === 'Q2' ? '#8B6914' : '#9B4D4D'
                  } />
                )}
              </div>
            )}
          </div>
        )
        return url ? (
          <a key={j.name} href={url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', display: 'block' }}>
            {content}
          </a>
        ) : (
          <div key={j.name}>{content}</div>
        )
      })}
    </div>
  )
}

function MetricPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 3,
      padding: '2px 7px',
      borderRadius: 6,
      backgroundColor: theme.pageBg,
      fontSize: 11,
      fontFamily: fontMono,
      color: color || theme.textMuted,
    }}>
      {label && <span style={{ fontWeight: 400 }}>{label}</span>}
      <span style={{ fontWeight: 600 }}>{value}</span>
    </span>
  )
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function markdownToHtml(md: string): string {
  // First, extract and convert markdown tables before escaping HTML
  let result = md

  // Convert markdown tables to HTML tables
  const tableRegex = /(?:^|\n)((?:\|.+\|\n)+)/g
  result = result.replace(tableRegex, (match, tableBlock: string) => {
    const rows = tableBlock.trim().split('\n').filter((r: string) => r.trim())
    if (rows.length < 2) return match

    // Check if second row is separator (|---|---|)
    const isSeparator = /^\|[\s\-:]+\|/.test(rows[1])
    if (!isSeparator) return match

    const parseRow = (row: string) =>
      row.split('|').slice(1, -1).map((c: string) => c.trim())

    const headers = parseRow(rows[0])
    const dataRows = rows.slice(2).map(parseRow)

    const headerHtml = headers.map((h: string) =>
      `<th style="padding:8px 12px;text-align:left;font-weight:600;font-size:13px;border-bottom:2px solid #E5E2DC;color:#2D2D2D">${h}</th>`
    ).join('')
    const bodyHtml = dataRows.map((cols: string[]) =>
      '<tr>' + cols.map((c: string) =>
        `<td style="padding:8px 12px;font-size:13px;border-bottom:1px solid #F0EDE8;color:#5C5C5C">${c}</td>`
      ).join('') + '</tr>'
    ).join('')

    return `\n<table style="width:100%;border-collapse:collapse;margin:12px 0;border:1px solid #E5E2DC;border-radius:8px;overflow:hidden"><thead><tr style="background:#FAF9F7">${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>\n`
  })

  // Now escape HTML entities (but preserve table HTML we just created)
  const tablePlaceholders: string[] = []
  result = result.replace(/<table[\s\S]*?<\/table>/g, (m) => {
    tablePlaceholders.push(m)
    return `__TABLE_${tablePlaceholders.length - 1}__`
  })

  result = result
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Restore tables
  tablePlaceholders.forEach((t, i) => {
    result = result.replace(`__TABLE_${i}__`, t)
  })

  result = result
    // Horizontal rules: --- or *** on their own line
    .replace(/^-{3,}$/gm, '<hr style="border:none;border-top:1px solid #E5E2DC;margin:20px 0"/>')
    .replace(/^\*{3,}$/gm, '<hr style="border:none;border-top:1px solid #E5E2DC;margin:20px 0"/>')
    // Markdown links with parentheses in URLs: [text](url) — handle nested parens for DOI links
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s]*?(?:\([^\s)]*\)[^\s]*?)*[^\s)]*)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:#4338CA;text-decoration:underline">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4 style="margin-top:20px;margin-bottom:8px;font-size:15px;font-weight:600;color:#2D2D2D">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="margin-top:24px;margin-bottom:10px;font-size:17px;font-weight:600;color:#2D2D2D">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="margin-top:28px;margin-bottom:12px;font-size:18px;font-weight:600;color:#2D2D2D">$1</h2>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:16px;margin-bottom:6px;line-height:1.6">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left:16px;margin-bottom:6px;line-height:1.6">$2</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')

  return result
}
