'use client'

import React, { useState, useRef, useEffect } from 'react'
import TopNav from '../shared/TopNav'
import Image from 'next/image'
import { useAuth } from '@/contexts/AuthContext'
import { useCoResearcher } from './useCoResearcher'
import { theme, font, statusColors } from './theme'
import type { ActionDetail, PlanPhase, ContextData, Hypothesis } from './types'

export default function CoResearcher() {
  const { user } = useAuth()
  const {
    sessions, activeSession, messages, hypotheses, plan, brief, context,
    isStreaming, streamingText, streamingActions,
    listSessions, createSession, loadSession, closeSession, deleteSession,
    sendMessage,
  } = useCoResearcher()

  const [expandedActions, setExpandedActions] = useState<Record<string, boolean>>({})
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load sessions on mount
  useEffect(() => {
    listSessions()
  }, [listSessions])

  // Auto-scroll on new messages or streaming text
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const toggleActions = (msgId: string) => {
    setExpandedActions(prev => ({ ...prev, [msgId]: !prev[msgId] }))
  }

  const handleSend = async () => {
    if (!inputValue.trim() || isStreaming) return
    const text = inputValue
    setInputValue('')

    if (!activeSession) {
      // Create a new session with this as the first message
      const session = await createSession(text)
      if (session) {
        // Stream the AI response — pass session ID directly to avoid stale closure
        // skipUserMsg because createSession already saved it
        await sendMessage(text, { sessionId: session.id, skipUserMsg: true })
      }
    } else {
      await sendMessage(text)
    }
  }

  // =========================================================================
  // SUB-COMPONENTS (same visual design as original)
  // =========================================================================

  const ActionIcon = ({ type }: { type: string }) => {
    if (type === 'search' || type === 'searching_kb' || type === 'searching_pubmed' || type === 'pubmed_done') return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round">
        <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
      </svg>
    )
    if (type === 'doc') return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.success} strokeWidth="2" strokeLinecap="round">
        <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.amber} strokeWidth="2" strokeLinecap="round">
        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    )
  }

  const StatusDot = ({ status }: { status: 'done' | 'active' | 'pending' }) => {
    const colors = statusColors[status]
    return (
      <div style={{
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        backgroundColor: colors.dot,
        flexShrink: 0,
        marginTop: '5px',
      }} />
    )
  }

  // Welcome message when no session is active
  const welcomeMsg = {
    id: 'welcome',
    role: 'assistant' as const,
    content: "Hi! I'm your co-researcher. I can help you explore topics, build research plans, test hypotheses, and synthesize findings from your knowledge base and PubMed. What would you like to research?",
  }

  // All messages to display
  const displayMessages = activeSession
    ? messages
    : [{ ...welcomeMsg, session_id: '', actions: [], sources: [], extra_data: {}, created_at: new Date().toISOString() }]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: theme.pageBg }}>
      <TopNav userName={user?.full_name?.split(' ')[0] || 'User'} />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left Panel: Chat */}
        <div style={{
          width: '40%',
          minWidth: '360px',
          borderRight: `1px solid ${theme.border}`,
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: theme.cardBg,
        }}>
          {/* Session header */}
          {activeSession && (
            <div style={{
              padding: '12px 24px',
              borderBottom: `1px solid ${theme.border}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <button
                onClick={() => { closeSession(); listSessions() }}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  border: 'none', background: 'none', cursor: 'pointer',
                  fontSize: '13px', color: theme.textSecondary, fontFamily: font,
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 12H5M12 19l-7-7 7-7" />
                </svg>
                Sessions
              </button>
              <span style={{ fontSize: '13px', fontWeight: 600, color: theme.textPrimary, fontFamily: font }}>
                {activeSession.title || 'Research Session'}
              </span>
              <div style={{ width: '60px' }} />
            </div>
          )}

          {/* Session list (when no active session) */}
          {!activeSession && sessions.length > 0 && (
            <div style={{ padding: '12px 24px', borderBottom: `1px solid ${theme.border}` }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: theme.textMuted, fontFamily: font, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Recent Sessions
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '120px', overflowY: 'auto' }}>
                {sessions.slice(0, 5).map(s => (
                  <button
                    key={s.id}
                    onClick={() => loadSession(s.id)}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 12px', borderRadius: '8px',
                      border: `1px solid ${theme.border}`, background: 'none', cursor: 'pointer',
                      fontSize: '13px', color: theme.textPrimary, fontFamily: font,
                      transition: 'background-color 0.1s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = theme.primaryLight }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
                  >
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {s.title || 'Untitled'}
                    </span>
                    <span style={{ fontSize: '11px', color: theme.textMuted, flexShrink: 0, marginLeft: '8px' }}>
                      {s.message_count} msgs
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Chat messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
            {displayMessages.map((msg) => (
              <div key={msg.id} style={{ marginBottom: '20px' }}>
                {msg.role === 'user' ? (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                    <div style={{
                      maxWidth: '80%',
                      padding: '10px 16px',
                      borderRadius: '18px 18px 4px 18px',
                      backgroundColor: theme.primaryLight,
                      fontSize: '14px',
                      lineHeight: '1.5',
                      color: theme.textPrimary,
                      fontFamily: font,
                    }}>
                      {msg.content}
                    </div>
                    <div style={{
                      width: '30px',
                      height: '30px',
                      borderRadius: '50%',
                      overflow: 'hidden',
                      flexShrink: 0,
                      border: `1.5px solid ${theme.border}`,
                    }}>
                      <Image src="/Maya.png" alt="You" width={30} height={30} />
                    </div>
                  </div>
                ) : (
                  <div>
                    {/* AI avatar + message */}
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                      <div style={{
                        width: '30px',
                        height: '30px',
                        borderRadius: '50%',
                        overflow: 'hidden',
                        flexShrink: 0,
                      }}>
                        <Image src="/owl.png" alt="AI" width={30} height={30} style={{ objectFit: 'contain' }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{
                          fontSize: '14px',
                          lineHeight: '1.6',
                          color: theme.textPrimary,
                          fontFamily: font,
                          whiteSpace: 'pre-wrap',
                        }}>
                          {msg.content}
                        </div>
                      </div>
                    </div>

                    {/* Expandable actions badge */}
                    {msg.actions && msg.actions.length > 0 && (
                      <div style={{ marginLeft: '40px', marginTop: '10px' }}>
                        <button
                          onClick={() => toggleActions(msg.id)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '5px 12px',
                            borderRadius: '8px',
                            border: `1px solid ${theme.border}`,
                            backgroundColor: expandedActions[msg.id] ? theme.primaryLight : 'transparent',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: 500,
                            color: theme.textSecondary,
                            fontFamily: font,
                            transition: 'all 0.15s',
                          }}
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          {msg.actions.length} action{msg.actions.length !== 1 ? 's' : ''}
                          <svg
                            width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                            style={{
                              transform: expandedActions[msg.id] ? 'rotate(180deg)' : 'rotate(0deg)',
                              transition: 'transform 0.2s',
                            }}
                          >
                            <polyline points="6 9 12 15 18 9" />
                          </svg>
                        </button>

                        {expandedActions[msg.id] && (
                          <div style={{
                            marginTop: '8px',
                            padding: '10px 14px',
                            borderRadius: '10px',
                            border: `1px solid ${theme.border}`,
                            backgroundColor: '#FAFAF8',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                          }}>
                            {msg.actions.map((action: ActionDetail, idx: number) => (
                              <div key={idx} style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                fontSize: '12px',
                                color: theme.textSecondary,
                                fontFamily: font,
                              }}>
                                <ActionIcon type={action.icon} />
                                <span>{action.text}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Streaming indicator */}
            {isStreaming && (
              <div style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <div style={{ width: '30px', height: '30px', borderRadius: '50%', overflow: 'hidden', flexShrink: 0 }}>
                    <Image src="/owl.png" alt="AI" width={30} height={30} style={{ objectFit: 'contain' }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    {/* Live actions */}
                    {streamingActions.length > 0 && !streamingText && (
                      <div style={{
                        display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '8px',
                      }}>
                        {streamingActions.map((action, idx) => (
                          <div key={idx} style={{
                            display: 'flex', alignItems: 'center', gap: '8px',
                            fontSize: '12px', color: theme.textSecondary, fontFamily: font,
                          }}>
                            <div style={{
                              width: '6px', height: '6px', borderRadius: '50%',
                              backgroundColor: idx === streamingActions.length - 1 ? theme.amber : theme.success,
                              animation: idx === streamingActions.length - 1 ? 'pulse 1s infinite' : 'none',
                            }} />
                            <span>{action.text}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {/* Streaming text */}
                    {streamingText && (
                      <div style={{
                        fontSize: '14px', lineHeight: '1.6', color: theme.textPrimary,
                        fontFamily: font, whiteSpace: 'pre-wrap',
                      }}>
                        {streamingText}
                        <span style={{ display: 'inline-block', width: '6px', height: '14px', backgroundColor: theme.primary, marginLeft: '2px', animation: 'blink 1s step-end infinite' }} />
                      </div>
                    )}
                    {/* Loading dots when no content yet */}
                    {!streamingText && streamingActions.length === 0 && (
                      <div style={{ fontSize: '14px', color: theme.textMuted, fontFamily: font }}>
                        Thinking...
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Reply input */}
          <div style={{
            padding: '16px 24px',
            borderTop: `1px solid ${theme.border}`,
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: '#F7F5F3',
              borderRadius: '12px',
              padding: '10px 16px',
              border: `1px solid ${theme.border}`,
            }}>
              <button style={{
                width: '28px', height: '28px', borderRadius: '50%', border: 'none',
                backgroundColor: 'transparent', cursor: 'pointer', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={theme.textMuted} strokeWidth="2" strokeLinecap="round">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
                </svg>
              </button>
              <input
                placeholder={activeSession ? "Reply..." : "What would you like to research?"}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                disabled={isStreaming}
                style={{
                  flex: 1, border: 'none', outline: 'none', fontSize: '14px',
                  fontFamily: font, color: theme.textPrimary, backgroundColor: 'transparent',
                  opacity: isStreaming ? 0.5 : 1,
                }}
              />
              <button
                onClick={handleSend}
                disabled={!inputValue.trim() || isStreaming}
                style={{
                  width: '30px', height: '30px', borderRadius: '50%', border: 'none',
                  backgroundColor: inputValue.trim() && !isStreaming ? theme.primary : theme.border,
                  cursor: inputValue.trim() && !isStreaming ? 'pointer' : 'not-allowed',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'background-color 0.15s',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Right Panel */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          backgroundColor: theme.pageBg,
        }}>
          {/* 2-column grid: Plan + Brief */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '16px',
            alignItems: 'start',
          }}>
            {/* Plan Card */}
            <div style={{
              backgroundColor: theme.cardBg,
              borderRadius: '12px',
              border: `1px solid ${theme.border}`,
              overflow: 'hidden',
            }}>
              <div style={{
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: `1px solid ${theme.border}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.amber} strokeWidth="2" strokeLinecap="round">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 6v6l4 2" />
                  </svg>
                  <h3 style={{
                    fontSize: '15px', fontWeight: 600, color: theme.textPrimary,
                    fontFamily: font, margin: 0,
                  }}>Plan</h3>
                </div>
              </div>

              <div style={{ padding: '14px 18px' }}>
                {plan.length > 0 ? plan.map((phase: PlanPhase) => (
                  <div key={phase.id} style={{ marginBottom: '16px' }}>
                    <div style={{
                      fontSize: '13px', fontWeight: 600, color: theme.textPrimary,
                      fontFamily: font, marginBottom: '10px',
                    }}>
                      {phase.title}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0px', position: 'relative' }}>
                      {phase.items.map((item, idx) => (
                        <div key={idx} style={{
                          display: 'flex', alignItems: 'flex-start', gap: '10px',
                          padding: '6px 8px', borderRadius: '6px', position: 'relative',
                        }}>
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                            <StatusDot status={item.status} />
                            {idx < phase.items.length - 1 && (
                              <div style={{ width: '1px', height: '18px', backgroundColor: theme.border, marginTop: '2px' }} />
                            )}
                          </div>
                          <span style={{
                            fontSize: '12.5px', fontFamily: font, lineHeight: '1.4',
                            color: item.status === 'done' ? statusColors.done.text :
                                   item.status === 'active' ? theme.textPrimary : theme.textMuted,
                            textDecoration: item.status === 'done' ? 'line-through' : 'none',
                          }}>
                            {item.text}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )) : (
                  <div style={{ fontSize: '12.5px', color: theme.textMuted, fontFamily: font, fontStyle: 'italic' }}>
                    Start a research question to generate a plan...
                  </div>
                )}
              </div>
            </div>

            {/* Research Brief Card */}
            <div style={{
              backgroundColor: theme.cardBg,
              borderRadius: '12px',
              border: `1px solid ${theme.border}`,
              overflow: 'hidden',
            }}>
              <div style={{
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: `1px solid ${theme.border}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round">
                    <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2zM22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
                  </svg>
                  <h3 style={{
                    fontSize: '15px', fontWeight: 600, color: theme.textPrimary,
                    fontFamily: font, margin: 0,
                  }}>Research brief</h3>
                </div>
              </div>

              <div style={{ padding: '14px 18px' }}>
                {brief.heading ? (
                  <>
                    <div style={{
                      fontSize: '13px', fontWeight: 600, color: theme.textPrimary,
                      fontFamily: font, marginBottom: '8px',
                    }}>
                      {brief.heading}
                    </div>
                    <p style={{
                      fontSize: '12.5px', lineHeight: '1.6', color: theme.textSecondary,
                      fontFamily: font, margin: 0,
                    }}>
                      {brief.description}
                    </p>
                    {brief.keyPoints && brief.keyPoints.length > 0 && (
                      <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {brief.keyPoints.map((point, idx) => (
                          <div key={idx} style={{
                            display: 'flex', alignItems: 'center', gap: '8px',
                            fontSize: '12px', color: theme.textSecondary, fontFamily: font,
                          }}>
                            <div style={{
                              width: '5px', height: '5px', borderRadius: '50%',
                              backgroundColor: theme.primary, flexShrink: 0,
                            }} />
                            {point}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ fontSize: '12.5px', color: theme.textMuted, fontFamily: font, fontStyle: 'italic' }}>
                    Research findings will appear here...
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Context Card (NEW — full width below the grid) */}
          {(context.documents.length > 0 || context.pubmed_papers.length > 0) && (
            <div style={{
              marginTop: '16px',
              backgroundColor: theme.cardBg,
              borderRadius: '12px',
              border: `1px solid ${theme.border}`,
              overflow: 'hidden',
            }}>
              <div style={{
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                borderBottom: `1px solid ${theme.border}`,
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.textSecondary} strokeWidth="2" strokeLinecap="round">
                  <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
                </svg>
                <h3 style={{
                  fontSize: '15px', fontWeight: 600, color: theme.textPrimary,
                  fontFamily: font, margin: 0,
                }}>Context</h3>
                <span style={{ fontSize: '12px', color: theme.textMuted, fontFamily: font, marginLeft: 'auto' }}>
                  {context.documents.length + context.pubmed_papers.length} sources
                </span>
              </div>

              <div style={{ padding: '14px 18px' }}>
                {/* Internal documents */}
                {context.documents.length > 0 && (
                  <div style={{ marginBottom: context.pubmed_papers.length > 0 ? '16px' : 0 }}>
                    <div style={{
                      fontSize: '11px', fontWeight: 600, color: theme.textMuted,
                      fontFamily: font, marginBottom: '8px', textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}>
                      Knowledge Base
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {context.documents.slice(0, 6).map((doc, idx) => (
                        <div key={idx} style={{
                          display: 'flex', alignItems: 'flex-start', gap: '8px',
                          padding: '8px 10px', borderRadius: '8px',
                          border: `1px solid ${theme.border}`, backgroundColor: '#FAFAF8',
                        }}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.success} strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0, marginTop: '2px' }}>
                            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              fontSize: '12.5px', fontWeight: 500, color: theme.textPrimary,
                              fontFamily: font, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            }}>
                              {doc.title}
                            </div>
                            {doc.preview && (
                              <div style={{
                                fontSize: '11.5px', color: theme.textMuted, fontFamily: font,
                                marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}>
                                {doc.preview}
                              </div>
                            )}
                          </div>
                          {doc.score !== undefined && doc.score > 0 && (
                            <span style={{
                              fontSize: '10px', color: theme.success, fontFamily: font, fontWeight: 600,
                              flexShrink: 0, padding: '2px 6px', borderRadius: '4px',
                              backgroundColor: statusColors.done.bg,
                            }}>
                              {(doc.score * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* PubMed papers */}
                {context.pubmed_papers.length > 0 && (
                  <div>
                    <div style={{
                      fontSize: '11px', fontWeight: 600, color: theme.textMuted,
                      fontFamily: font, marginBottom: '8px', textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}>
                      PubMed
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {context.pubmed_papers.slice(0, 6).map((paper, idx) => (
                        <div key={idx} style={{
                          display: 'flex', alignItems: 'flex-start', gap: '8px',
                          padding: '8px 10px', borderRadius: '8px',
                          border: `1px solid ${theme.border}`, backgroundColor: '#FAFAF8',
                        }}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0, marginTop: '2px' }}>
                            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
                          </svg>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              fontSize: '12.5px', fontWeight: 500, color: theme.textPrimary,
                              fontFamily: font, overflow: 'hidden', textOverflow: 'ellipsis',
                              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any,
                            }}>
                              {paper.url ? (
                                <a href={paper.url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
                                  {paper.title}
                                </a>
                              ) : paper.title}
                            </div>
                            <div style={{ fontSize: '11px', color: theme.textMuted, fontFamily: font, marginTop: '2px' }}>
                              {paper.authors?.slice(0, 3).join(', ')}{paper.authors && paper.authors.length > 3 ? ' et al.' : ''} {paper.year ? `(${paper.year})` : ''}
                              {paper.journal ? ` — ${paper.journal}` : ''}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Hypothesis Cards (full width, below context) */}
          {hypotheses.length > 0 && (
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {hypotheses.map((hyp: Hypothesis) => (
                <div key={hyp.id} style={{
                  backgroundColor: theme.cardBg,
                  borderRadius: '12px',
                  border: `1px solid ${theme.border}`,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    padding: '14px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    borderBottom: `1px solid ${theme.border}`,
                  }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={
                      hyp.status === 'supported' ? theme.success :
                      hyp.status === 'refuted' ? '#D97373' :
                      theme.amber
                    } strokeWidth="2" strokeLinecap="round">
                      <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <h3 style={{ fontSize: '15px', fontWeight: 600, color: theme.textPrimary, fontFamily: font, margin: 0, flex: 1 }}>
                      Hypothesis
                    </h3>
                    <span style={{
                      fontSize: '11px', fontWeight: 600, fontFamily: font,
                      padding: '3px 10px', borderRadius: '12px',
                      backgroundColor: hyp.status === 'supported' ? '#F0F7EE' :
                                       hyp.status === 'refuted' ? '#FEF0F0' :
                                       hyp.status === 'testing' ? theme.amberLight : '#F5F5F5',
                      color: hyp.status === 'supported' ? '#5A7D54' :
                             hyp.status === 'refuted' ? '#C44' :
                             hyp.status === 'testing' ? '#9A7520' : theme.textMuted,
                    }}>
                      {hyp.status} ({(hyp.confidence_score * 100).toFixed(0)}%)
                    </span>
                  </div>
                  <div style={{ padding: '14px 18px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 500, color: theme.textPrimary, fontFamily: font, marginBottom: '8px' }}>
                      {hyp.statement}
                    </div>
                    <div style={{ display: 'flex', gap: '12px', marginTop: '10px' }}>
                      <span style={{ fontSize: '12px', fontFamily: font, color: theme.success }}>
                        {hyp.supporting_count} supporting
                      </span>
                      <span style={{ fontSize: '12px', fontFamily: font, color: '#D97373' }}>
                        {hyp.contradicting_count} contradicting
                      </span>
                      <span style={{ fontSize: '12px', fontFamily: font, color: theme.textMuted }}>
                        {hyp.neutral_count} neutral
                      </span>
                    </div>
                    {hyp.assessment && (
                      <div style={{
                        marginTop: '12px', padding: '10px 12px', borderRadius: '8px',
                        backgroundColor: '#FAFAF8', border: `1px solid ${theme.border}`,
                        fontSize: '12.5px', lineHeight: '1.6', color: theme.textSecondary, fontFamily: font,
                        whiteSpace: 'pre-wrap', maxHeight: '200px', overflowY: 'auto',
                      }}>
                        {hyp.assessment}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom toolbar */}
      <div style={{
        borderTop: `1px solid ${theme.border}`,
        padding: '10px 24px',
        display: 'flex',
        justifyContent: 'center',
        gap: '8px',
        backgroundColor: theme.cardBg,
      }}>
        {[
          { icon: 'M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z', label: 'Chat' },
          { icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z', label: 'Search' },
          { icon: 'M12 5v14M5 12h14', label: 'Add' },
        ].map((item) => (
          <button
            key={item.label}
            title={item.label}
            style={{
              width: '36px', height: '36px', borderRadius: '8px', border: 'none',
              backgroundColor: 'transparent', cursor: 'pointer', display: 'flex',
              alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = theme.primaryLight }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={theme.textMuted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d={item.icon} />
            </svg>
          </button>
        ))}
      </div>

      {/* CSS animations for streaming */}
      <style jsx global>{`
        @keyframes blink {
          50% { opacity: 0; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}
