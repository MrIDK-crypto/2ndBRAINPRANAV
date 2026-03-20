'use client'

import React, { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { theme, font } from './theme'

// Co-researcher has its own dedicated backend on port 5010
const API_BASE = (process.env.NEXT_PUBLIC_CO_RESEARCHER_URL || 'http://localhost:5010') + '/api/co-researcher'

// Wellspring Warm Design System - matches 2nd Brain
const t = {
  bg: theme.pageBg,
  surface: theme.cardBg,
  border: theme.border,
  text: theme.textPrimary,
  textSec: theme.textSecondary,
  textMuted: theme.textMuted,
  accent: theme.primary,
  accentBg: theme.primaryLight,
  accentBorder: '#E8D5CF',
  font,
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  sessionId: string
}

export default function ChatPanel({ sessionId }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const msg = input.trim()
    if (!msg || loading) return

    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setInput('')
    setLoading(true)

    try {
      const resp = await fetch(`${API_BASE}/chat/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      })
      if (!resp.ok) throw new Error('Chat request failed')
      const data = await resp.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Something went wrong. Try again.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      borderRadius: 14, overflow: 'hidden',
      background: t.surface, border: `1px solid ${t.border}`,
    }}>
      <div style={{
        padding: '14px 20px', borderBottom: `1px solid ${t.border}`,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%', background: t.accent,
        }} />
        <span style={{ fontSize: 14, fontWeight: 600, color: t.text }}>Refine Translations</span>
        <span style={{ fontSize: 12, color: t.textMuted }}>
          Share constraints, ask questions, or push back
        </span>
      </div>

      {/* Messages */}
      <div style={{
        maxHeight: 400, overflowY: 'auto', padding: '16px 20px',
      }}>
        {messages.length === 0 && (
          <div style={{ color: t.textMuted, fontSize: 13, lineHeight: 1.6, padding: '8px 0' }}>
            The analysis is complete. You can now refine the translations by sharing constraints
            from your lab (&ldquo;we can&apos;t do X because Y&rdquo;), asking about alternative
            approaches, or questioning specific assumptions.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            marginBottom: 12,
            display: 'flex', gap: 10,
            flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
          }}>
            <div style={{
              maxWidth: '85%', padding: '10px 14px', borderRadius: 12,
              background: m.role === 'user' ? t.accent : t.bg,
              color: m.role === 'user' ? '#fff' : t.textSec,
              fontSize: 13, lineHeight: 1.6,
              borderBottomRightRadius: m.role === 'user' ? 4 : 12,
              borderBottomLeftRadius: m.role === 'user' ? 12 : 4,
            }}>
              {m.role === 'assistant' ? (
                <div className="co-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                </div>
              ) : m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
            <div style={{
              padding: '10px 14px', borderRadius: 12, borderBottomLeftRadius: 4,
              background: t.bg, color: t.textMuted, fontSize: 13,
            }}>
              <span style={{
                display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                border: `2px solid ${t.accent}30`, borderTopColor: t.accent,
                animation: 'co-spin 0.8s linear infinite',
              }} /> Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '12px 16px', borderTop: `1px solid ${t.border}`,
        display: 'flex', gap: 8,
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          placeholder="e.g. We can't make graded FBXL5 mutants because..."
          disabled={loading}
          style={{
            flex: 1, padding: '8px 12px', borderRadius: 8,
            border: `1px solid ${t.border}`, background: t.bg,
            fontSize: 13, color: t.text, outline: 'none',
            fontFamily: t.font,
          }}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || loading}
          style={{
            padding: '8px 16px', borderRadius: 8,
            background: input.trim() && !loading ? t.accent : '#e7e5e4',
            border: 'none', color: input.trim() && !loading ? '#fff' : '#a8a29e',
            fontSize: 13, fontWeight: 500, cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
          }}
        >Send</button>
      </div>
    </div>
  )
}
