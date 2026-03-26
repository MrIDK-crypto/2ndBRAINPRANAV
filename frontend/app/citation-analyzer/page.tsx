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
  font: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
}

interface MissingCitation {
  title: string
  authors: string[]
  year: number
  doi: string
  cited_by_count: number
  journal: string
  severity: 'high' | 'medium' | 'low'
  reason: string
}

interface OverCitedAuthor {
  author: string
  count: number
  warning: string
}

interface AnalysisResult {
  field: string
  subfield: string
  your_citations: number
  missing_citations: MissingCitation[]
  over_cited_authors: OverCitedAuthor[]
  citation_gap_count: number
  coverage_score: number
  recommendations: string[]
}

export default function CitationAnalyzerPage() {
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [inputMode, setInputMode] = useState<'file' | 'text'>('file')
  const [analyzing, setAnalyzing] = useState(false)
  const [progress, setProgress] = useState({ step: 0, message: '', percent: 0 })
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
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
      const response = await fetch(`${API_URL}/api/research-tools/citations/analyze`, {
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

  const severityColor = (severity: string) => {
    if (severity === 'high') return { bg: theme.errorBg, border: theme.error, text: theme.error }
    if (severity === 'medium') return { bg: theme.warningBg, border: theme.warning, text: theme.warning }
    return { bg: theme.successBg, border: theme.success, text: theme.success }
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
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
        </div>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: theme.text, margin: 0 }}>
            Who Should I Cite?
          </h1>
          <p style={{ fontSize: 12, color: theme.textMuted, margin: 0 }}>
            Find missing citations and gaps in your manuscript
          </p>
        </div>
      </header>

      <main style={{ maxWidth: 900, margin: '0 auto', padding: '32px' }}>
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
                  Upload File
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
                  Paste Text
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
                      Drop your manuscript here or click to browse<br />
                      <span style={{ fontSize: 12 }}>PDF, DOCX, TXT, MD supported</span>
                    </p>
                  )}
                </div>
              ) : (
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste your manuscript text here..."
                  style={{
                    width: '100%',
                    height: 200,
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
              {analyzing ? `${progress.message} (${progress.percent}%)` : 'Analyze Citations'}
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
            {/* Summary Card */}
            <div style={{
              background: theme.surface,
              borderRadius: 16,
              padding: 24,
              marginBottom: 24,
              border: `1px solid ${theme.border}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: theme.text }}>
                    {result.field} / {result.subfield}
                  </h2>
                  <p style={{ color: theme.textMuted, fontSize: 13, margin: '4px 0 0' }}>
                    Analyzed {result.your_citations} citations in your manuscript
                  </p>
                </div>
                <div style={{
                  padding: '12px 20px',
                  borderRadius: 12,
                  background: result.coverage_score >= 70 ? theme.successBg : theme.warningBg,
                  textAlign: 'center',
                }}>
                  <div style={{
                    fontSize: 28,
                    fontWeight: 700,
                    color: result.coverage_score >= 70 ? theme.success : theme.warning,
                  }}>
                    {result.coverage_score}%
                  </div>
                  <div style={{ fontSize: 11, color: theme.textMuted }}>Coverage Score</div>
                </div>
              </div>

              {/* Recommendations */}
              {result.recommendations?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  {result.recommendations.map((rec, i) => (
                    <div key={i} style={{
                      padding: '10px 14px',
                      background: theme.bg,
                      borderRadius: 8,
                      marginBottom: 8,
                      fontSize: 13,
                      color: theme.textSec,
                    }}>
                      {rec}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Missing Citations */}
            {result.missing_citations?.length > 0 && (
              <div style={{
                background: theme.surface,
                borderRadius: 16,
                padding: 24,
                marginBottom: 24,
                border: `1px solid ${theme.border}`,
              }}>
                <h3 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 16px', color: theme.text }}>
                  Missing Citations ({result.citation_gap_count} found)
                </h3>
                {result.missing_citations.map((citation, i) => {
                  const colors = severityColor(citation.severity)
                  return (
                    <div key={i} style={{
                      padding: 16,
                      borderRadius: 10,
                      background: colors.bg,
                      border: `1px solid ${colors.border}20`,
                      marginBottom: 12,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, color: theme.text, fontSize: 14, marginBottom: 4 }}>
                            {citation.title}
                          </div>
                          <div style={{ fontSize: 12, color: theme.textSec }}>
                            {citation.authors?.join(', ')} ({citation.year})
                          </div>
                          <div style={{ fontSize: 12, color: theme.textMuted, marginTop: 4 }}>
                            {citation.journal} &bull; {citation.cited_by_count.toLocaleString()} citations
                          </div>
                        </div>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: 6,
                          background: colors.border,
                          color: '#fff',
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                        }}>
                          {citation.severity}
                        </span>
                      </div>
                      {citation.doi && (
                        <a
                          href={citation.doi}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontSize: 12, color: theme.primary, marginTop: 8, display: 'inline-block' }}
                        >
                          View Paper
                        </a>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* Over-cited Authors */}
            {result.over_cited_authors?.length > 0 && (
              <div style={{
                background: theme.surface,
                borderRadius: 16,
                padding: 24,
                marginBottom: 24,
                border: `1px solid ${theme.border}`,
              }}>
                <h3 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 16px', color: theme.text }}>
                  Over-Cited Authors
                </h3>
                {result.over_cited_authors.map((author, i) => (
                  <div key={i} style={{
                    padding: 12,
                    borderRadius: 8,
                    background: theme.warningBg,
                    marginBottom: 8,
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}>
                    <span style={{ fontWeight: 500, color: theme.text }}>{author.author}</span>
                    <span style={{ color: theme.warning, fontWeight: 600 }}>{author.count} citations</span>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => { setResult(null); setFile(null); setText('') }}
              style={{
                padding: '12px 24px',
                borderRadius: 10,
                border: `1px solid ${theme.border}`,
                background: theme.surface,
                color: theme.text,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Analyze Another Manuscript
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
