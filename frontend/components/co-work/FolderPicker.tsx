'use client'

import React, { useState, useEffect, useRef, useCallback } from 'react'

// ── Design tokens ──
const COLORS = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  success: '#9CB896',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

// ── Source icon colors ──
const SOURCE_COLORS: Record<string, string> = {
  email: '#EA4335',
  gmail: '#EA4335',
  message: '#4A154B',
  slack: '#4A154B',
  file: '#C9A598',
  document: '#C9A598',
  box: '#0061D5',
  github: '#24292F',
  onedrive: '#0078D4',
  google_drive: '#4285F4',
  google_docs: '#4285F4',
  google_sheets: '#0F9D58',
  google_slides: '#F4B400',
  notion: '#000000',
  zotero: '#CC2936',
  pubmed: '#326599',
  webscraper: '#6B6B6B',
  firecrawl: '#FF6B35',
  outlook: '#0078D4',
  email_forwarding: '#9CB896',
  grant: '#D4A853',
  quartzy: '#00B4D8',
}

// ── Source icons (simple SVG paths) ──
function SourceIcon({ type, size = 14 }: { type: string; size?: number }) {
  const color = SOURCE_COLORS[type] || COLORS.textMuted

  // Map source types to simple icon shapes
  if (['email', 'gmail', 'outlook', 'email_forwarding'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <path d="M22 7l-10 7L2 7" />
      </svg>
    )
  }
  if (['message', 'slack'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
      </svg>
    )
  }
  if (['github'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
      </svg>
    )
  }
  if (['google_drive', 'onedrive'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12H2" />
        <path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z" />
        <line x1="6" y1="16" x2="6.01" y2="16" />
        <line x1="10" y1="16" x2="10.01" y2="16" />
      </svg>
    )
  }
  if (['notion'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
      </svg>
    )
  }
  if (['box'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
        <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
        <line x1="12" y1="22.08" x2="12" y2="12" />
      </svg>
    )
  }
  if (['webscraper', 'firecrawl'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
      </svg>
    )
  }
  if (['pubmed'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    )
  }
  if (['zotero'].includes(type)) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
        <line x1="8" y1="7" x2="16" y2="7" />
        <line x1="8" y1="11" x2="16" y2="11" />
        <line x1="8" y1="15" x2="12" y2="15" />
      </svg>
    )
  }
  // Default: folder icon
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
    </svg>
  )
}

// ── Types ──
interface SourceInfo {
  source_type: string
  label: string
  icon: string
  doc_count: number
}

interface FolderPickerProps {
  apiBase: string
  token: string | null
  selectedSources: string[]
  onSourcesChange: (sources: string[]) => void
}

export default function FolderPicker({
  apiBase,
  token,
  selectedSources,
  onSourcesChange,
}: FolderPickerProps) {
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Fetch available sources
  const fetchSources = useCallback(async () => {
    if (!token) return
    setIsLoading(true)
    try {
      const res = await fetch(`${apiBase}/documents/sources`, {
        headers: { 'Authorization': `Bearer ${token}` },
      })
      const data = await res.json()
      if (data.success && data.sources) {
        setSources(data.sources)
      }
    } catch (e) {
      console.error('[FolderPicker] Failed to fetch sources:', e)
    } finally {
      setIsLoading(false)
    }
  }, [apiBase, token])

  useEffect(() => {
    fetchSources()
  }, [fetchSources])

  // Close dropdown on outside click
  useEffect(() => {
    if (!isOpen) return
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [isOpen])

  const toggleSource = (sourceType: string) => {
    if (selectedSources.includes(sourceType)) {
      onSourcesChange(selectedSources.filter(s => s !== sourceType))
    } else {
      onSourcesChange([...selectedSources, sourceType])
    }
  }

  const clearAll = () => {
    onSourcesChange([])
  }

  const selectAll = () => {
    onSourcesChange(sources.map(s => s.source_type))
  }

  const totalDocs = sources.reduce((acc, s) => acc + s.doc_count, 0)
  const selectedCount = selectedSources.length
  const isFiltered = selectedCount > 0

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-block' }}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 12px',
          borderRadius: '8px',
          border: `1px solid ${isFiltered ? COLORS.primary : COLORS.border}`,
          backgroundColor: isFiltered ? COLORS.primaryLight : COLORS.cardBg,
          cursor: 'pointer',
          fontFamily: FONT,
          fontSize: '12px',
          fontWeight: 500,
          color: isFiltered ? COLORS.primary : COLORS.textSecondary,
          transition: 'all 0.15s ease',
          whiteSpace: 'nowrap',
        }}
        onMouseEnter={(e) => {
          if (!isFiltered) {
            e.currentTarget.style.borderColor = COLORS.primaryHover
            e.currentTarget.style.color = COLORS.primaryHover
          }
        }}
        onMouseLeave={(e) => {
          if (!isFiltered) {
            e.currentTarget.style.borderColor = COLORS.border
            e.currentTarget.style.color = COLORS.textSecondary
          }
        }}
      >
        {/* Folder icon */}
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
        </svg>
        {isFiltered ? (
          <>
            {selectedCount} source{selectedCount !== 1 ? 's' : ''}
            {/* Clear badge */}
            <span
              onClick={(e) => {
                e.stopPropagation()
                clearAll()
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                backgroundColor: COLORS.primary,
                color: '#FFFFFF',
                fontSize: '9px',
                fontWeight: 700,
                cursor: 'pointer',
                marginLeft: '2px',
                lineHeight: 1,
              }}
            >
              x
            </span>
          </>
        ) : (
          'All sources'
        )}
        {/* Chevron */}
        <svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.15s ease',
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            width: '260px',
            maxHeight: '360px',
            backgroundColor: COLORS.cardBg,
            borderRadius: '12px',
            border: `1px solid ${COLORS.border}`,
            boxShadow: '0 8px 24px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04)',
            zIndex: 100,
            overflow: 'hidden',
            fontFamily: FONT,
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '12px 14px 8px',
              borderBottom: `1px solid ${COLORS.border}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: COLORS.textPrimary }}>
                Filter by source
              </span>
              <span style={{ fontSize: '11px', color: COLORS.textMuted }}>
                {totalDocs} total docs
              </span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={selectAll}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '11px',
                  color: COLORS.primary,
                  fontWeight: 500,
                  padding: 0,
                  fontFamily: FONT,
                }}
              >
                Select all
              </button>
              <span style={{ color: COLORS.border }}>|</span>
              <button
                onClick={clearAll}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '11px',
                  color: COLORS.textMuted,
                  fontWeight: 500,
                  padding: 0,
                  fontFamily: FONT,
                }}
              >
                Clear all
              </button>
            </div>
          </div>

          {/* Source list */}
          <div
            style={{
              maxHeight: '280px',
              overflowY: 'auto',
              padding: '6px',
            }}
          >
            {isLoading ? (
              <div style={{ padding: '20px', textAlign: 'center' }}>
                <div
                  style={{
                    width: '16px',
                    height: '16px',
                    border: `2px solid ${COLORS.border}`,
                    borderTopColor: COLORS.primary,
                    borderRadius: '50%',
                    animation: 'fp-spin 0.8s linear infinite',
                    margin: '0 auto 8px',
                  }}
                />
                <span style={{ fontSize: '12px', color: COLORS.textMuted }}>Loading sources...</span>
              </div>
            ) : sources.length === 0 ? (
              <div style={{ padding: '20px', textAlign: 'center' }}>
                <span style={{ fontSize: '12px', color: COLORS.textMuted }}>
                  No document sources found. Connect an integration to get started.
                </span>
              </div>
            ) : (
              sources.map((source) => {
                const isSelected = selectedSources.includes(source.source_type)
                return (
                  <button
                    key={source.source_type}
                    onClick={() => toggleSource(source.source_type)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: 'none',
                      backgroundColor: isSelected ? COLORS.primaryLight : 'transparent',
                      cursor: 'pointer',
                      transition: 'background-color 0.12s ease',
                      fontFamily: FONT,
                      textAlign: 'left',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = COLORS.pageBg
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent'
                    }}
                  >
                    {/* Checkbox */}
                    <div
                      style={{
                        width: '16px',
                        height: '16px',
                        borderRadius: '4px',
                        border: `1.5px solid ${isSelected ? COLORS.primary : COLORS.borderDark}`,
                        backgroundColor: isSelected ? COLORS.primary : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        transition: 'all 0.12s ease',
                      }}
                    >
                      {isSelected && (
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </div>

                    {/* Icon */}
                    <SourceIcon type={source.source_type} size={15} />

                    {/* Label and count */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: isSelected ? 600 : 400,
                          color: isSelected ? COLORS.textPrimary : COLORS.textSecondary,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {source.label}
                      </div>
                    </div>

                    {/* Doc count badge */}
                    <span
                      style={{
                        fontSize: '11px',
                        color: COLORS.textMuted,
                        backgroundColor: COLORS.pageBg,
                        padding: '1px 7px',
                        borderRadius: '8px',
                        flexShrink: 0,
                      }}
                    >
                      {source.doc_count}
                    </span>
                  </button>
                )
              })
            )}
          </div>

          {/* Footer hint */}
          {isFiltered && (
            <div
              style={{
                padding: '8px 14px',
                borderTop: `1px solid ${COLORS.border}`,
                backgroundColor: COLORS.pageBg,
              }}
            >
              <span style={{ fontSize: '11px', color: COLORS.textMuted }}>
                Chat will only search selected sources
              </span>
            </div>
          )}
        </div>
      )}

      {/* Spinner keyframe */}
      <style>{`
        @keyframes fp-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
