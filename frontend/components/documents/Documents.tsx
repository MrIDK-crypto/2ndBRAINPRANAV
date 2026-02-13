'use client'

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import Image from 'next/image'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import DocumentViewer from './DocumentViewer'
import Sidebar from '../shared/Sidebar'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

// Modern Design System - Blue/Grey Theme
const colors = {
  // Primary
  primary: '#2563EB',
  primaryHover: '#1D4ED8',
  primaryLight: '#EFF6FF',

  // Backgrounds
  pageBg: '#F8FAFC',
  cardBg: '#FFFFFF',

  // Text
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',

  // Borders & Dividers
  border: '#E5E7EB',
  borderLight: '#F3F4F6',

  // Status Colors - Blue/Grey Palette
  statusActive: '#3B82F6',     // Blue - active/work items
  statusPending: '#94A3B8',    // Slate grey - pending items
  statusArchived: '#64748B',   // Darker slate - archived
  statusBlue: '#3B82F6',       // Primary blue
  statusAccent: '#60A5FA',     // Light blue accent
}

const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
}

interface Document {
  id: string
  name: string
  created: string
  lastModified: string
  type: string
  description: string
  category: 'Meetings' | 'Documents' | 'Personal Items' | 'Other Items' | 'Web Scraper' | 'Code'
  selected: boolean
  classification?: string
  source_type?: string
  folder_path?: string
  content?: string
  url?: string
  summary?: string
  quickSummary?: string
  score?: number
  classificationConfidence?: number
}

interface FullDocument {
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

// Status mapping for visual indicators - Blue/Grey theme
const getStatusInfo = (classification?: string, sourceType?: string) => {
  if (classification === 'work') return { label: 'Active', color: colors.statusActive }
  if (classification === 'personal') return { label: 'Personal', color: colors.statusPending }
  if (classification === 'spam') return { label: 'Archived', color: colors.statusArchived }
  if (sourceType === 'webscraper') return { label: 'Scraped', color: colors.statusBlue }
  if (sourceType === 'github') return { label: 'Code', color: colors.statusAccent }
  return { label: 'Pending', color: colors.textMuted }
}

export default function Documents() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [activeCategory, setActiveCategory] = useState<string>('All Items')
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [viewingDocument, setViewingDocument] = useState<FullDocument | null>(null)
  const [loadingDocument, setLoadingDocument] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [displayLimit, setDisplayLimit] = useState(50)
  const [sortField, setSortField] = useState<string>('created')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [activeFilters, setActiveFilters] = useState<string[]>([])
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [analyzingGaps, setAnalyzingGaps] = useState(false)
  const [showGapsMenu, setShowGapsMenu] = useState(false)

  // Share modal state
  const [showShareModal, setShowShareModal] = useState(false)
  const [shareEmail, setShareEmail] = useState('')
  const [shareMessage, setShareMessage] = useState('')
  const [sendingInvite, setSendingInvite] = useState(false)
  const [shareResult, setShareResult] = useState<{success: boolean, message: string} | null>(null)

  const authHeaders = useAuthHeaders()
  const { token, user, logout } = useAuth()
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const gapsMenuRef = useRef<HTMLDivElement>(null)

  // Track if we've loaded documents to prevent infinite loops
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    // Load documents when token is ready (only once per session)
    if (token && !hasLoadedRef.current) {
      hasLoadedRef.current = true
      loadDocuments()
    }
  }, [token])

  // Use useMemo for filtered documents - much faster than useState + useEffect
  const filteredDocuments = useMemo(() => {
    let filtered = [...documents]

    if (activeCategory !== 'All Items') {
      filtered = filtered.filter(d => d.category === activeCategory)
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(d =>
        d.name.toLowerCase().includes(query) ||
        d.description.toLowerCase().includes(query) ||
        d.type.toLowerCase().includes(query)
      )
    }

    // Sort
    filtered.sort((a, b) => {
      let aVal = a[sortField as keyof Document] || ''
      let bVal = b[sortField as keyof Document] || ''
      if (sortDirection === 'asc') {
        return String(aVal).localeCompare(String(bVal))
      }
      return String(bVal).localeCompare(String(aVal))
    })

    return filtered
  }, [documents, activeCategory, searchQuery, sortField, sortDirection])

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null)
      }
      if (gapsMenuRef.current && !gapsMenuRef.current.contains(event.target as Node)) {
        setShowGapsMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const loadDocuments = async () => {
    try {
      const response = await axios.get(`${API_BASE}/documents?limit=100`, {
        headers: authHeaders
      })

      if (response.data.success) {
        const apiDocs = response.data.documents
        const docs: Document[] = apiDocs.map((doc: any, index: number) => {
          let category: Document['category'] = 'Other Items'
          const title = doc.title?.toLowerCase() || ''
          const sourceType = doc.source_type?.toLowerCase() || ''
          const classification = doc.classification?.toLowerCase() || ''
          const folderPath = doc.metadata?.folder_path?.toLowerCase() || ''

          // Categorization logic
          if (sourceType === 'webscraper' || sourceType?.includes('webscraper')) {
            category = 'Web Scraper'
          } else if (sourceType === 'github' || sourceType?.includes('code') || /\.(js|ts|py|jsx|tsx|java|cpp|go|rs)$/i.test(title)) {
            category = 'Code'
          } else if (classification === 'personal' || classification === 'spam') {
            category = 'Personal Items'
          } else if (classification === 'work') {
            if (/meeting|schedule|agenda|discussion/i.test(title)) {
              category = 'Meetings'
            } else {
              category = 'Documents'
            }
          } else if (sourceType === 'box' || sourceType === 'file' || sourceType === 'notion' || sourceType === 'gdrive' || sourceType === 'zotero') {
            // Cloud storage and knowledge base sources default to Documents (Work)
            category = 'Documents'
          } else if (classification === 'unknown' || !classification) {
            // Unclassified documents default to Documents instead of Other/Personal
            category = 'Documents'
          }

          const createdDate = doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Unknown'
          let displayName = doc.title || 'Untitled Document'
          if (sourceType === 'github' && displayName.includes(' - ')) {
            displayName = displayName.split(' - ').pop() || displayName
          }

          // Quick summary
          let quickSummary = ''
          if (sourceType === 'github') {
            quickSummary = 'GitHub Repository'
          } else if (doc.summary?.trim()) {
            quickSummary = doc.summary.split(' ').slice(0, 8).join(' ')
            if (doc.summary.split(' ').length > 8) quickSummary += '...'
          } else if (doc.content?.trim()) {
            const words = doc.content.trim().split(/\s+/).slice(0, 8).join(' ')
            quickSummary = words + '...'
          } else {
            quickSummary = `${sourceType || 'Document'} file`
          }

          // Document type
          let docType = 'Document'
          if (sourceType === 'github') docType = 'Code'
          else if (sourceType === 'webscraper') docType = 'Web Page'
          else if (sourceType === 'email') docType = 'Email'
          else if (sourceType === 'box') docType = 'Box File'

          // Calculate work likelihood score from classification confidence
          // Higher score = more likely WORK, Lower score = more likely PERSONAL
          // If classified as work, score = confidence (high confidence = high work score)
          // If classified as personal/spam, score = 100 - confidence (high personal confidence = low work score)
          let workScore = 50 // Default for unknown
          if (doc.classification_confidence !== null && doc.classification_confidence !== undefined) {
            const confidence = doc.classification_confidence * 100
            if (classification === 'work') {
              workScore = Math.round(confidence)
            } else if (classification === 'personal' || classification === 'spam') {
              workScore = Math.round(100 - confidence)
            } else {
              workScore = 50 // Unknown classification
            }
          }

          return {
            id: doc.id || `doc_${index}`,
            name: displayName,
            created: createdDate,
            lastModified: doc.source_created_at ? new Date(doc.source_created_at).toLocaleDateString() : createdDate,
            type: docType,
            description: doc.summary || doc.title || 'No description',
            category,
            selected: false,
            classification: doc.classification,
            source_type: doc.source_type,
            url: doc.source_url || doc.metadata?.url || doc.metadata?.source_url,
            content: doc.content,
            summary: doc.summary,
            quickSummary,
            score: workScore,
            classificationConfidence: doc.classification_confidence
          }
        })
        setDocuments(docs)
      }
    } catch (error) {
      console.error('Error loading documents:', error)
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  const viewDocument = async (documentId: string) => {
    setLoadingDocument(true)
    try {
      const response = await axios.get(`${API_BASE}/documents/${documentId}`, {
        headers: authHeaders
      })
      if (response.data.success) {
        setViewingDocument(response.data.document)
      }
    } catch (error) {
      console.error('Error loading document:', error)
    } finally {
      setLoadingDocument(false)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    // Check for authentication
    if (!token) {
      console.error('No auth token available for upload')
      alert('Please log in to upload documents')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i])
      }
      // Don't set Content-Type for FormData - browser sets it with boundary automatically
      const response = await axios.post(`${API_BASE}/documents/upload`, formData, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.data.success) {
        loadDocuments()
      } else {
        console.error('Upload failed:', response.data.error)
        alert(`Upload failed: ${response.data.error || 'Unknown error'}`)
      }
    } catch (error: any) {
      console.error('Error uploading files:', error)
      const errorMsg = error.response?.data?.error || error.message || 'Unknown error'
      alert(`Upload failed: ${errorMsg}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDeleteDocument = async (documentId: string, documentName: string) => {
    // Immediately update UI (optimistic update)
    setDocuments(prev => prev.filter(d => d.id !== documentId))
    setSelectedDocs(prev => {
      const newSet = new Set(prev)
      newSet.delete(documentId)
      return newSet
    })
    setOpenMenuId(null)

    try {
      const response = await axios.delete(`${API_BASE}/documents/${documentId}`, {
        headers: authHeaders
      })
      if (!response.data.success) {
        // Revert on failure - reload documents
        loadDocuments()
        console.error('Delete failed:', response.data.error)
      }
    } catch (error: any) {
      console.error('Error deleting document:', error)
      // Revert on error - reload documents
      loadDocuments()
    }
  }

  const toggleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const removeFilter = (filter: string) => {
    setActiveFilters(prev => prev.filter(f => f !== filter))
  }

  const toggleDocSelection = (docId: string) => {
    setSelectedDocs(prev => {
      const newSet = new Set(prev)
      if (newSet.has(docId)) {
        newSet.delete(docId)
      } else {
        newSet.add(docId)
      }
      return newSet
    })
  }

  const toggleSelectAll = () => {
    if (selectedDocs.size === filteredDocuments.slice(0, displayLimit).length) {
      setSelectedDocs(new Set())
    } else {
      setSelectedDocs(new Set(filteredDocuments.slice(0, displayLimit).map(d => d.id)))
    }
  }

  const handleBulkDelete = async () => {
    if (selectedDocs.size === 0) return

    const docIds = Array.from(selectedDocs)

    // Immediately update UI (optimistic update)
    setDocuments(prev => prev.filter(d => !selectedDocs.has(d.id)))
    setSelectedDocs(new Set())

    try {
      // Delete each selected document in background
      await Promise.all(docIds.map(id =>
        axios.delete(`${API_BASE}/documents/${id}`, { headers: authHeaders })
      ))
    } catch (error) {
      console.error('Error deleting documents:', error)
      // Revert on error - reload documents
      loadDocuments()
    }
  }

  const handleCleanupAllData = async () => {
    if (!confirm('This will DELETE ALL your documents and knowledge gaps. This cannot be undone. Continue?')) return
    if (!confirm('Are you REALLY sure? All data will be permanently deleted.')) return

    try {
      // First delete local-tenant data (orphaned data)
      await axios.delete(`${API_BASE}/admin/delete-local-tenant`, {
        headers: authHeaders
      })

      // Then delete current tenant's documents
      const response = await axios.delete(`${API_BASE}/documents/all`, {
        headers: authHeaders
      })

      if (response.data.success) {
        alert(`Cleanup complete! Deleted ${response.data.documents_deleted || 0} documents.`)
        loadDocuments()
      }
    } catch (error: any) {
      console.error('Error cleaning up data:', error)
      alert(`Cleanup error: ${error.response?.data?.error || error.message}`)
    }
  }

  const handleMoveToCategory = async (docId: string, newCategory: string) => {
    // For now, this updates the local state. In production, you'd call an API to update the category.
    setDocuments(prev => prev.map(doc =>
      doc.id === docId ? { ...doc, category: newCategory as Document['category'] } : doc
    ))
    setOpenMenuId(null)
  }

  const handleBulkMoveToCategory = async (newCategory: string) => {
    if (selectedDocs.size === 0) return

    setDocuments(prev => prev.map(doc =>
      selectedDocs.has(doc.id) ? { ...doc, category: newCategory as Document['category'] } : doc
    ))
    setSelectedDocs(new Set())
  }

  const handleFindGaps = async (mode: 'simple' | 'code' = 'simple') => {
    if (documents.length === 0) return

    setShowGapsMenu(false)
    setAnalyzingGaps(true)
    try {
      console.log(`[FindGaps] Using ${mode} mode`)

      // First, analyze the documents to create knowledge gaps
      const response = await axios.post(`${API_BASE}/knowledge/analyze`, {
        force: true,
        include_pending: true,
        mode: mode
      }, { headers: authHeaders })

      if (response.data.success) {
        console.log(`Created ${response.data.gaps_created} knowledge gaps (mode: ${mode})`)
        if (response.data.result?.gaps_by_category) {
          console.log('Gaps by category:', response.data.result.gaps_by_category)
        }
      }

      // Then redirect to knowledge gaps page
      router.push('/knowledge-gaps')
    } catch (error) {
      console.error('Error analyzing documents:', error)
      // Still redirect even if analysis fails - user can retry from knowledge gaps page
      router.push('/knowledge-gaps')
    } finally {
      setAnalyzingGaps(false)
    }
  }

  const handleSendInvite = async () => {
    if (!shareEmail.trim()) return

    setSendingInvite(true)
    setShareResult(null)

    try {
      const response = await axios.post(`${API_BASE}/auth/invite`, {
        email: shareEmail.trim(),
        message: shareMessage.trim()
      }, { headers: authHeaders })

      if (response.data.success) {
        setShareResult({ success: true, message: 'Invitation sent! The email may take 1-2 minutes to arrive.' })
        // Clear form after success
        setTimeout(() => {
          setShareEmail('')
          setShareMessage('')
          setShowShareModal(false)
          setShareResult(null)
        }, 3000)
      } else {
        setShareResult({ success: false, message: response.data.error || 'Failed to send invitation' })
      }
    } catch (error: any) {
      console.error('Error sending invitation:', error)
      setShareResult({
        success: false,
        message: error.response?.data?.error || 'Failed to send invitation'
      })
    } finally {
      setSendingInvite(false)
    }
  }

  const counts = {
    all: documents.length,
    meetings: documents.filter(d => d.category === 'Meetings').length,
    documents: documents.filter(d => d.category === 'Documents').length,
    personal: documents.filter(d => d.category === 'Personal Items').length,
    code: documents.filter(d => d.category === 'Code').length,
    other: documents.filter(d => d.category === 'Other Items').length,
    webscraper: documents.filter(d => d.category === 'Web Scraper').length
  }

  // Folder Card Component
  const FolderCard = ({ title, count, size, active, onClick }: {
    title: string
    count: number
    size: string
    active: boolean
    onClick: () => void
  }) => (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        padding: '20px 28px',
        backgroundColor: colors.cardBg,
        border: `1px solid ${active ? colors.primary : colors.border}`,
        borderRadius: '12px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        minWidth: '240px',
        boxShadow: active ? `0 0 0 1px ${colors.primary}` : shadows.sm,
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.borderColor = colors.textMuted
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.borderColor = colors.border
      }}
    >
      <div style={{
        width: '48px',
        height: '48px',
        backgroundColor: colors.borderLight,
        borderRadius: '10px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill={colors.textMuted}>
          <path d="M3 7V17C3 18.1046 3.89543 19 5 19H19C20.1046 19 21 18.1046 21 17V9C21 7.89543 20.1046 7 19 7H13L11 5H5C3.89543 5 3 5.89543 3 7Z"/>
        </svg>
      </div>
      <div style={{ textAlign: 'left' }}>
        <div style={{
          fontSize: '16px',
          fontWeight: 600,
          color: colors.textPrimary,
          marginBottom: '4px',
        }}>
          {title}
        </div>
        <div style={{
          fontSize: '13px',
          color: colors.textMuted,
        }}>
          {count} files | {size}
        </div>
      </div>
    </button>
  )

  // Filter Pill Component
  const FilterPill = ({ label, active, hasClose, onClick, onClose }: {
    label: string
    active?: boolean
    hasClose?: boolean
    onClick?: () => void
    onClose?: () => void
  }) => (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '8px 14px',
        backgroundColor: active ? colors.primaryLight : colors.cardBg,
        border: `1px solid ${active ? colors.primary : colors.border}`,
        borderRadius: '20px',
        cursor: 'pointer',
        fontSize: '13px',
        fontWeight: 500,
        color: active ? colors.primary : colors.textSecondary,
        transition: 'all 0.15s ease',
      }}
    >
      {label}
      {hasClose && (
        <span
          onClick={(e) => { e.stopPropagation(); onClose?.() }}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            backgroundColor: colors.primary,
            color: '#fff',
            fontSize: '10px',
            marginLeft: '2px',
          }}
        >
          ×
        </span>
      )}
    </button>
  )

  // Sort Icon Component
  const SortIcon = ({ field }: { field: string }) => (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      style={{
        marginLeft: '4px',
        opacity: sortField === field ? 1 : 0.3,
        transform: sortField === field && sortDirection === 'asc' ? 'rotate(180deg)' : 'none',
        transition: 'all 0.15s ease'
      }}
    >
      <path d="M6 8L2 4H10L6 8Z" fill={colors.textMuted}/>
    </svg>
  )

  // Progress Bar Component - shows work likelihood score
  // Higher score = more likely WORK (green), Lower score = more likely PERSONAL (orange/red)
  const ProgressBar = ({ value }: { value: number }) => {
    // Color gradient: red/orange (personal) -> yellow (uncertain) -> green (work)
    let barColor = '#EF4444'  // Red for very low scores (likely personal)
    if (value > 75) {
      barColor = '#22C55E'    // Green for high scores (likely work)
    } else if (value > 50) {
      barColor = '#84CC16'    // Light green for moderate work likelihood
    } else if (value > 25) {
      barColor = '#F59E0B'    // Orange for uncertain/leaning personal
    }

    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{
          flex: 1,
          height: '8px',
          backgroundColor: colors.borderLight,
          borderRadius: '4px',
          overflow: 'hidden',
        }}>
          <div style={{
            width: `${value}%`,
            height: '100%',
            backgroundColor: barColor,
            borderRadius: '4px',
            transition: 'width 0.3s ease',
          }} />
        </div>
        <span style={{ fontSize: '13px', color: colors.textPrimary, fontWeight: 500, minWidth: '35px' }}>
          {value}%
        </span>
      </div>
    )
  }

  // Status Indicator Component
  const StatusIndicator = ({ status, color }: { status: string; color: string }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        backgroundColor: color,
      }} />
      <span style={{ fontSize: '13px', color: color, fontWeight: 500 }}>
        {status}
      </span>
    </div>
  )

  // Action Menu Component - with Move to category options
  const ActionMenu = ({ docId, docName }: { docId: string; docName: string }) => {
    const categories = [
      { label: 'Documents', value: 'Documents' },
      { label: 'Code', value: 'Code' },
      { label: 'Meetings', value: 'Meetings' },
      { label: 'Web Scraper', value: 'Web Scraper' },
      { label: 'Personal Items', value: 'Personal Items' },
      { label: 'Other Items', value: 'Other Items' },
    ]

    return (
      <div style={{ position: 'relative' }} ref={openMenuId === docId ? menuRef : null}>
        <button
          onClick={(e) => {
            e.stopPropagation()
            setOpenMenuId(openMenuId === docId ? null : docId)
          }}
          style={{
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'background-color 0.15s ease',
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill={colors.textMuted}>
            <circle cx="8" cy="3" r="1.5"/>
            <circle cx="8" cy="8" r="1.5"/>
            <circle cx="8" cy="13" r="1.5"/>
          </svg>
        </button>

        {openMenuId === docId && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            backgroundColor: colors.cardBg,
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            boxShadow: shadows.lg,
            minWidth: '180px',
            zIndex: 100,
            overflow: 'hidden',
          }}>
            {/* View Options */}
            <button
              onClick={(e) => { e.stopPropagation(); viewDocument(docId); setOpenMenuId(null) }}
              style={{
                width: '100%',
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                backgroundColor: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontSize: '13px',
                color: colors.textPrimary,
                textAlign: 'left',
                transition: 'background-color 0.15s ease',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <span>📄</span> View Document
            </button>

            <div style={{ height: '1px', backgroundColor: colors.border, margin: '4px 0' }} />

            {/* Move to Section */}
            <div style={{ padding: '6px 14px', fontSize: '11px', fontWeight: 600, color: colors.textMuted, textTransform: 'uppercase' }}>
              Move to
            </div>
            {categories.map((cat) => (
              <button
                key={cat.value}
                onClick={(e) => { e.stopPropagation(); handleMoveToCategory(docId, cat.value) }}
                style={{
                  width: '100%',
                  padding: '8px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '13px',
                  color: colors.textSecondary,
                  textAlign: 'left',
                  transition: 'background-color 0.15s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <span>📁</span> {cat.label}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: colors.pageBg }}>
      {/* Sidebar */}
      <Sidebar userName={user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'User'} />

      {/* Main Content */}
      <main style={{ flex: 1, padding: '32px', overflowY: 'auto' }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '32px',
        }}>
          <h1 style={{
            fontSize: '28px',
            fontWeight: 700,
            color: colors.textPrimary,
            margin: 0,
          }}>
            Documents
          </h1>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                backgroundColor: uploading ? colors.textMuted : colors.primary,
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '14px',
                fontWeight: 500,
                cursor: uploading ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!uploading) e.currentTarget.style.backgroundColor = colors.primaryHover
              }}
              onMouseLeave={(e) => {
                if (!uploading) e.currentTarget.style.backgroundColor = colors.primary
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              {uploading ? 'Uploading...' : 'Add Document'}
            </button>
            {/* Find Gaps Dropdown */}
            <div ref={gapsMenuRef} style={{ position: 'relative' }}>
              <button
                onClick={() => setShowGapsMenu(!showGapsMenu)}
                disabled={documents.length === 0 || analyzingGaps}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  backgroundColor: (documents.length === 0 || analyzingGaps) ? colors.textMuted : colors.statusBlue,
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: (documents.length === 0 || analyzingGaps) ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (documents.length > 0 && !analyzingGaps) e.currentTarget.style.backgroundColor = colors.primaryHover
                }}
                onMouseLeave={(e) => {
                  if (documents.length > 0 && !analyzingGaps) e.currentTarget.style.backgroundColor = colors.statusBlue
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/>
                  <path d="m21 21-4.35-4.35"/>
                </svg>
                {analyzingGaps ? 'Analyzing...' : 'Find Gaps'}
                <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" style={{ marginLeft: '4px' }}>
                  <path d="M3 4.5L6 7.5L9 4.5H3Z"/>
                </svg>
              </button>

              {/* Dropdown Menu */}
              {showGapsMenu && (
                <div
                  style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    marginTop: '4px',
                    backgroundColor: '#fff',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                    border: `1px solid ${colors.border}`,
                    minWidth: '160px',
                    zIndex: 100,
                    overflow: 'hidden'
                  }}
                >
                  <button
                    onClick={() => handleFindGaps('simple')}
                    style={{
                      width: '100%',
                      padding: '10px 16px',
                      border: 'none',
                      backgroundColor: 'transparent',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: 500,
                      color: colors.textPrimary,
                      textAlign: 'left',
                      transition: 'background-color 0.15s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.primaryLight}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    Find Gaps
                  </button>
                  <div style={{ height: '1px', backgroundColor: colors.border }} />
                  <button
                    onClick={() => handleFindGaps('code')}
                    style={{
                      width: '100%',
                      padding: '10px 16px',
                      border: 'none',
                      backgroundColor: 'transparent',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: 500,
                      color: colors.textPrimary,
                      textAlign: 'left',
                      transition: 'background-color 0.15s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.primaryLight}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    Find Code Gaps
                  </button>
                </div>
              )}
            </div>
            <button
              onClick={() => setShowShareModal(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                backgroundColor: '#FFFFFF',
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                color: colors.textPrimary,
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = colors.primaryLight
                e.currentTarget.style.borderColor = colors.primary
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#FFFFFF'
                e.currentTarget.style.borderColor = colors.border
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="18" cy="5" r="3"/>
                <circle cx="6" cy="12" r="3"/>
                <circle cx="18" cy="19" r="3"/>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
              </svg>
              Share
            </button>
          </div>
        </div>

        {/* Folders Section */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h2 style={{
                fontSize: '16px',
                fontWeight: 600,
                color: colors.textPrimary,
                margin: 0,
              }}>
                Folders
              </h2>
              <button style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 10px',
                backgroundColor: 'transparent',
                border: 'none',
                color: colors.primary,
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
              }}>
                + New folder
              </button>
            </div>
            <button style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 10px',
              backgroundColor: 'transparent',
              border: 'none',
              color: colors.primary,
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
            }}>
              + View all
            </button>
          </div>

          <div style={{
            display: 'flex',
            gap: '16px',
            overflowX: 'auto',
            paddingBottom: '8px',
          }}>
            <FolderCard
              title="All Documents"
              count={counts.all}
              size={`${Math.floor(counts.all * 0.8)} MB`}
              active={activeCategory === 'All Items'}
              onClick={() => setActiveCategory('All Items')}
            />
            <FolderCard
              title="Work Documents"
              count={counts.documents}
              size={`${Math.floor(counts.documents * 1.2)} MB`}
              active={activeCategory === 'Documents'}
              onClick={() => setActiveCategory('Documents')}
            />
            <FolderCard
              title="Code Files"
              count={counts.code}
              size={`${Math.floor(counts.code * 0.5)} MB`}
              active={activeCategory === 'Code'}
              onClick={() => setActiveCategory('Code')}
            />
            <FolderCard
              title="Web Scraper"
              count={counts.webscraper}
              size={`${Math.floor(counts.webscraper * 0.3)} MB`}
              active={activeCategory === 'Web Scraper'}
              onClick={() => setActiveCategory('Web Scraper')}
            />
            <FolderCard
              title="Personal & Other"
              count={counts.personal + counts.other}
              size={`${Math.floor((counts.personal + counts.other) * 0.6)} MB`}
              active={activeCategory === 'Personal Items' || activeCategory === 'Other Items'}
              onClick={() => setActiveCategory('Personal Items')}
            />
          </div>
        </div>

        {/* Files Section */}
        <div style={{
          backgroundColor: colors.cardBg,
          borderRadius: '12px',
          border: `1px solid ${colors.border}`,
          boxShadow: shadows.sm,
          overflow: 'hidden',
        }}>
          {/* Filter Bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: `1px solid ${colors.border}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <FilterPill label="Sort by: latest" />
              <FilterPill label="Filter keywords" />
              <FilterPill label="Type" />
              <FilterPill label="Source" />
              {activeFilters.map(filter => (
                <FilterPill
                  key={filter}
                  label={filter}
                  active
                  hasClose
                  onClose={() => removeFilter(filter)}
                />
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Bulk Actions - show when items selected */}
              {selectedDocs.size > 0 && (
                <>
                  <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                    {selectedDocs.size} selected
                  </span>
                  {/* Bulk Move Dropdown */}
                  <select
                    onChange={(e) => {
                      if (e.target.value) {
                        handleBulkMoveToCategory(e.target.value)
                        e.target.value = ''
                      }
                    }}
                    style={{
                      padding: '8px 12px',
                      backgroundColor: colors.cardBg,
                      border: `1px solid ${colors.border}`,
                      borderRadius: '6px',
                      fontSize: '13px',
                      color: colors.textSecondary,
                      cursor: 'pointer',
                    }}
                  >
                    <option value="">Move to...</option>
                    <option value="Documents">Documents</option>
                    <option value="Code">Code</option>
                    <option value="Meetings">Meetings</option>
                    <option value="Web Scraper">Web Scraper</option>
                    <option value="Personal Items">Personal Items</option>
                    <option value="Other Items">Other Items</option>
                  </select>
                  {/* Bulk Delete Button */}
                  <button
                    onClick={handleBulkDelete}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 14px',
                      backgroundColor: colors.statusArchived,
                      border: 'none',
                      borderRadius: '6px',
                      color: '#fff',
                      fontSize: '13px',
                      fontWeight: 500,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#475569'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = colors.statusArchived}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                    Delete
                  </button>
                </>
              )}
              {/* Clean Up All Data Button */}
              <button
                onClick={handleCleanupAllData}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  backgroundColor: '#475569',
                  border: 'none',
                  borderRadius: '6px',
                  color: '#fff',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#334155'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#475569'}
                title="Delete ALL documents and start fresh"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 6h18"/>
                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                  <line x1="10" y1="11" x2="10" y2="17"/>
                  <line x1="14" y1="11" x2="14" y2="17"/>
                </svg>
                Clean All Data
              </button>
              {/* Search */}
              <div style={{ position: 'relative', minWidth: '200px' }}>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search"
                  style={{
                    width: '100%',
                    padding: '10px 16px',
                    paddingLeft: '40px',
                    backgroundColor: colors.borderLight,
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '14px',
                    color: colors.textPrimary,
                    outline: 'none',
                  }}
                />
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke={colors.textMuted}
                  strokeWidth="2"
                  style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }}
                >
                  <circle cx="11" cy="11" r="8"/>
                  <path d="m21 21-4.35-4.35"/>
                </svg>
              </div>
            </div>
          </div>

          {/* Table */}
          {loading ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '80px',
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                border: `3px solid ${colors.border}`,
                borderTop: `3px solid ${colors.primary}`,
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }} />
              <style jsx>{`
                @keyframes spin {
                  0% { transform: rotate(0deg); }
                  100% { transform: rotate(360deg); }
                }
              `}</style>
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '80px',
              gap: '16px',
            }}>
              <div style={{ fontSize: '48px', opacity: 0.4 }}>📂</div>
              <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                {searchQuery ? 'No documents found' : 'No documents yet'}
              </h3>
              <p style={{ fontSize: '14px', color: colors.textMuted, margin: 0 }}>
                {searchQuery
                  ? `No documents match "${searchQuery}"`
                  : 'Connect your tools or upload documents to get started'}
              </p>
            </div>
          ) : (
            <>
              {/* Table Header */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '24px 2fr 1.2fr 1fr 1fr 140px 48px',
                gap: '16px',
                padding: '12px 20px',
                backgroundColor: colors.cardBg,
                borderBottom: `1px solid ${colors.border}`,
              }}>
                <div>
                  <input
                    type="checkbox"
                    checked={selectedDocs.size === filteredDocuments.slice(0, displayLimit).length && filteredDocuments.length > 0}
                    onChange={toggleSelectAll}
                    style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                  />
                </div>
                {[
                  { label: 'Document', field: 'name' },
                  { label: 'Type', field: 'type' },
                  { label: 'Source', field: 'source_type' },
                  { label: 'Date', field: 'created' },
                  { label: 'Work Score', field: 'score' },
                ].map((col) => (
                  <button
                    key={col.field}
                    onClick={() => toggleSort(col.field)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      fontSize: '12px',
                      fontWeight: 500,
                      color: colors.textMuted,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      cursor: 'pointer',
                    }}
                  >
                    {col.label}
                    <SortIcon field={col.field} />
                  </button>
                ))}
                <div />
              </div>

              {/* Table Body */}
              <div>
                {filteredDocuments.slice(0, displayLimit).map((doc) => {
                  const isSelected = selectedDocs.has(doc.id)
                  return (
                    <div
                      key={doc.id}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '24px 2fr 1.2fr 1fr 1fr 140px 48px',
                        gap: '16px',
                        padding: '16px 20px',
                        alignItems: 'center',
                        borderBottom: `1px solid ${colors.borderLight}`,
                        cursor: 'pointer',
                        backgroundColor: isSelected ? colors.primaryLight : undefined,
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) e.currentTarget.style.backgroundColor = colors.borderLight
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) e.currentTarget.style.backgroundColor = ''
                      }}
                      onClick={() => {
                        // Open directly in source app if source_url is available
                        if (doc.url) {
                          window.open(doc.url, '_blank', 'noopener,noreferrer')
                        } else {
                          // Fall back to modal if no source URL
                          viewDocument(doc.id)
                        }
                      }}
                    >
                      <div onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedDocs.has(doc.id)}
                          onChange={() => toggleDocSelection(doc.id)}
                          style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                        />
                      </div>

                      {/* Document Name */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', overflow: 'hidden' }}>
                        <div style={{
                          width: '32px',
                          height: '32px',
                          backgroundColor: colors.borderLight,
                          borderRadius: '6px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill={colors.textMuted}>
                            <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z"/>
                          </svg>
                        </div>
                        <span style={{
                          fontSize: '14px',
                          fontWeight: 500,
                          color: colors.textPrimary,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}>
                          {doc.name}
                        </span>
                      </div>

                      {/* Type */}
                      <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                        {doc.type}
                      </span>

                      {/* Source */}
                      <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                        {doc.source_type || 'Upload'}
                      </span>

                      {/* Date */}
                      <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                        {doc.created}
                      </span>

                      {/* Work Score - higher = more likely work, lower = more likely personal */}
                      <ProgressBar value={doc.score ?? 50} />

                      {/* Actions */}
                      <div onClick={(e) => e.stopPropagation()}>
                        <ActionMenu docId={doc.id} docName={doc.name} />
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Load More */}
              {filteredDocuments.length > displayLimit && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  padding: '20px',
                  borderTop: `1px solid ${colors.border}`,
                }}>
                  <button
                    onClick={() => setDisplayLimit(prev => prev + 50)}
                    style={{
                      padding: '10px 24px',
                      backgroundColor: 'transparent',
                      border: `1px solid ${colors.border}`,
                      borderRadius: '8px',
                      color: colors.textSecondary,
                      fontSize: '14px',
                      fontWeight: 500,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = colors.textMuted}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = colors.border}
                  >
                    Show More ({filteredDocuments.length - displayLimit} remaining)
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* Document Viewer Modal */}
      {viewingDocument && (
        <DocumentViewer
          document={viewingDocument}
          onClose={() => setViewingDocument(null)}
        />
      )}

      {/* Loading Overlay */}
      {loadingDocument && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            backgroundColor: colors.cardBg,
            borderRadius: '12px',
            padding: '32px',
            boxShadow: shadows.lg,
          }}>
            <span style={{ fontSize: '15px', fontWeight: 500, color: colors.textPrimary }}>
              Loading document...
            </span>
          </div>
        </div>
      )}

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls"
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />

      {/* Share Modal */}
      {showShareModal && (
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
            zIndex: 1000,
          }}
          onClick={() => {
            setShowShareModal(false)
            setShareResult(null)
          }}
        >
          <div
            style={{
              backgroundColor: colors.cardBg,
              borderRadius: '16px',
              padding: '32px',
              maxWidth: '480px',
              width: '90%',
              boxShadow: shadows.lg,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                Invite to 2nd Brain
              </h2>
              <button
                onClick={() => {
                  setShowShareModal(false)
                  setShareResult(null)
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: colors.textMuted,
                  padding: '4px',
                }}
              >
                ×
              </button>
            </div>

            <p style={{ color: colors.textSecondary, fontSize: '14px', marginBottom: '24px' }}>
              Share 2nd Brain with a colleague or friend. They&apos;ll receive an email invitation to sign up.
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: colors.textPrimary, marginBottom: '8px' }}>
                Email Address *
              </label>
              <input
                type="email"
                value={shareEmail}
                onChange={(e) => setShareEmail(e.target.value)}
                placeholder="colleague@example.com"
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  fontSize: '14px',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = colors.primary}
                onBlur={(e) => e.currentTarget.style.borderColor = colors.border}
              />
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: colors.textPrimary, marginBottom: '8px' }}>
                Personal Message (optional)
              </label>
              <textarea
                value={shareMessage}
                onChange={(e) => setShareMessage(e.target.value)}
                placeholder="Hey! I've been using 2nd Brain to organize my knowledge and thought you'd like it too."
                rows={3}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  fontSize: '14px',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  outline: 'none',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit',
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = colors.primary}
                onBlur={(e) => e.currentTarget.style.borderColor = colors.border}
              />
            </div>

            {shareResult && (
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: '8px',
                  marginBottom: '16px',
                  backgroundColor: shareResult.success ? colors.primaryLight : '#F1F5F9',
                  color: shareResult.success ? colors.primary : colors.statusArchived,
                  fontSize: '14px',
                }}
              >
                {shareResult.success ? '✓ ' : '✗ '}{shareResult.message}
              </div>
            )}

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => {
                  setShowShareModal(false)
                  setShareResult(null)
                }}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  fontWeight: 500,
                  backgroundColor: 'transparent',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  color: colors.textPrimary,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSendInvite}
                disabled={!shareEmail.trim() || sendingInvite}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  fontWeight: 500,
                  backgroundColor: (!shareEmail.trim() || sendingInvite) ? colors.textMuted : colors.primary,
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  cursor: (!shareEmail.trim() || sendingInvite) ? 'not-allowed' : 'pointer',
                }}
              >
                {sendingInvite ? 'Sending email...' : 'Send Invitation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
