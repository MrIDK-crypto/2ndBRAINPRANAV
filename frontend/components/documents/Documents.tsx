'use client'

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import Image from 'next/image'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import DocumentViewer from './DocumentViewer'
import Sidebar from '../shared/Sidebar'
import {
  colors, shadows, Z_INDEX,
  CATEGORIES, MOVE_CATEGORIES, CATEGORY_TO_CLASSIFICATION,
  CODE_EXTENSIONS, CODE_EXTENSIONS_REGEX, MEETING_KEYWORDS,
  SOURCE_TYPE_MAP, getSourceTypeInfo,
  ACCEPTED_FILE_TYPES, DISPLAY_PAGE_SIZE, API_FETCH_LIMIT, SUMMARY_WORD_LIMIT,
  formatFileSize,
} from './constants'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

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
  embedded_at?: string | null
  fileSize?: number
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

// Status mapping for visual indicators
const getStatusInfo = (classification?: string, sourceType?: string) => {
  if (classification === 'work') return { label: 'Active', color: colors.statusActive }
  if (classification === 'personal') return { label: 'Personal', color: colors.statusPending }
  if (classification === 'spam') return { label: 'Archived', color: colors.statusArchived }
  const srcInfo = getSourceTypeInfo(sourceType)
  if (srcInfo.docType === 'Web Page') return { label: 'Scraped', color: colors.statusSuccess }
  if (srcInfo.docType === 'Code') return { label: 'Code', color: colors.statusAccent }
  return { label: 'Pending', color: colors.textMuted }
}

// Professional file type icons - warm consistent color
const iconColor = '#7A7A7A'

const getFileTypeInfo = (filename: string, type?: string) => {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const fileType = type?.toLowerCase() || ''

  // PDF
  if (ext === 'pdf' || fileType.includes('pdf')) {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
          <path d="M14 2v6h6"/>
          <path d="M9 15v-2h1.5a1.5 1.5 0 0 0 0-3H9v5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    }
  }

  // Word Documents
  if (['doc', 'docx'].includes(ext) || fileType.includes('word') || fileType.includes('document')) {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
          <path d="M14 2v6h6"/>
          <path d="M8 13h8M8 17h6"/>
        </svg>
      )
    }
  }

  // Excel/Spreadsheets
  if (['xls', 'xlsx', 'csv'].includes(ext) || fileType.includes('excel') || fileType.includes('spreadsheet')) {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
          <path d="M14 2v6h6"/>
          <path d="M8 12h8v6H8zM12 12v6M8 15h8"/>
        </svg>
      )
    }
  }

  // PowerPoint
  if (['ppt', 'pptx'].includes(ext) || fileType.includes('powerpoint') || fileType.includes('presentation')) {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
          <path d="M14 2v6h6"/>
          <rect x="7" y="11" width="10" height="6" rx="1"/>
        </svg>
      )
    }
  }

  // Images
  if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp'].includes(ext) || fileType.includes('image')) {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/>
          <path d="M21 15l-5-5L5 21"/>
        </svg>
      )
    }
  }

  // Code files
  if (CODE_EXTENSIONS.has(ext) || fileType.includes('code')) {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
          <path d="M14 2v6h6"/>
          <path d="M10 12l-2 2 2 2M14 12l2 2-2 2"/>
        </svg>
      )
    }
  }

  // Email
  if (fileType.includes('email') || fileType.includes('mail') || ext === 'eml') {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <rect x="2" y="4" width="20" height="16" rx="2"/>
          <path d="M22 6l-10 7L2 6"/>
        </svg>
      )
    }
  }

  // Text files
  if (['txt', 'rtf'].includes(ext) || fileType.includes('text')) {
    return {
      color: iconColor,
      bgColor: '#F0EEEC',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
          <path d="M14 2v6h6"/>
          <path d="M8 13h8M8 17h5"/>
        </svg>
      )
    }
  }

  // Default
  return {
    color: iconColor,
    bgColor: '#F0EEEC',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
        <path d="M14 2v6h6"/>
      </svg>
    )
  }
}

export default function Documents() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [activeCategory, setActiveCategory] = useState<string>('All Items')
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [viewingDocument, setViewingDocument] = useState<FullDocument | null>(null)
  const [loadingDocument, setLoadingDocument] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  const [uploadFileCount, setUploadFileCount] = useState<number>(0)
  const [displayLimit, setDisplayLimit] = useState(DISPLAY_PAGE_SIZE)
  const [sortField, setSortField] = useState<string>('created')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [activeFilters, setActiveFilters] = useState<string[]>([])
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [analyzingGaps, setAnalyzingGaps] = useState(false)
  const [showGapsMenu, setShowGapsMenu] = useState(false)
  const [sourceFilter, setSourceFilter] = useState<string>('all')

  // Notification state
  const [showNotifications, setShowNotifications] = useState(false)
  const [clearedNotifications, setClearedNotifications] = useState<Set<string>>(new Set())

  // Invite modal state
  const [showInviteModal, setShowInviteModal] = useState(false)
  const [inviteEmails, setInviteEmails] = useState('')
  const [inviteMessage, setInviteMessage] = useState('')
  const [sendingInvites, setSendingInvites] = useState(false)
  const [inviteResult, setInviteResult] = useState<{sent: string[], failed: {email: string, reason: string}[]} | null>(null)
  const [existingInvitations, setExistingInvitations] = useState<{id: string, recipient_email: string, status: string, created_at: string | null}[]>([])

  const authHeaders = useAuthHeaders()
  const { token, user, logout } = useAuth()
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const gapsMenuRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)

  // Track if we've loaded documents to prevent infinite loops
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    // Load documents when token is ready (only once per session)
    if (token && !hasLoadedRef.current) {
      hasLoadedRef.current = true
      loadDocuments()
    }
  }, [token])

  // Load cleared notifications from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('2b_cleared_notifs')
      if (saved) setClearedNotifications(new Set(JSON.parse(saved)))
    } catch {}
  }, [])

  // Compute notification items: all indexed docs not yet cleared
  const notifications = useMemo(() => {
    return documents
      .filter(d => d.embedded_at && !clearedNotifications.has(d.id))
      .sort((a, b) => {
        // Most recently indexed first
        const aDate = a.embedded_at ? new Date(a.embedded_at).getTime() : 0
        const bDate = b.embedded_at ? new Date(b.embedded_at).getTime() : 0
        return bDate - aDate
      })
  }, [documents, clearedNotifications])

  const clearNotification = useCallback((docId: string) => {
    setClearedNotifications(prev => {
      const next = new Set(prev)
      next.add(docId)
      localStorage.setItem('2b_cleared_notifs', JSON.stringify(Array.from(next)))
      return next
    })
  }, [])

  const clearAllNotifications = useCallback(() => {
    const allIds = documents.filter(d => d.embedded_at).map(d => d.id)
    const merged = Array.from(clearedNotifications).concat(allIds)
    const next = new Set(merged)
    localStorage.setItem('2b_cleared_notifs', JSON.stringify(Array.from(next)))
    setClearedNotifications(next)
  }, [documents, clearedNotifications])

  // Derive unique source types from loaded documents for the filter dropdown
  const availableSources = useMemo(() => {
    const sourceSet = new Set<string>()
    for (const d of documents) {
      if (d.source_type) sourceSet.add(d.source_type.toLowerCase())
    }
    // Sort alphabetically by display label
    return Array.from(sourceSet)
      .map(st => ({ value: st, label: getSourceTypeInfo(st).label }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [documents])

  // Use useMemo for filtered documents - much faster than useState + useEffect
  const filteredDocuments = useMemo(() => {
    let filtered = [...documents]

    if (activeCategory !== 'All Items') {
      filtered = filtered.filter(d => d.category === activeCategory)
    }

    if (sourceFilter !== 'all') {
      filtered = filtered.filter(d => d.source_type?.toLowerCase() === sourceFilter)
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
  }, [documents, activeCategory, sourceFilter, searchQuery, sortField, sortDirection])

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null)
      }
      if (gapsMenuRef.current && !gapsMenuRef.current.contains(event.target as Node)) {
        setShowGapsMenu(false)
      }
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const loadDocuments = async () => {
    try {
      const response = await axios.get(`${API_BASE}/documents?limit=${API_FETCH_LIMIT}`, {
        headers: authHeaders
      })

      if (response.data.success) {
        const apiDocs = response.data.documents
        const docs: Document[] = apiDocs.map((doc: any, index: number) => {
          let category: Document['category'] = 'Other Items'
          const title = doc.title?.toLowerCase() || ''
          const sourceType = doc.source_type?.toLowerCase() || ''
          const classification = doc.classification?.toLowerCase() || ''

          // Categorization logic using shared constants
          const srcInfo = getSourceTypeInfo(doc.source_type)
          if (srcInfo.docType === 'Web Page') {
            category = 'Web Scraper'
          } else if (sourceType === 'github' || sourceType?.includes('code') || CODE_EXTENSIONS_REGEX.test(title)) {
            category = 'Code'
          } else if (classification === 'personal' || classification === 'spam') {
            category = 'Personal Items'
          } else if (classification === 'work') {
            if (MEETING_KEYWORDS.test(title)) {
              category = 'Meetings'
            } else {
              category = 'Documents'
            }
          } else if (['box', 'file', 'notion', 'gdrive', 'zotero', 'onedrive'].includes(sourceType)) {
            category = 'Documents'
          } else if (classification === 'unknown' || !classification) {
            category = 'Documents'
          }

          const createdDate = doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Unknown'
          let displayName = doc.title || 'Untitled Document'
          if (sourceType === 'github' && displayName.includes(' - ')) {
            displayName = displayName.split(' - ').pop() || displayName
          }

          // Quick summary using shared constant
          let quickSummary = ''
          if (sourceType === 'github') {
            quickSummary = 'GitHub Repository'
          } else if (doc.summary?.trim()) {
            const words = doc.summary.split(' ')
            quickSummary = words.slice(0, SUMMARY_WORD_LIMIT).join(' ')
            if (words.length > SUMMARY_WORD_LIMIT) quickSummary += '...'
          } else if (doc.content?.trim()) {
            quickSummary = doc.content.trim().split(/\s+/).slice(0, SUMMARY_WORD_LIMIT).join(' ') + '...'
          } else {
            quickSummary = `${srcInfo.label} file`
          }

          // Document type from shared source map
          const docType = srcInfo.docType

          // Work likelihood score from classification confidence
          let workScore = 50
          if (doc.classification_confidence !== null && doc.classification_confidence !== undefined) {
            const confidence = doc.classification_confidence * 100
            if (classification === 'work') {
              workScore = Math.round(confidence)
            } else if (classification === 'personal' || classification === 'spam') {
              workScore = Math.round(100 - confidence)
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
            url: doc.source_url,
            content: doc.content,
            summary: doc.summary,
            quickSummary,
            score: workScore,
            classificationConfidence: doc.classification_confidence,
            embedded_at: doc.embedded_at || null,
            fileSize: doc.file_size || 0,
          }
        })

        setDocuments(docs)
        setTotalCount(response.data.pagination?.total ?? docs.length)
      } else {
        setDocuments([])
        setTotalCount(0)
      }
    } catch (error) {
      console.error('Error loading documents:', error)
      setDocuments([])
      setTotalCount(0)
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
        const doc = response.data.document
        // For manual uploads with S3 file, open original file in new tab
        const fileUrl = doc.metadata?.file_url
        if (fileUrl && doc.source_type === 'manual_upload') {
          window.open(fileUrl, '_blank')
        } else {
          setViewingDocument(doc)
        }
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
    setUploadProgress(0)
    setUploadFileCount(files.length)
    try {
      const formData = new FormData()
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i])
      }
      // Don't set Content-Type for FormData - browser sets it with boundary automatically
      const response = await axios.post(`${API_BASE}/documents/upload`, formData, {
        headers: { 'Authorization': `Bearer ${token}` },
        timeout: 300000, // 5 minute timeout for large file uploads
        maxContentLength: 100 * 1024 * 1024, // 100MB
        maxBodyLength: 100 * 1024 * 1024, // 100MB
        onUploadProgress: (progressEvent) => {
          const pct = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1))
          setUploadProgress(pct)
        }
      })
      if (response.data.success) {
        loadDocuments()
      } else {
        console.error('Upload failed:', response.data.error)
        alert(`Upload failed: ${response.data.error || 'Unknown error'}`)
      }
    } catch (error: any) {
      console.error('Error uploading files:', error)
      // If upload progress reached 100% but we got a network error, the file likely
      // processed successfully but the response was lost (ALB/proxy timeout).
      if (uploadProgress >= 100 && (error.message === 'Network Error' || error.code === 'ECONNABORTED')) {
        alert('Upload appears to have completed but the connection timed out during processing. Refreshing documents...')
        loadDocuments()
      } else {
        const errorMsg = error.response?.data?.error || error.message || 'Unknown error'
        alert(`Upload failed: ${errorMsg}`)
      }
    } finally {
      setUploading(false)
      setUploadProgress(0)
      setUploadFileCount(0)
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
    const classification = CATEGORY_TO_CLASSIFICATION[newCategory] || 'unknown'

    // Optimistic update
    setDocuments(prev => prev.map(doc =>
      doc.id === docId ? { ...doc, category: newCategory as Document['category'], classification } : doc
    ))
    setOpenMenuId(null)

    try {
      await axios.put(`${API_BASE}/documents/${docId}/classify`, {
        classification
      }, { headers: authHeaders })
    } catch (error) {
      console.error('Error updating document category:', error)
      loadDocuments()
    }
  }

  const handleBulkMoveToCategory = async (newCategory: string) => {
    if (selectedDocs.size === 0) return
    const classification = CATEGORY_TO_CLASSIFICATION[newCategory] || 'unknown'
    const docIds = Array.from(selectedDocs)

    // Optimistic update
    setDocuments(prev => prev.map(doc =>
      selectedDocs.has(doc.id) ? { ...doc, category: newCategory as Document['category'], classification } : doc
    ))
    setSelectedDocs(new Set())

    try {
      await axios.post(`${API_BASE}/documents/bulk/classify`, {
        document_ids: docIds,
        classification
      }, { headers: authHeaders })
    } catch (error) {
      console.error('Error bulk updating categories:', error)
      loadDocuments()
    }
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

  const fetchInvitations = async () => {
    try {
      const response = await axios.get(`${API_BASE}/auth/invitations`, { headers: authHeaders })
      if (response.data.success) {
        setExistingInvitations(response.data.invitations || [])
      }
    } catch (error) {
      console.error('Error fetching invitations:', error)
    }
  }

  const handleSendInvites = async () => {
    const emails = inviteEmails.split(/[,\n]/).map(e => e.trim()).filter(e => e)
    if (emails.length === 0) return

    setSendingInvites(true)
    setInviteResult(null)
    try {
      const response = await axios.post(`${API_BASE}/auth/invite`, {
        emails,
        message: inviteMessage || undefined
      }, { headers: authHeaders })
      if (response.data) {
        setInviteResult({ sent: response.data.sent || [], failed: response.data.failed || [] })
        if (response.data.sent?.length > 0) {
          setInviteEmails('')
          setInviteMessage('')
          fetchInvitations()
        }
      }
    } catch (error: any) {
      const msg = error?.response?.data?.error || 'Failed to send invitations'
      setInviteResult({ sent: [], failed: [{ email: emails.join(', '), reason: msg }] })
    } finally {
      setSendingInvites(false)
    }
  }

  const handleRevokeInvitation = async (invitationId: string) => {
    try {
      await axios.delete(`${API_BASE}/auth/invitations/${invitationId}`, { headers: authHeaders })
      setExistingInvitations(prev => prev.filter(i => i.id !== invitationId))
    } catch (error) {
      console.error('Error revoking invitation:', error)
    }
  }

  const { counts, sizes } = useMemo(() => {
    const c = { all: 0, meetings: 0, documents: 0, personal: 0, code: 0, other: 0, webscraper: 0 }
    const s = { all: 0, meetings: 0, documents: 0, personal: 0, code: 0, other: 0, webscraper: 0 }
    for (const d of documents) {
      c.all++
      s.all += d.fileSize || 0
      switch (d.category) {
        case 'Meetings':       c.meetings++;   s.meetings += d.fileSize || 0; break
        case 'Documents':      c.documents++;  s.documents += d.fileSize || 0; break
        case 'Personal Items': c.personal++;   s.personal += d.fileSize || 0; break
        case 'Code':           c.code++;       s.code += d.fileSize || 0; break
        case 'Other Items':    c.other++;      s.other += d.fileSize || 0; break
        case 'Web Scraper':    c.webscraper++; s.webscraper += d.fileSize || 0; break
      }
    }
    return { counts: c, sizes: s }
  }, [documents])

  // Folder Card Component
  const FolderCard = ({ title, count, size, active, onClick, iconType }: {
    title: string
    count: number
    size: string
    active: boolean
    onClick: () => void
    iconType: 'all' | 'work' | 'code' | 'web' | 'personal'
  }) => {
    const iconColor = active ? colors.primaryHover : '#7A7A7A'
    const bgColor = active ? colors.primaryLight : '#F7F5F3'

    const icons = {
      all: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <rect x="3" y="3" width="7" height="7" rx="1.5"/>
          <rect x="14" y="3" width="7" height="7" rx="1.5"/>
          <rect x="3" y="14" width="7" height="7" rx="1.5"/>
          <rect x="14" y="14" width="7" height="7" rx="1.5"/>
        </svg>
      ),
      work: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
          <path d="M14 2v6h6"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
      ),
      code: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <polyline points="16 18 22 12 16 6"/>
          <polyline points="8 6 2 12 8 18"/>
        </svg>
      ),
      web: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <circle cx="12" cy="12" r="10"/>
          <line x1="2" y1="12" x2="22" y2="12"/>
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>
      ),
      personal: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="1.5">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
      ),
    }

    return (
      <button
        onClick={onClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          padding: '20px 28px',
          backgroundColor: active ? colors.primaryLight : '#F7F5F3',
          border: `1px solid ${active ? '#D4C4BE' : colors.border}`,
          borderRadius: '16px',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          minWidth: '240px',
          boxShadow: shadows.sm,
        }}
        onMouseEnter={(e) => {
          if (!active) e.currentTarget.style.borderColor = '#D4C4BE'
        }}
        onMouseLeave={(e) => {
          if (!active) e.currentTarget.style.borderColor = colors.border
        }}
      >
        <div style={{
          width: '44px',
          height: '44px',
          backgroundColor: bgColor,
          borderRadius: '10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {icons[iconType]}
        </div>
        <div style={{ textAlign: 'left' }}>
          <div style={{
            fontSize: '15px',
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
  }

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
            zIndex: Z_INDEX.dropdown,
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
            {MOVE_CATEGORIES.map((cat) => (
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
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {/* Notifications Bell */}
            <div ref={notifRef} style={{ position: 'relative' }}>
              <button
                onClick={() => setShowNotifications(!showNotifications)}
                style={{
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '40px',
                  height: '40px',
                  backgroundColor: showNotifications ? colors.primaryLight : 'transparent',
                  border: `1px solid ${showNotifications ? colors.primary : colors.border}`,
                  borderRadius: '8px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!showNotifications) {
                    e.currentTarget.style.backgroundColor = colors.primaryLight
                    e.currentTarget.style.borderColor = '#D4C4BE'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!showNotifications) {
                    e.currentTarget.style.backgroundColor = 'transparent'
                    e.currentTarget.style.borderColor = colors.border
                  }
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={colors.textSecondary} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {notifications.length > 0 && (
                  <div style={{
                    position: 'absolute',
                    top: '-4px',
                    right: '-4px',
                    minWidth: '18px',
                    height: '18px',
                    backgroundColor: colors.primary,
                    borderRadius: '9px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '0 4px',
                  }}>
                    <span style={{ fontSize: '10px', fontWeight: 700, color: '#fff', lineHeight: 1 }}>
                      {notifications.length > 99 ? '99+' : notifications.length}
                    </span>
                  </div>
                )}
              </button>

              {/* Notifications Dropdown */}
              {showNotifications && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: '8px',
                  width: '360px',
                  maxHeight: '420px',
                  backgroundColor: colors.cardBg,
                  border: `1px solid ${colors.border}`,
                  borderRadius: '12px',
                  boxShadow: shadows.lg,
                  zIndex: Z_INDEX.dropdown,
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}>
                  {/* Header */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '14px 16px',
                    borderBottom: `1px solid ${colors.border}`,
                  }}>
                    <span style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary }}>
                      Indexed Documents
                    </span>
                    {notifications.length > 0 && (
                      <button
                        onClick={clearAllNotifications}
                        style={{
                          background: 'none',
                          border: 'none',
                          fontSize: '12px',
                          fontWeight: 500,
                          color: colors.primary,
                          cursor: 'pointer',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          transition: 'background-color 0.15s',
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.primaryLight}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        Clear all
                      </button>
                    )}
                  </div>
                  {/* List */}
                  <div style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: notifications.length === 0 ? '0' : '4px 0',
                  }}>
                    {notifications.length === 0 ? (
                      <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '32px 16px',
                        gap: '8px',
                      }}>
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={colors.textMuted} strokeWidth="1.5" style={{ opacity: 0.5 }}>
                          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                        </svg>
                        <span style={{ fontSize: '13px', color: colors.textMuted }}>No new notifications</span>
                      </div>
                    ) : (
                      notifications.map((doc) => (
                        <div
                          key={doc.id}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            padding: '10px 16px',
                            transition: 'background-color 0.15s',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          onClick={() => {
                            if (doc.url) {
                              window.open(doc.url, '_blank', 'noopener,noreferrer')
                            } else {
                              viewDocument(doc.id)
                            }
                          }}
                        >
                          {/* Green dot */}
                          <div style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            backgroundColor: colors.searchableActiveDot,
                            flexShrink: 0,
                          }} />
                          {/* Content */}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              fontSize: '13px',
                              fontWeight: 500,
                              color: colors.textPrimary,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}>
                              {doc.name}
                            </div>
                            <div style={{ fontSize: '11px', color: colors.textMuted, marginTop: '2px' }}>
                              Indexed {doc.embedded_at ? new Date(doc.embedded_at).toLocaleDateString() : ''} &middot; {doc.type}
                            </div>
                          </div>
                          {/* Clear button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              clearNotification(doc.id)
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: '24px',
                              height: '24px',
                              backgroundColor: 'transparent',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              flexShrink: 0,
                              transition: 'background-color 0.15s',
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.border}
                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={colors.textMuted} strokeWidth="2" strokeLinecap="round">
                              <line x1="18" y1="6" x2="6" y2="18"/>
                              <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
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
                  backgroundColor: (documents.length === 0 || analyzingGaps) ? colors.textMuted : colors.primary,
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
                  if (documents.length > 0 && !analyzingGaps) e.currentTarget.style.backgroundColor = colors.primary
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
                    backgroundColor: colors.pageBg,
                    borderRadius: '8px',
                    boxShadow: shadows.md,
                    border: `1px solid ${colors.border}`,
                    minWidth: '160px',
                    zIndex: Z_INDEX.dropdown,
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
            {user?.role === 'admin' && (
            <button
              onClick={() => { setShowInviteModal(true); fetchInvitations() }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                backgroundColor: colors.cardBg,
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
                e.currentTarget.style.backgroundColor = colors.cardBg
                e.currentTarget.style.borderColor = colors.border
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="8.5" cy="7" r="4"/>
                <line x1="20" y1="8" x2="20" y2="14"/>
                <line x1="23" y1="11" x2="17" y2="11"/>
              </svg>
              Invite Members
            </button>
            )}
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
            </div>
          </div>

          <div style={{
            display: 'flex',
            gap: '16px',
            overflowX: 'auto',
            paddingBottom: '8px',
          }}>
            <FolderCard
              title="All Documents"
              count={totalCount}
              size={formatFileSize(sizes.all)}
              active={activeCategory === 'All Items'}
              onClick={() => setActiveCategory('All Items')}
              iconType="all"
            />
            <FolderCard
              title="Work Documents"
              count={counts.documents}
              size={formatFileSize(sizes.documents)}
              active={activeCategory === 'Documents'}
              onClick={() => setActiveCategory('Documents')}
              iconType="work"
            />
            <FolderCard
              title="Code Files"
              count={counts.code}
              size={formatFileSize(sizes.code)}
              active={activeCategory === 'Code'}
              onClick={() => setActiveCategory('Code')}
              iconType="code"
            />
            <FolderCard
              title="Web Scraper"
              count={totalCount > counts.all ? counts.webscraper + (totalCount - counts.all) : counts.webscraper}
              size={formatFileSize(sizes.webscraper)}
              active={activeCategory === 'Web Scraper'}
              onClick={() => setActiveCategory('Web Scraper')}
              iconType="web"
            />
            <FolderCard
              title="Personal & Other"
              count={counts.personal + counts.other}
              size={formatFileSize(sizes.personal + sizes.other)}
              active={activeCategory === 'Personal Items' || activeCategory === 'Other Items'}
              onClick={() => setActiveCategory('Personal Items')}
              iconType="personal"
            />
          </div>
        </div>

        {/* Upload Progress Bar */}
        {uploading && (
          <div style={{
            backgroundColor: colors.cardBg,
            borderRadius: '12px',
            border: `1px solid ${colors.primary}`,
            padding: '16px 20px',
            marginBottom: '16px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={colors.primary} strokeWidth="2" style={{ animation: uploadProgress >= 100 ? 'none' : 'spin 1s linear infinite' }}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <span style={{ fontSize: '14px', fontWeight: 500, color: colors.textPrimary }}>
                  {uploadProgress >= 100 ? 'Processing files...' : `Uploading ${uploadFileCount} file${uploadFileCount !== 1 ? 's' : ''}...`}
                </span>
              </div>
              <span style={{ fontSize: '13px', fontWeight: 600, color: colors.primary }}>
                {uploadProgress >= 100 ? 'Almost done' : `${uploadProgress}%`}
              </span>
            </div>
            <div style={{
              width: '100%',
              height: '6px',
              backgroundColor: colors.borderLight,
              borderRadius: '3px',
              overflow: 'hidden',
            }}>
              {uploadProgress >= 100 ? (
                <div style={{
                  width: '100%',
                  height: '100%',
                  borderRadius: '3px',
                  background: `linear-gradient(90deg, ${colors.primary} 0%, ${colors.primaryHover} 50%, ${colors.primary} 100%)`,
                  backgroundSize: '200% 100%',
                  animation: 'shimmer 1.5s ease-in-out infinite',
                }} />
              ) : (
                <div style={{
                  width: `${uploadProgress}%`,
                  height: '100%',
                  backgroundColor: colors.primary,
                  borderRadius: '3px',
                  transition: 'width 0.3s ease',
                }} />
              )}
            </div>
            <style>{`
              @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
              @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
            `}</style>
          </div>
        )}

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
              {sourceFilter !== 'all' && (
                <FilterPill
                  label={`Source: ${getSourceTypeInfo(sourceFilter).label}`}
                  active
                  hasClose
                  onClose={() => setSourceFilter('all')}
                />
              )}
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
                    {MOVE_CATEGORIES.map(cat => (
                      <option key={cat.value} value={cat.value}>{cat.label}</option>
                    ))}
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
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.textMuted}
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
                  backgroundColor: colors.primary,
                  border: 'none',
                  borderRadius: '6px',
                  color: '#fff',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.primaryHover}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = colors.primary}
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
              {/* Source Filter */}
              {availableSources.length > 1 && (
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  style={{
                    padding: '8px 12px',
                    backgroundColor: sourceFilter !== 'all' ? colors.primaryLight : colors.cardBg,
                    border: `1px solid ${sourceFilter !== 'all' ? colors.primary : colors.border}`,
                    borderRadius: '6px',
                    fontSize: '13px',
                    color: sourceFilter !== 'all' ? colors.primary : colors.textSecondary,
                    cursor: 'pointer',
                    fontWeight: sourceFilter !== 'all' ? 500 : 400,
                  }}
                >
                  <option value="all">All Sources</option>
                  {availableSources.map(src => (
                    <option key={src.value} value={src.value}>{src.label}</option>
                  ))}
                </select>
              )}
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
                gridTemplateColumns: '36px 2fr 1fr 1fr 1fr 48px',
                gap: '16px',
                padding: '12px 20px',
                backgroundColor: colors.border,
                borderBottom: `1px solid ${colors.border}`,
                alignItems: 'center',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '36px', flexShrink: 0 }}>
                  <label style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={selectedDocs.size === filteredDocuments.slice(0, displayLimit).length && filteredDocuments.length > 0}
                      onChange={toggleSelectAll}
                      style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
                    />
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '18px',
                      height: '18px',
                      borderRadius: '4px',
                      border: (selectedDocs.size === filteredDocuments.slice(0, displayLimit).length && filteredDocuments.length > 0) ? `2px solid ${colors.primary}` : `2px solid ${colors.textMuted}`,
                      backgroundColor: (selectedDocs.size === filteredDocuments.slice(0, displayLimit).length && filteredDocuments.length > 0) ? colors.primary : 'transparent',
                      transition: 'all 0.15s ease',
                      flexShrink: 0,
                    }}>
                      {(selectedDocs.size === filteredDocuments.slice(0, displayLimit).length && filteredDocuments.length > 0) && (
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M2.5 6L5 8.5L9.5 3.5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </span>
                  </label>
                </div>
                {[
                  { label: 'Document', field: 'name' },
                  { label: 'Type', field: 'type' },
                  { label: 'Source', field: 'source_type' },
                  { label: 'Date', field: 'created' },
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
                        gridTemplateColumns: '36px 2fr 1fr 1fr 1fr 48px',
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
                      <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '36px', flexShrink: 0 }}>
                        <label style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={selectedDocs.has(doc.id)}
                            onChange={() => toggleDocSelection(doc.id)}
                            style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
                          />
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: '18px',
                            height: '18px',
                            borderRadius: '4px',
                            border: selectedDocs.has(doc.id) ? `2px solid ${colors.primary}` : `2px solid ${colors.textMuted}`,
                            backgroundColor: selectedDocs.has(doc.id) ? colors.primary : 'transparent',
                            transition: 'all 0.15s ease',
                            flexShrink: 0,
                          }}>
                            {selectedDocs.has(doc.id) && (
                              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                <path d="M2.5 6L5 8.5L9.5 3.5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            )}
                          </span>
                        </label>
                      </div>

                      {/* Document Name */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', overflow: 'hidden' }}>
                        {(() => {
                          const fileInfo = getFileTypeInfo(doc.name, doc.type)
                          return (
                            <div style={{
                              width: '36px',
                              height: '36px',
                              backgroundColor: fileInfo.bgColor,
                              borderRadius: '8px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              flexShrink: 0,
                              border: `1px solid ${fileInfo.color}20`,
                            }}>
                              {fileInfo.icon}
                            </div>
                          )
                        })()}
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
                    onClick={() => setDisplayLimit(prev => prev + DISPLAY_PAGE_SIZE)}
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
          zIndex: Z_INDEX.modal,
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
        accept={ACCEPTED_FILE_TYPES}
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />

      {/* Invite Members Modal */}
      {showInviteModal && (
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
            zIndex: Z_INDEX.modal,
          }}
          onClick={() => { setShowInviteModal(false); setInviteResult(null) }}
        >
          <div
            style={{
              backgroundColor: colors.cardBg,
              borderRadius: '16px',
              padding: '32px',
              maxWidth: '520px',
              width: '90%',
              boxShadow: shadows.lg,
              maxHeight: '85vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                Invite Team Members
              </h2>
              <button
                onClick={() => { setShowInviteModal(false); setInviteResult(null) }}
                style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: colors.textMuted, padding: '4px' }}
              >
                &times;
              </button>
            </div>

            <p style={{ color: colors.textSecondary, fontSize: '14px', marginBottom: '20px' }}>
              Invite people by email. They will create an account and join your organization with full access to documents, chatbot, knowledge gaps, and integrations.
            </p>

            {/* Email Input */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: colors.textPrimary, marginBottom: '6px' }}>
                Email addresses
              </label>
              <textarea
                value={inviteEmails}
                onChange={(e) => setInviteEmails(e.target.value)}
                placeholder="Enter emails separated by commas or new lines&#10;e.g. alice@lab.edu, bob@lab.edu"
                rows={3}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '14px',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  backgroundColor: colors.pageBg,
                  color: colors.textPrimary,
                  outline: 'none',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit',
                }}
                onFocus={(e) => { e.target.style.borderColor = colors.primary }}
                onBlur={(e) => { e.target.style.borderColor = colors.border }}
              />
            </div>

            {/* Personal Message */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: colors.textPrimary, marginBottom: '6px' }}>
                Personal message <span style={{ fontWeight: 400, color: colors.textMuted }}>(optional)</span>
              </label>
              <input
                type="text"
                value={inviteMessage}
                onChange={(e) => setInviteMessage(e.target.value)}
                placeholder="Welcome to our knowledge base!"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '14px',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  backgroundColor: colors.pageBg,
                  color: colors.textPrimary,
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => { e.target.style.borderColor = colors.primary }}
                onBlur={(e) => { e.target.style.borderColor = colors.border }}
              />
            </div>

            {/* Send Button */}
            <button
              onClick={handleSendInvites}
              disabled={sendingInvites || !inviteEmails.trim()}
              style={{
                width: '100%',
                padding: '12px 20px',
                fontSize: '14px',
                fontWeight: 600,
                backgroundColor: (sendingInvites || !inviteEmails.trim()) ? colors.textMuted : colors.primary,
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                cursor: (sendingInvites || !inviteEmails.trim()) ? 'not-allowed' : 'pointer',
                marginBottom: '16px',
              }}
            >
              {sendingInvites ? 'Sending invitations...' : 'Send Invitations'}
            </button>

            {/* Result Feedback */}
            {inviteResult && (
              <div style={{ marginBottom: '16px' }}>
                {inviteResult.sent.length > 0 && (
                  <div style={{ padding: '10px 14px', backgroundColor: '#F0FDF4', borderRadius: '8px', marginBottom: '8px', fontSize: '13px', color: '#166534' }}>
                    Invitation sent to: {inviteResult.sent.join(', ')}
                  </div>
                )}
                {inviteResult.failed.length > 0 && inviteResult.failed.map((f, i) => (
                  <div key={i} style={{ padding: '10px 14px', backgroundColor: '#FEF2F2', borderRadius: '8px', marginBottom: '4px', fontSize: '13px', color: '#991B1B' }}>
                    {f.email}: {f.reason}
                  </div>
                ))}
              </div>
            )}

            {/* Existing Invitations List */}
            {existingInvitations.length > 0 && (
              <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '16px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: colors.textMuted, textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.5px' }}>
                  Invitations
                </div>
                {existingInvitations.map((inv) => (
                  <div
                    key={inv.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 12px',
                      backgroundColor: colors.pageBg,
                      borderRadius: '8px',
                      marginBottom: '6px',
                      fontSize: '13px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                      <span style={{ color: colors.textPrimary, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {inv.recipient_email}
                      </span>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: '10px',
                        flexShrink: 0,
                        backgroundColor: inv.status === 'accepted' ? '#DCFCE7' : inv.status === 'revoked' ? '#FEE2E2' : '#FEF3C7',
                        color: inv.status === 'accepted' ? '#166534' : inv.status === 'revoked' ? '#991B1B' : '#92400E',
                      }}>
                        {inv.status}
                      </span>
                      {inv.created_at && (
                        <span style={{ color: colors.textMuted, fontSize: '12px', flexShrink: 0 }}>
                          {new Date(inv.created_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    {inv.status === 'pending' && (
                      <button
                        onClick={() => handleRevokeInvitation(inv.id)}
                        style={{ background: 'none', border: 'none', fontSize: '16px', cursor: 'pointer', color: colors.textMuted, padding: '2px 6px' }}
                        title="Revoke invitation"
                      >
                        &times;
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button
                onClick={() => { setShowInviteModal(false); setInviteResult(null) }}
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
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
