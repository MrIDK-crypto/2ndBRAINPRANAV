'use client'

import React, { useState, useEffect, useRef } from 'react'
import Image from 'next/image'

interface SyncProgressModalProps {
  syncId: string
  connectorType: string
  onClose: () => void
  onCloseWhileActive?: () => void  // Called when user closes modal while sync is still running
  initialEstimatedSeconds?: number  // From prescan, shown until we can calculate from rate
}

interface ProgressData {
  sync_id: string
  connector_type: string
  status: 'connecting' | 'syncing' | 'parsing' | 'embedding' | 'complete' | 'error'
  stage: string
  total_items: number
  processed_items: number
  failed_items: number
  current_item?: string
  error_message?: string
  percent_complete: number
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5003/api'

// All integrations use actual logo images
const connectorConfig: Record<string, { logo: string; name: string }> = {
  github: { logo: '/github.png', name: 'GitHub' },
  gmail: { logo: '/gmail.png', name: 'Gmail' },
  slack: { logo: '/slack.png', name: 'Slack' },
  box: { logo: '/box.png', name: 'Box' },
  onedrive: { logo: '/docs.png', name: 'OneDrive' },
  googledrive: { logo: '/gdrive.png', name: 'Google Drive' },
  gdrive: { logo: '/gdrive.png', name: 'Google Drive' },
  notion: { logo: '/notion.png', name: 'Notion' },
  zotero: { logo: '/pubmed.png', name: 'Zotero' },
  outlook: { logo: '/outlook.png', name: 'Outlook' },
  excel: { logo: '/excel.png', name: 'Excel' },
  powerpoint: { logo: '/powerpoint.png', name: 'PowerPoint' },
  gdocs: { logo: '/gdocs.png', name: 'Google Docs' },
  gsheets: { logo: '/gsheets.png', name: 'Google Sheets' },
  gslides: { logo: '/gslides.png', name: 'Google Slides' },
  webscraper: { logo: '/docs.png', name: 'Website' },
  default: { logo: '/owl.png', name: 'Integration' }
}

// Consistent color palette - Blue/Grey Theme
const colors = {
  primary: '#2563EB',
  primaryLight: '#EFF6FF',
  primaryBorder: '#BFDBFE',
  success: '#3B82F6',       // Blue for success
  successLight: '#EFF6FF',
  successBorder: '#BFDBFE',
  error: '#64748B',         // Slate grey for errors
  errorLight: '#F1F5F9',
  errorBorder: '#CBD5E1',
  gray: '#6B7280',
  grayLight: '#F9FAFB',
  grayBorder: '#E5E7EB',
  text: '#111827',
  textMuted: '#6B7280'
}

export default function SyncProgressModal({ syncId, connectorType, onClose, onCloseWhileActive, initialEstimatedSeconds }: SyncProgressModalProps) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [isMinimized, setIsMinimized] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [startTime] = useState(Date.now())
  const [emailWhenDone, setEmailWhenDone] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Use refs to avoid stale closure in useEffect callbacks
  const emailWhenDoneRef = useRef(emailWhenDone)
  const emailSentRef = useRef(emailSent)

  // Keep refs in sync with state
  useEffect(() => {
    emailWhenDoneRef.current = emailWhenDone
  }, [emailWhenDone])

  useEffect(() => {
    emailSentRef.current = emailSent
  }, [emailSent])

  const config = connectorConfig[connectorType] || connectorConfig.default

  // Send email notification when sync completes
  // Uses refs to avoid stale closure issues
  const sendEmailNotification = async () => {
    console.log('[SyncProgress] sendEmailNotification called, emailWhenDone:', emailWhenDoneRef.current, 'emailSent:', emailSentRef.current)

    if (!emailWhenDoneRef.current || emailSentRef.current) {
      console.log('[SyncProgress] Skipping email notification - emailWhenDone:', emailWhenDoneRef.current, 'emailSent:', emailSentRef.current)
      return
    }

    try {
      const token = localStorage.getItem('accessToken')
      if (!token) {
        console.log('[SyncProgress] No token found, skipping email')
        return
      }

      console.log('[SyncProgress] Sending email notification request to:', `${API_BASE}/sync-progress/${syncId}/notify`)
      const response = await fetch(`${API_BASE}/sync-progress/${syncId}/notify`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      const data = await response.json()
      console.log('[SyncProgress] Email notification response:', response.status, data)

      if (response.ok && data.success) {
        console.log('[SyncProgress] Email notification sent successfully')
        setEmailSent(true)
        emailSentRef.current = true
      } else {
        console.error('[SyncProgress] Email notification failed:', data.error || 'Unknown error')
      }
    } catch (err) {
      console.error('[SyncProgress] Failed to send email notification:', err)
    }
  }

  // Timer
  useEffect(() => {
    if (progress?.status === 'complete' || progress?.status === 'error') return
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [startTime, progress?.status])

  // SSE connection with polling fallback for multi-worker deployments
  useEffect(() => {
    const token = localStorage.getItem('accessToken')
    if (!token) return

    let pollingInterval: NodeJS.Timeout | null = null
    let lastUpdateTime = Date.now()
    let sseConnected = false

    // Polling fallback function
    const pollProgress = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/integrations/${connectorType}/sync/status`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        if (response.ok) {
          const data = await response.json()
          if (data.success && data.status) {
            // Map status endpoint format to SSE format
            const mappedProgress: ProgressData = {
              sync_id: syncId,
              connector_type: connectorType,
              status: data.status.status === 'completed' ? 'complete' : data.status.status,
              stage: data.status.current_file || data.status.status || 'Processing...',
              total_items: data.status.documents_found || 0,
              processed_items: data.status.documents_parsed || 0,
              failed_items: 0,
              current_item: data.status.current_file,
              percent_complete: data.status.progress || 0
            }
            setProgress(mappedProgress)
            lastUpdateTime = Date.now()

            // Stop polling on complete
            if (data.status.status === 'completed' || data.status.status === 'error') {
              if (pollingInterval) clearInterval(pollingInterval)
              if (data.status.status === 'completed') {
                // Send email notification if enabled (uses refs internally)
                sendEmailNotification()
                setTimeout(() => onClose(), 3000)
              }
            }
          }
        }
      } catch (err) {
        console.error('[SyncProgress] Polling error:', err)
      }
    }

    const es = new EventSource(
      `${API_BASE}/sync-progress/${syncId}/stream?token=${encodeURIComponent(token)}`,
      { withCredentials: true }
    )

    const handle = (e: MessageEvent) => {
      if (!e.data || e.data === 'undefined' || e.data === 'null') return
      try {
        setProgress(JSON.parse(e.data))
        lastUpdateTime = Date.now()
        sseConnected = true
      } catch (parseErr) {
        console.error('[SyncProgress] Parse error:', parseErr)
      }
    }
    es.addEventListener('current_state', handle)
    es.addEventListener('started', handle)
    es.addEventListener('progress', handle)
    es.addEventListener('complete', (e: MessageEvent) => {
      if (!e.data || e.data === 'undefined' || e.data === 'null') return
      try {
        setProgress(JSON.parse(e.data))
      } catch {}
      if (pollingInterval) clearInterval(pollingInterval)
      // Send email notification if enabled (uses refs internally)
      sendEmailNotification()
      setTimeout(() => { es.close(); onClose() }, 3000)
    })
    es.addEventListener('error', (e: MessageEvent) => {
      try { if (e.data && e.data !== 'undefined') setProgress(JSON.parse(e.data)) } catch {}
    })
    es.addEventListener('connected', () => {
      sseConnected = true
      console.log('[SyncProgress] SSE connected')
    })

    eventSourceRef.current = es

    // Start polling fallback after 3 seconds if SSE hasn't provided updates
    const checkSSE = setTimeout(() => {
      if (!sseConnected || Date.now() - lastUpdateTime > 3000) {
        console.log('[SyncProgress] SSE inactive, starting polling fallback')
        pollProgress() // Initial poll
        pollingInterval = setInterval(pollProgress, 2000) // Poll every 2 seconds
      }
    }, 3000)

    return () => {
      es.close()
      clearTimeout(checkSSE)
      if (pollingInterval) clearInterval(pollingInterval)
    }
  }, [syncId, connectorType, onClose])

  const isComplete = progress?.status === 'complete'
  const isError = progress?.status === 'error'
  const isActive = !isComplete && !isError
  // Calculate percentage, but show minimum 10% when actively syncing to indicate activity
  const rawPct = progress?.total_items ? Math.round((progress.processed_items / progress.total_items) * 100) : 0
  // During early phases (syncing/analyzing), show at least 10% so it doesn't look stuck
  const isAnalyzing = progress?.status === 'syncing' && progress?.stage?.toLowerCase().includes('analyz')
  const pct = isAnalyzing && rawPct === 0 ? 10 : rawPct

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    return m > 0 ? `${m}m ${s % 60}s` : `${s}s`
  }

  // Calculate estimated remaining time based on progress rate
  const getEstimatedRemaining = () => {
    if (!isActive) return null

    // Prefer initial estimate from prescan until we have significant progress (>20%)
    // This avoids wild fluctuations early in the sync when LLM analysis skews the rate
    if (progress) {
      const { processed_items, total_items } = progress
      const progressPercent = total_items > 0 ? (processed_items / total_items) * 100 : 0

      // Only calculate from rate after 20% progress AND at least 30 seconds elapsed
      // This gives us more stable data after the initial LLM analysis phase
      if (progressPercent > 20 && elapsed > 30 && processed_items > 0) {
        const rate = processed_items / elapsed
        if (rate > 0) {
          const remainingItems = total_items - processed_items
          const remainingSeconds = Math.ceil(remainingItems / rate)
          // Cap at reasonable maximum (don't show > 30 minutes)
          return Math.min(remainingSeconds, 1800)
        }
      }
    }

    // Use initial estimate from prescan (more reliable early on)
    if (initialEstimatedSeconds && initialEstimatedSeconds > elapsed) {
      return initialEstimatedSeconds - elapsed
    }

    // If elapsed exceeds initial estimate, show small buffer
    if (initialEstimatedSeconds) {
      return Math.max(30, initialEstimatedSeconds - elapsed + 60) // At least 30s, or estimate + 1min buffer
    }

    return null
  }

  const remainingTime = getEstimatedRemaining()

  const getStatusText = () => {
    if (!progress) return 'Connecting...'
    // If stage contains file count info (from pre-scan), show it
    if (progress.stage && progress.stage.includes('Found')) {
      return progress.stage
    }
    switch (progress.status) {
      case 'connecting': return 'Connecting...'
      case 'syncing': return progress.stage || 'Fetching data...'
      case 'parsing': return progress.stage || 'Processing files...'
      case 'embedding': return progress.stage || 'Building index...'
      case 'complete': return 'Sync complete!'
      case 'error': return 'Sync failed'
      default: return progress.stage || 'Processing...'
    }
  }

  // Minimized floating pill
  if (isMinimized) {
    return (
      <>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        <div
          onClick={() => setIsMinimized(false)}
          style={{
            position: 'fixed', bottom: 24, right: 24,
            background: isComplete ? colors.success : isError ? colors.error : '#fff',
            color: isComplete || isError ? '#fff' : colors.text,
            padding: '12px 20px', borderRadius: 12,
            boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
            fontSize: 14, fontWeight: 500, zIndex: 9999,
            border: isComplete || isError ? 'none' : `1px solid ${colors.grayBorder}`
          }}
        >
          {isActive && (
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              border: `2px solid ${colors.grayBorder}`, borderTopColor: colors.primary,
              animation: 'spin 1s linear infinite'
            }} />
          )}
          {isComplete && '✓'} {isError && '✕'}
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Image src={config.logo} alt={config.name} width={16} height={16} style={{ borderRadius: 4 }} />
            {config.name}
          </span>
          {isActive && progress?.total_items ? (
            <span style={{ background: 'rgba(0,0,0,0.08)', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>{pct}%</span>
          ) : null}
        </div>
      </>
    )
  }

  return (
    <>
      <style>{`
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
      `}</style>

      <div style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 9999
      }}>
        <div style={{
          background: '#fff', borderRadius: 16,
          width: 420, maxWidth: '90vw',
          boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
          overflow: 'hidden'
        }}>
          {/* Blue top accent */}
          <div style={{
            height: 4,
            background: isComplete ? colors.success : isError ? colors.error : colors.primary
          }} />

          {/* Header */}
          <div style={{ padding: '20px 24px', borderBottom: `1px solid ${colors.grayBorder}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 12,
                  background: isComplete ? colors.successLight : isError ? colors.errorLight : colors.primaryLight,
                  border: `1px solid ${isComplete ? colors.successBorder : isError ? colors.errorBorder : colors.primaryBorder}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 24
                }}>
                  {isComplete ? '✓' : isError ? '✕' : (
                    <Image src={config.logo} alt={config.name} width={28} height={28} style={{ borderRadius: 4 }} />
                  )}
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: colors.text }}>
                    {isComplete ? `${config.name} Synced` : isError ? `${config.name} Failed` : `Syncing ${config.name}`}
                  </h2>
                  <p style={{ margin: '2px 0 0', fontSize: 13, color: colors.textMuted }}>
                    {isActive ? 'Runs in background if you close' : isComplete ? 'All items processed' : 'Something went wrong'}
                  </p>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {isActive && (
                  <button onClick={() => setIsMinimized(true)} style={btnStyle} title="Minimize">↓</button>
                )}
                <button onClick={() => {
                  if (isActive && onCloseWhileActive) {
                    onCloseWhileActive()
                  }
                  onClose()
                }} style={btnStyle} title="Close">×</button>
              </div>
            </div>
          </div>

          {/* Content */}
          <div style={{ padding: '20px 24px' }}>
            {/* Status */}
            <div style={{
              padding: 16, borderRadius: 12, marginBottom: 16,
              background: isComplete ? colors.successLight : isError ? colors.errorLight : colors.grayLight,
              border: `1px solid ${isComplete ? colors.successBorder : isError ? colors.errorBorder : colors.grayBorder}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: isActive ? 12 : 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {isActive && (
                    <div style={{
                      width: 20, height: 20, borderRadius: '50%',
                      border: `2px solid ${colors.grayBorder}`, borderTopColor: colors.primary,
                      animation: 'spin 0.8s linear infinite'
                    }} />
                  )}
                  {isComplete && <span style={{ color: colors.success, fontSize: 20 }}>✓</span>}
                  {isError && <span style={{ color: colors.error, fontSize: 20 }}>✕</span>}
                  <span style={{
                    fontSize: 14, fontWeight: 600,
                    color: isComplete ? colors.success : isError ? colors.error : colors.text
                  }}>
                    {getStatusText()}
                  </span>
                </div>
                {isActive && (progress?.total_items ?? 0) > 0 && (
                  <span style={{ fontSize: 14, fontWeight: 600, color: colors.primary }}>{pct}%</span>
                )}
              </div>

              {/* Progress bar */}
              {isActive && (
                <div style={{ height: 6, background: colors.grayBorder, borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: progress?.total_items ? `${pct}%` : '30%',
                    background: colors.primary,
                    borderRadius: 3,
                    transition: 'width 0.3s',
                    // Pulse animation when analyzing (0% real progress) or when no total_items
                    animation: (!progress?.total_items || isAnalyzing) ? 'pulse 1.5s ease-in-out infinite' : 'none'
                  }} />
                </div>
              )}

              {/* Current item */}
              {isActive && progress?.current_item && (
                <p style={{
                  fontSize: 12, color: colors.textMuted, marginTop: 10,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                }}>
                  {progress.current_item}
                </p>
              )}
            </div>

            {/* Stats - all using blue theme */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              <StatBox value={progress?.total_items || 0} label="Found" color={colors.primary} bgColor={colors.primaryLight} borderColor={colors.primaryBorder} />
              <StatBox value={progress?.processed_items || 0} label="Done" color={colors.success} bgColor={colors.successLight} borderColor={colors.successBorder} />
              <StatBox
                value={progress?.failed_items || 0}
                label="Failed"
                color={(progress?.failed_items || 0) > 0 ? colors.error : colors.gray}
                bgColor={(progress?.failed_items || 0) > 0 ? colors.errorLight : colors.grayLight}
                borderColor={(progress?.failed_items || 0) > 0 ? colors.errorBorder : colors.grayBorder}
              />
            </div>

            {/* Error message */}
            {progress?.error_message && (
              <div style={{
                marginTop: 16, padding: 12, borderRadius: 10,
                background: colors.errorLight, border: `1px solid ${colors.errorBorder}`
              }}>
                <p style={{ margin: 0, fontSize: 13, color: colors.error }}>{progress.error_message}</p>
              </div>
            )}

            {/* Email me when done checkbox */}
            {isActive && (
              <div style={{
                marginTop: 16, paddingTop: 16, borderTop: `1px solid ${colors.grayBorder}`,
              }}>
                <label style={{
                  display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
                  fontSize: 13, color: colors.text
                }}>
                  <input
                    type="checkbox"
                    checked={emailWhenDone}
                    onChange={(e) => setEmailWhenDone(e.target.checked)}
                    style={{ width: 16, height: 16, cursor: 'pointer' }}
                  />
                  <span>Email me when sync completes</span>
                </label>
              </div>
            )}

            {/* Email sent confirmation */}
            {emailSent && (
              <div style={{
                marginTop: 12, padding: '8px 12px', borderRadius: 8,
                background: colors.successLight, border: `1px solid ${colors.successBorder}`,
                fontSize: 13, color: colors.success, display: 'flex', alignItems: 'center', gap: 8
              }}>
                <span>✓</span>
                <span>Email notification sent</span>
              </div>
            )}

            {/* Footer */}
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginTop: 16, paddingTop: 16, borderTop: `1px solid ${colors.grayBorder}`,
              fontSize: 13, color: colors.textMuted
            }}>
              <span>{isComplete ? 'Completed' : isError ? 'Failed' : 'Sync continues in background'}</span>
              <div style={{ display: 'flex', gap: 16 }}>
                {isActive && remainingTime !== null && (
                  <span style={{ color: colors.primary, fontWeight: 500 }}>
                    ~{formatTime(remainingTime)} left
                  </span>
                )}
                <span>⏱ {formatTime(elapsed)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

const btnStyle: React.CSSProperties = {
  width: 32, height: 32, borderRadius: 8,
  border: '1px solid #E5E7EB', background: '#fff',
  cursor: 'pointer', fontSize: 16, color: '#6B7280',
  display: 'flex', alignItems: 'center', justifyContent: 'center'
}

function StatBox({ value, label, color, bgColor, borderColor }: {
  value: number; label: string; color: string; bgColor: string; borderColor: string
}) {
  return (
    <div style={{
      padding: '14px 8px', borderRadius: 10, textAlign: 'center',
      background: bgColor, border: `1px solid ${borderColor}`
    }}>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color, fontWeight: 600, marginTop: 2, textTransform: 'uppercase' }}>{label}</div>
    </div>
  )
}
