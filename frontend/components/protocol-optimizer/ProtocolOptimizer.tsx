'use client'

import React, { useState, useRef, useCallback } from 'react'
import TopNav from '../shared/TopNav'
import { useAuth } from '@/contexts/AuthContext'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5002'

// ── Wellspring Warm Theme with Subtle Design Principles ─────────────────────
// Uses rgba for borders/backgrounds for whisper-quiet surface elevation

const theme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: 'rgba(0, 0, 0, 0.06)',
  borderDark: 'rgba(0, 0, 0, 0.08)',
  success: '#9CB896',
  successBg: 'rgba(156, 184, 150, 0.08)',
  successBorder: 'rgba(156, 184, 150, 0.25)',
  amber: '#E2A336',
  amberBg: 'rgba(226, 163, 54, 0.08)',
  amberBorder: 'rgba(226, 163, 54, 0.25)',
  error: '#D97B7B',
  errorBg: 'rgba(217, 123, 123, 0.08)',
  errorBorder: 'rgba(217, 123, 123, 0.25)',
  primaryBorder: 'rgba(201, 165, 152, 0.25)',
}

const font = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

// Subtle risk colors with rgba for blending
const riskColors: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  high: { bg: 'rgba(217, 123, 123, 0.08)', border: 'rgba(217, 123, 123, 0.25)', text: '#9B4D4D', badge: '#D97B7B' },
  medium: { bg: 'rgba(226, 163, 54, 0.08)', border: 'rgba(226, 163, 54, 0.25)', text: '#8B6914', badge: '#E2A336' },
  low: { bg: 'rgba(156, 184, 150, 0.08)', border: 'rgba(156, 184, 150, 0.25)', text: '#3D6B35', badge: '#9CB896' },
}

// ── Types ──────────────────────────────────────────────────────────────────

interface Progress {
  step: number
  message: string
  percent: number
}

interface UserContext {
  organism?: string
  organism_type?: string
  tissue?: string
  cell_type?: string
  technique?: string
  specific_target?: string
  issue_reported?: string
  equipment_mentioned?: string[]
  constraints?: string[]
}

interface ProtocolContext {
  organism?: string
  tissue?: string
  technique?: string
}

interface ContextMismatch {
  type: string
  severity: string
  user_context?: string
  protocol_context?: string
  message: string
}

interface LiteratureEvidence {
  title: string
  finding?: string
  year?: string
  url?: string
  pmid?: string
  doi?: string
}

interface Issue {
  step_number?: number
  step_text?: string
  risk_level: string
  issue_type?: string
  problem: string
  explanation?: string
  corpus_evidence?: {
    matching_protocols_found?: number
    typical_value_in_corpus?: string
  }
  literature_evidence?: LiteratureEvidence[]
  failed_experiment_warning?: string
  suggested_optimization: string
  alternative_reagents?: string[]
  confidence?: number
}

interface FailedExperiment {
  title: string
  what_failed?: string
  why_failed?: string
  lessons_learned?: string
  field?: string
  upvotes?: number
}

interface ScoreBreakdown {
  context_mismatch: number
  high_risk_issues: number
  medium_risk_issues: number
  low_risk_issues: number
  missing_parameters: number
  no_corpus_support: number
}

interface AnalysisResult {
  success: boolean
  elapsed_seconds?: number
  user_context?: UserContext
  protocol_context?: ProtocolContext
  issues: Issue[]
  reproducibility_score: number
  reproducibility_score_after: number
  score_breakdown?: ScoreBreakdown
  corpus_evidence?: {
    matching_protocols?: number
    typical_parameters?: Record<string, any>
  }
  literature_evidence?: {
    papers_found?: number
    key_papers?: any[]
  }
  failed_experiments?: FailedExperiment[]
  optimized_protocol?: string
}

// ── Icons ──────────────────────────────────────────────────────────────────

const FlaskIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 22h12" />
    <path d="M6 22a2 2 0 01-2-2v-2.5c0-1.5 1.5-3 3-3.5l3-1.5V4" />
    <path d="M18 22a2 2 0 002-2v-2.5c0-1.5-1.5-3-3-3.5l-3-1.5V4" />
    <path d="M9 4h6" />
    <path d="M10 4v8.5" />
    <path d="M14 4v8.5" />
  </svg>
)

const UploadIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
)

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.success} strokeWidth="2.5" strokeLinecap="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

const AlertIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
)

const BookIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round">
    <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
    <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
  </svg>
)

const CopyIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
  </svg>
)

// ── Component ──────────────────────────────────────────────────────────────

export default function ProtocolOptimizer() {
  const { user } = useAuth()

  // State
  const [state, setState] = useState<'input' | 'analyzing' | 'results'>('input')
  const [progress, setProgress] = useState<Progress>({ step: 0, message: '', percent: 0 })
  const [contextText, setContextText] = useState('')
  const [contextFile, setContextFile] = useState<File | null>(null)
  const [protocolText, setProtocolText] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  // Result state
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [userContext, setUserContext] = useState<UserContext | null>(null)
  const [protocolContext, setProtocolContext] = useState<ProtocolContext | null>(null)
  const [issues, setIssues] = useState<Issue[]>([])
  const [mismatches, setMismatches] = useState<ContextMismatch[]>([])
  const [failedExperiments, setFailedExperiments] = useState<FailedExperiment[]>([])
  const [score, setScore] = useState<number>(0)
  const [scoreAfter, setScoreAfter] = useState<number>(0)
  const [optimizedProtocol, setOptimizedProtocol] = useState('')

  const fileInputRef = useRef<HTMLInputElement>(null)
  const contextFileInputRef = useRef<HTMLInputElement>(null)

  const reset = useCallback(() => {
    setState('input')
    setProgress({ step: 0, message: '', percent: 0 })
    setResult(null)
    setUserContext(null)
    setProtocolContext(null)
    setIssues([])
    setMismatches([])
    setFailedExperiments([])
    setScore(0)
    setScoreAfter(0)
    setOptimizedProtocol('')
    setError('')
    setContextText('')
    setContextFile(null)
    setProtocolText('')
    setSelectedFile(null)
  }, [])

  const processSSEStream = useCallback(async (response: Response) => {
    const reader = response.body!.getReader()
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
              case 'context_parsed':
                setUserContext(data.user_context)
                break
              case 'protocol_parsed':
                setProtocolContext(data.designed_for)
                break
              case 'mismatch_detected':
                setMismatches(data.mismatches || [])
                break
              case 'failures_checked':
                setFailedExperiments(data.failures || [])
                break
              case 'score_calculated':
                setScore(data.current_score)
                setScoreAfter(data.potential_score)
                break
              case 'complete':
                setResult(data)
                setUserContext(data.user_context)
                setProtocolContext(data.protocol_context)
                setIssues(data.issues || [])
                setScore(data.reproducibility_score)
                setScoreAfter(data.reproducibility_score_after)
                setOptimizedProtocol(data.optimized_protocol || '')
                setFailedExperiments(data.failed_experiments || [])
                setState('results')
                break
              case 'error':
                setError(data.error)
                setState('input')
                break
            }
          } catch {
            // skip unparseable lines
          }
          eventType = ''
        }
      }
    }
  }, [])

  const handleFile = useCallback((file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['pdf', 'docx', 'txt', 'md'].includes(ext)) {
      setError('Please upload a PDF, DOCX, TXT, or MD file.')
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      setError('File too large. Maximum size is 20MB.')
      return
    }
    setError('')
    setSelectedFile(file)
  }, [])

  const handleContextFile = useCallback((file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['pdf', 'docx', 'txt', 'md'].includes(ext)) {
      setError('Please upload a PDF, DOCX, TXT, or MD file for context.')
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      setError('File too large. Maximum size is 20MB.')
      return
    }
    setError('')
    setContextFile(file)
  }, [])

  const handleSubmit = useCallback(async () => {
    // Validate context - need either text (20+ chars) or a file
    const hasContextText = contextText.trim().length >= 20
    const hasContextFile = !!contextFile
    if (!hasContextText && !hasContextFile) {
      setError('Please describe your experimental context (at least 20 characters) or upload a reference paper.')
      return
    }
    if (!protocolText.trim() && !selectedFile) {
      setError('Please paste a protocol or upload a file.')
      return
    }
    if (protocolText.trim() && protocolText.trim().length < 50) {
      setError('Protocol text is too short. Please provide the complete protocol.')
      return
    }

    setError('')
    setState('analyzing')
    setProgress({ step: 1, message: 'Starting analysis...', percent: 2 })

    const formData = new FormData()
    formData.append('context', contextText.trim())

    // Add context file if provided
    if (contextFile) {
      formData.append('context_file', contextFile)
    }

    if (selectedFile) {
      formData.append('file', selectedFile)
    } else {
      formData.append('protocol', protocolText.trim())
    }

    try {
      const response = await fetch(`${API_URL}/api/protocol/optimize`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      })

      if (!response.ok || !response.body) {
        setError('Server error. Please try again.')
        setState('input')
        return
      }

      await processSSEStream(response)
    } catch (e) {
      console.error('[ProtocolOptimizer] Error:', e)
      const errMsg = e instanceof Error ? e.message : String(e)
      setError(`Connection failed: ${errMsg}`)
      setState('input')
    }
  }, [contextText, contextFile, protocolText, selectedFile, processSSEStream])

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(optimizedProtocol)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [optimizedProtocol])

  // ── Render: Input State ─────────────────────────────────────────────────

  const renderInput = () => (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '32px 24px' }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16,
          background: theme.primaryLight, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 16px',
        }}>
          <FlaskIcon />
        </div>
        <h1 style={{
          fontSize: 26, fontWeight: 600, color: theme.textPrimary,
          fontFamily: font, marginBottom: 8,
        }}>
          Protocol Optimizer
        </h1>
        <p style={{
          fontSize: 14, color: theme.textSecondary,
          fontFamily: font, maxWidth: 500, margin: '0 auto', lineHeight: 1.6,
        }}>
          Describe your experimental context and paste your protocol. We'll identify potential
          issues and suggest optimizations based on scientific literature and our protocol corpus.
        </p>
      </div>

      {/* Context Input Card */}
      <div style={{
        background: theme.cardBg,
        border: `1px solid ${theme.border}`,
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 16,
      }}>
        <div style={{
          padding: '14px 18px',
          borderBottom: `1px solid ${theme.border}`,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.amber} strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </svg>
          <span style={{ fontSize: 14, fontWeight: 600, color: theme.textPrimary, fontFamily: font }}>
            Your Experimental Context
          </span>
        </div>
        <div style={{ padding: 18 }}>
          <p style={{ fontSize: 12.5, color: theme.textMuted, fontFamily: font, marginBottom: 12, lineHeight: 1.5 }}>
            Describe your organism, tissue type, what you're trying to do, and any issues you're experiencing.
            You can also upload a reference paper to provide additional context.
          </p>

          {/* Context file upload */}
          <div style={{ marginBottom: 12 }}>
            <input
              ref={contextFileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => e.target.files?.[0] && handleContextFile(e.target.files[0])}
              style={{ display: 'none' }}
            />
            <button
              onClick={() => contextFileInputRef.current?.click()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                background: contextFile ? theme.successBg : 'transparent',
                border: `1px solid ${contextFile ? theme.success : theme.border}`,
                borderRadius: 8,
                color: contextFile ? riskColors.low.text : theme.textMuted,
                fontSize: 12,
                fontFamily: font,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {contextFile ? <CheckIcon /> : <BookIcon />}
              {contextFile ? contextFile.name : 'Upload Reference Paper (optional)'}
            </button>
            {contextFile && (
              <button
                onClick={() => setContextFile(null)}
                style={{
                  marginLeft: 8,
                  padding: '8px 12px',
                  background: 'transparent',
                  border: `1px solid ${theme.border}`,
                  borderRadius: 8,
                  color: theme.textMuted,
                  fontSize: 12,
                  fontFamily: font,
                  cursor: 'pointer',
                }}
              >
                Clear
              </button>
            )}
          </div>

          <textarea
            value={contextText}
            onChange={(e) => setContextText(e.target.value)}
            placeholder="Example: I'm working with Arabidopsis root tips. I'm trying to do DAPI nuclear staining but getting very weak signal. The protocol I have was written for mouse brain sections."
            style={{
              width: '100%',
              minHeight: 100,
              padding: 12,
              background: '#FAFAF8',
              border: `1px solid ${theme.border}`,
              borderRadius: 8,
              color: theme.textPrimary,
              fontSize: 13.5,
              fontFamily: font,
              lineHeight: 1.6,
              resize: 'vertical',
              outline: 'none',
              transition: 'border-color 0.15s',
            }}
            onFocus={(e) => e.currentTarget.style.borderColor = theme.primary}
            onBlur={(e) => e.currentTarget.style.borderColor = theme.border}
          />
        </div>
      </div>

      {/* Protocol Input Card */}
      <div style={{
        background: theme.cardBg,
        border: `1px solid ${theme.border}`,
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 16,
      }}>
        <div style={{
          padding: '14px 18px',
          borderBottom: `1px solid ${theme.border}`,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span style={{ fontSize: 14, fontWeight: 600, color: theme.textPrimary, fontFamily: font }}>
            Protocol
          </span>
        </div>
        <div style={{ padding: 18 }}>
          <p style={{ fontSize: 12.5, color: theme.textMuted, fontFamily: font, marginBottom: 12, lineHeight: 1.5 }}>
            Paste the protocol text or upload a file (PDF, DOCX, TXT, MD).
          </p>

          {/* File upload area */}
          <div style={{ marginBottom: 16 }}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              style={{ display: 'none' }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 18px',
                background: selectedFile ? theme.successBg : theme.primaryLight,
                border: `1px solid ${selectedFile ? theme.success : theme.border}`,
                borderRadius: 8,
                color: selectedFile ? riskColors.low.text : theme.textSecondary,
                fontSize: 13,
                fontFamily: font,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {selectedFile ? <CheckIcon /> : <UploadIcon />}
              {selectedFile ? selectedFile.name : 'Upload Protocol File'}
            </button>
            {selectedFile && (
              <button
                onClick={() => setSelectedFile(null)}
                style={{
                  marginLeft: 10,
                  padding: '10px 14px',
                  background: 'transparent',
                  border: `1px solid ${theme.border}`,
                  borderRadius: 8,
                  color: theme.textMuted,
                  fontSize: 13,
                  fontFamily: font,
                  cursor: 'pointer',
                }}
              >
                Clear
              </button>
            )}
          </div>

          {!selectedFile && (
            <>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12,
                margin: '16px 0',
              }}>
                <div style={{ flex: 1, height: 1, background: theme.border }} />
                <span style={{ fontSize: 11, color: theme.textMuted, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  or paste text
                </span>
                <div style={{ flex: 1, height: 1, background: theme.border }} />
              </div>
              <textarea
                value={protocolText}
                onChange={(e) => setProtocolText(e.target.value)}
                placeholder={`1. Fix tissue in 4% PFA for 24h at 4°C
2. Wash 3x with PBS
3. Permeabilize with 0.3% Triton X-100 for 1h
4. Block with 5% BSA in PBS for 2h
5. Incubate with primary antibody (1:500) overnight at 4°C
...`}
                style={{
                  width: '100%',
                  minHeight: 180,
                  padding: 12,
                  background: '#FAFAF8',
                  border: `1px solid ${theme.border}`,
                  borderRadius: 8,
                  color: theme.textPrimary,
                  fontSize: 13,
                  fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace',
                  lineHeight: 1.7,
                  resize: 'vertical',
                  outline: 'none',
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = theme.primary}
                onBlur={(e) => e.currentTarget.style.borderColor = theme.border}
              />
            </>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          background: theme.errorBg,
          border: `1px solid ${theme.error}`,
          borderRadius: 8,
          padding: 14,
          marginBottom: 16,
        }}>
          <AlertIcon />
          <span style={{ fontSize: 13, color: theme.error, fontFamily: font, lineHeight: 1.5 }}>
            {error}
          </span>
        </div>
      )}

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        style={{
          width: '100%',
          padding: '14px 24px',
          background: theme.primary,
          border: 'none',
          borderRadius: 10,
          color: '#fff',
          fontSize: 15,
          fontWeight: 600,
          fontFamily: font,
          cursor: 'pointer',
          transition: 'background 0.15s',
        }}
        onMouseOver={(e) => (e.currentTarget.style.background = theme.primaryHover)}
        onMouseOut={(e) => (e.currentTarget.style.background = theme.primary)}
      >
        Analyze Protocol
      </button>
    </div>
  )

  // ── Render: Analyzing State ─────────────────────────────────────────────

  const renderAnalyzing = () => (
    <div style={{ maxWidth: 500, margin: '100px auto', padding: '0 24px', textAlign: 'center' }}>
      <div style={{
        width: 60,
        height: 60,
        border: `3px solid ${theme.border}`,
        borderTopColor: theme.primary,
        borderRadius: '50%',
        margin: '0 auto 24px',
        animation: 'spin 1s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <h2 style={{ fontSize: 20, fontWeight: 600, color: theme.textPrimary, fontFamily: font, marginBottom: 8 }}>
        Analyzing Protocol
      </h2>
      <p style={{ fontSize: 14, color: theme.textSecondary, fontFamily: font, marginBottom: 24 }}>
        {progress.message || 'Processing...'}
      </p>

      <div style={{
        width: '100%',
        height: 4,
        background: theme.border,
        borderRadius: 2,
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${progress.percent}%`,
          height: '100%',
          background: theme.primary,
          transition: 'width 0.3s ease',
        }} />
      </div>
      <p style={{ fontSize: 12, color: theme.textMuted, fontFamily: font, marginTop: 10 }}>
        Step {progress.step}/9 — {progress.percent}%
      </p>
    </div>
  )

  // ── Render: Results State ───────────────────────────────────────────────

  const renderResults = () => (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: theme.textPrimary, fontFamily: font }}>
          Analysis Results
        </h1>
        <button
          onClick={reset}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 16px',
            background: 'transparent',
            border: `1px solid ${theme.border}`,
            borderRadius: 8,
            color: theme.textSecondary,
            fontSize: 13,
            fontFamily: font,
            cursor: 'pointer',
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = theme.primaryLight }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Analyze Another
        </button>
      </div>

      {/* Score Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <div style={{
          background: theme.cardBg,
          border: `1px solid ${theme.border}`,
          borderRadius: 12,
          padding: 18,
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 11, color: theme.textMuted, fontFamily: font, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Current Score
          </div>
          <div style={{
            fontSize: 36,
            fontWeight: 700,
            fontFamily: font,
            color: score >= 70 ? theme.success : score >= 40 ? theme.amber : theme.error
          }}>
            {score}
          </div>
          <div style={{ fontSize: 12, color: theme.textMuted, fontFamily: font }}>/100</div>
        </div>

        <div style={{
          background: theme.cardBg,
          border: `1px solid ${theme.border}`,
          borderRadius: 12,
          padding: 18,
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 11, color: theme.textMuted, fontFamily: font, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            After Optimization
          </div>
          <div style={{ fontSize: 36, fontWeight: 700, fontFamily: font, color: theme.success }}>
            {scoreAfter}
          </div>
          <div style={{ fontSize: 12, color: theme.textMuted, fontFamily: font }}>/100</div>
        </div>

        <div style={{
          background: theme.cardBg,
          border: `1px solid ${theme.border}`,
          borderRadius: 12,
          padding: 18,
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 11, color: theme.textMuted, fontFamily: font, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Issues Found
          </div>
          <div style={{
            fontSize: 36,
            fontWeight: 700,
            fontFamily: font,
            color: issues.length > 0 ? theme.amber : theme.success
          }}>
            {issues.length}
          </div>
          <div style={{ fontSize: 12, color: theme.textMuted, fontFamily: font }}>
            {issues.filter(i => i.risk_level === 'high').length} high risk
          </div>
        </div>
      </div>

      {/* Context Summary Card */}
      {(userContext || protocolContext) && (
        <div style={{
          background: theme.cardBg,
          border: `1px solid ${theme.border}`,
          borderRadius: 12,
          overflow: 'hidden',
          marginBottom: 16,
        }}>
          <div style={{
            padding: '14px 18px',
            borderBottom: `1px solid ${theme.border}`,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.textSecondary} strokeWidth="2" strokeLinecap="round">
              <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <span style={{ fontSize: 14, fontWeight: 600, color: theme.textPrimary, fontFamily: font }}>
              Context Analysis
            </span>
          </div>
          <div style={{ padding: 18 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div>
                <div style={{ fontSize: 10, fontWeight: 600, color: theme.textMuted, fontFamily: font, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Your Context
                </div>
                <div style={{ fontSize: 13, color: theme.textPrimary, fontFamily: font, lineHeight: 1.7 }}>
                  {userContext?.organism && <div><strong>Organism:</strong> {userContext.organism}</div>}
                  {userContext?.tissue && <div><strong>Tissue:</strong> {userContext.tissue}</div>}
                  {userContext?.technique && <div><strong>Technique:</strong> {userContext.technique}</div>}
                  {userContext?.issue_reported && <div><strong>Issue:</strong> {userContext.issue_reported}</div>}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, fontWeight: 600, color: theme.textMuted, fontFamily: font, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Protocol Designed For
                </div>
                <div style={{ fontSize: 13, color: theme.textPrimary, fontFamily: font, lineHeight: 1.7 }}>
                  {protocolContext?.organism && <div><strong>Organism:</strong> {protocolContext.organism}</div>}
                  {protocolContext?.tissue && <div><strong>Tissue:</strong> {protocolContext.tissue}</div>}
                  {protocolContext?.technique && <div><strong>Technique:</strong> {protocolContext.technique}</div>}
                  {!protocolContext?.organism && !protocolContext?.tissue && (
                    <div style={{ color: theme.textMuted, fontStyle: 'italic' }}>Not specified in protocol</div>
                  )}
                </div>
              </div>
            </div>

            {mismatches.length > 0 && (
              <div style={{
                marginTop: 16,
                padding: 12,
                background: theme.errorBg,
                border: `1px solid ${theme.errorBorder}`,
                borderRadius: 8,
              }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: riskColors.high.text, fontFamily: font, marginBottom: 6, textTransform: 'uppercase' }}>
                  Context Mismatches Detected
                </div>
                {mismatches.map((m, i) => (
                  <div key={i} style={{ fontSize: 12.5, color: riskColors.high.text, fontFamily: font, lineHeight: 1.5 }}>
                    {m.message}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Issues Card */}
      {issues.length > 0 && (
        <div style={{
          background: theme.cardBg,
          border: `1px solid ${theme.border}`,
          borderRadius: 12,
          overflow: 'hidden',
          marginBottom: 16,
        }}>
          <div style={{
            padding: '14px 18px',
            borderBottom: `1px solid ${theme.border}`,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <AlertIcon />
            <span style={{ fontSize: 14, fontWeight: 600, color: theme.textPrimary, fontFamily: font }}>
              Issues & Optimizations
            </span>
          </div>
          <div style={{ padding: 18 }}>
            {issues.map((issue, i) => {
              const risk = riskColors[issue.risk_level] || riskColors.low
              return (
                <div key={i} style={{
                  background: risk.bg,
                  border: `1px solid ${risk.border}`,
                  borderRadius: 10,
                  padding: 16,
                  marginBottom: i < issues.length - 1 ? 12 : 0,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                    <span style={{
                      padding: '3px 10px',
                      background: risk.badge,
                      borderRadius: 12,
                      fontSize: 10,
                      fontWeight: 600,
                      fontFamily: font,
                      color: '#fff',
                      textTransform: 'uppercase',
                      letterSpacing: '0.3px',
                    }}>
                      {issue.risk_level}
                    </span>
                    {issue.step_number && (
                      <span style={{ fontSize: 12, color: theme.textMuted, fontFamily: font }}>
                        Step {issue.step_number}
                      </span>
                    )}
                  </div>

                  {issue.step_text && (
                    <div style={{
                      fontSize: 12,
                      color: theme.textMuted,
                      fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace',
                      background: theme.pageBg,
                      padding: 10,
                      borderRadius: 6,
                      marginBottom: 12,
                    }}>
                      "{issue.step_text}"
                    </div>
                  )}

                  <div style={{ fontSize: 13.5, fontWeight: 600, color: risk.text, fontFamily: font, marginBottom: 8 }}>
                    {issue.problem}
                  </div>

                  {issue.explanation && (
                    <div style={{ fontSize: 13, color: theme.textPrimary, fontFamily: font, marginBottom: 12, lineHeight: 1.6 }}>
                      {issue.explanation}
                    </div>
                  )}

                  {/* Corpus Evidence */}
                  {issue.corpus_evidence && (
                    <div style={{ fontSize: 12, color: theme.textMuted, fontFamily: font, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={theme.textMuted} strokeWidth="2">
                        <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
                      </svg>
                      <strong>Corpus:</strong> {issue.corpus_evidence.matching_protocols_found || 0} matching protocols
                      {issue.corpus_evidence.typical_value_in_corpus && (
                        <span> · Typical: {issue.corpus_evidence.typical_value_in_corpus}</span>
                      )}
                    </div>
                  )}

                  {/* Literature Evidence */}
                  {issue.literature_evidence && issue.literature_evidence.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: theme.textMuted, fontFamily: font, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                        <BookIcon />
                        Literature Support
                      </div>
                      {issue.literature_evidence.slice(0, 2).map((lit, j) => (
                        <div key={j} style={{ fontSize: 12, color: theme.textSecondary, fontFamily: font, marginBottom: 4, paddingLeft: 18 }}>
                          • {lit.url ? (
                            <a
                              href={lit.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: theme.primary, textDecoration: 'underline', cursor: 'pointer' }}
                            >
                              {lit.title}
                            </a>
                          ) : lit.title} {lit.finding && <span style={{ color: theme.textMuted }}>— {lit.finding}</span>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Optimization Suggestion */}
                  <div style={{
                    background: theme.successBg,
                    border: `1px solid ${theme.successBorder}`,
                    borderRadius: 8,
                    padding: 12,
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: riskColors.low.text, fontFamily: font, marginBottom: 6, textTransform: 'uppercase' }}>
                      Suggested Optimization
                    </div>
                    <div style={{ fontSize: 13, color: riskColors.low.text, fontFamily: font, lineHeight: 1.5 }}>
                      {issue.suggested_optimization}
                    </div>
                    {issue.alternative_reagents && issue.alternative_reagents.length > 0 && (
                      <div style={{ fontSize: 12, color: theme.textMuted, fontFamily: font, marginTop: 8 }}>
                        <strong>Alternatives:</strong> {issue.alternative_reagents.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Failed Experiments Warning */}
      {failedExperiments.length > 0 && (
        <div style={{
          background: theme.amberBg,
          border: `1px solid ${theme.amber}`,
          borderRadius: 12,
          padding: 18,
          marginBottom: 16,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={theme.amber} strokeWidth="2" strokeLinecap="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#9A7520', fontFamily: font }}>
              Related Failed Experiments
            </span>
          </div>
          <p style={{ fontSize: 12.5, color: theme.textSecondary, fontFamily: font, marginBottom: 12, lineHeight: 1.5 }}>
            Other researchers have reported failures with similar protocols:
          </p>
          {failedExperiments.map((exp, i) => (
            <div key={i} style={{
              background: theme.cardBg,
              borderRadius: 8,
              padding: 12,
              marginBottom: i < failedExperiments.length - 1 ? 8 : 0,
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: theme.textPrimary, fontFamily: font, marginBottom: 6 }}>
                {exp.title}
              </div>
              {exp.what_failed && (
                <div style={{ fontSize: 12, color: theme.error, fontFamily: font, marginBottom: 4 }}>
                  <strong>What failed:</strong> {exp.what_failed}
                </div>
              )}
              {exp.lessons_learned && (
                <div style={{ fontSize: 12, color: riskColors.low.text, fontFamily: font }}>
                  <strong>Lesson:</strong> {exp.lessons_learned}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Optimized Protocol */}
      {optimizedProtocol && (
        <div style={{
          background: theme.cardBg,
          border: `1px solid ${theme.success}`,
          borderRadius: 12,
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '14px 18px',
            borderBottom: `1px solid ${theme.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <CheckIcon />
              <span style={{ fontSize: 14, fontWeight: 600, color: theme.textPrimary, fontFamily: font }}>
                Optimized Protocol
              </span>
            </div>
            <button
              onClick={handleCopy}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px',
                background: copied ? theme.success : theme.primaryLight,
                border: `1px solid ${copied ? theme.success : theme.border}`,
                borderRadius: 6,
                color: copied ? '#fff' : theme.textSecondary,
                fontSize: 12,
                fontFamily: font,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <CopyIcon />
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
          <div style={{ padding: 18 }}>
            <pre style={{
              background: '#FAFAF8',
              padding: 16,
              borderRadius: 8,
              fontSize: 12.5,
              color: theme.textPrimary,
              fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace',
              lineHeight: 1.8,
              whiteSpace: 'pre-wrap',
              maxHeight: 400,
              overflow: 'auto',
              margin: 0,
            }}>
              {optimizedProtocol}
            </pre>
          </div>
        </div>
      )}
    </div>
  )

  // ── Main Render ──────────────────────────────────────────────────────────

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100vh',
      backgroundColor: theme.pageBg,
      fontFamily: font,
    }}>
      <TopNav userName={user?.full_name?.split(' ')[0] || 'Researcher'} />

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {state === 'input' && renderInput()}
        {state === 'analyzing' && renderAnalyzing()}
        {state === 'results' && renderResults()}
      </div>
    </div>
  )
}
