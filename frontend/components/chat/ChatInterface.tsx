'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { flushSync } from 'react-dom'
import Sidebar from '../shared/Sidebar'
import Image from 'next/image'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { analytics } from '@/utils/analytics'
import mermaid from 'mermaid'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

interface Message {
  id: string
  text: string
  isUser: boolean
  sources?: any[]
  sourceMap?: { [key: string]: { name: string; doc_id: string } }
  attachments?: { name: string; type: string }[]
  isStreaming?: boolean  // True while streaming - shows plain text for performance
}

interface Conversation {
  id: string
  title: string | null
  created_at: string
  updated_at: string
  last_message_at: string
  is_archived: boolean
  is_pinned: boolean
  message_count: number
}

// Wellspring-Inspired Warm Design System
const warmTheme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  chatBg: '#FAF9F7',
  cardBg: '#FFFFFE',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  statusSuccess: '#9CB896',
}

// Initialize Mermaid for diagram rendering
if (typeof window !== 'undefined') {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'neutral',
    securityLevel: 'loose',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  })
}

// Mermaid diagram renderer component
const MermaidDiagram = ({ code }: { code: string }) => {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const [svg, setSvg] = React.useState<string>('')
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    const renderDiagram = async () => {
      try {
        const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`
        const { svg: renderedSvg } = await mermaid.render(id, code.trim())
        setSvg(renderedSvg)
        setError(null)
      } catch (e: any) {
        setError(e.message || 'Failed to render diagram')
        // Still show the raw mermaid code as fallback
      }
    }
    renderDiagram()
  }, [code])

  if (error) {
    return (
      <pre style={{ backgroundColor: '#1E1E2E', color: '#CDD6F4', borderRadius: '12px', padding: '16px', overflow: 'auto', margin: '12px 0', fontSize: '13px' }}>
        <code>{code}</code>
      </pre>
    )
  }

  return (
    <div
      ref={containerRef}
      style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '12px',
        padding: '16px',
        margin: '12px 0',
        border: '1px solid #E5E7EB',
        overflow: 'auto',
        textAlign: 'center',
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

const WelcomeCard = ({ icon, title, description, onClick }: any) => (
  <div
    onClick={onClick}
    style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'flex-start',
      gap: '8px',
      flex: 1,
      padding: '16px',
      borderRadius: '16px',
      backgroundColor: '#FFFFFE',
      border: `1px solid #F0EEEC`,
      cursor: 'pointer',
      transition: 'all 0.15s ease',
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.06)'
      e.currentTarget.style.transform = 'translateY(-2px)'
      e.currentTarget.style.borderColor = '#D4A59A'
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.boxShadow = 'none'
      e.currentTarget.style.transform = 'translateY(0)'
      e.currentTarget.style.borderColor = '#F0EEEC'
    }}
  >
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: '12px',
        backgroundColor: warmTheme.primaryLight,
        width: '40px',
        height: '40px'
      }}
    >
      <div style={{ width: '21.5px', height: '21.5px', flexShrink: 0 }}>
        <Image src={icon} alt={title} width={21.5} height={21.5} />
      </div>
    </div>
    <div>
      <h3 style={{
        color: warmTheme.textPrimary,
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        fontSize: '14px',
        fontWeight: 600,
        marginBottom: '4px'
      }}>
        {title}
      </h3>
      <p style={{
        color: warmTheme.textSecondary,
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        fontSize: '12px',
        lineHeight: 1.4
      }}>
        {description}
      </p>
    </div>
  </div>
)

export default function ChatInterface() {
  const { user, token, tenant, isLoading: authLoading, logout } = useAuth()
  const [activeItem, setActiveItem] = useState('ChatBot')
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Attachment state
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  // Chat History State
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)

  // Feedback & copy state (must be before any conditional returns)
  const [feedbackState, setFeedbackState] = useState<Record<string, 'up' | 'down'>>({})
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Auth headers for API calls
  const getAuthHeaders = () => {
    if (token) {
      return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
    }
    return { 'Content-Type': 'application/json' }
  }
  // Note: X-Tenant removed - tenant ID extracted from JWT on backend

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
  }

  // Handle file selection for chat attachments
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    // Add to existing attachments (max 5 files)
    const newFiles = Array.from(files).slice(0, 5 - attachedFiles.length)
    setAttachedFiles(prev => [...prev, ...newFiles])

    // Reset input for re-selection
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Remove an attached file
  const removeAttachment = (index: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index))
  }

  // Fetch chat history
  const fetchConversations = useCallback(async (): Promise<Conversation[]> => {
    if (!token) return []
    setIsLoadingHistory(true)
    try {
      const response = await axios.get(`${API_BASE}/chat/conversations`, {
        headers: getAuthHeaders()
      })
      if (response.data.success) {
        const convs = response.data.conversations || []
        setConversations(convs)
        return convs
      }
    } catch (error) {
      console.error('Error fetching conversations:', error)
    } finally {
      setIsLoadingHistory(false)
    }
    return []
  }, [token])

  // Load a specific conversation
  const loadConversation = async (conversationId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/chat/conversations/${conversationId}`, {
        headers: getAuthHeaders()
      })
      if (response.data.success) {
        const conv = response.data.conversation
        // Convert backend messages to frontend format
        const loadedMessages: Message[] = conv.messages.map((m: any) => ({
          id: m.id,
          text: m.content,
          isUser: m.role === 'user',
          sources: m.sources || [],
        }))
        setMessages(loadedMessages)
        setCurrentConversationId(conversationId)
      }
    } catch (error) {
      console.error('Error loading conversation:', error)
    }
  }

  // Save message to a conversation (pass convId explicitly to avoid stale state)
  const saveMessage = async (role: 'user' | 'assistant', content: string, sources?: any[], convId?: string) => {
    const targetId = convId || currentConversationId
    if (!targetId) return
    try {
      await axios.post(
        `${API_BASE}/chat/conversations/${targetId}/messages`,
        { role, content, sources: sources || [] },
        { headers: getAuthHeaders() }
      )
    } catch (error) {
      console.error('Error saving message:', error)
    }
  }

  // Create new conversation
  const createNewConversation = async (): Promise<string | null> => {
    try {
      const response = await axios.post(
        `${API_BASE}/chat/conversations`,
        {},
        { headers: getAuthHeaders() }
      )
      if (response.data.success) {
        return response.data.conversation.id
      }
    } catch (error) {
      console.error('Error creating conversation:', error)
    }
    return null
  }

  // Delete conversation
  const deleteConversation = async (conversationId: string) => {
    try {
      await axios.delete(`${API_BASE}/chat/conversations/${conversationId}`, {
        headers: getAuthHeaders()
      })
      setConversations(prev => prev.filter(c => c.id !== conversationId))
      if (currentConversationId === conversationId) {
        setMessages([])
        setCurrentConversationId(null)
      }
    } catch (error) {
      console.error('Error deleting conversation:', error)
    }
  }

  // useEffect must be called before any conditional returns
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Fetch conversations on mount and auto-load the most recent one from the cloud
  useEffect(() => {
    if (token) {
      fetchConversations().then((convs) => {
        // Auto-load the most recent conversation from the server (cloud-based memory)
        if (convs && convs.length > 0 && messages.length === 0 && !currentConversationId) {
          loadConversation(convs[0].id)
        }
      })
    }
  }, [token])

  // Handler for starting new chat
  const handleNewChat = () => {
    setMessages([])
    setCurrentConversationId(null)
  }

  // Show loading while checking auth (after all hooks)
  if (authLoading) {
    return (
      <div style={{
        display: 'flex',
        height: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: warmTheme.pageBg
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '32px',
            height: '32px',
            border: `2px solid ${warmTheme.border}`,
            borderTopColor: warmTheme.primary,
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 16px'
          }}></div>
          <p style={{ color: warmTheme.textSecondary }}>Loading...</p>
        </div>
      </div>
    )
  }

  const handleSend = async () => {
    if ((!inputValue.trim() && attachedFiles.length === 0) || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputValue,
      isUser: true,
      attachments: attachedFiles.map(f => ({ name: f.name, type: f.type }))
    }

    setMessages(prev => [...prev, userMessage])
    const queryText = inputValue
    setInputValue('')
    setIsLoading(true)

    // Track analytics
    analytics.chatQuestion(queryText.length)

    let uploadedDocIds: string[] = []

    // Step 1: Upload attachments if any
    if (attachedFiles.length > 0) {
      setIsUploading(true)
      try {
        const formData = new FormData()
        attachedFiles.forEach(file => formData.append('files', file))

        const uploadResponse = await axios.post(`${API_BASE}/documents/upload-and-embed`, formData, {
          headers: {
            'Authorization': token ? `Bearer ${token}` : '',
          }
        })

        if (uploadResponse.data.success) {
          uploadedDocIds = uploadResponse.data.documents.map((d: any) => d.id)
          console.log(`Uploaded and embedded ${uploadedDocIds.length} documents`)
        }
      } catch (error) {
        console.error('Upload failed:', error)
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: 'Failed to upload attachments. Please try again.',
          isUser: false,
        }
        setMessages(prev => [...prev, errorMessage])
        setIsLoading(false)
        setIsUploading(false)
        setAttachedFiles([])
        return
      } finally {
        setIsUploading(false)
        setAttachedFiles([])
      }
    }

    // Create new conversation if needed
    let convId = currentConversationId
    if (!convId) {
      convId = await createNewConversation()
      if (convId) {
        setCurrentConversationId(convId)
      }
    }

    // Save user message to conversation (pass convId explicitly since state may not have updated yet)
    if (convId) {
      await saveMessage('user', queryText, undefined, convId)
    }

    try {
      // Build conversation history from cloud - fetch full history from backend
      let conversationHistory: Array<{ role: string; content: string }> = []
      if (convId) {
        try {
          const historyResponse = await axios.get(
            `${API_BASE}/chat/conversations/${convId}`,
            { headers: getAuthHeaders() }
          )
          if (historyResponse.data.success) {
            const cloudMessages = historyResponse.data.conversation.messages || []
            // Use up to 500 messages from cloud for full memory
            conversationHistory = cloudMessages.slice(-500).map((m: any) => ({
              role: m.role,
              content: m.content
            }))
          }
        } catch (histErr) {
          console.error('Error fetching conversation history:', histErr)
        }
      }
      // Append the current user message that was just sent (not yet saved to cloud)
      conversationHistory.push({ role: 'user', content: queryText })

      // Use STREAMING search - words appear in real-time like GPT/Claude!
      const aiMessageId = (Date.now() + 1).toString()
      let streamedAnswer = ''
      let sourcesData: any[] = []
      let sourceMapData: { [key: string]: { name: string; doc_id: string; source_url: string } } = {}

      // Add placeholder AI message with typing indicator
      setMessages(prev => [...prev, {
        id: aiMessageId,
        text: '', // Empty - cursor is CSS animated
        isUser: false,
        sources: [],
        sourceMap: {},
        isStreaming: true,  // Mark as streaming for plain text rendering
      }])

      // Update DOM directly for instant streaming (bypass React for performance)
      const updateStreamingText = (text: string) => {
        const el = document.getElementById(`streaming-${aiMessageId}`)
        if (el) {
          // Update only the text node, keep the cursor element
          const textNode = el.firstChild
          if (textNode && textNode.nodeType === Node.TEXT_NODE) {
            textNode.textContent = text
          } else {
            el.insertBefore(document.createTextNode(text), el.firstChild)
          }
        }
      }

      // Use fetch for SSE streaming
      const streamResponse = await fetch(`${API_BASE}/search/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify({
          query: queryText,
          conversation_history: conversationHistory,
          top_k: 15,
          boost_doc_ids: uploadedDocIds
        })
      })

      if (!streamResponse.ok) {
        throw new Error(`Stream request failed: ${streamResponse.status}`)
      }

      const reader = streamResponse.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No reader available')
      }

      // Process SSE stream
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.content !== undefined) {
                // Chunk - append text and update DOM directly (instant!)
                streamedAnswer += data.content
                updateStreamingText(streamedAnswer)
              } else if (data.sources !== undefined) {
                // Done event - got final sources
                sourcesData = data.sources || []

                // Build source mapping
                sourcesData.forEach((s: any, idx: number) => {
                  const sourceName = s.title || `Source ${idx + 1}`
                  const doc_id = s.doc_id || ''
                  const source_url = s.source_url || ''
                  const cleanName = (sourceName.split('/').pop()?.replace(/^(space_msg_|File-)/, '') || sourceName).replace(/:/g, ' -')
                  sourceMapData[`Source ${idx + 1}`] = { name: cleanName, doc_id, source_url }
                  sourceMapData[cleanName] = { name: cleanName, doc_id, source_url }
                })
              } else if (data.error) {
                throw new Error(data.error)
              }
            } catch (e) {
              // Ignore parse errors for partial data
            }
          }
        }
      }

      // Clean up the streamed answer (same cleanup as before)
      let cleanedAnswer = streamedAnswer
      cleanedAnswer = cleanedAnswer.replace(/Sources Used:.*$/gm, '')
      cleanedAnswer = cleanedAnswer.replace(/.*Citation Coverage:.*$/gm, '')
      cleanedAnswer = cleanedAnswer.replace(/^.*📊.*$/gm, '')
      cleanedAnswer = cleanedAnswer.replace(/^.*📄 Sources:.*$/gm, '')
      cleanedAnswer = cleanedAnswer.replace(/\n{3,}/g, '\n\n').trim()

      // Replace [Source X] with markers
      cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+)\]/g, (match: string, num: string) => {
        const source = sourceMapData[`Source ${num}`]
        return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : ''
      })
      cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+), Source (\d+)\]/g, (match: string, num1: string, num2: string) => {
        const source1 = sourceMapData[`Source ${num1}`]
        const source2 = sourceMapData[`Source ${num2}`]
        const parts = []
        if (source1) parts.push(`[[SOURCE:${source1.name}:${source1.doc_id}:${source1.source_url || ''}]]`)
        if (source2) parts.push(`[[SOURCE:${source2.name}:${source2.doc_id}:${source2.source_url || ''}]]`)
        return parts.join(', ')
      })
      cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+(?:,\s*\d+)+)\]/g, (match: string, nums: string) => {
        const numbers = nums.split(/,\s*/)
        return numbers.map((n: string) => {
          const source = sourceMapData[`Source ${n.trim()}`]
          return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : null
        }).filter(Boolean).join(', ')
      })
      cleanedAnswer = cleanedAnswer.replace(/\[Sources (\d+(?:,\s*\d+)+)\]/gi, (match: string, nums: string) => {
        const numbers = nums.split(/,\s*/)
        return numbers.map((n: string) => {
          const source = sourceMapData[`Source ${n.trim()}`]
          return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : null
        }).filter(Boolean).join(', ')
      })
      cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+):\s*[^\]]+\]/g, (match: string, num: string) => {
        const source = sourceMapData[`Source ${num}`]
        return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : ''
      })
      cleanedAnswer = cleanedAnswer.replace(/\[(\d+)\]/g, (match: string, num: string) => {
        const source = sourceMapData[`Source ${num}`]
        return source ? `[[SOURCE:${source.name}:${source.doc_id}:${source.source_url || ''}]]` : ''
      })
      cleanedAnswer = cleanedAnswer.replace(/\[Sources?\s*\d+(?:,\s*\d+)*\]/gi, '')
      cleanedAnswer = cleanedAnswer.replace(/(\[\[SOURCE:([^:]+):[^\]]+\]\])(?:\s*,?\s*\[\[SOURCE:\2:[^\]]+\]\])+/g, '$1')
      cleanedAnswer = cleanedAnswer.replace(/\]\]\s+\[\[SOURCE:/g, ']], [[SOURCE:')
      cleanedAnswer = cleanedAnswer.replace(/,\s*,/g, ',')
      cleanedAnswer = cleanedAnswer.replace(/[^\S\n]{2,}/g, ' ')
      cleanedAnswer = cleanedAnswer.replace(/\n{3,}/g, '\n\n')

      const aiSources = sourcesData.map((s: any, idx: number) => ({
        doc_id: s.doc_id,
        subject: s.title || `Source ${idx + 1}`,
        project: 'Unknown',
        score: s.score,
        content: (s.content_preview || '').substring(0, 200) + '...',
        source_url: s.source_url || ''
      }))

      // Final update with cleaned answer and sources - disable streaming mode for markdown rendering
      setMessages(prev => prev.map(m =>
        m.id === aiMessageId ? { ...m, text: cleanedAnswer, sources: aiSources, sourceMap: sourceMapData, isStreaming: false } : m
      ))

      // Save to conversation
      if (convId) {
        saveMessage('assistant', cleanedAnswer, aiSources, convId)
        fetchConversations()
      }
    } catch (error: any) {
      console.error('Error:', error)
      // Extract actual error message for better debugging
      let errorText = 'Sorry, I encountered an error.'
      if (error.response?.data?.error) {
        errorText += ` Error: ${error.response.data.error}`
      } else if (error.response?.status) {
        errorText += ` Server returned status ${error.response.status}.`
      } else if (error.message) {
        errorText += ` ${error.message}`
      }
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: errorText,
        isUser: false,
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuickAction = (prompt: string) => {
    setInputValue(prompt)
  }

  // Voice recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRecorderRef.current = new MediaRecorder(stream)
      chunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach(track => track.stop())
        await transcribeAudio(audioBlob)
      }

      mediaRecorderRef.current.start()
      setIsRecording(true)
    } catch (error) {
      console.error('Recording error:', error)
      alert('Could not access microphone. Please allow microphone access.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const transcribeAudio = async (audioBlob: Blob) => {
    setIsTranscribing(true)
    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')

      const response = await axios.post(`${API_BASE}/knowledge/transcribe`, formData, {
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
        }
      })

      if (response.data.success && response.data.transcription?.text) {
        // Append transcribed text to input
        setInputValue(prev => prev ? `${prev} ${response.data.transcription.text}` : response.data.transcription.text)
      }
    } catch (error) {
      console.error('Transcription error:', error)
      alert('Failed to transcribe audio. Please try again.')
    } finally {
      setIsTranscribing(false)
    }
  }

  // Render markdown text with proper formatting
  const renderMarkdownMessage = (text: string) => {
    // Pre-process: Fix tables that LLM generates incorrectly

    // Step 1: Unwrap pipe-delimited tables from code fences
    let preprocessed = text.replace(/```[^\n]*\n((?:\s*\|.*\|\s*\n)+)```/g, '\n$1\n')

    // Step 2: Convert tabular data inside code blocks to proper markdown tables
    // (LLM sometimes puts space/tab-separated data in code blocks instead of using | pipes)
    preprocessed = preprocessed.replace(/```[^\n]*\n([\s\S]*?)```/g, (match: string, inner: string) => {
      const lines = inner.trim().split('\n').filter((l: string) => l.trim())
      if (lines.length < 2) return match

      // Skip if it contains obvious code syntax
      if (lines.some((l: string) => /[{}();=<>\\]|\/\/|def |class |import |function |const |let |var |return |=>/.test(l))) {
        return match
      }

      // Try splitting by tabs or 2+ spaces
      const splitLine = (line: string) => line.trim().split(/\t+|\s{2,}/).filter((c: string) => c.trim())
      const rows = lines.map(splitLine)

      // Check all rows have >= 2 columns (otherwise it's not tabular data)
      if (!rows.every((r: string[]) => r.length >= 2)) return match

      // Build proper markdown table
      const header = rows[0]
      const separator = header.map(() => '---')
      let table = '| ' + header.join(' | ') + ' |\n'
      table += '| ' + separator.join(' | ') + ' |\n'
      for (const row of rows.slice(1)) {
        while (row.length < header.length) row.push('')
        table += '| ' + row.slice(0, header.length).join(' | ') + ' |\n'
      }

      return '\n' + table + '\n'
    })

    // Step 3: Add missing separator row to pipe tables
    // (e.g., |Header1|Header2| followed by |Data1|Data2| without |---|---| between)
    preprocessed = preprocessed.replace(
      /(\|[^|\n]+(?:\|[^|\n]+)+\|)[ \t]*\n(?!\s*\|[\s\-:]+[\s\-:|]*\n)/g,
      (match: string, headerRow: string) => {
        // Only fix if the NEXT line also looks like a table row (has pipes)
        const nextLineMatch = preprocessed.slice(preprocessed.indexOf(match) + headerRow.length).match(/^\s*\n(\|[^|\n]+\|)/)
        if (!nextLineMatch) return match
        const cols = headerRow.split('|').filter((c: string) => c.trim() !== '')
        const separator = '| ' + cols.map(() => '---').join(' | ') + ' |'
        return headerRow + '\n' + separator + '\n'
      }
    )

    // Pre-process: Convert [[SOURCE:name:doc_id]] markers into markdown links
    const sourceToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
    const processedText = preprocessed.replace(
      /\[\[SOURCE:([^:]+):([^:\]]+):?([^\]]*)\]\]/g,
      (match: string, name: string, docId: string, sourceUrl: string) => {
        // Use source_url directly if available (e.g., GitHub file links)
        if (sourceUrl) {
          return `[${name}](${sourceUrl})`
        }
        const hasValidDocId = docId && docId.length >= 32
        if (hasValidDocId && sourceToken) {
          const url = `${API_BASE}/documents/${encodeURIComponent(docId)}/view?token=${encodeURIComponent(sourceToken)}`
          return `[${name}](${url})`
        } else if (hasValidDocId) {
          return `[${name}](${API_BASE}/documents/${encodeURIComponent(docId)}/view)`
        }
        return `**${name}**`
      }
    )

    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Style code blocks — detect mermaid and render as diagrams
          code: ({ className, children, ...props }: any) => {
            const isMermaid = className === 'language-mermaid'
            if (isMermaid) {
              const codeStr = String(children).replace(/\n$/, '')
              return <MermaidDiagram code={codeStr} />
            }
            // If inside a pre (block code) — className is set for language-tagged blocks
            if (className) {
              return (
                <code style={{ fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, monospace', fontSize: '13px', lineHeight: '1.6' }} {...props}>
                  {children}
                </code>
              )
            }
            // Inline code
            return (
              <code style={{ backgroundColor: '#E5E7EB', padding: '2px 6px', borderRadius: '4px', fontSize: '0.9em', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', color: '#374151' }} {...props}>
                {children}
              </code>
            )
          },
          // Style pre blocks (code containers) — all block code goes through pre
          pre: ({ children }: any) => {
            // Check if child is a MermaidDiagram (already rendered)
            const childProps = React.Children.toArray(children)?.[0] as any
            if (childProps?.type === MermaidDiagram) {
              return <>{children}</>
            }
            return (
              <pre style={{ backgroundColor: '#1E1E2E', color: '#CDD6F4', borderRadius: '12px', padding: '16px', overflow: 'auto', margin: '12px 0', fontSize: '13px', lineHeight: '1.6', fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, monospace' }}>
                {children}
              </pre>
            )
          },
          // Style paragraphs
          p: ({ children }: any) => (
            <p className="mb-3 last:mb-0">{children}</p>
          ),
          // Style headers
          h1: ({ children }: any) => <h1 className="text-xl font-bold mb-3 mt-4">{children}</h1>,
          h2: ({ children }: any) => <h2 className="text-lg font-bold mb-2 mt-3">{children}</h2>,
          h3: ({ children }: any) => <h3 className="text-base font-semibold mb-2 mt-2">{children}</h3>,
          // Style lists
          ul: ({ children }: any) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
          ol: ({ children }: any) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
          li: ({ children }: any) => <li className="mb-1">{children}</li>,
          // Style links
          a: ({ href, children }: any) => (
            <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: '#8B5E4B', fontWeight: 500, textDecoration: 'underline', textUnderlineOffset: '2px' }} onMouseEnter={(e) => e.currentTarget.style.color = '#6B4436'} onMouseLeave={(e) => e.currentTarget.style.color = '#8B5E4B'}>
              {children}
            </a>
          ),
          // Style blockquotes
          blockquote: ({ children }: any) => (
            <blockquote className="border-l-4 border-gray-300 pl-4 italic my-3 text-gray-600">
              {children}
            </blockquote>
          ),
          // Style strong/bold
          strong: ({ children }: any) => <strong className="font-semibold">{children}</strong>,
          // Style tables (GFM)
          table: ({ children }: any) => (
            <div className="overflow-x-auto my-3">
              <table className="min-w-full border-collapse text-sm" style={{ border: '1px solid #D1D5DB', borderRadius: '8px' }}>
                {children}
              </table>
            </div>
          ),
          thead: ({ children }: any) => (
            <thead style={{ backgroundColor: '#E5E7EB' }}>{children}</thead>
          ),
          tbody: ({ children }: any) => (
            <tbody>{children}</tbody>
          ),
          tr: ({ children }: any) => (
            <tr style={{ borderBottom: '1px solid #D1D5DB' }}>{children}</tr>
          ),
          th: ({ children }: any) => (
            <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#1F2937', border: '1px solid #D1D5DB', backgroundColor: '#E5E7EB' }}>{children}</th>
          ),
          td: ({ children }: any) => (
            <td style={{ padding: '10px 14px', color: '#374151', border: '1px solid #D1D5DB', backgroundColor: '#F9FAFB' }}>{children}</td>
          ),
        }}
      >
        {processedText}
      </ReactMarkdown>
    )
  }

  const handleFeedback = async (message: Message, rating: 'up' | 'down') => {
    // Toggle off if same rating clicked again
    if (feedbackState[message.id] === rating) {
      setFeedbackState(prev => { const n = { ...prev }; delete n[message.id]; return n })
      return
    }
    setFeedbackState(prev => ({ ...prev, [message.id]: rating }))
    try {
      await axios.post(`${API_BASE}/feedback`, {
        query: messages.find(m => m.isUser && parseInt(m.id) < parseInt(message.id))?.text || '',
        answer: message.text,
        rating: rating,
        source_ids: message.sources?.map(s => s.doc_id) || []
      }, {
        headers: getAuthHeaders()
      })
      analytics.feedbackGiven(rating)
    } catch (error) {
      console.error('Error submitting feedback:', error)
    }
  }

  const handleCopy = async (message: Message) => {
    try {
      await navigator.clipboard.writeText(message.text)
      setCopiedId(message.id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      // Fallback for non-HTTPS
      const textarea = document.createElement('textarea')
      textarea.value = message.text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopiedId(message.id)
      setTimeout(() => setCopiedId(null), 2000)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ backgroundColor: warmTheme.pageBg }}>
      {/* Sidebar - Always Visible */}
      <Sidebar
        activeItem={activeItem}
        onItemClick={setActiveItem}
        userName={user?.full_name?.split(' ')[0] || 'User'}
        conversations={conversations}
        currentConversationId={currentConversationId}
        onLoadConversation={loadConversation}
        onDeleteConversation={deleteConversation}
        onNewChat={handleNewChat}
        isLoadingHistory={isLoadingHistory}
      />

      {/* Main Content - Full page chat */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Chat Area */}
        <div className="flex-1 flex items-center justify-center px-8 overflow-hidden" style={{ backgroundColor: warmTheme.chatBg }}>
          <div
            className="flex flex-col items-center gap-3 rounded-3xl px-5 pt-3 pb-3 w-full"
            style={{ maxWidth: '1000px', height: '100%', backgroundColor: '#F7F5F3', border: '1px solid #F0EEEC' }}
          >
            {/* Messages or Welcome Screen */}
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-6 w-full overflow-auto">
                <div style={{ textAlign: 'center' }}>
                  <div style={{
                    width: '64px',
                    height: '80px',
                    margin: '0 auto 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <Image src="/owl.png" alt="2nd Brain" width={64} height={80} style={{ objectFit: 'contain' }} />
                  </div>
                  <h2 style={{
                    color: warmTheme.textPrimary,
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    fontSize: '26px',
                    fontWeight: 700,
                    marginBottom: '8px'
                  }}>
                    Hi {user?.full_name?.split(' ')[0] || 'there'}!
                  </h2>
                  <p style={{
                    color: warmTheme.textSecondary,
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    fontSize: '15px',
                    marginBottom: '6px'
                  }}>
                    Ask me anything about your knowledge base.
                  </p>
                  <p style={{
                    color: warmTheme.textMuted,
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    fontSize: '13px'
                  }}>
                    Or try one of these to get started:
                  </p>
                </div>

                {/* Quick Actions Grid */}
                <div className="grid grid-cols-3 gap-3 w-full max-w-3xl px-4">
                  <WelcomeCard
                    icon="/Research.svg"
                    title="Search Knowledge"
                    description="Find info across all your connected sources."
                    onClick={() => handleQuickAction("What do we know about...")}
                  />
                  <WelcomeCard
                    icon="/Project.svg"
                    title="Understand Context"
                    description="Get background on past decisions and projects."
                    onClick={() => handleQuickAction("What was the reasoning behind...")}
                  />
                  <WelcomeCard
                    icon="/Article.svg"
                    title="Onboard Faster"
                    description="Learn about processes and team knowledge."
                    onClick={() => handleQuickAction("Help me understand how we handle...")}
                  />
                  <WelcomeCard
                    icon="/Data.svg"
                    title="Find Documents"
                    description="Search through synced emails and files."
                    onClick={() => handleQuickAction("Find all documents related to...")}
                  />
                  <WelcomeCard
                    icon="/PPT.svg"
                    title="Explore Topics"
                    description="Discover what your team knows about a subject."
                    onClick={() => handleQuickAction("What information do we have on...")}
                  />
                  <WelcomeCard
                    icon="/Code.svg"
                    title="Summarize Content"
                    description="Get summaries of documents or threads."
                    onClick={() => handleQuickAction("Summarize the key points from...")}
                  />
                </div>
              </div>
            ) : (
              <div className="flex-1 w-full overflow-y-auto px-4 space-y-4 scrollbar-thin">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    style={{
                      display: 'flex',
                      justifyContent: message.isUser ? 'flex-end' : 'flex-start'
                    }}
                  >
                    <div
                      style={{
                        padding: '16px 20px',
                        borderRadius: '16px',
                        maxWidth: message.isUser ? '60%' : '100%',
                        backgroundColor: message.isUser ? '#FFFFFF' : '#FFFFFF',
                        border: message.isUser ? `1px solid ${warmTheme.border}` : 'none',
                        boxShadow: message.isUser ? '0 1px 3px rgba(0,0,0,0.04)' : 'none'
                      }}
                    >
                      <div style={{
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                        fontSize: '15px',
                        lineHeight: '1.6',
                        color: warmTheme.textPrimary
                      }}>
                        {message.isUser ? message.text : (message.isStreaming ? (
                          <span
                            id={`streaming-${message.id}`}
                            style={{
                              whiteSpace: 'pre-wrap',
                              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                            }}
                          >
                            {message.text}
                            <span
                              className="streaming-cursor"
                              style={{
                                display: 'inline-block',
                                width: '2px',
                                height: '1.1em',
                                backgroundColor: warmTheme.primary,
                                marginLeft: '2px',
                                verticalAlign: 'text-bottom',
                                animation: 'blink 1s step-end infinite',
                              }}
                            />
                          </span>
                        ) : renderMarkdownMessage(message.text))}
                      </div>

                      {/* Display attachments for user messages */}
                      {message.isUser && message.attachments && message.attachments.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {message.attachments.map((att, idx) => (
                            <span key={idx} style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 8px',
                              backgroundColor: warmTheme.primaryLight,
                              borderRadius: '12px',
                              fontSize: '12px',
                              color: warmTheme.primary
                            }}>
                              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z" clipRule="evenodd" />
                              </svg>
                              {att.name}
                            </span>
                          ))}
                        </div>
                      )}

                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {message.sources
                            .filter((source, idx, arr) => arr.findIndex(s => (s.subject || s.doc_id) === (source.subject || source.doc_id)) === idx)
                            .slice(0, 5).map((source, idx) => {
                            const sourceToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
                            // Only create clickable link if doc_id exists and looks like a valid UUID
                            const hasValidDocId = source.doc_id && source.doc_id.length >= 32
                            // Use source_url directly if available (e.g., GitHub file links), otherwise fall back to document view
                            const sourceViewUrl = source.source_url
                              ? source.source_url
                              : hasValidDocId
                                ? `${API_BASE}/documents/${encodeURIComponent(source.doc_id)}/view${sourceToken ? `?token=${encodeURIComponent(sourceToken)}` : ''}`
                                : null
                            return (
                            <div key={idx} className="group relative inline-block">
                              {sourceViewUrl ? (
                                <a
                                  href={sourceViewUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                    padding: '4px 10px',
                                    borderRadius: '12px',
                                    backgroundColor: warmTheme.primaryLight,
                                    fontSize: '12px',
                                    color: warmTheme.primary,
                                    textDecoration: 'none',
                                    transition: 'all 0.15s ease'
                                  }}
                                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#F5EBE7'}
                                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = warmTheme.primaryLight}
                                >
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                  <span style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{source.subject?.split('/').pop() || source.subject}</span>
                                </a>
                              ) : (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  padding: '4px 10px',
                                  borderRadius: '12px',
                                  backgroundColor: warmTheme.border,
                                  fontSize: '12px',
                                  color: warmTheme.textMuted
                                }}>
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                  <span style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{source.subject?.split('/').pop() || source.subject}</span>
                                </span>
                              )}
                              {/* Tooltip on hover */}
                              <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                                <div className="bg-gray-800 text-white text-xs rounded-lg px-3 py-2 max-w-[250px] shadow-lg">
                                  <p className="font-medium mb-1">{source.subject}</p>
                                  <p className="text-gray-300 text-[10px]">{source.project}</p>
                                </div>
                              </div>
                            </div>
                          )})}

                        </div>
                      )}

                      {/* Feedback buttons for AI responses */}
                      {!message.isUser && (
                        <div style={{
                          marginTop: '12px',
                          paddingTop: '12px',
                          borderTop: `1px solid ${warmTheme.border}`,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}>
                          <button
                            onClick={() => handleFeedback(message, 'up')}
                            style={{
                              padding: '6px',
                              background: feedbackState[message.id] === 'up' ? warmTheme.primaryLight : 'none',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              color: feedbackState[message.id] === 'up' ? warmTheme.primary : warmTheme.textMuted,
                              display: 'flex',
                              alignItems: 'center',
                              transition: 'all 0.15s'
                            }}
                            title="Good answer"
                            onMouseEnter={(e) => {
                              if (feedbackState[message.id] !== 'up') {
                                e.currentTarget.style.backgroundColor = warmTheme.border
                                e.currentTarget.style.color = warmTheme.primary
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (feedbackState[message.id] !== 'up') {
                                e.currentTarget.style.backgroundColor = 'transparent'
                                e.currentTarget.style.color = warmTheme.textMuted
                              }
                            }}
                          >
                            <svg width="16" height="16" fill={feedbackState[message.id] === 'up' ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleFeedback(message, 'down')}
                            style={{
                              padding: '6px',
                              background: feedbackState[message.id] === 'down' ? warmTheme.primaryLight : 'none',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              color: feedbackState[message.id] === 'down' ? warmTheme.primary : warmTheme.textMuted,
                              display: 'flex',
                              alignItems: 'center',
                              transition: 'all 0.15s'
                            }}
                            title="Poor answer"
                            onMouseEnter={(e) => {
                              if (feedbackState[message.id] !== 'down') {
                                e.currentTarget.style.backgroundColor = warmTheme.border
                                e.currentTarget.style.color = warmTheme.primary
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (feedbackState[message.id] !== 'down') {
                                e.currentTarget.style.backgroundColor = 'transparent'
                                e.currentTarget.style.color = warmTheme.textMuted
                              }
                            }}
                          >
                            <svg width="16" height="16" fill={feedbackState[message.id] === 'down' ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                            </svg>
                          </button>
                          <button
                            style={{
                              padding: '6px',
                              background: copiedId === message.id ? warmTheme.primaryLight : 'none',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              color: copiedId === message.id ? warmTheme.primary : warmTheme.textMuted,
                              display: 'flex',
                              alignItems: 'center',
                              marginLeft: '4px',
                              transition: 'all 0.15s'
                            }}
                            title={copiedId === message.id ? 'Copied!' : 'Copy response'}
                            onClick={() => handleCopy(message)}
                            onMouseEnter={(e) => {
                              if (copiedId !== message.id) {
                                e.currentTarget.style.backgroundColor = warmTheme.border
                                e.currentTarget.style.color = warmTheme.primary
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (copiedId !== message.id) {
                                e.currentTarget.style.backgroundColor = 'transparent'
                                e.currentTarget.style.color = warmTheme.textMuted
                              }
                            }}
                          >
                            {copiedId === message.id ? (
                              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                            ) : (
                              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="flex justify-start">
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '12px 20px',
                      background: warmTheme.primaryLight,
                      borderRadius: '16px',
                      border: `1px solid ${warmTheme.border}`
                    }}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <div style={{ width: '8px', height: '8px', backgroundColor: warmTheme.primary, borderRadius: '50%', animation: 'pulse 1.5s ease-in-out infinite' }}></div>
                        <div style={{ width: '8px', height: '8px', backgroundColor: warmTheme.primary, borderRadius: '50%', animation: 'pulse 1.5s ease-in-out infinite', animationDelay: '0.2s', opacity: 0.7 }}></div>
                        <div style={{ width: '8px', height: '8px', backgroundColor: warmTheme.primary, borderRadius: '50%', animation: 'pulse 1.5s ease-in-out infinite', animationDelay: '0.4s', opacity: 0.5 }}></div>
                      </div>
                      <span style={{ color: warmTheme.primary, fontSize: '14px', fontWeight: 500 }}>Thinking</span>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>
            )}

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls,.json,.md"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />

            {/* Upload progress indicator */}
            {isUploading && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 16px',
                backgroundColor: warmTheme.primaryLight,
                borderRadius: '12px',
                marginBottom: '8px'
              }}>
                <div style={{
                  width: '16px',
                  height: '16px',
                  border: `2px solid ${warmTheme.primary}`,
                  borderTopColor: 'transparent',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }}></div>
                <span style={{ fontSize: '14px', color: warmTheme.primary }}>
                  Uploading and processing documents...
                </span>
              </div>
            )}

            {/* Attached files preview */}
            {attachedFiles.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                {attachedFiles.map((file, idx) => (
                  <div key={idx} style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '6px 12px',
                    backgroundColor: warmTheme.border,
                    borderRadius: '20px',
                    fontSize: '14px'
                  }}>
                    <svg style={{ width: '16px', height: '16px', color: warmTheme.textSecondary }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: warmTheme.textPrimary }}>{file.name}</span>
                    <button
                      onClick={() => removeAttachment(idx)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: warmTheme.textMuted }}
                    >
                      <svg style={{ width: '16px', height: '16px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Input Box */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                alignSelf: 'stretch',
                backgroundColor: '#FFFFFF',
                borderRadius: '16px',
                border: `1px solid ${warmTheme.border}`,
                padding: '12px 16px',
                transition: 'border-color 0.2s'
              }}
            >
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || attachedFiles.length >= 5}
                title={attachedFiles.length >= 5 ? 'Max 5 files' : 'Attach files'}
                style={{
                  padding: '8px',
                  background: 'none',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: isUploading || attachedFiles.length >= 5 ? 'not-allowed' : 'pointer',
                  opacity: isUploading || attachedFiles.length >= 5 ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  transition: 'background-color 0.15s'
                }}
                onMouseEnter={(e) => {
                  if (!isUploading && attachedFiles.length < 5) {
                    e.currentTarget.style.backgroundColor = warmTheme.primaryLight
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent'
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={warmTheme.textSecondary} strokeWidth="2">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
                </svg>
              </button>

              <input
                type="text"
                placeholder={isTranscribing ? "Transcribing..." : attachedFiles.length > 0 ? "Ask about your documents..." : "Ask anything..."}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                disabled={isTranscribing}
                style={{
                  flex: 1,
                  border: 'none',
                  outline: 'none',
                  fontSize: '15px',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  color: warmTheme.textPrimary,
                  backgroundColor: 'transparent'
                }}
              />

              {/* Voice Recording Button */}
              <button
                onClick={() => isRecording ? stopRecording() : startRecording()}
                disabled={isLoading || isUploading || isTranscribing}
                title={isRecording ? 'Stop recording' : 'Start voice input'}
                style={{
                  padding: '8px',
                  background: isRecording ? warmTheme.primary : 'none',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: isLoading || isUploading || isTranscribing ? 'not-allowed' : 'pointer',
                  opacity: isLoading || isUploading || isTranscribing ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.15s'
                }}
                onMouseEnter={(e) => {
                  if (!isLoading && !isUploading && !isTranscribing && !isRecording) {
                    e.currentTarget.style.backgroundColor = warmTheme.primaryLight
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isRecording) {
                    e.currentTarget.style.backgroundColor = 'transparent'
                  }
                }}
              >
                {isTranscribing ? (
                  <div style={{
                    width: '20px',
                    height: '20px',
                    border: `2px solid ${warmTheme.border}`,
                    borderTopColor: warmTheme.primary,
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }} />
                ) : (
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={isRecording ? '#FFFFFF' : warmTheme.textSecondary}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="22" />
                  </svg>
                )}
              </button>

              <button
                onClick={handleSend}
                disabled={isLoading || isUploading || isTranscribing || (!inputValue.trim() && attachedFiles.length === 0)}
                style={{
                  padding: '8px 16px',
                  backgroundColor: isLoading || isUploading || isTranscribing || (!inputValue.trim() && attachedFiles.length === 0) ? warmTheme.border : warmTheme.primary,
                  border: 'none',
                  borderRadius: '8px',
                  cursor: isLoading || isUploading || isTranscribing || (!inputValue.trim() && attachedFiles.length === 0) ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'background-color 0.15s'
                }}
                onMouseEnter={(e) => {
                  if (!isLoading && !isUploading && !isTranscribing && (inputValue.trim() || attachedFiles.length > 0)) {
                    e.currentTarget.style.backgroundColor = warmTheme.primaryHover
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isLoading && !isUploading && !isTranscribing && (inputValue.trim() || attachedFiles.length > 0)) {
                    e.currentTarget.style.backgroundColor = warmTheme.primary
                  }
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* CSS Animations */}
      <style jsx global>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.9); }
        }
      `}</style>
    </div>
  )
}
