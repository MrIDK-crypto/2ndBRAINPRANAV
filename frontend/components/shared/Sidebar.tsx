'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { analytics } from '@/utils/analytics'
import { useAuth } from '@/contexts/AuthContext'

interface ChatConversation {
  id: string
  title: string | null
  last_message_at: string
  message_count: number
}

interface SidebarProps {
  activeItem?: string
  onItemClick?: (item: string) => void
  // User Props
  userName?: string
  // Chat History Props
  conversations?: ChatConversation[]
  currentConversationId?: string | null
  onLoadConversation?: (id: string) => void
  onDeleteConversation?: (id: string) => void
  onNewChat?: () => void
  isLoadingHistory?: boolean
}

export default function Sidebar({
  activeItem,
  onItemClick,
  userName = 'User',
  conversations = [],
  currentConversationId,
  onLoadConversation,
  onDeleteConversation,
  onNewChat,
  isLoadingHistory = false
}: SidebarProps) {
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false)
  const pathname = usePathname()
  const { user: authUser } = useAuth()
  const isAdmin = authUser?.role === 'admin'

  // Determine active item from pathname if not provided
  const getActiveItem = () => {
    if (activeItem) return activeItem
    if (pathname === '/integrations') return 'Integrations'
    if (pathname === '/documents') return 'Documents'
    if (pathname === '/knowledge-gaps') return 'Knowledge Gaps'
    if (pathname === '/training-guides') return 'Training Videos'
    if (pathname === '/inventory') return 'Inventory'
    if (pathname === '/analytics') return 'Analytics'
    if (pathname === '/grants') return 'Grant Finder'
    if (pathname === '/' || pathname === '/chat') return 'ChatBot'
    return 'ChatBot'
  }

  const currentActive = getActiveItem()

  const handleClick = (item: string) => {
    analytics.sidebarClick(item)
    // Clicking ChatBot should always open a new chat
    if (item === 'ChatBot' && onNewChat) {
      onNewChat()
    }
    if (onItemClick) {
      onItemClick(item)
    }
  }

  // Format relative time
  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m`
    if (diffHours < 24) return `${diffHours}h`
    if (diffDays < 7) return `${diffDays}d`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const showChatHistory = currentActive === 'ChatBot' && (conversations.length > 0 || onNewChat)

  // Menu items configuration - Order: Integrations, Documents, Knowledge Gaps, ChatBot, Training Guides, Inventory, Analytics
  // Using inline SVG icons for better quality and consistency
  const allMenuItems = [
    { id: 'Integrations', label: 'Integrations', href: '/integrations', icon: 'integrations', adminOnly: true },
    { id: 'Documents', label: 'Documents', href: '/documents', icon: 'documents', adminOnly: false },
    { id: 'Knowledge Gaps', label: 'Knowledge Gaps', href: '/knowledge-gaps', icon: 'gaps', adminOnly: false },
    { id: 'Grant Finder', label: 'Grant Finder', href: '/grants', icon: 'grants', adminOnly: false },
    { id: 'ChatBot', label: 'ChatBot', href: '/', icon: 'chatbot', adminOnly: false },
    { id: 'Training Videos', label: 'Training Videos', href: '/training-guides', icon: 'training', adminOnly: false },
    { id: 'Inventory', label: 'Inventory', href: '/inventory', icon: 'inventory', adminOnly: false },
    { id: 'Analytics', label: 'Analytics', href: '/analytics', icon: 'analytics', adminOnly: true },
  ]

  const menuItems = isAdmin
    ? allMenuItems
    : allMenuItems.filter(item => !item.adminOnly)

  // SVG icon components
  const renderIcon = (iconId: string, isActive: boolean) => {
    const color = isActive ? '#C9A598' : '#8A8A8A'

    switch (iconId) {
      case 'integrations':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        )
      case 'documents':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14,2 14,8 20,8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <line x1="10" y1="9" x2="8" y2="9" />
          </svg>
        )
      case 'gaps':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        )
      case 'chatbot':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
            <line x1="9" y1="10" x2="9.01" y2="10" />
            <line x1="15" y1="10" x2="15.01" y2="10" />
          </svg>
        )
      case 'training':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="5,3 19,12 5,21 5,3" />
          </svg>
        )
      case 'analytics':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
        )
      case 'inventory':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
            <polyline points="3.27,6.96 12,12.01 20.73,6.96" />
            <line x1="12" y1="22.08" x2="12" y2="12" />
          </svg>
        )
      case 'grants':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <path d="M11 8v6" />
            <path d="M8 11h6" />
          </svg>
        )
      default:
        return null
    }
  }

  return (
    <div
      style={{
        width: '280px',
        minHeight: '100vh',
        backgroundColor: '#FAF9F7',
        borderRight: '1px solid #F0EEEC',
        display: 'flex',
        flexDirection: 'column',
        padding: '24px 0'
      }}
    >
      <div style={{ padding: '0 24px' }}>
        {/* Logo */}
        <div style={{ marginBottom: '32px' }}>
          <Link href="/">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
              <div style={{ width: '48px', height: '60px', flexShrink: 0 }}>
                <Image
                  src="/owl.png"
                  alt="2nd Brain Logo"
                  width={48}
                  height={60}
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>
              <h1
                style={{
                  color: '#1A1A1A',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  fontSize: '20px',
                  fontWeight: 700,
                  lineHeight: '24px',
                  whiteSpace: 'nowrap',
                  margin: 0
                }}
              >
                2nd Brain
              </h1>
            </div>
          </Link>
        </div>

        {/* Search */}
        <div style={{ marginBottom: '24px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '10px 14px',
              backgroundColor: '#FFFFFF',
              borderRadius: '10px',
              border: '1px solid #F0EEEC'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
            <input
              type="text"
              placeholder="Search..."
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                backgroundColor: 'transparent',
                fontSize: '14px',
                color: '#374151',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
              }}
            />
          </div>
        </div>

        {/* Menu Items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {menuItems.map((item) => {
            const isActive = currentActive === item.id
            return (
              <Link href={item.href} key={item.id}>
                <div
                  onClick={() => handleClick(item.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    backgroundColor: isActive ? '#FBF4F1' : 'transparent',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = '#FAF8F6'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent'
                    }
                  }}
                >
                  {/* Icon */}
                  <div style={{ width: '20px', height: '20px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {renderIcon(item.icon, isActive)}
                  </div>
                  <span
                    style={{
                      color: isActive ? '#C9A598' : '#5C5C5C',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                      fontSize: '15px',
                      fontWeight: isActive ? 500 : 400
                    }}
                  >
                    {item.label}
                  </span>
                </div>
              </Link>
            )
          })}
        </div>

        {/* Chat History Section - Only show on ChatBot page */}
        {showChatHistory && (
          <div style={{ marginTop: '24px' }}>
            {/* Section Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', marginBottom: '8px' }}>
              <button
                onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#7A7A7A',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0
                }}
              >
                <svg
                  style={{
                    width: '12px',
                    height: '12px',
                    transition: 'transform 0.2s',
                    transform: isHistoryExpanded ? 'rotate(90deg)' : 'rotate(0deg)'
                  }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Chat History
              </button>
              {onNewChat && (
                <button
                  onClick={onNewChat}
                  style={{
                    padding: '4px',
                    color: '#9CA3AF',
                    background: 'none',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                  title="New Chat"
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#F3F4F6'
                    e.currentTarget.style.color = '#7A7A7A'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent'
                    e.currentTarget.style.color = '#9CA3AF'
                  }}
                >
                  <svg style={{ width: '16px', height: '16px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </button>
              )}
            </div>

            {/* Conversation List */}
            {isHistoryExpanded && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxHeight: '280px', overflowY: 'auto' }}>
                {isLoadingHistory ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
                    <div style={{
                      width: '16px',
                      height: '16px',
                      border: '2px solid #ECEAE8',
                      borderTopColor: '#C9A598',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite'
                    }} />
                  </div>
                ) : conversations.length === 0 ? (
                  <div style={{ padding: '16px', textAlign: 'center' }}>
                    <p style={{ fontSize: '12px', color: '#9CA3AF', margin: 0 }}>No chat history yet</p>
                  </div>
                ) : (
                  conversations.slice(0, 10).map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => onLoadConversation?.(conv.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '8px 16px',
                        cursor: 'pointer',
                        borderRadius: '8px',
                        backgroundColor: currentConversationId === conv.id ? '#FBF4F1' : 'transparent',
                        transition: 'background-color 0.15s'
                      }}
                      onMouseEnter={(e) => {
                        if (currentConversationId !== conv.id) {
                          e.currentTarget.style.backgroundColor = '#F5F3F1'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (currentConversationId !== conv.id) {
                          e.currentTarget.style.backgroundColor = 'transparent'
                        }
                      }}
                    >
                      {/* Chat Icon */}
                      <svg style={{ width: '14px', height: '14px', color: '#9CA3AF', flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>

                      {/* Title */}
                      <span style={{
                        flex: 1,
                        fontSize: '13px',
                        color: currentConversationId === conv.id ? '#C9A598' : '#4A4A4A',
                        fontWeight: currentConversationId === conv.id ? 500 : 400,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}>
                        {conv.title || 'Untitled'}
                      </span>

                      {/* Time */}
                      <span style={{ fontSize: '10px', color: '#9CA3AF', flexShrink: 0 }}>
                        {formatRelativeTime(conv.last_message_at)}
                      </span>

                      {/* Delete button */}
                      {onDeleteConversation && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onDeleteConversation(conv.id)
                          }}
                          style={{
                            padding: '2px',
                            background: 'none',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            color: '#9CA3AF',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            opacity: 0,
                            transition: 'opacity 0.15s, color 0.15s'
                          }}
                          className="chat-delete-btn"
                          title="Delete conversation"
                          onMouseEnter={(e) => {
                            e.currentTarget.style.color = '#EF4444'
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.color = '#9CA3AF'
                          }}
                        >
                          <svg style={{ width: '12px', height: '12px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* User Profile at Bottom */}
      <div style={{ padding: '0 24px' }}>
        <div
          style={{
            borderTop: '1px solid #ECEAE8',
            paddingTop: '20px',
            marginTop: '20px'
          }}
        >
          <Link href="/settings">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  transition: 'background-color 0.15s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#F5F3F1'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent'
                }}
              >
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  overflow: 'hidden',
                  flexShrink: 0,
                  border: '2px solid #ECEAE8'
                }}>
                  <Image src="/Maya.png" alt="User" width={40} height={40} />
                </div>
                <div>
                  <div style={{
                    color: '#1A1A1A',
                    fontSize: '14px',
                    fontWeight: 600,
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                  }}>
                    {userName}
                  </div>
                  <div style={{
                    color: '#7A7A7A',
                    fontSize: '12px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                  }}>
                    Account settings
                  </div>
                </div>
              </div>
            </Link>
        </div>
      </div>

      {/* CSS for spinner animation and chat delete hover */}
      <style jsx global>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        div:hover > .chat-delete-btn {
          opacity: 1 !important;
        }
      `}</style>
    </div>
  )
}
