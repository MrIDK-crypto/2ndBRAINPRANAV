'use client'

import React, { useState, useEffect, useMemo } from 'react'
import Image from 'next/image'

export interface PendingDoc {
  id: string
  title: string
  source_type: string
  doc_type: string
  size: number | null
  date: string | null
}

interface DocumentSelectionModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (selectedIds: string[]) => void
  onImportAll: () => void
  documents: PendingDoc[]
  connectorName: string
  connectorLogo: string
  isConfirming: boolean
}

const connectorLogos: Record<string, string> = {
  gdrive: '/gdrive.png',
  gdocs: '/gdocs.png',
  gsheets: '/gsheets.png',
  gslides: '/gslides.png',
  onedrive: '/microsoft365.png',
  notion: '/notion.png',
}

const connectorNames: Record<string, string> = {
  gdrive: 'Google Drive',
  gdocs: 'Google Docs',
  gsheets: 'Google Sheets',
  gslides: 'Google Slides',
  onedrive: 'OneDrive',
  notion: 'Notion',
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return ''
  }
}

function getFileTypeLabel(docType: string): string {
  if (!docType) return 'DOC'
  const lower = docType.toLowerCase()
  if (lower.includes('pdf')) return 'PDF'
  if (lower.includes('word') || lower.includes('docx')) return 'DOCX'
  if (lower.includes('sheet') || lower.includes('xlsx') || lower.includes('spreadsheet')) return 'XLSX'
  if (lower.includes('presentation') || lower.includes('pptx') || lower.includes('slide')) return 'PPTX'
  if (lower.includes('image') || lower.includes('png') || lower.includes('jpg')) return 'IMG'
  if (lower.includes('text')) return 'TXT'
  if (lower.includes('html')) return 'HTML'
  if (lower.includes('csv')) return 'CSV'
  // Notion pages
  if (lower === 'document' || lower === 'page') return 'PAGE'
  return 'DOC'
}

export default function DocumentSelectionModal({
  isOpen,
  onClose,
  onConfirm,
  onImportAll,
  documents,
  connectorName,
  connectorLogo,
  isConfirming
}: DocumentSelectionModalProps) {
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  // Initialize all docs as selected
  useEffect(() => {
    setSelectedDocs(new Set(documents.map(d => d.id)))
    setSearchQuery('')
  }, [documents])

  const toggleDoc = (id: string) => {
    setSelectedDocs(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  const selectAll = () => {
    setSelectedDocs(new Set(filteredDocs.map(d => d.id)))
  }

  const selectNone = () => {
    setSelectedDocs(new Set())
  }

  const filteredDocs = useMemo(() => {
    if (!searchQuery.trim()) return documents
    const q = searchQuery.toLowerCase()
    return documents.filter(d => d.title.toLowerCase().includes(q))
  }, [documents, searchQuery])

  if (!isOpen) return null

  const logo = connectorLogo || connectorLogos[connectorName] || '/docs.png'
  const displayName = connectorNames[connectorName] || connectorName

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          padding: '32px',
          maxWidth: '600px',
          width: '90%',
          maxHeight: '85vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <Image src={logo} alt={displayName} width={32} height={32} style={{ borderRadius: '6px' }} />
          <h2 style={{
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontSize: '22px',
            fontWeight: 600,
            color: '#1A1A1A',
            margin: 0
          }}>
            Select Documents from {displayName}
          </h2>
        </div>
        <p style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          color: '#71717A',
          marginBottom: '16px',
          marginTop: '4px'
        }}>
          Choose which files to import into your knowledge base. Unselected files will not be processed.
        </p>

        {/* Search bar */}
        <div style={{ marginBottom: '12px' }}>
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              fontSize: '14px',
              fontFamily: 'Inter, sans-serif',
              outline: 'none',
              boxSizing: 'border-box',
              backgroundColor: '#FAFAFA'
            }}
          />
        </div>

        {/* Quick select buttons */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'center' }}>
          <button
            onClick={selectAll}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #D4D4D8',
              backgroundColor: '#fff',
              fontSize: '12px',
              cursor: 'pointer',
              fontFamily: 'Inter, sans-serif'
            }}
          >
            Select All ({filteredDocs.length})
          </button>
          <button
            onClick={selectNone}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #D4D4D8',
              backgroundColor: '#fff',
              fontSize: '12px',
              cursor: 'pointer',
              fontFamily: 'Inter, sans-serif'
            }}
          >
            Select None
          </button>
          <span style={{
            marginLeft: 'auto',
            fontSize: '12px',
            color: '#71717A',
            fontFamily: 'Inter, sans-serif'
          }}>
            {selectedDocs.size} of {documents.length} selected
          </span>
        </div>

        {/* Document list */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          border: '1px solid #E4E4E7',
          borderRadius: '8px',
          backgroundColor: '#fff',
          minHeight: '200px',
          maxHeight: '50vh'
        }}>
          {filteredDocs.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#71717A', fontFamily: 'Inter, sans-serif' }}>
              {searchQuery ? 'No documents match your search' : 'No documents found'}
            </div>
          ) : (
            filteredDocs.map((doc, idx) => (
              <div
                key={doc.id}
                onClick={() => toggleDoc(doc.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '10px 14px',
                  borderBottom: idx < filteredDocs.length - 1 ? '1px solid #F0EEEC' : 'none',
                  cursor: 'pointer',
                  backgroundColor: selectedDocs.has(doc.id) ? '#FBF4F1' : 'transparent',
                  transition: 'background-color 0.15s ease'
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedDocs.has(doc.id)}
                  onChange={() => {}}
                  style={{
                    marginRight: '12px',
                    cursor: 'pointer',
                    width: '16px',
                    height: '16px',
                    accentColor: '#C9A598',
                    flexShrink: 0
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '14px',
                    fontWeight: 500,
                    color: '#18181B',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {doc.title}
                  </div>
                  <div style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '12px',
                    color: '#71717A',
                    display: 'flex',
                    gap: '8px',
                    marginTop: '2px'
                  }}>
                    <span style={{
                      backgroundColor: '#F0EEEC',
                      padding: '1px 6px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 500,
                      color: '#52525B'
                    }}>
                      {getFileTypeLabel(doc.doc_type)}
                    </span>
                    {doc.date && <span>{formatDate(doc.date)}</span>}
                    {doc.size && <span>{formatFileSize(doc.size)}</span>}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div style={{ marginTop: '20px' }}>
          {/* Action buttons */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <button
              onClick={onClose}
              disabled={isConfirming}
              style={{
                padding: '10px 20px',
                borderRadius: '8px',
                border: '1px solid #D4D4D8',
                backgroundColor: '#fff',
                fontSize: '14px',
                fontWeight: 500,
                cursor: isConfirming ? 'not-allowed' : 'pointer',
                fontFamily: 'Inter, sans-serif',
                opacity: isConfirming ? 0.5 : 1
              }}
            >
              Cancel
            </button>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <button
                onClick={onImportAll}
                disabled={isConfirming}
                style={{
                  padding: '10px 16px',
                  borderRadius: '8px',
                  border: '1px solid #D4D4D8',
                  backgroundColor: '#fff',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: isConfirming ? 'not-allowed' : 'pointer',
                  fontFamily: 'Inter, sans-serif',
                  color: '#52525B',
                  opacity: isConfirming ? 0.5 : 1
                }}
              >
                Import All
              </button>
              <button
                onClick={() => onConfirm(Array.from(selectedDocs))}
                disabled={selectedDocs.size === 0 || isConfirming}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: selectedDocs.size === 0 || isConfirming ? '#9ca3af' : '#C9A598',
                  color: '#fff',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: selectedDocs.size === 0 || isConfirming ? 'not-allowed' : 'pointer',
                  fontFamily: 'Inter, sans-serif',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                {isConfirming ? (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}>
                      <path d="M21 12a9 9 0 11-6.219-8.56" />
                    </svg>
                    Importing...
                  </>
                ) : (
                  `Import Selected (${selectedDocs.size})`
                )}
              </button>
            </div>
          </div>
        </div>

        <style>{`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </div>
  )
}
