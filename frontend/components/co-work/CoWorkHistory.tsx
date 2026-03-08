'use client'

import React, { useState, useEffect, useCallback } from 'react'

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
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface Conversation {
  id: string
  title: string
  last_message_at: string
  message_count: number
}

interface CoWorkHistoryProps {
  apiBase: string
  token: string | null
  activeConversationId: string | null
  onSelectConversation: (id: string) => void
  onNewChat: () => void
}

export default function CoWorkHistory({
  apiBase, token, activeConversationId, onSelectConversation, onNewChat
}: CoWorkHistoryProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isOpen, setIsOpen] = useState(true)

  const fetchConversations = useCallback(async () => {
    if (!token) return
    try {
      const res = await fetch(`${apiBase}/chat/conversations?limit=30`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.success) {
        setConversations(data.conversations || [])
      }
    } catch (e) {
      console.error('[History] Failed to fetch conversations:', e)
    }
  }, [apiBase, token])

  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  // Refresh when active conversation changes (new one created)
  useEffect(() => {
    if (activeConversationId) fetchConversations()
  }, [activeConversationId, fetchConversations])

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return 'Today'
    if (diff < 172800000) return 'Yesterday'
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <div style={{
      width: isOpen ? '200px' : '40px',
      height: '100%',
      borderRight: `1px solid ${COLORS.border}`,
      backgroundColor: COLORS.pageBg,
      transition: 'width 0.2s ease',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 10px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        borderBottom: `1px solid ${COLORS.border}`,
        flexShrink: 0,
      }}>
        <button onClick={() => setIsOpen(!isOpen)} style={{
          width: '28px', height: '28px', borderRadius: '6px',
          border: 'none', backgroundColor: 'transparent', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: COLORS.textSecondary, flexShrink: 0,
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
        </button>
        {isOpen && (
          <span style={{
            fontSize: '13px', fontWeight: 600, color: COLORS.textPrimary,
            fontFamily: FONT, flex: 1,
          }}>
            History
          </span>
        )}
      </div>

      {/* Conversation list */}
      {isOpen && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '6px' }}>
          {/* New Chat button */}
          <button
            onClick={onNewChat}
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: '8px',
              border: `1px dashed ${COLORS.border}`,
              backgroundColor: 'transparent',
              cursor: 'pointer',
              textAlign: 'left',
              marginBottom: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: COLORS.textMuted,
              fontSize: '12px',
              fontFamily: FONT,
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = COLORS.primary; e.currentTarget.style.color = COLORS.primary }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = COLORS.border; e.currentTarget.style.color = COLORS.textMuted }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Chat
          </button>

          {conversations.length === 0 ? (
            <p style={{
              fontSize: '11px', color: COLORS.textMuted,
              textAlign: 'center', padding: '16px 8px',
              fontFamily: FONT,
            }}>
              No conversations yet
            </p>
          ) : (
            conversations.map(conv => (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: conv.id === activeConversationId ? COLORS.primaryLight : 'transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  marginBottom: '2px',
                  transition: 'background-color 0.15s',
                  fontFamily: FONT,
                }}
                onMouseEnter={(e) => { if (conv.id !== activeConversationId) e.currentTarget.style.backgroundColor = '#F5F3F1' }}
                onMouseLeave={(e) => { if (conv.id !== activeConversationId) e.currentTarget.style.backgroundColor = 'transparent' }}
              >
                <div style={{
                  fontSize: '12px', fontWeight: 500,
                  color: COLORS.textPrimary,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {conv.title || 'Untitled'}
                </div>
                <div style={{
                  fontSize: '10px', color: COLORS.textMuted,
                  marginTop: '2px',
                }}>
                  {formatDate(conv.last_message_at)}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
