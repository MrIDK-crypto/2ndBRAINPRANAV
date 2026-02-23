'use client'

import React, { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { useSyncProgress } from '@/contexts/SyncProgressContext'
import DocumentSelectionModal, { PendingDoc } from '../integrations/DocumentSelectionModal'

const SELECTION_REQUIRED_CONNECTORS = new Set(['gdrive', 'gdocs', 'gsheets', 'gslides', 'onedrive', 'notion'])

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5006/api'

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
  const { activeSyncs, setEmailWhenDone, removeSync, updateSync } = useSyncProgress()
  const [expandedSync, setExpandedSync] = useState<string | null>(null)

  // Document selection modal state (global — works from any page)
  const [showDocSelectionModal, setShowDocSelectionModal] = useState(false)
  const [pendingDocuments, setPendingDocuments] = useState<PendingDoc[]>([])
  const [pendingSyncId, setPendingSyncId] = useState<string | null>(null)
  const [pendingConnectorType, setPendingConnectorType] = useState<string | null>(null)
  const [isConfirmingSelection, setIsConfirmingSelection] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  // Track which sync IDs we've already shown the modal for (prevent re-opening after close)
  const dismissedSyncsRef = useRef<Set<string>>(new Set())

  // Watch activeSyncs for awaiting_selection status → auto-open document selection modal
  useEffect(() => {
    for (const sync of Array.from(activeSyncs.values())) {
      if (
        sync.status === 'awaiting_selection' &&
        sync.documents &&
        sync.documents.length > 0 &&
        SELECTION_REQUIRED_CONNECTORS.has(sync.connectorType) &&
        !showDocSelectionModal &&
        !dismissedSyncsRef.current.has(sync.syncId)
      ) {
        console.log(`[GlobalSync] Detected awaiting_selection for ${sync.connectorType} (${sync.syncId}), opening selection modal`)
        setPendingDocuments(sync.documents as PendingDoc[])
        setPendingSyncId(sync.syncId)
        setPendingConnectorType(sync.connectorType)
        setConfirmError(null)
        setShowDocSelectionModal(true)
        break
      }
    }
  }, [activeSyncs, showDocSelectionModal])

  // Confirm selected documents for import
  const confirmDocumentSelection = async (selectedIds: string[]) => {
    if (!pendingSyncId || !pendingConnectorType) return
    setIsConfirmingSelection(true)
    setConfirmError(null)
    try {
      const token = localStorage.getItem('accessToken')
      const response = await fetch(
        `${API_BASE}/integrations/${pendingConnectorType}/sync/confirm`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ sync_id: pendingSyncId, selected_document_ids: selectedIds })
        }
      )
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.error || `Server error ${response.status}`)
      }
      console.log(`[GlobalSync] Confirmed ${selectedIds.length} docs for ${pendingConnectorType}`)
      // Transition sync to extracting so the pill shows progress instead of "Select Documents"
      updateSync(pendingSyncId, {
        status: 'extracting' as any,
        stage: 'Extracting document summaries...',
        percentComplete: 33,
        documents: undefined
      })
      dismissedSyncsRef.current.add(pendingSyncId)
      setShowDocSelectionModal(false)
    } catch (err: any) {
      console.error('[GlobalSync] Confirm selection error:', err)
      // On "no pending documents" error (404), close modal — docs are stale
      if (err.message?.includes('No pending documents') || err.message?.includes('404')) {
        console.log('[GlobalSync] No pending docs — closing stale modal')
        if (pendingSyncId) {
          dismissedSyncsRef.current.add(pendingSyncId)
          removeSync(pendingSyncId)
        }
        setShowDocSelectionModal(false)
        setConfirmError('Documents not found — they may have been cleaned. Please re-sync.')
      } else {
        setConfirmError(err.message || 'Failed to confirm selection. Please try again.')
      }
    } finally {
      setIsConfirmingSelection(false)
    }
  }

  // Import all documents (skip selection)
  const importAllDocuments = async () => {
    if (!pendingSyncId || !pendingConnectorType) return
    setIsConfirmingSelection(true)
    setConfirmError(null)
    try {
      const token = localStorage.getItem('accessToken')
      const response = await fetch(
        `${API_BASE}/integrations/${pendingConnectorType}/sync/confirm`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ sync_id: pendingSyncId, selected_document_ids: [] })
        }
      )
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.error || `Server error ${response.status}`)
      }
      console.log(`[GlobalSync] Import all for ${pendingConnectorType}`)
      // Transition sync to extracting so the pill shows progress instead of "Select Documents"
      updateSync(pendingSyncId, {
        status: 'extracting' as any,
        stage: 'Extracting document summaries...',
        percentComplete: 33,
        documents: undefined
      })
      dismissedSyncsRef.current.add(pendingSyncId)
      setShowDocSelectionModal(false)
    } catch (err: any) {
      console.error('[GlobalSync] Import all error:', err)
      // On "no pending documents" error (404), close modal — docs are stale
      if (err.message?.includes('No pending documents') || err.message?.includes('404')) {
        console.log('[GlobalSync] No pending docs — closing stale modal')
        if (pendingSyncId) {
          dismissedSyncsRef.current.add(pendingSyncId)
          removeSync(pendingSyncId)
        }
        setShowDocSelectionModal(false)
        setConfirmError('Documents not found — they may have been cleaned. Please re-sync.')
      } else {
        setConfirmError(err.message || 'Failed to import documents. Please try again.')
      }
    } finally {
      setIsConfirmingSelection(false)
    }
  }

  // Cancel / close modal — mark as dismissed so it doesn't re-open
  const handleCloseModal = () => {
    if (pendingSyncId) {
      dismissedSyncsRef.current.add(pendingSyncId)
    }
    setShowDocSelectionModal(false)
    setConfirmError(null)
  }

  if (activeSyncs.size === 0 && !showDocSelectionModal) return null

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
        @keyframes pulse { 0%, 100% { opacity: 1 } 50% { opacity: 0.5 } }
      `}</style>

      {/* Floating sync indicator pills */}
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

                  {/* Awaiting selection: show button to open modal */}
                  {isAwaitingSelection && sync.documents && sync.documents.length > 0 && (
                    <button
                      onClick={() => {
                        setPendingDocuments(sync.documents as PendingDoc[])
                        setPendingSyncId(sync.syncId)
                        setPendingConnectorType(sync.connectorType)
                        setConfirmError(null)
                        dismissedSyncsRef.current.delete(sync.syncId)
                        setShowDocSelectionModal(true)
                      }}
                      style={{
                        width: '100%',
                        padding: '10px 16px',
                        borderRadius: 8,
                        border: 'none',
                        backgroundColor: '#C9A598',
                        color: '#fff',
                        fontSize: 14,
                        fontWeight: 500,
                        cursor: 'pointer',
                        marginBottom: 8
                      }}
                    >
                      Choose Documents ({sync.documents.length})
                    </button>
                  )}

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

          // Minimized pill — click opens modal directly for awaiting_selection
          return (
            <div
              key={sync.syncId}
              onClick={() => {
                if (isAwaitingSelection && sync.documents && sync.documents.length > 0) {
                  // Open selection modal directly
                  setPendingDocuments(sync.documents as PendingDoc[])
                  setPendingSyncId(sync.syncId)
                  setPendingConnectorType(sync.connectorType)
                  setConfirmError(null)
                  dismissedSyncsRef.current.delete(sync.syncId)
                  setShowDocSelectionModal(true)
                } else {
                  setExpandedSync(sync.syncId)
                }
              }}
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
              {isAwaitingSelection && (
                <span style={{
                  background: 'rgba(255,255,255,0.25)',
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontSize: 11
                }}>
                  Select
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Document Selection Modal (global — renders from any page) */}
      <DocumentSelectionModal
        isOpen={showDocSelectionModal}
        onClose={handleCloseModal}
        onConfirm={confirmDocumentSelection}
        onImportAll={importAllDocuments}
        documents={pendingDocuments}
        connectorName={pendingConnectorType || ''}
        connectorLogo=""
        isConfirming={isConfirmingSelection}
      />

      {/* Error toast for confirm failures */}
      {confirmError && (
        <div style={{
          position: 'fixed',
          top: 24,
          right: 24,
          zIndex: 10001,
          background: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: 8,
          padding: '12px 16px',
          fontSize: 13,
          color: '#991B1B',
          maxWidth: 350,
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <span>{confirmError}</span>
          <button
            onClick={() => setConfirmError(null)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 16, color: '#991B1B', padding: '0 4px'
            }}
          >
            x
          </button>
        </div>
      )}
    </>
  )
}
