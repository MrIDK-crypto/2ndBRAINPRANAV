'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import { useSyncProgress } from '@/contexts/SyncProgressContext'

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

export default function GlobalSyncIndicator() {
  const { activeSyncs, setEmailWhenDone, removeSync } = useSyncProgress()
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
          const isAwaitingSelection = sync.status === 'awaiting_selection'
          const isActive = !isComplete && !isError && !isAwaitingSelection
          const isExpanded = expandedSync === sync.syncId

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
                  border: '1px solid #E5E7EB'
                }}
              >
                {/* Header */}
                <div style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #E5E7EB',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Image src={config.logo} alt={config.name} width={24} height={24} style={{ borderRadius: 4 }} />
                    <span style={{ fontWeight: 600, fontSize: 14 }}>
                      {isComplete ? `${config.name} Synced` : isError ? `${config.name} Failed` : isAwaitingSelection ? `${config.name} — Select Documents` : `Syncing ${config.name}`}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => setExpandedSync(null)}
                      style={{
                        width: 28, height: 28, borderRadius: 6,
                        border: '1px solid #E5E7EB', background: '#fff',
                        cursor: 'pointer', fontSize: 12
                      }}
                    >
                      _
                    </button>
                    {(isComplete || isError) && (
                      <button
                        onClick={() => removeSync(sync.syncId)}
                        style={{
                          width: 28, height: 28, borderRadius: 6,
                          border: '1px solid #E5E7EB', background: '#fff',
                          cursor: 'pointer', fontSize: 14
                        }}
                      >
                        x
                      </button>
                    )}
                  </div>
                </div>

                {/* Content */}
                <div style={{ padding: 16 }}>
                  {/* Status */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    marginBottom: 12
                  }}>
                    {isActive && (
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%',
                        border: '2px solid #E5E7EB', borderTopColor: '#2563EB',
                        animation: 'spin 0.8s linear infinite'
                      }} />
                    )}
                    {isAwaitingSelection && <span style={{ color: '#C9A598', fontSize: 16 }}>&#9998;</span>}
                    {isComplete && <span style={{ color: '#3B82F6', fontSize: 16 }}>&#10003;</span>}
                    {isError && <span style={{ color: '#64748B', fontSize: 16 }}>&#10005;</span>}
                    <span style={{ fontSize: 13, color: '#374151' }}>
                      {isAwaitingSelection ? 'Select documents to import' : sync.stage}
                    </span>
                  </div>

                  {/* Progress bar */}
                  {isActive && (
                    <div style={{
                      height: 6,
                      background: '#E5E7EB',
                      borderRadius: 3,
                      overflow: 'hidden',
                      marginBottom: 12
                    }}>
                      <div style={{
                        height: '100%',
                        width: sync.totalItems > 0 ? `${sync.percentComplete}%` : '30%',
                        background: '#2563EB',
                        borderRadius: 3,
                        transition: 'width 0.3s',
                        animation: sync.totalItems === 0 ? 'pulse 1.5s ease-in-out infinite' : 'none'
                      }} />
                    </div>
                  )}


                  {/* Email checkbox */}
                  {isActive && (
                    <label style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 13,
                      cursor: 'pointer',
                      paddingTop: 12,
                      borderTop: '1px solid #E5E7EB'
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
                      background: '#F1F5F9',
                      borderRadius: 6,
                      fontSize: 12,
                      color: '#64748B'
                    }}>
                      {sync.errorMessage}
                    </div>
                  )}
                </div>
              </div>
            )
          }

          // Minimized pill
          return (
            <div
              key={sync.syncId}
              onClick={() => setExpandedSync(sync.syncId)}
              style={{
                background: isComplete ? '#3B82F6' : isError ? '#64748B' : isAwaitingSelection ? '#C9A598' : '#fff',
                color: isComplete || isError || isAwaitingSelection ? '#fff' : '#111827',
                padding: '10px 16px',
                borderRadius: 10,
                boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 13,
                fontWeight: 500,
                border: isComplete || isError || isAwaitingSelection ? 'none' : '1px solid #E5E7EB'
              }}
            >
              {isActive && (
                <div style={{
                  width: 14, height: 14, borderRadius: '50%',
                  border: '2px solid #E5E7EB', borderTopColor: '#2563EB',
                  animation: 'spin 1s linear infinite'
                }} />
              )}
              {isAwaitingSelection && <span>&#9998;</span>}
              {isComplete && <span>&#10003;</span>}
              {isError && <span>&#10005;</span>}
              <Image src={config.logo} alt={config.name} width={16} height={16} style={{ borderRadius: 3 }} />
              <span>{config.name}</span>
              {isActive && sync.totalItems > 0 && (
                <span style={{
                  background: 'rgba(0,0,0,0.08)',
                  padding: '2px 6px',
                  borderRadius: 4,
                  fontSize: 11
                }}>
                  {sync.percentComplete}%
                </span>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
