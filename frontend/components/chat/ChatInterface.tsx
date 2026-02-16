'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react'
import Sidebar from '../shared/Sidebar'
import Image from 'next/image'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'
import { sessionManager } from '@/utils/sessionManager'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { analytics } from '@/utils/analytics'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

interface Message {
  id: string
  text: string
  isUser: boolean
  sources?: any[]
  sourceMap?: { [key: string]: { name: string; doc_id: string } }
  attachments?: { name: string; type: string }[]
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
  const { user, token, tenant, isLoading: authLoading, logout, isSharedAccess } = useAuth()
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
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(() => {
    // Restore last conversation from localStorage
    if (typeof window !== 'undefined') {
      return localStorage.getItem('2ndBrain_currentConversationId') || null
    }
    return null
  })

  // Auth headers for API calls
  const getAuthHeaders = () => {
    if (token) {
      return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
    }
    // Fallback to share token
    const shareToken = sessionManager.getShareToken()
    if (shareToken) {
      return { 'X-Share-Token': shareToken, 'Content-Type': 'application/json' }
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
  const fetchConversations = useCallback(async () => {
    if (!token) return
    setIsLoadingHistory(true)
    try {
      const response = await axios.get(`${API_BASE}/chat/conversations`, {
        headers: getAuthHeaders()
      })
      if (response.data.success) {
        setConversations(response.data.conversations || [])
      }
    } catch (error) {
      console.error('Error fetching conversations:', error)
    } finally {
      setIsLoadingHistory(false)
    }
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

  // Save message to current conversation
  const saveMessage = async (role: 'user' | 'assistant', content: string, sources?: any[]) => {
    if (!currentConversationId) return
    try {
      await axios.post(
        `${API_BASE}/chat/conversations/${currentConversationId}/messages`,
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

  // Persist currentConversationId to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (currentConversationId) {
        localStorage.setItem('2ndBrain_currentConversationId', currentConversationId)
      } else {
        localStorage.removeItem('2ndBrain_currentConversationId')
      }
    }
  }, [currentConversationId])

  // Fetch conversations on mount and auto-load last conversation
  useEffect(() => {
    if (token) {
      fetchConversations().then(() => {
        // Auto-load last conversation if we have one saved and no messages loaded yet
        const savedId = typeof window !== 'undefined' ? localStorage.getItem('2ndBrain_currentConversationId') : null
        if (savedId && messages.length === 0) {
          loadConversation(savedId)
        }
      })
    }
  }, [token, fetchConversations])

  // Handler for starting new chat
  const handleNewChat = () => {
    setMessages([])
    setCurrentConversationId(null)
    if (typeof window !== 'undefined') {
      localStorage.removeItem('2ndBrain_currentConversationId')
    }
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

    // Save user message to conversation
    if (convId) {
      saveMessage('user', queryText)
    }

    try {
      // Build conversation history for context - include recent messages for memory
      const allCurrentMessages = [...messages, userMessage]
      const conversationHistory = allCurrentMessages.slice(-20).map(m => ({
        role: m.isUser ? 'user' : 'assistant',
        content: m.text
      }))

      // Use Enhanced RAG v2.1 endpoint with auth headers and conversation history
      const response = await axios.post(`${API_BASE}/search`, {
        query: queryText,
        conversation_history: conversationHistory,
        top_k: 15,  // Get more results for better context
        boost_doc_ids: uploadedDocIds  // Boost newly uploaded documents
      }, {
        headers: getAuthHeaders()
      })

      // RAG response includes answer, sources, confidence, etc.
      // Clean up the answer text - remove citation coverage and sources used lines
      let cleanedAnswer = response.data.answer || ''

      // Remove "Sources Used: [Source X, Source Y]" line
      cleanedAnswer = cleanedAnswer.replace(/Sources Used:.*$/gm, '')
      // Remove "Citation Coverage: X% of statements are cited." line
      cleanedAnswer = cleanedAnswer.replace(/.*Citation Coverage:.*$/gm, '')
      // Remove emoji lines like "📊 Citation Coverage..."
      cleanedAnswer = cleanedAnswer.replace(/^.*📊.*$/gm, '')
      cleanedAnswer = cleanedAnswer.replace(/^.*📄 Sources:.*$/gm, '')
      // Clean up extra newlines
      cleanedAnswer = cleanedAnswer.replace(/\n{3,}/g, '\n\n').trim()

      // Build source name mapping for inline citations
      const sourceMapData: { [key: string]: { name: string; doc_id: string } } = {}
      response.data.sources?.forEach((s: any, idx: number) => {
        // Never use raw doc_id/chunk_id as display name — use title or generic label
        const sourceName = s.metadata?.file_name || s.title || s.metadata?.title || s.metadata?.subject || `Source ${idx + 1}`
        const doc_id = s.doc_id || s.chunk_id || ''
        // Clean up source name - get just the filename
        const cleanName = sourceName.split('/').pop()?.replace(/^(space_msg_|File-)/, '') || sourceName
        sourceMapData[`Source ${idx + 1}`] = { name: cleanName, doc_id }
        sourceMapData[cleanName] = { name: cleanName, doc_id }
      })

      // Replace [Source X] with placeholder markers that we'll render as links
      // Use a special marker format: [[SOURCE:name:doc_id]]
      cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+)\]/g, (match: string, num: string) => {
        const key = `Source ${num}`
        const source = sourceMapData[key]
        if (source) {
          return `[[SOURCE:${source.name}:${source.doc_id}]]`
        }
        // No mapping — remove the raw [Source N] text entirely so it doesn't clutter the answer
        return ''
      })
      // Also handle [Source X, Source Y] format (full prefix)
      cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+), Source (\d+)\]/g, (match: string, num1: string, num2: string) => {
        const source1 = sourceMapData[`Source ${num1}`]
        const source2 = sourceMapData[`Source ${num2}`]
        const parts = []
        if (source1) parts.push(`[[SOURCE:${source1.name}:${source1.doc_id}]]`)
        if (source2) parts.push(`[[SOURCE:${source2.name}:${source2.doc_id}]]`)
        return parts.length > 0 ? parts.join(', ') : ''
      })
      // Handle [Source 1, 2] or [Source 1, 2, 3] shorthand format
      cleanedAnswer = cleanedAnswer.replace(
        /\[Source (\d+(?:,\s*\d+)+)\]/g,
        (match: string, nums: string) => {
          const numbers = nums.split(/,\s*/)
          const markers = numbers
            .map((n: string) => {
              const source = sourceMapData[`Source ${n.trim()}`]
              return source ? `[[SOURCE:${source.name}:${source.doc_id}]]` : null
            })
            .filter(Boolean)
          return markers.join(', ')
        }
      )
      // Handle [Sources 1, 2, 3] plural format
      cleanedAnswer = cleanedAnswer.replace(
        /\[Sources (\d+(?:,\s*\d+)+)\]/gi,
        (match: string, nums: string) => {
          const numbers = nums.split(/,\s*/)
          const markers = numbers
            .map((n: string) => {
              const source = sourceMapData[`Source ${n.trim()}`]
              return source ? `[[SOURCE:${source.name}:${source.doc_id}]]` : null
            })
            .filter(Boolean)
          return markers.join(', ')
        }
      )
      // Handle [Source 3: filename.py] format (with filename after colon)
      cleanedAnswer = cleanedAnswer.replace(
        /\[Source (\d+):\s*[^\]]+\]/g,
        (match: string, num: string) => {
          const source = sourceMapData[`Source ${num}`]
          return source ? `[[SOURCE:${source.name}:${source.doc_id}]]` : ''
        }
      )

      // Catch-all: remove any remaining raw [Source N] that weren't mapped
      cleanedAnswer = cleanedAnswer.replace(/\[Sources?\s*\d+(?:,\s*\d+)*\]/gi, '')

      // Add commas between consecutive source markers (e.g. ]] [[SOURCE: → ]], [[SOURCE:)
      cleanedAnswer = cleanedAnswer.replace(/\]\]\s+\[\[SOURCE:/g, ']], [[SOURCE:')

      // Clean up orphaned commas and extra whitespace from removed sources
      cleanedAnswer = cleanedAnswer.replace(/,\s*,/g, ',')
      cleanedAnswer = cleanedAnswer.replace(/\s{2,}/g, ' ')
      cleanedAnswer = cleanedAnswer.replace(/\n{3,}/g, '\n\n')

      const aiSources = response.data.sources?.map((s: any, idx: number) => ({
        doc_id: s.doc_id || s.chunk_id,
        subject: s.metadata?.file_name || s.title || s.metadata?.title || s.metadata?.subject || `Source ${idx + 1}`,
        project: s.metadata?.project || 'Unknown',
        score: s.rerank_score || s.score,
        content: s.content?.substring(0, 200) + '...'
      }))

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: cleanedAnswer,
        isUser: false,
        sources: aiSources,
        sourceMap: sourceMapData,
      }
      setMessages(prev => [...prev, aiMessage])

      // Save AI response to conversation and refresh sidebar
      if (convId) {
        saveMessage('assistant', cleanedAnswer, aiSources)
        // Refresh conversation list so sidebar shows updated titles/timestamps
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
    // Pre-process: Convert [[SOURCE:name:doc_id]] markers into markdown links
    const sourceToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
    const shareToken = sessionManager.getShareToken()
    const authToken = sourceToken || shareToken
    const processedText = text.replace(
      /\[\[SOURCE:([^:]+):([^\]]+)\]\]/g,
      (match: string, name: string, docId: string) => {
        const hasValidDocId = docId && docId.length >= 32
        if (hasValidDocId && authToken) {
          const tokenParam = sourceToken
            ? `token=${encodeURIComponent(sourceToken)}`
            : `share_token=${encodeURIComponent(shareToken || '')}`
          const url = `${API_BASE}/documents/${encodeURIComponent(docId)}/view?${tokenParam}`
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
          // Style code blocks — pre handles the container, code just renders text
          code: ({ className, children, ...props }: any) => {
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
          pre: ({ children }: any) => (
            <pre style={{ backgroundColor: '#1E1E2E', color: '#CDD6F4', borderRadius: '12px', padding: '16px', overflow: 'auto', margin: '12px 0', fontSize: '13px', lineHeight: '1.6', fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, monospace' }}>
              {children}
            </pre>
          ),
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

  return (
    <div className="flex h-screen overflow-hidden" style={{ backgroundColor: warmTheme.pageBg }}>
      {/* Sidebar - Always Visible */}
      <Sidebar
        activeItem={activeItem}
        onItemClick={setActiveItem}
        userName={user?.full_name?.split(' ')[0] || 'User'}
        isSharedAccess={isSharedAccess}
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
        <div className="flex-1 flex items-center justify-center px-8 py-4 overflow-hidden" style={{ backgroundColor: warmTheme.chatBg }}>
          <div
            className="flex flex-col items-center gap-5 rounded-3xl p-5 h-full max-h-[calc(100vh-40px)] w-full"
            style={{ maxWidth: '1000px', backgroundColor: '#F7F5F3', border: '1px solid #F0EEEC' }}
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
                        maxWidth: message.isUser ? '60%' : '75%',
                        backgroundColor: message.isUser ? '#FFFFFF' : warmTheme.primaryLight,
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
                        {message.isUser ? message.text : renderMarkdownMessage(message.text)}
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
                          {message.sources.slice(0, 5).map((source, idx) => {
                            const sourceToken = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
                            // Only create clickable link if doc_id exists and looks like a valid UUID
                            const hasValidDocId = source.doc_id && source.doc_id.length >= 32
                            const sourceViewUrl = hasValidDocId
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
                              background: 'none',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              color: warmTheme.textMuted,
                              display: 'flex',
                              alignItems: 'center',
                              transition: 'all 0.15s'
                            }}
                            title="Good answer"
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = warmTheme.border
                              e.currentTarget.style.color = warmTheme.primary
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = 'transparent'
                              e.currentTarget.style.color = warmTheme.textMuted
                            }}
                          >
                            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleFeedback(message, 'down')}
                            style={{
                              padding: '6px',
                              background: 'none',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              color: warmTheme.textMuted,
                              display: 'flex',
                              alignItems: 'center',
                              transition: 'all 0.15s'
                            }}
                            title="Poor answer"
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = warmTheme.border
                              e.currentTarget.style.color = warmTheme.primary
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = 'transparent'
                              e.currentTarget.style.color = warmTheme.textMuted
                            }}
                          >
                            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                            </svg>
                          </button>
                          <button
                            style={{
                              padding: '6px',
                              background: 'none',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              color: warmTheme.textMuted,
                              display: 'flex',
                              alignItems: 'center',
                              marginLeft: '4px',
                              transition: 'all 0.15s'
                            }}
                            title="Copy response"
                            onClick={() => navigator.clipboard.writeText(message.text)}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = warmTheme.border
                              e.currentTarget.style.color = warmTheme.primary
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = 'transparent'
                              e.currentTarget.style.color = warmTheme.textMuted
                            }}
                          >
                            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
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
