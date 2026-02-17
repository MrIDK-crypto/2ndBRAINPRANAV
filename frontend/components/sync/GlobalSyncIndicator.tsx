'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import { useSyncProgress } from '@/contexts/SyncProgressContext'

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

const colors = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  success: '#9CB896',
  successLight: '#F0F7EE',
  error: '#B87070',
  errorLight: '#FBF0F0',
  text: '#2D2D2D',
  textMuted: '#6B6B6B',
  grayBorder: '#F0EEEC',
  grayLight: '#FAF9F7',
}

export default function GlobalSyncIndicator() {
  const { activeSyncs, dismissSync, setEmailWhenDone } = useSyncProgress()
  const [expandedSync, setExpandedSync] = useState<string | null>(null)

  if (activeSyncs.size === 0) return null

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
        @keyframes pulse { 0%, 100% { opacity: 1 } 50% { opacity: 0.5 } }
      `}</style>

      <div style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 12
      }}>
        {Array.from(activeSyncs.values()).map(sync => {
          const config = connectorConfig[sync.connectorType] || connectorConfig.default
          const isComplete = sync.status === 'complete' || sync.status === 'completed'
          const isError = sync.status === 'error'
          const isActive = !isComplete && !isError
          const isExpanded = expandedSync === sync.syncId
          const pct = Math.round(sync.percentComplete ?? 0)

          if (isExpanded) {
            return (
              <div
                key={sync.syncId}
                style={{
                  background: '#fff',
                  borderRadius: 12,
                  boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                  width: 320,
                  overflow: 'hidden',
                  border: `1px solid ${colors.grayBorder}`
                }}
              >
                {/* Header */}
                <div style={{
                  padding: '12px 16px',
                  borderBottom: `1px solid ${colors.grayBorder}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Image src={config.logo} alt={config.name} width={24} height={24} style={{ borderRadius: 4 }} />
                    <span style={{ fontWeight: 600, fontSize: 14, color: colors.text }}>
                      {isComplete ? `${config.name} Synced` : isError ? `${config.name} Failed` : `Syncing ${config.name}`}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => setExpandedSync(null)}
                      style={miniBtn}
                    >
                      _
                    </button>
                    {(isComplete || isError) && (
                      <button
                        onClick={() => dismissSync(sync.syncId)}
                        style={miniBtn}
                      >
                        ×
                      </button>
                    )}
                  </div>
                </div>

                {/* Content */}
                <div style={{ padding: 16 }}>
                  {/* Status + phase */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    marginBottom: 12
                  }}>
                    {isActive && (
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%',
                        border: `2px solid ${colors.grayBorder}`, borderTopColor: colors.primary,
                        animation: 'spin 0.8s linear infinite'
                      }} />
                    )}
                    {isComplete && <span style={{ color: colors.success, fontSize: 16 }}>✓</span>}
                    {isError && <span style={{ color: colors.error, fontSize: 16 }}>✕</span>}
                    <span style={{ fontSize: 13, color: colors.text }}>
                      {sync.phaseLabel || sync.stage}
                    </span>
                  </div>

                  {/* Progress bar */}
                  {isActive && (
                    <div style={{
                      height: 6,
                      background: colors.grayBorder,
                      borderRadius: 3,
                      overflow: 'hidden',
                      marginBottom: 12
                    }}>
                      <div style={{
                        height: '100%',
                        width: pct > 0 ? `${pct}%` : '30%',
                        background: colors.primary,
                        borderRadius: 3,
                        transition: 'width 0.3s',
                        animation: pct === 0 ? 'pulse 1.5s ease-in-out infinite' : 'none'
                      }} />
                    </div>
                  )}

                  {/* Stats */}
                  <div style={{
                    display: 'flex',
                    gap: 16,
                    fontSize: 12,
                    color: colors.textMuted,
                    marginBottom: isActive ? 12 : 0
                  }}>
                    {isActive && sync.phaseNumber > 0 && (
                      <span style={{ fontWeight: 600 }}>Step {sync.phaseNumber} of {sync.totalPhases}</span>
                    )}
                    {pct > 0 && <span>{pct}%</span>}
                    <span>Found: {sync.totalItems}</span>
                    <span>Done: {sync.processedItems}</span>
                    {sync.failedItems > 0 && <span>Failed: {sync.failedItems}</span>}
                  </div>

                  {/* Email checkbox */}
                  {isActive && (
                    <label style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 13,
                      cursor: 'pointer',
                      paddingTop: 12,
                      borderTop: `1px solid ${colors.grayBorder}`
                    }}>
                      <input
                        type="checkbox"
                        checked={sync.emailWhenDone}
                        onChange={(e) => setEmailWhenDone(sync.syncId, e.target.checked)}
                        style={{ width: 14, height: 14 }}
                      />
                      Email me when sync completes
                    </label>
                  )}

                  {/* Error message */}
                  {sync.errorMessage && (
                    <div style={{
                      marginTop: 12,
                      padding: 10,
                      background: colors.errorLight,
                      borderRadius: 6,
                      fontSize: 12,
                      color: colors.error
                    }}>
                      {sync.errorMessage}
                    </div>
                  )}
                </div>
              </div>
            )
          }

          // Minimized pill - no auto-removal on completion
          return (
            <div
              key={sync.syncId}
              style={{
                background: isComplete ? colors.success : isError ? colors.error : '#fff',
                color: isComplete || isError ? '#fff' : colors.text,
                padding: '10px 16px',
                borderRadius: 10,
                boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 13,
                fontWeight: 500,
                border: isComplete || isError ? 'none' : `1px solid ${colors.grayBorder}`
              }}
              onClick={() => setExpandedSync(sync.syncId)}
            >
              {isActive && (
                <div style={{
                  width: 14, height: 14, borderRadius: '50%',
                  border: `2px solid ${colors.grayBorder}`, borderTopColor: colors.primary,
                  animation: 'spin 1s linear infinite'
                }} />
              )}
              {isComplete && <span>✓</span>}
              {isError && <span>✕</span>}
              <Image src={config.logo} alt={config.name} width={16} height={16} style={{ borderRadius: 3 }} />
              <span>{config.name}</span>
              {isActive && pct > 0 && (
                <span style={{
                  background: 'rgba(0,0,0,0.08)',
                  padding: '2px 6px',
                  borderRadius: 4,
                  fontSize: 11
                }}>
                  {pct}%
                </span>
              )}
              {isComplete && (
                <span style={{
                  background: 'rgba(255,255,255,0.2)',
                  padding: '2px 6px',
                  borderRadius: 4,
                  fontSize: 11
                }}>
                  Done
                </span>
              )}
              {/* Dismiss button for completed/errored */}
              {(isComplete || isError) && (
                <button
                  onClick={(e) => { e.stopPropagation(); dismissSync(sync.syncId) }}
                  style={{
                    background: 'rgba(255,255,255,0.3)',
                    border: 'none',
                    borderRadius: 4,
                    padding: '0 4px',
                    cursor: 'pointer',
                    color: 'inherit',
                    fontSize: 14,
                    lineHeight: '16px',
                    marginLeft: 4
                  }}
                >
                  ×
                </button>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}

const miniBtn: React.CSSProperties = {
  width: 28, height: 28, borderRadius: 6,
  border: '1px solid #E5E7EB', background: '#fff',
  cursor: 'pointer', fontSize: 12, color: '#6B7280',
  display: 'flex', alignItems: 'center', justifyContent: 'center'
}
