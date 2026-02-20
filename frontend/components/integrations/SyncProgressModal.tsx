'use client'

import React, { useState, useEffect, useRef } from 'react'
import Image from 'next/image'

interface SyncProgressModalProps {
  syncId: string
  connectorType: string
  onClose: () => void
  onCloseWhileActive?: () => void
  initialEstimatedSeconds?: number
}

interface ProgressData {
  sync_id: string
  connector_type: string
  status: 'connecting' | 'fetching' | 'syncing' | 'saving' | 'extracting' | 'embedding' | 'parsing' | 'complete' | 'error'
  stage: string
  total_items: number
  processed_items: number
  failed_items: number
  current_item?: string
  error_message?: string
  overall_percent: number
  percent_complete: number
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5006/api'

// All integrations use actual logo images
const connectorConfig: Record<string, { logo: string; name: string }> = {
  github: { logo: '/github.png', name: 'GitHub' },
  gmail: { logo: '/gmail.png', name: 'Gmail' },
  slack: { logo: '/slack.png', name: 'Slack' },
  box: { logo: '/box.png', name: 'Box' },
  onedrive: { logo: '/microsoft365.png', name: 'OneDrive' },
  googledrive: { logo: '/gdrive.png', name: 'Google Drive' },
  gdrive: { logo: '/gdrive.png', name: 'Google Drive' },
  notion: { logo: '/notion.png', name: 'Notion' },
  zotero: { logo: '/zotero.webp', name: 'Zotero' },
  outlook: { logo: '/outlook.png', name: 'Outlook' },
  excel: { logo: '/excel.png', name: 'Excel' },
  powerpoint: { logo: '/powerpoint.png', name: 'PowerPoint' },
  gdocs: { logo: '/gdocs.png', name: 'Google Docs' },
  gsheets: { logo: '/gsheets.png', name: 'Google Sheets' },
  gslides: { logo: '/gslides.png', name: 'Google Slides' },
  webscraper: { logo: '/website-builder.png', name: 'Website' },
  firecrawl: { logo: '/website-builder.png', name: 'Website' },
  quartzy: { logo: '/quartzy.png', name: 'Quartzy' },
  default: { logo: '/owl.png', name: 'Integration' }
}

// Warm Coral theme (matches app-wide palette)
const colors = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  primaryBorder: '#E8D5CE',
  success: '#9CB896',
  successLight: '#F0F7EE',
  successBorder: '#C8DCC3',
  error: '#B87070',
  errorLight: '#FBF0F0',
  errorBorder: '#E0B8B8',
  gray: '#6B6B6B',
  grayLight: '#FAF9F7',
  grayBorder: '#F0EEEC',
  text: '#2D2D2D',
  textMuted: '#6B6B6B'
}

export default function SyncProgressModal({ syncId, connectorType, onClose, onCloseWhileActive, initialEstimatedSeconds }: SyncProgressModalProps) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [isMinimized, setIsMinimized] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [startTime] = useState(Date.now())
  const [emailWhenDone, setEmailWhenDone] = useState(false)
  const [emailSubscribed, setEmailSubscribed] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  const config = connectorConfig[connectorType] || connectorConfig.default

  // Subscribe for server-side email notification
  const subscribeEmail = async () => {
    try {
      const token = localStorage.getItem('accessToken')
      if (!token) return

      const response = await fetch(`${API_BASE}/sync-progress/${syncId}/subscribe-email`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      const data = await response.json()
      if (response.ok && data.success) {
        setEmailSubscribed(true)
        console.log('[SyncProgress] Email subscription registered server-side')
      } else {
        console.error('[SyncProgress] Email subscription failed:', data.error)
      }
    } catch (err) {
      console.error('[SyncProgress] Failed to subscribe email:', err)
    }
  }

  // Handle email checkbox toggle
  const handleEmailToggle = (checked: boolean) => {
    setEmailWhenDone(checked)
    if (checked && !emailSubscribed) {
      subscribeEmail()
    }
  }

  // Timer
  useEffect(() => {
    if (progress?.status === 'complete' || progress?.status === 'error') return
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [startTime, progress?.status])

  // SSE connection with polling fallback
  useEffect(() => {
    const token = localStorage.getItem('accessToken')
    if (!token) return

    let pollingInterval: NodeJS.Timeout | null = null
    let lastUpdateTime = Date.now()
    let sseConnected = false

    // Polling fallback
    const pollProgress = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/integrations/${connectorType}/sync/status`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        if (response.ok) {
          const data = await response.json()
          if (data.success && data.status) {
            const mappedProgress: ProgressData = {
              sync_id: syncId,
              connector_type: connectorType,
              status: data.status.status === 'completed' ? 'complete' : data.status.status,
              stage: data.status.current_file || data.status.status || 'Processing...',
              total_items: data.status.documents_found || 0,
              processed_items: data.status.documents_parsed || 0,
              failed_items: 0,
              current_item: data.status.current_file,
              overall_percent: data.status.overall_percent ?? data.status.progress ?? 0,
              percent_complete: data.status.overall_percent ?? data.status.progress ?? 0
            }
            setProgress(mappedProgress)
            lastUpdateTime = Date.now()

            if (data.status.status === 'completed' || data.status.status === 'complete' || data.status.status === 'error') {
              if (pollingInterval) clearInterval(pollingInterval)
              if (data.status.status !== 'error') {
                setTimeout(() => onCloseRef.current(), 3000)
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
      // Email notification is now handled server-side (no client-side call needed)
      setTimeout(() => { es.close(); onCloseRef.current() }, 3000)
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
        pollProgress()
        pollingInterval = setInterval(pollProgress, 2000)
      }
    }, 3000)

    return () => {
      es.close()
      clearTimeout(checkSSE)
      if (pollingInterval) clearInterval(pollingInterval)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncId, connectorType])

  const isComplete = progress?.status === 'complete'
  const isError = progress?.status === 'error'
  const isActive = !isComplete && !isError

  // Use server-calculated percentage directly (accurate, phase-based)
  const pct = Math.round(progress?.overall_percent ?? progress?.percent_complete ?? 0)

  // Determine if we're in an indeterminate phase (fetch - no item count yet)
  const isFetching = isActive && (!progress || progress.status === 'connecting' || progress.status === 'fetching' || progress.status === 'syncing')

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    return m > 0 ? `${m}m ${s % 60}s` : `${s}s`
  }

  // Estimated remaining based on progress rate
  const getEstimatedRemaining = () => {
    if (!isActive || pct <= 0) return null

    // Calculate from overall percent rate
    if (pct > 5 && elapsed > 10) {
      const percentPerSec = pct / elapsed
      if (percentPerSec > 0) {
        const remainingPercent = 100 - pct
        const remainingSeconds = Math.ceil(remainingPercent / percentPerSec)
        return Math.min(remainingSeconds, 1800)
      }
    }

    if (initialEstimatedSeconds && initialEstimatedSeconds > elapsed) {
      return initialEstimatedSeconds - elapsed
    }

    return null
  }

  const remainingTime = getEstimatedRemaining()

  const getStatusText = () => {
    if (!progress) return 'Connecting...'
    if (progress.stage && progress.stage.includes('Found')) return progress.stage
    switch (progress.status) {
      case 'connecting': return 'Connecting...'
      case 'fetching':
      case 'syncing': return progress.stage || 'Fetching data...'
      case 'saving': return progress.stage || 'Saving documents...'
      case 'extracting': return progress.stage || 'Extracting summaries...'
      case 'embedding': return progress.stage || 'Embedding documents...'
      case 'parsing': return progress.stage || 'Processing files...'
      case 'complete': return 'Sync complete!'
      case 'error': return 'Sync failed'
      default: return progress.stage || 'Processing...'
    }
  }

  // Auto-dismiss minimized pill when sync completes
  const [pillFading, setPillFading] = useState(false)
  useEffect(() => {
    if (isMinimized && (isComplete || pct >= 100)) {
      const timer = setTimeout(() => {
        setPillFading(true)
        setTimeout(() => onCloseRef.current(), 500)
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [isMinimized, isComplete, pct])

  // Minimized floating pill
  if (isMinimized) {
    const pillDone = isComplete || pct >= 100
    return (
      <>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        <div
          onClick={() => setIsMinimized(false)}
          style={{
            position: 'fixed', bottom: 24, right: 24,
            background: pillDone ? colors.success : isError ? colors.error : '#fff',
            color: pillDone || isError ? '#fff' : colors.text,
            padding: '12px 20px', borderRadius: 12,
            boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
            fontSize: 14, fontWeight: 500, zIndex: 9999,
            border: pillDone || isError ? 'none' : `1px solid ${colors.grayBorder}`,
            opacity: pillFading ? 0 : 1,
            transition: 'opacity 0.5s ease-out'
          }}
        >
          {!pillDone && !isError && (
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              border: `2px solid ${colors.grayBorder}`, borderTopColor: colors.primary,
              animation: 'spin 1s linear infinite'
            }} />
          )}
          {pillDone && <span style={{ fontSize: 16 }}>✓</span>}
          {isError && <span style={{ fontSize: 16 }}>✕</span>}
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Image src={config.logo} alt={config.name} width={16} height={16} style={{ borderRadius: 4 }} />
            {config.name}
          </span>
          {pillDone ? (
            <span style={{ background: 'rgba(255,255,255,0.2)', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>Done</span>
          ) : isActive && pct > 0 ? (
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
        @keyframes indeterminate{
          0%{transform:translateX(-100%)}
          100%{transform:translateX(200%)}
        }
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
          {/* Top accent bar */}
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
                {isActive && pct > 0 && (
                  <span style={{ fontSize: 14, fontWeight: 600, color: colors.primary }}>{pct}%</span>
                )}
              </div>

              {/* Progress bar */}
              {isActive && (
                <div style={{ height: 6, background: colors.grayBorder, borderRadius: 3, overflow: 'hidden' }}>
                  {isFetching ? (
                    /* Indeterminate sliding bar during fetch phase */
                    <div style={{
                      height: '100%',
                      width: '40%',
                      background: colors.primary,
                      borderRadius: 3,
                      opacity: 0.6,
                      animation: 'indeterminate 1.5s ease-in-out infinite'
                    }} />
                  ) : (
                    /* Determinate progress bar during processing phases */
                    <div style={{
                      height: '100%',
                      width: `${pct}%`,
                      background: colors.primary,
                      borderRadius: 3,
                      transition: 'width 0.5s ease'
                    }} />
                  )}
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
                    onChange={(e) => handleEmailToggle(e.target.checked)}
                    style={{ width: 16, height: 16, cursor: 'pointer' }}
                  />
                  <span>Email me when sync completes</span>
                </label>
                {emailSubscribed && (
                  <p style={{ margin: '6px 0 0 26px', fontSize: 12, color: colors.success }}>
                    ✓ You will be emailed when this sync finishes
                  </p>
                )}
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
                <span>{formatTime(elapsed)}</span>
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

