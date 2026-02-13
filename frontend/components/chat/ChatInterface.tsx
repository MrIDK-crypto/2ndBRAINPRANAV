'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react'
import Sidebar from '../shared/Sidebar'
import Image from 'next/image'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'
import ReactMarkdown from 'react-markdown'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

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

const WelcomeCard = ({ icon, title, description, onClick }: any) => (
  <div 
    onClick={onClick}
    className="flex flex-col justify-center items-start gap-2 flex-1 px-4 py-4 rounded-xl bg-white hover:shadow-md transition-shadow cursor-pointer border border-gray-100"
  >
    <div 
      className="flex items-center justify-center rounded-lg" 
      style={{ 
        backgroundColor: '#F3F3F3',
        width: '40px',
        height: '40px'
      }}
    >
      <div style={{ width: '21.5px', height: '21.5px', flexShrink: 0 }}>
        <Image src={icon} alt={title} width={21.5} height={21.5} />
      </div>
    </div>
    <div>
      <h3 className="text-neutral-800 font-sans text-sm font-semibold mb-1">
        {title}
      </h3>
      <p className="text-gray-600 font-sans text-xs leading-tight">
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

  // Chat History State
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)

  // Auth headers for API calls
  const getAuthHeaders = () => ({
    'Authorization': token ? `Bearer ${token}` : '',
    'Content-Type': 'application/json'
  })
  // Note: X-Tenant removed - tenant ID extracted from JWT on backend

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
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

  // Fetch conversations on mount and when token changes
  useEffect(() => {
    if (token) {
      fetchConversations()
    }
  }, [token, fetchConversations])

  // Handler for starting new chat
  const handleNewChat = () => {
    setMessages([])
    setCurrentConversationId(null)
  }

  // Show loading while checking auth (after all hooks)
  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-primary">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
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
      // Build conversation history for context (last 5 messages)
      const conversationHistory = messages.slice(-10).map(m => ({
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
        const sourceName = s.metadata?.file_name || s.doc_id || s.chunk_id || `Source ${idx + 1}`
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
        return match
      })
      // Also handle [Source X, Source Y] format
      cleanedAnswer = cleanedAnswer.replace(/\[Source (\d+), Source (\d+)\]/g, (match: string, num1: string, num2: string) => {
        const source1 = sourceMapData[`Source ${num1}`]
        const source2 = sourceMapData[`Source ${num2}`]
        if (source1 && source2) {
          return `[[SOURCE:${source1.name}:${source1.doc_id}]], [[SOURCE:${source2.name}:${source2.doc_id}]]`
        }
        return match
      })

      const aiSources = response.data.sources?.map((s: any) => ({
        doc_id: s.doc_id || s.chunk_id,
        subject: s.metadata?.file_name || s.doc_id || s.chunk_id,
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

      // Save AI response to conversation
      if (convId) {
        saveMessage('assistant', cleanedAnswer, aiSources)
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

  // Render markdown text with proper formatting
  const renderMarkdownMessage = (text: string) => {
    return (
      <ReactMarkdown
        components={{
          // Style code blocks
          code: ({ className, children, ...props }: any) => {
            const isInline = !className
            return isInline ? (
              <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-gray-800" {...props}>
                {children}
              </code>
            ) : (
              <code className="block bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm font-mono my-2" {...props}>
                {children}
              </code>
            )
          },
          // Style pre blocks (code containers)
          pre: ({ children }: any) => (
            <pre className="bg-gray-900 rounded-lg overflow-x-auto my-3">
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
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
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
        }}
      >
        {text}
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
      // Visual feedback - could add toast notification here
      console.log(`Feedback recorded: ${rating}`)
    } catch (error) {
      console.error('Error submitting feedback:', error)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#F8FAFC' }}>
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
        <div className="flex-1 flex items-center justify-center px-8 py-4 overflow-hidden" style={{ backgroundColor: '#F0F7FF' }}>
          <div
            className="flex flex-col justify-end items-center gap-5 bg-white rounded-3xl shadow-sm p-5 h-full max-h-[calc(100vh-40px)] w-full"
            style={{ maxWidth: '1000px' }}
          >
            {/* Messages or Welcome Screen */}
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-6 w-full overflow-auto">
                <div className="text-center">
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 mx-auto mb-3 overflow-hidden">
                    <Image src="/Maya.png" alt="Rishit" width={80} height={80} />
                  </div>
                  <h2 className="text-neutral-800 font-work text-2xl font-semibold mb-2">
                    Welcome, {user?.full_name?.split(' ')[0] || 'User'}
                  </h2>
                  <p className="text-gray-600 font-sans text-sm">
                    Ask anything about your organization's knowledge.
                  </p>
                  <p className="text-gray-500 font-sans text-xs">
                    Try one of these to get started:
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
                    className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`px-6 py-4 rounded-2xl ${
                        message.isUser
                          ? 'bg-white text-neutral-800 shadow-sm max-w-[50%]'
                          : 'bg-transparent text-neutral-800 max-w-[70%]'
                      }`}
                    >
                      <div className="font-sans text-[15px] leading-relaxed prose prose-sm max-w-none">
                        {message.isUser ? message.text : renderMarkdownMessage(message.text)}
                      </div>

                      {/* Display attachments for user messages */}
                      {message.isUser && message.attachments && message.attachments.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {message.attachments.map((att, idx) => (
                            <span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 rounded-full text-xs text-blue-700">
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
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 hover:bg-gray-200 text-xs text-gray-600 hover:text-gray-800 transition-colors cursor-pointer"
                                >
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                  <span className="max-w-[120px] truncate">{source.subject?.split('/').pop() || source.subject}</span>
                                </a>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 text-xs text-gray-500">
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                  <span className="max-w-[120px] truncate">{source.subject?.split('/').pop() || source.subject}</span>
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
                        <div className="mt-2 flex items-center gap-1 pt-2">
                          <button
                            onClick={() => handleFeedback(message, 'up')}
                            className="p-1.5 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 transition-colors"
                            title="Good answer"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleFeedback(message, 'down')}
                            className="p-1.5 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 transition-colors"
                            title="Poor answer"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                            </svg>
                          </button>
                          <button
                            className="p-1.5 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 transition-colors ml-1"
                            title="Copy response"
                            onClick={() => navigator.clipboard.writeText(message.text)}
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                    <div className="flex items-center gap-3 px-5 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl border border-blue-100">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                        <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-2 h-2 bg-blue-300 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
                      </div>
                      <span className="text-blue-600 text-sm font-medium">Thinking</span>
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
              <div className="flex items-center gap-3 px-4 py-2 bg-blue-50 rounded-lg mb-2">
                <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                <span className="text-sm text-blue-700">
                  Uploading and processing documents...
                </span>
              </div>
            )}

            {/* Attached files preview */}
            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {attachedFiles.map((file, idx) => (
                  <div key={idx} className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full text-sm">
                    <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="max-w-[150px] truncate text-gray-700">{file.name}</span>
                    <button
                      onClick={() => removeAttachment(idx)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Input Box */}
            <div
              className="flex flex-col justify-between items-start self-stretch bg-white rounded-[20px] border border-gray-200 p-4"
              style={{ minHeight: '79px' }}
            >
              <div className="flex items-center gap-3 w-full">
                <button
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading || attachedFiles.length >= 5}
                  title={attachedFiles.length >= 5 ? 'Max 5 files' : 'Attach files'}
                >
                  <Image src="/attach.svg" alt="Attach" width={20} height={20} />
                </button>

                <input
                  type="text"
                  placeholder={attachedFiles.length > 0 ? "Ask about your documents..." : "Write your message ..."}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                  className="flex-1 outline-none text-gray-700 font-sans text-[15px]"
                />

                <button
                  onClick={handleSend}
                  disabled={isLoading || isUploading || (!inputValue.trim() && attachedFiles.length === 0)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Image src="/send.svg" alt="Send" width={20} height={20} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
