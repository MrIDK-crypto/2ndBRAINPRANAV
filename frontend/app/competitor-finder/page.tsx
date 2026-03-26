'use client'

import React, { useState, useRef } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5002'

const theme = {
  bg: '#FAF9F7',
  surface: '#FFFFFF',
  primary: '#C9A598',
  primaryHover: '#B8948A',
  text: '#2D2D2D',
  textSec: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
  successBg: '#F0F7EE',
  warning: '#E2A336',
  warningBg: '#FEF7E8',
  error: '#D97373',
  errorBg: '#FEF0F0',
  blue: '#5B8DEF',
  blueBg: '#EEF4FF',
  font: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
}

interface Insight {
  type: string
  message: string
  action: string
}

interface CompetitorLab {
  name: string
  institution: string
  recent_papers: number
  total_citations: number
  key_authors: string[]
  most_recent_year: number
  top_papers: any[]
}

interface Preprint {
  title: string
  authors: string[]
  arxiv_id: string
  url: string
  published: string
  days_ago: number
  is_very_recent: boolean
  abstract: string
}

interface Grant {
  title: string
  pi_name: string
  organization: string
  total_cost: number
  start_date: string
  end_date: string
  nih_link: string
}

interface AnalysisResult {
  domain: string
  research_question: string
  urgency_level: 'low' | 'medium' | 'high'
  insights: Insight[]
  competitor_labs: CompetitorLab[]
  recent_preprints: Preprint[]
  active_grants: Grant[]
  summary: {
    total_competitors: number
    total_preprints: number
    very_recent_preprints: number
    active_grants: number
  }
}

export default function CompetitorFinderPage() {
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [inputMode, setInputMode] = useState<'file' | 'text'>('file')
  const [analyzing, setAnalyzing] = useState(false)
  const [progress, setProgress] = useState({ step: 0, message: '', percent: 0 })
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'labs' | 'preprints' | 'grants'>('labs')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleAnalyze = async () => {
    setAnalyzing(true)
    setError(null)
    setResult(null)
    setProgress({ step: 0, message: 'Starting analysis...', percent: 0 })

    const formData = new FormData()
    if (inputMode === 'file' && file) {
      formData.append('file', file)
    } else if (inputMode === 'text' && text) {
      formData.append('text', text)
    } else {
      setError('Please provide a manuscript')
      setAnalyzing(false)
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/research-tools/competitors/analyze`, {
        method: 'POST',
        body: formData,
      })

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event:')) {
            const eventType = line.replace('event:', '').trim()
            const dataLine = lines[lines.indexOf(line) + 1]
            if (dataLine?.startsWith('data:')) {
              try {
                const data = JSON.parse(dataLine.replace('data:', '').trim())

                if (eventType === 'progress') {
                  setProgress(data)
                } else if (eventType === 'complete') {
                  setResult(data)
                  setAnalyzing(false)
                } else if (eventType === 'error') {
                  setError(data.message || data.error)
                  setAnalyzing(false)
                }
              } catch {}
            }
          }
        }
      }
    } catch (e: any) {
      setError(e.message)
      setAnalyzing(false)
    }
  }

  const urgencyColor = (level: string) => {
    if (level === 'high') return { bg: theme.errorBg, text: theme.error, label: 'High Alert' }
    if (level === 'medium') return { bg: theme.warningBg, text: theme.warning, label: 'Monitor' }
    return { bg: theme.successBg, text: theme.success, label: 'Low Competition' }
  }

  return (
    <div style={{ minHeight: '100vh', background: theme.bg, fontFamily: theme.font }}>
      {/* Header */}
      <header style={{
        padding: '20px 32px',
        borderBottom: `1px solid ${theme.border}`,
        background: theme.surface,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: theme.primary,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
        </div>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: theme.text, margin: 0 }}>
            Peer Labs
          </h1>
          <p style={{ fontSize: 12, color: theme.textMuted, margin: 0 }}>
            Discover labs, preprints, and grants in your research area
          </p>
        </div>
      </header>

      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '32px' }}>
        {/* Input Section */}
        {!result && (
          <div style={{
            background: theme.surface,
            borderRadius: 16,
            padding: 32,
            border: `1px solid ${theme.border}`,
          }}>
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
                <button
                  onClick={() => setInputMode('file')}
                  style={{
                    padding: '10px 20px',
                    borderRadius: 8,
                    border: `1px solid ${inputMode === 'file' ? theme.primary : theme.border}`,
                    background: inputMode === 'file' ? theme.primary : theme.surface,
                    color: inputMode === 'file' ? '#fff' : theme.text,
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  Upload Manuscript
                </button>
                <button
                  onClick={() => setInputMode('text')}
                  style={{
                    padding: '10px 20px',
                    borderRadius: 8,
                    border: `1px solid ${inputMode === 'text' ? theme.primary : theme.border}`,
                    background: inputMode === 'text' ? theme.primary : theme.surface,
                    color: inputMode === 'text' ? '#fff' : theme.text,
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  Paste Abstract
                </button>
              </div>

              {inputMode === 'file' ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: `2px dashed ${theme.border}`,
                    borderRadius: 12,
                    padding: 40,
                    textAlign: 'center',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    style={{ display: 'none' }}
                  />
                  {file ? (
                    <p style={{ color: theme.text, fontWeight: 500 }}>{file.name}</p>
                  ) : (
                    <p style={{ color: theme.textMuted }}>
                      Drop your manuscript or abstract here<br />
                      <span style={{ fontSize: 12 }}>PDF, DOCX, TXT supported</span>
                    </p>
                  )}
                </div>
              ) : (
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste your abstract or research description..."
                  style={{
                    width: '100%',
                    height: 180,
                    padding: 16,
                    borderRadius: 12,
                    border: `1px solid ${theme.border}`,
                    fontFamily: theme.font,
                    fontSize: 14,
                    resize: 'vertical',
                  }}
                />
              )}
            </div>

            <button
              onClick={handleAnalyze}
              disabled={analyzing || (!file && !text)}
              style={{
                width: '100%',
                padding: '14px 24px',
                borderRadius: 10,
                border: 'none',
                background: analyzing ? theme.textMuted : theme.primary,
                color: '#fff',
                fontSize: 15,
                fontWeight: 600,
                cursor: analyzing ? 'not-allowed' : 'pointer',
              }}
            >
              {analyzing ? `${progress.message} (${progress.percent}%)` : 'Find Peer Labs'}
            </button>

            {error && (
              <div style={{
                marginTop: 16,
                padding: 16,
                borderRadius: 10,
                background: theme.errorBg,
                color: theme.error,
              }}>
                {error}
              </div>
            )}
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div>
            {/* Summary Banner */}
            <div style={{
              background: urgencyColor(result.urgency_level).bg,
              borderRadius: 16,
              padding: 24,
              marginBottom: 24,
              border: `1px solid ${urgencyColor(result.urgency_level).text}30`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{
                    display: 'inline-block',
                    padding: '4px 12px',
                    borderRadius: 6,
                    background: urgencyColor(result.urgency_level).text,
                    color: '#fff',
                    fontSize: 12,
                    fontWeight: 600,
                    marginBottom: 8,
                  }}>
                    {urgencyColor(result.urgency_level).label}
                  </span>
                  <h2 style={{ fontSize: 18, fontWeight: 600, margin: '8px 0 4px', color: theme.text }}>
                    {result.domain}
                  </h2>
                  <p style={{ fontSize: 13, color: theme.textSec, margin: 0 }}>
                    {result.research_question?.slice(0, 150)}...
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 16, textAlign: 'center' }}>
                  <div>
                    <div style={{ fontSize: 28, fontWeight: 700, color: theme.text }}>
                      {result.summary.total_competitors}
                    </div>
                    <div style={{ fontSize: 11, color: theme.textMuted }}>Labs</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 28, fontWeight: 700, color: result.summary.very_recent_preprints > 0 ? theme.error : theme.text }}>
                      {result.summary.total_preprints}
                    </div>
                    <div style={{ fontSize: 11, color: theme.textMuted }}>Preprints</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 28, fontWeight: 700, color: theme.text }}>
                      {result.summary.active_grants}
                    </div>
                    <div style={{ fontSize: 11, color: theme.textMuted }}>Grants</div>
                  </div>
                </div>
              </div>

              {/* Insights */}
              {result.insights?.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  {result.insights.map((insight, i) => (
                    <div key={i} style={{
                      padding: '10px 14px',
                      background: 'rgba(255,255,255,0.7)',
                      borderRadius: 8,
                      marginTop: 8,
                      fontSize: 13,
                    }}>
                      <strong style={{ color: theme.text }}>{insight.message}</strong>
                      <div style={{ color: theme.textSec, marginTop: 2 }}>{insight.action}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
              {(['labs', 'preprints', 'grants'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: '10px 20px',
                    borderRadius: 8,
                    border: `1px solid ${activeTab === tab ? theme.primary : theme.border}`,
                    background: activeTab === tab ? theme.primary : theme.surface,
                    color: activeTab === tab ? '#fff' : theme.text,
                    fontWeight: 500,
                    cursor: 'pointer',
                    textTransform: 'capitalize',
                  }}
                >
                  {tab === 'labs' ? `Labs (${result.competitor_labs?.length || 0})` :
                   tab === 'preprints' ? `Preprints (${result.recent_preprints?.length || 0})` :
                   `Grants (${result.active_grants?.length || 0})`}
                </button>
              ))}
            </div>

            {/* Labs Tab */}
            {activeTab === 'labs' && (
              <div style={{
                background: theme.surface,
                borderRadius: 16,
                padding: 24,
                border: `1px solid ${theme.border}`,
              }}>
                {result.competitor_labs?.map((lab, i) => (
                  <div key={i} style={{
                    padding: 16,
                    borderRadius: 10,
                    background: i === 0 ? theme.warningBg : theme.bg,
                    border: `1px solid ${i === 0 ? theme.warning + '30' : theme.border}`,
                    marginBottom: 12,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <div>
                        <h4 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: theme.text }}>
                          {lab.name} Lab
                          {i === 0 && <span style={{ color: theme.warning, marginLeft: 8, fontSize: 12 }}>Most Active</span>}
                        </h4>
                        <p style={{ margin: '4px 0', fontSize: 12, color: theme.textMuted }}>
                          {lab.key_authors?.slice(0, 3).join(', ')}
                        </p>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 18, fontWeight: 700, color: theme.text }}>{lab.recent_papers}</div>
                        <div style={{ fontSize: 11, color: theme.textMuted }}>Recent Papers</div>
                      </div>
                    </div>
                    <div style={{ marginTop: 8, fontSize: 12, color: theme.textSec }}>
                      {lab.total_citations.toLocaleString()} total citations &bull; Most recent: {lab.most_recent_year}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Preprints Tab */}
            {activeTab === 'preprints' && (
              <div style={{
                background: theme.surface,
                borderRadius: 16,
                padding: 24,
                border: `1px solid ${theme.border}`,
              }}>
                {result.recent_preprints?.map((preprint, i) => (
                  <div key={i} style={{
                    padding: 16,
                    borderRadius: 10,
                    background: preprint.is_very_recent ? theme.errorBg : theme.bg,
                    border: `1px solid ${preprint.is_very_recent ? theme.error + '30' : theme.border}`,
                    marginBottom: 12,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: theme.text }}>
                          {preprint.title}
                        </h4>
                        <p style={{ margin: '4px 0', fontSize: 12, color: theme.textMuted }}>
                          {preprint.authors?.slice(0, 3).join(', ')}
                        </p>
                      </div>
                      {preprint.is_very_recent && (
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: 6,
                          background: theme.error,
                          color: '#fff',
                          fontSize: 11,
                          fontWeight: 600,
                        }}>
                          {preprint.days_ago} days ago!
                        </span>
                      )}
                    </div>
                    <p style={{ fontSize: 12, color: theme.textSec, margin: '8px 0' }}>
                      {preprint.abstract}
                    </p>
                    <a
                      href={preprint.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ fontSize: 12, color: theme.primary }}
                    >
                      View on arXiv ({preprint.arxiv_id})
                    </a>
                  </div>
                ))}
                {(!result.recent_preprints || result.recent_preprints.length === 0) && (
                  <p style={{ color: theme.textMuted, textAlign: 'center', padding: 40 }}>
                    No recent preprints found in your area
                  </p>
                )}
              </div>
            )}

            {/* Grants Tab */}
            {activeTab === 'grants' && (
              <div style={{
                background: theme.surface,
                borderRadius: 16,
                padding: 24,
                border: `1px solid ${theme.border}`,
              }}>
                {result.active_grants?.map((grant, i) => (
                  <div key={i} style={{
                    padding: 16,
                    borderRadius: 10,
                    background: theme.blueBg,
                    border: `1px solid ${theme.blue}30`,
                    marginBottom: 12,
                  }}>
                    <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: theme.text }}>
                      {grant.title}
                    </h4>
                    <p style={{ margin: '4px 0', fontSize: 12, color: theme.textSec }}>
                      PI: {grant.pi_name} &bull; {grant.organization}
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                      <span style={{ fontSize: 12, color: theme.textMuted }}>
                        {grant.start_date} - {grant.end_date}
                      </span>
                      {grant.total_cost > 0 && (
                        <span style={{ fontSize: 12, fontWeight: 600, color: theme.blue }}>
                          ${grant.total_cost.toLocaleString()}
                        </span>
                      )}
                    </div>
                    <a
                      href={grant.nih_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ fontSize: 12, color: theme.primary, marginTop: 8, display: 'inline-block' }}
                    >
                      View on NIH Reporter
                    </a>
                  </div>
                ))}
                {(!result.active_grants || result.active_grants.length === 0) && (
                  <p style={{ color: theme.textMuted, textAlign: 'center', padding: 40 }}>
                    No active NIH grants found in your area
                  </p>
                )}
              </div>
            )}

            <button
              onClick={() => { setResult(null); setFile(null); setText('') }}
              style={{
                marginTop: 24,
                padding: '12px 24px',
                borderRadius: 10,
                border: `1px solid ${theme.border}`,
                background: theme.surface,
                color: theme.text,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              New Search
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
