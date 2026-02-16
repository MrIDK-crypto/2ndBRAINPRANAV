'use client'

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import Sidebar from '../shared/Sidebar'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

// Wellspring-Inspired Warm Design System
const theme = {
  pageBg: '#FAF9F6',
  cardBg: '#F7F5F3',
  glassBg: 'rgba(250, 249, 246, 0.85)',
  ink: '#2D2D2D',
  body: '#4A4A4A',
  muted: '#6B6B6B',
  subtle: '#9A9A9A',
  accent: '#C9A598',
  accentHover: '#B8948A',
  accentLight: '#FBF4F1',
  forest: '#9CB896',
  forestLight: 'rgba(156, 184, 150, 0.15)',
  border: '#F0EEEC',
  borderLight: '#F7F5F3',
  progressBg: '#F0EEEC',
  progressFill: '#C9A598',
}

const fonts = {
  serif: '"Merriweather", Georgia, "Times New Roman", serif',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  mono: '"JetBrains Mono", "Fira Code", monospace',
}

interface KnowledgeGap {
  id: string
  description: string
  project: string
  answered?: boolean
  answer?: string
  category?: string
  priority?: string
  quality_score?: number
  evidence?: string
  context?: string
  suggested_sources?: string[]
  detection_method?: string
  estimated_time?: number
  flagged?: boolean
  skipped?: boolean
}

// Standalone FocusCard Component - OUTSIDE the main component
function FocusCard({
  gap,
  answer,
  onAnswerChange,
  onSubmit,
  onSkip,
  onFlag,
  isSubmitting,
  inputMode,
  onInputModeChange,
  isRecording,
  audioLevel,
  onStartRecording,
  onStopRecording,
  contextSummary,
  loadingContext,
}: {
  gap: KnowledgeGap
  answer: string
  onAnswerChange: (value: string) => void
  onSubmit: () => void
  onSkip: () => void
  onFlag: () => void
  isSubmitting: boolean
  inputMode: 'type' | 'speak'
  onInputModeChange: (mode: 'type' | 'speak') => void
  isRecording: boolean
  audioLevel: number
  onStartRecording: () => void
  onStopRecording: () => void
  contextSummary?: string
  loadingContext?: boolean
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const canSubmit = answer.trim().length >= 10

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onAnswerChange(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.max(120, textareaRef.current.scrollHeight) + 'px'
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px', height: '100%' }}>
      {/* Left Pane - Question & Context */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {/* Category & Meta */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          {gap.category && (
            <span style={{
              padding: '6px 14px',
              backgroundColor: theme.accentLight,
              color: theme.accent,
              fontSize: '11px',
              fontWeight: 600,
              borderRadius: '20px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              fontFamily: fonts.sans,
            }}>
              {gap.category}
            </span>
          )}
          <span style={{ fontSize: '12px', color: theme.subtle, fontFamily: fonts.mono }}>
            ~{gap.estimated_time || 3} min
          </span>
          {gap.flagged && <span style={{ fontSize: '16px' }}>🚩</span>}
        </div>

        {/* Question */}
        <h2 style={{
          fontFamily: fonts.serif,
          fontSize: '28px',
          fontWeight: 700,
          color: theme.ink,
          lineHeight: 1.4,
          marginBottom: '32px',
          letterSpacing: '-0.01em',
        }}>
          {gap.description}
        </h2>

        {/* Context Box - LLM Summarized */}
        <div style={{
          padding: '20px',
          background: theme.borderLight,
          borderRadius: '12px',
          border: `1px solid ${theme.border}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.muted} strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
            </svg>
            <span style={{ fontSize: '11px', fontWeight: 600, color: theme.muted, textTransform: 'uppercase', fontFamily: fonts.sans }}>
              Context
            </span>
          </div>
          {loadingContext ? (
            <p style={{ fontSize: '14px', color: theme.subtle, lineHeight: 1.6, fontFamily: fonts.sans, margin: 0, fontStyle: 'italic' }}>
              Loading context...
            </p>
          ) : contextSummary ? (
            <p style={{ fontSize: '14px', color: theme.body, lineHeight: 1.6, fontFamily: fonts.sans, margin: 0 }}>
              {contextSummary}
            </p>
          ) : (
            <p style={{ fontSize: '14px', color: theme.subtle, lineHeight: 1.6, fontFamily: fonts.sans, margin: 0, fontStyle: 'italic' }}>
              Answer this question to help capture organizational knowledge.
            </p>
          )}
        </div>

        {/* Quick Actions */}
        <div style={{ marginTop: 'auto', paddingTop: '32px', display: 'flex', gap: '12px' }}>
          <button
            onClick={onSkip}
            style={{
              padding: '10px 20px',
              background: 'transparent',
              border: `1px solid ${theme.border}`,
              borderRadius: '8px',
              color: theme.muted,
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: fonts.sans,
            }}
          >
            Skip for now
          </button>
          <button
            onClick={onFlag}
            style={{
              padding: '10px 20px',
              background: gap.flagged ? theme.accentLight : 'transparent',
              border: `1px solid ${gap.flagged ? theme.accent : theme.border}`,
              borderRadius: '8px',
              color: gap.flagged ? theme.accent : theme.muted,
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: fonts.sans,
            }}
          >
            {gap.flagged ? 'Flagged' : 'Flag'}
          </button>
        </div>
      </div>

      {/* Right Pane - Answer Input */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        background: theme.cardBg,
        borderRadius: '20px',
        padding: '32px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
      }}>
        {/* Input Mode Toggle */}
        <div style={{
          display: 'flex',
          gap: '8px',
          marginBottom: '20px',
          padding: '4px',
          background: theme.borderLight,
          borderRadius: '10px',
          width: 'fit-content',
        }}>
          <button
            onClick={() => onInputModeChange('type')}
            style={{
              padding: '10px 20px',
              background: inputMode === 'type' ? theme.cardBg : 'transparent',
              border: 'none',
              borderRadius: '8px',
              color: inputMode === 'type' ? theme.ink : theme.muted,
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: fonts.sans,
              boxShadow: inputMode === 'type' ? '0 2px 8px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            Type
          </button>
          <button
            onClick={() => onInputModeChange('speak')}
            style={{
              padding: '10px 20px',
              background: inputMode === 'speak' ? theme.cardBg : 'transparent',
              border: 'none',
              borderRadius: '8px',
              color: inputMode === 'speak' ? theme.ink : theme.muted,
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: fonts.sans,
              boxShadow: inputMode === 'speak' ? '0 2px 8px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            Speak
          </button>
        </div>

        {/* Input Area */}
        {inputMode === 'type' ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <textarea
              ref={textareaRef}
              value={answer}
              onChange={handleTextareaChange}
              placeholder="Share your knowledge here..."
              style={{
                flex: 1,
                minHeight: '200px',
                padding: '20px',
                background: theme.borderLight,
                border: '2px solid transparent',
                borderRadius: '12px',
                fontSize: '16px',
                color: theme.ink,
                resize: 'none',
                outline: 'none',
                fontFamily: fonts.sans,
                lineHeight: 1.7,
              }}
            />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '16px' }}>
              <span style={{ fontSize: '12px', color: answer.length >= 10 ? theme.forest : theme.subtle, fontFamily: fonts.mono }}>
                {answer.length} characters {answer.length < 10 && '(min 10)'}
              </span>
            </div>
          </div>
        ) : (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px',
            background: theme.borderLight,
            borderRadius: '12px',
          }}>
            <button
              onClick={() => isRecording ? onStopRecording() : onStartRecording()}
              style={{
                width: '100px',
                height: '100px',
                borderRadius: '50%',
                background: isRecording ? theme.accent : theme.ink,
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transform: isRecording ? 'scale(1.1)' : 'scale(1)',
                transition: 'all 0.2s ease',
              }}
            >
              {isRecording ? (
                <svg width="32" height="32" viewBox="0 0 24 24" fill="#fff"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
              ) : (
                <svg width="32" height="32" viewBox="0 0 24 24" fill="#fff">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" fill="none" stroke="#fff" strokeWidth="2"/>
                </svg>
              )}
            </button>
            <p style={{ marginTop: '20px', fontSize: '14px', color: theme.muted, fontFamily: fonts.sans }}>
              {isRecording ? 'Recording... Click to stop' : 'Click to start recording'}
            </p>
            {isRecording && (
              <div style={{ display: 'flex', gap: '3px', marginTop: '16px' }}>
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} style={{
                    width: '4px',
                    height: audioLevel > (i * 8) ? '28px' : '8px',
                    background: audioLevel > (i * 8) ? theme.accent : theme.border,
                    borderRadius: '2px',
                    transition: 'height 0.1s ease',
                  }} />
                ))}
              </div>
            )}
            {answer && (
              <div style={{ marginTop: '20px', padding: '16px', background: theme.cardBg, borderRadius: '8px', width: '100%', maxHeight: '120px', overflow: 'auto' }}>
                <p style={{ margin: 0, fontSize: '14px', color: theme.body, fontFamily: fonts.sans, lineHeight: 1.6 }}>{answer}</p>
              </div>
            )}
          </div>
        )}

        {/* Submit Button */}
        <button
          onClick={onSubmit}
          disabled={!canSubmit || isSubmitting}
          style={{
            marginTop: '20px',
            padding: '16px 32px',
            background: canSubmit ? theme.accent : theme.border,
            border: 'none',
            borderRadius: '12px',
            color: canSubmit ? '#fff' : theme.subtle,
            fontSize: '15px',
            fontWeight: 600,
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            fontFamily: fonts.sans,
            boxShadow: canSubmit ? '0 4px 12px rgba(37, 99, 235, 0.3)' : 'none',
          }}
        >
          {isSubmitting ? 'Saving...' : 'Submit Answer'}
        </button>
      </div>
    </div>
  )
}

export default function KnowledgeGaps() {
  const router = useRouter()
  const [gaps, setGaps] = useState<KnowledgeGap[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [timeStrategy, setTimeStrategy] = useState<'10' | '20' | '30' | 'all'>('20')
  const [viewMode, setViewMode] = useState<'focus' | 'list'>('focus')
  const [currentGapIndex, setCurrentGapIndex] = useState(0)

  // Simple answer state - keyed by gap ID
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [inputModes, setInputModes] = useState<Record<string, 'type' | 'speak'>>({})
  const [recordingGapId, setRecordingGapId] = useState<string | null>(null)
  const [audioLevel, setAudioLevel] = useState(0)

  // LLM-summarized context for each gap
  const [contextSummaries, setContextSummaries] = useState<Record<string, string>>({})
  const [loadingContexts, setLoadingContexts] = useState<Record<string, boolean>>({})

  const [sessionAnswered, setSessionAnswered] = useState(0)
  const [sessionSkipped, setSessionSkipped] = useState(0)
  const [submittingId, setSubmittingId] = useState<string | null>(null)

  const authHeaders = useAuthHeaders()
  const { user } = useAuth()

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    // Only load once when auth is ready
    if (authHeaders && authHeaders.Authorization && !hasLoadedRef.current) {
      hasLoadedRef.current = true
      loadKnowledgeGaps()
    }
  }, [authHeaders])

  // Fetch LLM-summarized context for a gap
  const fetchContextForGap = async (gapId: string) => {
    // Skip API call for sample/demo gaps
    if (gapId.startsWith('sample_')) return

    // Extract original gap ID (remove question index suffix if present)
    const idParts = gapId.split('_')
    const originalGapId = idParts.length > 1 ? idParts.slice(0, -1).join('_') : gapId

    // Skip if already loaded or loading
    if (contextSummaries[gapId] || loadingContexts[gapId]) return

    setLoadingContexts(prev => ({ ...prev, [gapId]: true }))

    try {
      const response = await axios.get(`${API_BASE}/knowledge/gaps/${originalGapId}/context`, { headers: authHeaders })
      if (response.data.success && response.data.context) {
        setContextSummaries(prev => ({ ...prev, [gapId]: response.data.context }))
      }
    } catch (error) {
      console.error('[KnowledgeGaps] Error fetching context:', error)
    } finally {
      setLoadingContexts(prev => ({ ...prev, [gapId]: false }))
    }
  }

  // Context extractor - skip raw metadata, return empty if not useful
  const getCleanContext = (rawContext: any): string => {
    // For now, just return empty - the context data is all garbage metadata
    // The question itself should be self-explanatory
    return ''
  }

  // Clean question text
  const getCleanQuestion = (text: string): string => {
    if (!text) return ''
    // Remove "Context:" and everything after
    const idx = text.indexOf('Context:')
    if (idx > 0) return text.substring(0, idx).trim()
    return text.trim()
  }

  // Sample knowledge gaps for demo
  const SAMPLE_GAPS: KnowledgeGap[] = [
    {
      id: 'sample_1',
      description: 'What is the onboarding process for new team members joining the engineering department?',
      project: 'Onboarding',
      category: 'Process',
      priority: 'high',
      estimated_time: 5,
    },
    {
      id: 'sample_2',
      description: 'How do we handle customer escalations that require executive involvement?',
      project: 'Customer Success',
      category: 'Escalation',
      priority: 'high',
      estimated_time: 4,
    },
    {
      id: 'sample_3',
      description: 'What are the key metrics we track for quarterly business reviews?',
      project: 'Operations',
      category: 'Metrics',
      priority: 'medium',
      estimated_time: 3,
    },
    {
      id: 'sample_4',
      description: 'Who are the primary stakeholders for the product roadmap decisions?',
      project: 'Product',
      category: 'Stakeholders',
      priority: 'medium',
      estimated_time: 2,
    },
    {
      id: 'sample_5',
      description: 'What documentation standards should be followed for API changes?',
      project: 'Engineering',
      category: 'Documentation',
      priority: 'low',
      estimated_time: 3,
    },
  ]

  const loadKnowledgeGaps = async () => {
    if (!authHeaders || !authHeaders.Authorization) return

    try {
      const response = await axios.get(`${API_BASE}/knowledge/gaps`, { headers: authHeaders })
      if (response.data.success && response.data.gaps && response.data.gaps.length > 0) {
        const allGaps: KnowledgeGap[] = []
        const initialAnswers: Record<string, string> = {}

        response.data.gaps.forEach((gap: any) => {
          const groupName = gap.title || gap.category || 'General'
          const questions = gap.questions || []
          const priorityMap: Record<number, string> = { 1: 'low', 2: 'low', 3: 'medium', 4: 'high', 5: 'high' }
          const priorityStr = typeof gap.priority === 'number' ? priorityMap[gap.priority] || 'medium' : gap.priority || 'medium'
          const timeMap: Record<string, number> = { 'high': 5, 'medium': 3, 'low': 2 }
          const estTime = gap.estimated_time || timeMap[priorityStr] || 3

          const cleanContext = getCleanContext(gap.context)

          if (questions.length === 0 && gap.description) {
            const cleanDesc = getCleanQuestion(gap.description)
            if (cleanDesc) {
              allGaps.push({
                id: gap.id,
                description: cleanDesc,
                project: groupName,
                answered: gap.status === 'answered' || gap.status === 'verified',
                answer: '',
                category: gap.category,
                priority: priorityStr,
                context: cleanContext,
                estimated_time: estTime,
              })
              initialAnswers[gap.id] = ''
            }
          } else {
            questions.forEach((question: any, qIndex: number) => {
              // Support both 'text' and 'question' field names (backend may use either)
              const rawText = typeof question === 'string'
                ? question
                : (question.text || question.question || '')
              const cleanText = getCleanQuestion(rawText)
              if (cleanText) {
                const gapId = `${gap.id}_${qIndex}`
                const answerObj = gap.answers?.find((a: any) => a.question_index === qIndex)
                allGaps.push({
                  id: gapId,
                  description: cleanText,
                  project: groupName,
                  answered: gap.status === 'answered',
                  answer: answerObj?.answer_text || '',
                  category: gap.category,
                  priority: priorityStr,
                  context: cleanContext,
                  estimated_time: estTime,
                })
                initialAnswers[gapId] = answerObj?.answer_text || ''
              }
            })
          }
        })

        setGaps(allGaps)
        setAnswers(initialAnswers)
      } else {
        // Use sample gaps for demo
        setGaps(SAMPLE_GAPS)
        const sampleAnswers: Record<string, string> = {}
        SAMPLE_GAPS.forEach(g => { sampleAnswers[g.id] = '' })
        setAnswers(sampleAnswers)
      }
    } catch (error: any) {
      console.error('[KnowledgeGaps] Error:', error)
      // On error, still show sample gaps for demo
      setGaps(SAMPLE_GAPS)
      const sampleAnswers: Record<string, string> = {}
      SAMPLE_GAPS.forEach(g => { sampleAnswers[g.id] = '' })
      setAnswers(sampleAnswers)
    } finally {
      setLoading(false)
    }
  }

  const generateQuestions = async () => {
    setGenerating(true)
    try {
      await axios.post(`${API_BASE}/knowledge/analyze`, { force: true, include_pending: true, mode: 'intelligent' }, { headers: authHeaders })
      await loadKnowledgeGaps()
    } catch (error) {
      console.error('Error analyzing:', error)
    } finally {
      setGenerating(false)
    }
  }

  const handleSubmitAnswer = async (gapId: string) => {
    const answerText = answers[gapId]
    if (!answerText?.trim() || submittingId) return

    setSubmittingId(gapId)
    try {
      // Skip API call for sample/demo gaps - just update local state
      if (gapId.startsWith('sample_')) {
        setGaps(prev => prev.map(g => g.id === gapId ? { ...g, answered: true } : g))
        setSessionAnswered(prev => prev + 1)
        const filtered = getFilteredGaps()
        const currentIdx = filtered.findIndex(g => g.id === gapId)
        if (currentIdx < filtered.length - 1) setCurrentGapIndex(currentIdx + 1)
        return
      }

      const idParts = gapId.split('_')
      const questionIndex = idParts.length > 1 ? parseInt(idParts[idParts.length - 1]) : 0
      const originalGapId = idParts.length > 1 ? idParts.slice(0, -1).join('_') : gapId

      await axios.post(`${API_BASE}/knowledge/gaps/${originalGapId}/answers`, {
        question_index: questionIndex, answer_text: answerText
      }, { headers: authHeaders })

      setGaps(prev => prev.map(g => g.id === gapId ? { ...g, answered: true } : g))
      setSessionAnswered(prev => prev + 1)

      // Move to next gap
      const filtered = getFilteredGaps()
      const currentIdx = filtered.findIndex(g => g.id === gapId)
      if (currentIdx < filtered.length - 1) setCurrentGapIndex(currentIdx + 1)
    } catch (error) {
      console.error('Error submitting:', error)
      alert('Failed to save answer')
    } finally {
      setSubmittingId(null)
    }
  }

  const handleSkip = (gapId: string) => {
    setGaps(prev => prev.map(g => g.id === gapId ? { ...g, skipped: true } : g))
    setSessionSkipped(prev => prev + 1)
    const filtered = getFilteredGaps()
    const currentIdx = filtered.findIndex(g => g.id === gapId)
    if (currentIdx < filtered.length - 1) setCurrentGapIndex(currentIdx + 1)
  }

  const handleFlag = (gapId: string) => {
    setGaps(prev => prev.map(g => g.id === gapId ? { ...g, flagged: !g.flagged } : g))
  }

  // Voice recording
  const startRecording = async (gapId: string) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioContextRef.current = new AudioContext()
      const source = audioContextRef.current.createMediaStreamSource(stream)
      analyserRef.current = audioContextRef.current.createAnalyser()
      analyserRef.current.fftSize = 256
      source.connect(analyserRef.current)

      mediaRecorderRef.current = new MediaRecorder(stream)
      chunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach(track => track.stop())
        if (audioContextRef.current) audioContextRef.current.close()
        await transcribeAudio(gapId, audioBlob)
      }

      mediaRecorderRef.current.start()
      setRecordingGapId(gapId)
      visualizeAudio(gapId)
    } catch (error) {
      console.error('Recording error:', error)
      alert('Could not access microphone')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && recordingGapId) {
      mediaRecorderRef.current.stop()
      setRecordingGapId(null)
      setAudioLevel(0)
    }
  }

  const visualizeAudio = (gapId: string) => {
    if (!analyserRef.current) return
    const bufferLength = analyserRef.current.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)

    const update = () => {
      if (recordingGapId !== gapId) return
      analyserRef.current!.getByteFrequencyData(dataArray)
      const avg = dataArray.reduce((a, b) => a + b) / bufferLength
      setAudioLevel(Math.min(100, (avg / 255) * 100 * 2))
      requestAnimationFrame(update)
    }
    update()
  }

  const transcribeAudio = async (gapId: string, audioBlob: Blob) => {
    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')
      const response = await axios.post(`${API_BASE}/knowledge/transcribe`, formData, {
        headers: { ...authHeaders, 'Content-Type': 'multipart/form-data' }
      })
      if (response.data.success && response.data.transcription) {
        setAnswers(prev => ({
          ...prev,
          [gapId]: (prev[gapId] || '') + ' ' + response.data.transcription.text
        }))
      }
    } catch (error) {
      console.error('Transcription error:', error)
    }
  }

  const getFilteredGaps = useCallback(() => {
    let filtered = gaps.filter(g => !g.answered && !g.skipped)
    filtered.sort((a, b) => (b.quality_score || 0) - (a.quality_score || 0))
    if (timeStrategy === 'all') return filtered

    const timeLimit = parseInt(timeStrategy)
    let totalTime = 0
    const result: KnowledgeGap[] = []
    for (const gap of filtered) {
      const estTime = gap.estimated_time || 3
      if (totalTime + estTime <= timeLimit) {
        result.push(gap)
        totalTime += estTime
      }
    }
    return result
  }, [gaps, timeStrategy])

  const filteredGaps = getFilteredGaps()
  const totalAnswered = gaps.filter(g => g.answered).length
  const progressPercent = gaps.length > 0 ? Math.round((totalAnswered / gaps.length) * 100) : 0
  const currentGap = filteredGaps[currentGapIndex]

  // Fetch context when current gap changes (Focus mode)
  useEffect(() => {
    if (currentGap && authHeaders && authHeaders.Authorization) {
      fetchContextForGap(currentGap.id)
    }
  }, [currentGap?.id, authHeaders])

  // Fetch contexts for all gaps in List mode
  useEffect(() => {
    if (viewMode === 'list' && authHeaders && authHeaders.Authorization && filteredGaps.length > 0) {
      // Fetch context for first 10 gaps to avoid too many requests
      filteredGaps.slice(0, 10).forEach(gap => {
        if (!contextSummaries[gap.id] && !loadingContexts[gap.id]) {
          fetchContextForGap(gap.id)
        }
      })
    }
  }, [viewMode, filteredGaps.length, authHeaders])

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: theme.pageBg }}>
      <Sidebar userName={user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'User'} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Progress Bar */}
        <div style={{ height: '4px', background: theme.progressBg }}>
          <div style={{ height: '100%', width: `${progressPercent}%`, background: theme.accent, transition: 'width 0.5s ease' }} />
        </div>

        {/* Header */}
        <header style={{
          padding: '20px 40px',
          borderBottom: `1px solid ${theme.border}`,
          background: theme.cardBg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div>
            <h1 style={{ fontFamily: fonts.serif, fontSize: '24px', fontWeight: 700, color: theme.ink, margin: 0 }}>
              Knowledge Workshop
            </h1>
            <p style={{ fontFamily: fonts.sans, fontSize: '13px', color: theme.muted, margin: '4px 0 0' }}>
              {totalAnswered} of {gaps.length} answered - {progressPercent}% complete
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* Time Strategy */}
            <div style={{ display: 'flex', gap: '6px', background: theme.borderLight, padding: '4px', borderRadius: '10px' }}>
              {(['10', '20', '30', 'all'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTimeStrategy(t)}
                  style={{
                    padding: '8px 16px',
                    background: timeStrategy === t ? theme.cardBg : 'transparent',
                    border: 'none',
                    borderRadius: '8px',
                    color: timeStrategy === t ? theme.ink : theme.muted,
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontFamily: fonts.sans,
                  }}
                >
                  {t === 'all' ? 'All' : `${t}m`}
                </button>
              ))}
            </div>

            {/* View Mode Toggle */}
            <div style={{ display: 'flex', gap: '4px', background: theme.borderLight, padding: '4px', borderRadius: '8px' }}>
              <button
                onClick={() => setViewMode('focus')}
                style={{
                  padding: '8px 16px',
                  background: viewMode === 'focus' ? theme.cardBg : 'transparent',
                  border: 'none',
                  borderRadius: '6px',
                  color: viewMode === 'focus' ? theme.ink : theme.muted,
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: fonts.sans,
                }}
              >
                Focus
              </button>
              <button
                onClick={() => setViewMode('list')}
                style={{
                  padding: '8px 16px',
                  background: viewMode === 'list' ? theme.cardBg : 'transparent',
                  border: 'none',
                  borderRadius: '6px',
                  color: viewMode === 'list' ? theme.ink : theme.muted,
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: fonts.sans,
                }}
              >
                List
              </button>
            </div>

            <button
              onClick={generateQuestions}
              disabled={generating}
              style={{
                padding: '10px 20px',
                background: theme.accent,
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '13px',
                fontWeight: 600,
                cursor: generating ? 'not-allowed' : 'pointer',
                fontFamily: fonts.sans,
                opacity: generating ? 0.7 : 1,
              }}
            >
              {generating ? 'Analyzing...' : 'Find Gaps'}
            </button>
          </div>
        </header>

        {/* Main Content */}
        <main style={{ flex: 1, padding: '40px', overflow: 'auto' }}>
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
              <div style={{
                width: '48px', height: '48px',
                border: `3px solid ${theme.border}`,
                borderTopColor: theme.accent,
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }} />
            </div>
          ) : gaps.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', textAlign: 'center' }}>
              <div style={{ width: '80px', height: '80px', borderRadius: '20px', backgroundColor: theme.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '24px' }}>
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={theme.accent} strokeWidth="1.5">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                  <circle cx="12" cy="17" r="0.5" fill={theme.accent}/>
                </svg>
              </div>
              <h2 style={{ fontFamily: fonts.serif, fontSize: '28px', color: theme.ink, margin: '0 0 12px' }}>No knowledge gaps yet</h2>
              <p style={{ fontFamily: fonts.sans, fontSize: '15px', color: theme.muted, maxWidth: '400px' }}>
                Analyze your documents to identify knowledge gaps.
              </p>
              <button onClick={generateQuestions} disabled={generating} style={{
                marginTop: '32px', padding: '16px 32px', background: theme.accent, border: 'none',
                borderRadius: '12px', color: '#fff', fontSize: '15px', fontWeight: 600, cursor: 'pointer', fontFamily: fonts.sans,
              }}>
                {generating ? 'Analyzing...' : 'Analyze Documents'}
              </button>
            </div>
          ) : filteredGaps.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '80px', background: theme.accentLight, borderRadius: '20px', maxWidth: '600px', margin: '0 auto' }}>
              <div style={{ width: '80px', height: '80px', borderRadius: '50%', backgroundColor: theme.accent, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
                  <path d="M20 6L9 17l-5-5"/>
                </svg>
              </div>
              <h2 style={{ fontFamily: fonts.serif, fontSize: '28px', color: theme.ink, margin: '0 0 12px' }}>All done!</h2>
              <p style={{ fontFamily: fonts.sans, fontSize: '15px', color: theme.muted }}>
                You've answered all gaps{timeStrategy !== 'all' ? ` in your ${timeStrategy} minute session` : ''}.
              </p>
            </div>
          ) : viewMode === 'focus' && currentGap ? (
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
              {/* Navigation */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px' }}>
                <span style={{ fontFamily: fonts.mono, fontSize: '13px', color: theme.muted }}>
                  Question {currentGapIndex + 1} of {filteredGaps.length}
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => setCurrentGapIndex(prev => Math.max(0, prev - 1))}
                    disabled={currentGapIndex === 0}
                    style={{
                      padding: '8px 16px', background: 'transparent', border: `1px solid ${theme.border}`,
                      borderRadius: '8px', color: currentGapIndex === 0 ? theme.subtle : theme.body,
                      fontSize: '13px', cursor: currentGapIndex === 0 ? 'not-allowed' : 'pointer', fontFamily: fonts.sans,
                    }}
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentGapIndex(prev => Math.min(filteredGaps.length - 1, prev + 1))}
                    disabled={currentGapIndex === filteredGaps.length - 1}
                    style={{
                      padding: '8px 16px', background: 'transparent', border: `1px solid ${theme.border}`,
                      borderRadius: '8px', color: currentGapIndex === filteredGaps.length - 1 ? theme.subtle : theme.body,
                      fontSize: '13px', cursor: currentGapIndex === filteredGaps.length - 1 ? 'not-allowed' : 'pointer', fontFamily: fonts.sans,
                    }}
                  >
                    Next
                  </button>
                </div>
              </div>

              <FocusCard
                key={currentGap.id}
                gap={currentGap}
                answer={answers[currentGap.id] || ''}
                onAnswerChange={(value) => setAnswers(prev => ({ ...prev, [currentGap.id]: value }))}
                onSubmit={() => handleSubmitAnswer(currentGap.id)}
                onSkip={() => handleSkip(currentGap.id)}
                onFlag={() => handleFlag(currentGap.id)}
                isSubmitting={submittingId === currentGap.id}
                inputMode={inputModes[currentGap.id] || 'type'}
                onInputModeChange={(mode) => setInputModes(prev => ({ ...prev, [currentGap.id]: mode }))}
                isRecording={recordingGapId === currentGap.id}
                audioLevel={audioLevel}
                onStartRecording={() => startRecording(currentGap.id)}
                onStopRecording={stopRecording}
                contextSummary={contextSummaries[currentGap.id]}
                loadingContext={loadingContexts[currentGap.id]}
              />
            </div>
          ) : viewMode === 'list' ? (
            <div style={{ maxWidth: '900px', margin: '0 auto' }}>
              {filteredGaps.map((gap) => (
                <div
                  key={gap.id}
                  style={{
                    background: theme.cardBg,
                    borderRadius: '12px',
                    border: `1px solid ${theme.border}`,
                    padding: '24px',
                    marginBottom: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px' }}>
                    <div>
                      {gap.category && (
                        <span style={{
                          padding: '4px 10px',
                          background: theme.accentLight,
                          color: theme.accent,
                          fontSize: '10px',
                          fontWeight: 600,
                          borderRadius: '12px',
                          textTransform: 'uppercase',
                          marginRight: '8px',
                        }}>
                          {gap.category}
                        </span>
                      )}
                      <span style={{ fontSize: '11px', color: theme.subtle, fontFamily: fonts.mono }}>~{gap.estimated_time || 3} min</span>
                    </div>
                  </div>
                  <h3 style={{ fontFamily: fonts.serif, fontSize: '18px', fontWeight: 600, color: theme.ink, margin: '0 0 12px', lineHeight: 1.4 }}>
                    {gap.description}
                  </h3>
                  {/* Context */}
                  <div style={{
                    padding: '12px 16px',
                    background: theme.borderLight,
                    borderRadius: '8px',
                    marginBottom: '16px',
                    borderLeft: `3px solid ${theme.accent}`,
                  }}>
                    {loadingContexts[gap.id] ? (
                      <p style={{ fontSize: '13px', color: theme.subtle, margin: 0, fontStyle: 'italic', fontFamily: fonts.sans }}>
                        Loading context...
                      </p>
                    ) : contextSummaries[gap.id] ? (
                      <p style={{ fontSize: '13px', color: theme.body, margin: 0, lineHeight: 1.5, fontFamily: fonts.sans }}>
                        {contextSummaries[gap.id]}
                      </p>
                    ) : (
                      <p style={{ fontSize: '13px', color: theme.subtle, margin: 0, fontStyle: 'italic', fontFamily: fonts.sans }}>
                        Answer this question to capture organizational knowledge.
                      </p>
                    )}
                  </div>
                  <textarea
                    value={answers[gap.id] || ''}
                    onChange={(e) => setAnswers(prev => ({ ...prev, [gap.id]: e.target.value }))}
                    placeholder="Type your answer..."
                    style={{
                      width: '100%',
                      minHeight: '80px',
                      padding: '12px',
                      background: theme.borderLight,
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '14px',
                      color: theme.ink,
                      resize: 'vertical',
                      outline: 'none',
                      fontFamily: fonts.sans,
                      marginBottom: '12px',
                    }}
                  />
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => handleSkip(gap.id)}
                      style={{
                        padding: '8px 16px', background: 'transparent', border: `1px solid ${theme.border}`,
                        borderRadius: '6px', color: theme.muted, fontSize: '12px', cursor: 'pointer', fontFamily: fonts.sans,
                      }}
                    >
                      Skip
                    </button>
                    <button
                      onClick={() => handleSubmitAnswer(gap.id)}
                      disabled={!(answers[gap.id]?.trim().length >= 10) || submittingId === gap.id}
                      style={{
                        padding: '8px 16px',
                        background: (answers[gap.id]?.trim().length >= 10) ? theme.accent : theme.border,
                        border: 'none',
                        borderRadius: '6px',
                        color: (answers[gap.id]?.trim().length >= 10) ? '#fff' : theme.subtle,
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: (answers[gap.id]?.trim().length >= 10) ? 'pointer' : 'not-allowed',
                        fontFamily: fonts.sans,
                      }}
                    >
                      {submittingId === gap.id ? 'Saving...' : 'Submit'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </main>

        {/* Footer */}
        <footer style={{
          padding: '16px 40px',
          borderTop: `1px solid ${theme.border}`,
          background: theme.cardBg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <span style={{ fontFamily: fonts.mono, fontSize: '12px', color: theme.subtle }}>
            Session: {sessionAnswered} answered, {sessionSkipped} skipped
          </span>
          <button
            onClick={() => router.push('/documents')}
            style={{
              padding: '10px 20px', background: theme.forest, border: 'none', borderRadius: '8px',
              color: '#fff', fontSize: '13px', fontWeight: 600, cursor: 'pointer', fontFamily: fonts.sans,
            }}
          >
            Done
          </button>
        </footer>
      </div>

      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Merriweather:wght@400;700&family=JetBrains+Mono:wght@400;500&display=swap');
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
