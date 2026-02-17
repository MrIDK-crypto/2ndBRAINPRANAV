'use client'

import React, { useState } from 'react'
import { colors, shadows, Z_INDEX, getSourceTypeInfo } from './constants'

interface DocumentViewerProps {
  document: {
    id: string
    title: string
    content: string
    content_html?: string
    classification?: string
    source_type?: string
    sender?: string
    sender_email?: string
    recipients?: string[]
    source_created_at?: string
    summary?: string
    metadata?: any
    source_url?: string
  }
  onClose: () => void
}

// Simple markdown-like renderer for code documents
function renderMarkdownContent(content: string): React.ReactNode {
  if (!content) return null

  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let inCodeBlock = false
  let codeBlockContent: string[] = []
  let codeBlockLang = ''
  let key = 0

  const flushCodeBlock = () => {
    if (codeBlockContent.length > 0) {
      elements.push(
        <pre
          key={key++}
          style={{
            backgroundColor: '#2D2D2D',
            color: '#E8E0DB',
            padding: '16px',
            borderRadius: '8px',
            overflow: 'auto',
            fontSize: '13px',
            lineHeight: '1.5',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            margin: '12px 0',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}
        >
          <code>{codeBlockContent.join('\n')}</code>
        </pre>
      )
      codeBlockContent = []
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Code block handling
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        flushCodeBlock()
        inCodeBlock = false
      } else {
        inCodeBlock = true
        codeBlockLang = line.slice(3).trim()
      }
      continue
    }

    if (inCodeBlock) {
      codeBlockContent.push(line)
      continue
    }

    // Headers
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={key++} style={{ fontSize: '24px', fontWeight: 700, color: colors.textPrimary, margin: '24px 0 12px', borderBottom: `1px solid ${colors.border}`, paddingBottom: '8px' }}>
          {line.slice(2)}
        </h1>
      )
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={key++} style={{ fontSize: '20px', fontWeight: 600, color: colors.textPrimary, margin: '20px 0 10px' }}>
          {line.slice(3)}
        </h2>
      )
    } else if (line.startsWith('### ')) {
      elements.push(
        <h3 key={key++} style={{ fontSize: '16px', fontWeight: 600, color: colors.textSecondary, margin: '16px 0 8px' }}>
          {line.slice(4)}
        </h3>
      )
    }
    // List items
    else if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(
        <li key={key++} style={{ color: colors.textSecondary, fontSize: '14px', lineHeight: '1.6', marginLeft: '20px', marginBottom: '4px' }}>
          {renderInlineCode(line.slice(2))}
        </li>
      )
    }
    // Numbered lists
    else if (/^\d+\.\s/.test(line)) {
      const match = line.match(/^(\d+)\.\s(.*)/)
      if (match) {
        elements.push(
          <li key={key++} style={{ color: colors.textSecondary, fontSize: '14px', lineHeight: '1.6', marginLeft: '20px', marginBottom: '4px', listStyleType: 'decimal' }}>
            {renderInlineCode(match[2])}
          </li>
        )
      }
    }
    // Empty lines
    else if (line.trim() === '') {
      elements.push(<div key={key++} style={{ height: '8px' }} />)
    }
    // Regular paragraphs
    else {
      elements.push(
        <p key={key++} style={{ color: colors.textSecondary, fontSize: '14px', lineHeight: '1.7', margin: '8px 0' }}>
          {renderInlineCode(line)}
        </p>
      )
    }
  }

  // Flush any remaining code block
  flushCodeBlock()

  return elements
}

// Render inline code (backticks)
function renderInlineCode(text: string): React.ReactNode {
  const parts = text.split(/(`[^`]+`)/)
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          style={{
            backgroundColor: colors.primaryLight,
            color: colors.textPrimary,
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '13px',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
          }}
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    // Bold text
    if (part.includes('**')) {
      const boldParts = part.split(/(\*\*[^*]+\*\*)/)
      return boldParts.map((bp, j) => {
        if (bp.startsWith('**') && bp.endsWith('**')) {
          return <strong key={`${i}-${j}`}>{bp.slice(2, -2)}</strong>
        }
        return bp
      })
    }
    return part
  })
}

// Classification badge colors using warm palette
const classificationBadgeColors: Record<string, { bg: string; text: string }> = {
  work: { bg: colors.classificationWork, text: '#FFFFFF' },
  personal: { bg: colors.classificationPersonal, text: '#FFFFFF' },
  spam: { bg: colors.classificationSpam, text: '#FFFFFF' },
  unknown: { bg: colors.classificationUnknown, text: '#FFFFFF' },
}

export default function DocumentViewer({ document, onClose }: DocumentViewerProps) {
  const [activeTab, setActiveTab] = useState<'content' | 'raw'>('content')

  // Handle escape key to close
  React.useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  // Check if this is a code/GitHub document
  const isCodeDocument = document.source_type?.toLowerCase() === 'github'

  // Get source URL from document or metadata
  const getSourceUrl = () => {
    return document.source_url || document.metadata?.url || document.metadata?.source_url || null
  }

  // Use shared source type map
  const sourceInfo = getSourceTypeInfo(document.source_type)

  // Format classification for display
  const getClassificationBadge = () => {
    if (!document.classification) return null
    const badge = classificationBadgeColors[document.classification] || classificationBadgeColors.unknown

    return (
      <span
        style={{
          padding: '4px 12px',
          borderRadius: '16px',
          backgroundColor: badge.bg,
          color: badge.text,
          fontSize: '11px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}
      >
        {document.classification}
      </span>
    )
  }

  // Format date
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A'
    try {
      return new Date(dateStr).toLocaleString()
    } catch {
      return dateStr
    }
  }

  const sourceUrl = getSourceUrl()

  // For GitHub/code documents, show content viewer
  // For other documents without URL, also show content viewer
  const showContentViewer = isCodeDocument || (!sourceUrl && document.content)

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: Z_INDEX.modal,
        padding: '20px'
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: colors.pageBg,
          borderRadius: '16px',
          boxShadow: shadows.lg,
          maxWidth: showContentViewer ? '900px' : '600px',
          width: '100%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            padding: '20px 24px',
            borderBottom: `1px solid ${colors.border}`,
            backgroundColor: isCodeDocument ? '#2D2D2D' : colors.cardBg
          }}
        >
          <div style={{ flex: 1, paddingRight: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '24px' }}>{sourceInfo.icon}</span>
              <span
                style={{
                  color: isCodeDocument ? colors.primary : sourceInfo.color,
                  fontSize: '12px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}
              >
                {sourceInfo.label}
              </span>
              {isCodeDocument && document.metadata?.repository && (
                <span style={{ color: colors.textMuted, fontSize: '12px' }}>
                  • {document.metadata.repository}
                </span>
              )}
            </div>
            <h2
              style={{
                color: isCodeDocument ? '#F0EEEC' : colors.textPrimary,
                fontSize: '18px',
                fontWeight: 600,
                lineHeight: '1.4',
                marginBottom: '12px',
                wordBreak: 'break-word'
              }}
            >
              {document.title || 'Untitled Document'}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              {getClassificationBadge()}
              <span style={{ color: isCodeDocument ? colors.textMuted : colors.textSecondary, fontSize: '13px' }}>
                {formatDate(document.source_created_at)}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              backgroundColor: isCodeDocument ? '#3D3D3D' : colors.border,
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              transition: 'background-color 0.15s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = isCodeDocument ? '#4D4D4D' : colors.borderLight}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = isCodeDocument ? '#3D3D3D' : colors.border}
          >
            <span style={{ color: isCodeDocument ? colors.textMuted : colors.textSecondary, fontSize: '20px', lineHeight: 1 }}>×</span>
          </button>
        </div>

        {/* Tabs for code documents */}
        {showContentViewer && (
          <div style={{ display: 'flex', borderBottom: `1px solid ${colors.border}`, backgroundColor: colors.cardBg }}>
            <button
              onClick={() => setActiveTab('content')}
              style={{
                padding: '12px 20px',
                border: 'none',
                backgroundColor: activeTab === 'content' ? colors.pageBg : 'transparent',
                borderBottom: activeTab === 'content' ? `2px solid ${colors.primary}` : '2px solid transparent',
                color: activeTab === 'content' ? colors.primary : colors.textMuted,
                fontWeight: 500,
                fontSize: '14px',
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              Formatted
            </button>
            <button
              onClick={() => setActiveTab('raw')}
              style={{
                padding: '12px 20px',
                border: 'none',
                backgroundColor: activeTab === 'raw' ? colors.pageBg : 'transparent',
                borderBottom: activeTab === 'raw' ? `2px solid ${colors.primary}` : '2px solid transparent',
                color: activeTab === 'raw' ? colors.primary : colors.textMuted,
                fontWeight: 500,
                fontSize: '14px',
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              {'</>'} Raw
            </button>
          </div>
        )}

        {/* Main Content */}
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            backgroundColor: colors.pageBg
          }}
        >
          {showContentViewer ? (
            <div style={{ padding: '24px' }}>
              {activeTab === 'content' ? (
                <div style={{ maxWidth: '100%' }}>
                  {renderMarkdownContent(document.content)}
                </div>
              ) : (
                <pre
                  style={{
                    backgroundColor: '#2D2D2D',
                    color: '#E8E0DB',
                    padding: '20px',
                    borderRadius: '8px',
                    overflow: 'auto',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    margin: 0
                  }}
                >
                  {document.content}
                </pre>
              )}
            </div>
          ) : sourceUrl ? (
            <div
              style={{
                padding: '32px 24px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center'
              }}
            >
              <div
                style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '16px',
                  backgroundColor: colors.primaryLight,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '20px'
                }}
              >
                <span style={{ fontSize: '40px' }}>{sourceInfo.icon}</span>
              </div>
              <h3
                style={{
                  color: colors.textPrimary,
                  fontSize: '16px',
                  fontWeight: 600,
                  marginBottom: '8px'
                }}
              >
                View this document in {sourceInfo.label}
              </h3>
              <p
                style={{
                  color: colors.textSecondary,
                  fontSize: '14px',
                  marginBottom: '24px',
                  maxWidth: '360px'
                }}
              >
                Click below to open the original document in its source application.
              </p>
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '14px 28px',
                  borderRadius: '10px',
                  backgroundColor: colors.primary,
                  color: '#FFFFFF',
                  fontSize: '15px',
                  fontWeight: 600,
                  textDecoration: 'none',
                  transition: 'background-color 0.15s, transform 0.1s',
                  boxShadow: shadows.sm
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = colors.primaryHover
                  e.currentTarget.style.transform = 'translateY(-1px)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = colors.primary
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
                Open in {sourceInfo.label}
              </a>
            </div>
          ) : (
            <div
              style={{
                padding: '32px 24px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center'
              }}
            >
              <div
                style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '16px',
                  backgroundColor: colors.cardBg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '20px'
                }}
              >
                <span style={{ fontSize: '40px' }}>📄</span>
              </div>
              <h3
                style={{
                  color: colors.textPrimary,
                  fontSize: '16px',
                  fontWeight: 600,
                  marginBottom: '8px'
                }}
              >
                Document Preview
              </h3>
              <p
                style={{
                  color: colors.textSecondary,
                  fontSize: '14px',
                  marginBottom: '16px'
                }}
              >
                No content available for this document.
              </p>
              {document.summary && (
                <div
                  style={{
                    backgroundColor: colors.cardBg,
                    borderRadius: '8px',
                    padding: '16px',
                    maxWidth: '100%',
                    textAlign: 'left'
                  }}
                >
                  <p style={{ color: colors.textSecondary, fontSize: '14px', lineHeight: '1.6' }}>
                    {document.summary}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 24px',
            borderTop: `1px solid ${colors.border}`,
            backgroundColor: colors.cardBg,
            gap: '12px'
          }}
        >
          <div style={{ fontSize: '13px', color: colors.textMuted }}>
            {document.content && `${document.content.length.toLocaleString()} characters`}
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              backgroundColor: colors.border,
              color: colors.textPrimary,
              border: 'none',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
              transition: 'background-color 0.15s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = colors.border}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
