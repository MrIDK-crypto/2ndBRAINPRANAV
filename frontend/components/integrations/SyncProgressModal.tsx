'use client'

import React, { useState, useEffect } from 'react'
import Image from 'next/image'
import { useSyncProgress } from '@/contexts/SyncProgressContext'

interface SyncProgressModalProps {
  syncId: string
  connectorType: string
  onClose: () => void
  onCloseWhileActive?: () => void
  initialEstimatedSeconds?: number
}

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

// Phase step definitions
const PHASES = [
  { label: 'Save', number: 1 },
  { label: 'Extract', number: 2 },
  { label: 'Embed', number: 3 },
]

export default function SyncProgressModal({ syncId, connectorType, onClose, onCloseWhileActive, initialEstimatedSeconds }: SyncProgressModalProps) {
  const { activeSyncs, setEmailWhenDone, dismissSync } = useSyncProgress()
  const [elapsed, setElapsed] = useState(0)
  const [startTime] = useState(Date.now())

  const progress = activeSyncs.get(syncId)
  const config = connectorConfig[connectorType] || connectorConfig.default

  // Timer
  useEffect(() => {
    if (progress?.status === 'complete' || progress?.status === 'completed' || progress?.status === 'error') return
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [startTime, progress?.status])

  const isComplete = progress?.status === 'complete' || progress?.status === 'completed'
  const isError = progress?.status === 'error'
  const isActive = !isComplete && !isError

  // Use server-calculated percentage directly
  const pct = Math.round(progress?.percentComplete ?? 0)

  // Determine if we're in an indeterminate phase
  const isFetching = isActive && (!progress || progress.status === 'connecting' || progress.status === 'fetching' || progress.status === 'syncing')

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    return m > 0 ? `${m}m ${s % 60}s` : `${s}s`
  }

  // Estimated remaining
  const getEstimatedRemaining = () => {
    if (!isActive || pct <= 0) return null
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

  const handleClose = () => {
    if (isComplete || isError) {
      dismissSync(syncId)
    } else if (onCloseWhileActive) {
      onCloseWhileActive()
    }
    onClose()
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
              <button onClick={handleClose} style={btnStyle} title="Close">×</button>
            </div>
          </div>

          {/* Content */}
          <div style={{ padding: '20px 24px' }}>
            {/* Phase Step Indicator */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: 0, marginBottom: 20, padding: '0 16px'
            }}>
              {PHASES.map((phase, idx) => {
                const phaseNum = progress?.phaseNumber ?? 0
                const isDone = phaseNum > phase.number || isComplete
                const isCurrent = phaseNum === phase.number && isActive
                const isPending = !isDone && !isCurrent

                return (
                  <React.Fragment key={phase.number}>
                    {/* Connector line before (except first) */}
                    {idx > 0 && (
                      <div style={{
                        flex: 1, height: 2,
                        background: isDone || isCurrent ? colors.primary : colors.grayBorder,
                        transition: 'background 0.3s'
                      }} />
                    )}
                    {/* Circle */}
                    <div style={{
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4
                    }}>
                      <div style={{
                        width: 32, height: 32, borderRadius: '50%',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13, fontWeight: 600,
                        background: isDone ? colors.primary : isCurrent ? colors.primaryLight : colors.grayLight,
                        color: isDone ? '#fff' : isCurrent ? colors.primary : colors.textMuted,
                        border: `2px solid ${isDone ? colors.primary : isCurrent ? colors.primary : colors.grayBorder}`,
                        transition: 'all 0.3s'
                      }}>
                        {isDone ? '✓' : phase.number}
                      </div>
                      <span style={{
                        fontSize: 11, fontWeight: isCurrent ? 600 : 400,
                        color: isDone || isCurrent ? colors.text : colors.textMuted
                      }}>
                        {phase.label}
                      </span>
                    </div>
                  </React.Fragment>
                )
              })}
            </div>

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
                    {progress?.phaseLabel || progress?.stage || 'Connecting...'}
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
                    <div style={{
                      height: '100%', width: '40%',
                      background: colors.primary, borderRadius: 3,
                      opacity: 0.6, animation: 'indeterminate 1.5s ease-in-out infinite'
                    }} />
                  ) : (
                    <div style={{
                      height: '100%', width: `${pct}%`,
                      background: colors.primary, borderRadius: 3,
                      transition: 'width 0.5s ease'
                    }} />
                  )}
                </div>
              )}

              {/* Current item */}
              {isActive && progress?.currentItem && (
                <p style={{
                  fontSize: 12, color: colors.textMuted, marginTop: 10,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                }}>
                  {progress.currentItem}
                </p>
              )}
            </div>

            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              <StatBox value={progress?.totalItems || 0} label="Found" color={colors.primary} bgColor={colors.primaryLight} borderColor={colors.primaryBorder} />
              <StatBox value={progress?.processedItems || 0} label="Done" color={colors.success} bgColor={colors.successLight} borderColor={colors.successBorder} />
              <StatBox
                value={progress?.failedItems || 0}
                label="Failed"
                color={(progress?.failedItems || 0) > 0 ? colors.error : colors.gray}
                bgColor={(progress?.failedItems || 0) > 0 ? colors.errorLight : colors.grayLight}
                borderColor={(progress?.failedItems || 0) > 0 ? colors.errorBorder : colors.grayBorder}
              />
            </div>

            {/* Error message */}
            {progress?.errorMessage && (
              <div style={{
                marginTop: 16, padding: 12, borderRadius: 10,
                background: colors.errorLight, border: `1px solid ${colors.errorBorder}`
              }}>
                <p style={{ margin: 0, fontSize: 13, color: colors.error }}>{progress.errorMessage}</p>
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
                    checked={progress?.emailWhenDone || false}
                    onChange={(e) => setEmailWhenDone(syncId, e.target.checked)}
                    style={{ width: 16, height: 16, cursor: 'pointer' }}
                  />
                  <span>Email me when sync completes</span>
                </label>
                {progress?.emailWhenDone && (
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
              <span>
                {isComplete ? 'Completed' : isError ? 'Failed' : progress?.phaseNumber ? `Step ${progress.phaseNumber} of ${progress.totalPhases}` : 'Connecting...'}
              </span>
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
