'use client'

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import Image from 'next/image'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import { useRouter, useSearchParams } from 'next/navigation'
import DocumentViewer from './DocumentViewer'
import TopNav from '../shared/TopNav'
import {
  colors, shadows, Z_INDEX,
  CATEGORIES, MOVE_CATEGORIES, CATEGORY_TO_CLASSIFICATION,
  CODE_EXTENSIONS, CODE_EXTENSIONS_REGEX, MEETING_KEYWORDS,
  SOURCE_TYPE_MAP, getSourceTypeInfo,
  ACCEPTED_FILE_TYPES, DISPLAY_PAGE_SIZE, API_FETCH_LIMIT, SUMMARY_WORD_LIMIT,
  formatFileSize,
} from './constants'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

// Integration type definition
interface ConnectedIntegration {
  id: string
  name: string
  logo: string
  sourceTypes: string[]  // Matches document source_type values
  connected: boolean
}

// All available integrations with their source_type mappings
// Integration config with sourceTypes that match document source_type values
const INTEGRATION_CONFIG: { id: string; name: string; logo: string; sourceTypes: string[] }[] = [
  { id: 'gmail', name: 'Gmail', logo: '/gmail.png', sourceTypes: ['gmail', 'email'] },
  { id: 'slack', name: 'Slack', logo: '/slack.png', sourceTypes: ['slack'] },
  { id: 'box', name: 'Box', logo: '/box.png', sourceTypes: ['box'] },
  { id: 'github', name: 'GitHub', logo: '/github.png', sourceTypes: ['github'] },
  { id: 'gdrive', name: 'Google Drive', logo: '/gdrive.png', sourceTypes: ['gdrive', 'google_drive'] },
  { id: 'onedrive', name: 'OneDrive', logo: '/outlook.png', sourceTypes: ['onedrive', 'microsoft'] },
  { id: 'notion', name: 'Notion', logo: '/notion.png', sourceTypes: ['notion'] },
  { id: 'zotero', name: 'Zotero', logo: '/zotero.png', sourceTypes: ['zotero'] },
  { id: 'outlook', name: 'Outlook', logo: '/outlook.png', sourceTypes: ['outlook'] },
  { id: 'webscraper', name: 'Web Scraper', logo: '/docs.png', sourceTypes: ['webscraper', 'firecrawl', 'web', 'scraper'] },
  { id: 'email-forwarding', name: 'Email Forwarding', logo: '/email-forward.png', sourceTypes: ['email_forwarding', 'forwarded'] },
  { id: 'pubmed', name: 'PubMed', logo: '/pubmed.png', sourceTypes: ['pubmed'] },
  { id: 'upload', name: 'Uploads', logo: '/docs.png', sourceTypes: ['upload', 'file', 'manual'] },
]

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
const iconColor = '#64748B'

const getFileTypeInfo = (filename: string, type?: string) => {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const fileType = type?.toLowerCase() || ''

  // PDF
  if (ext === 'pdf' || fileType.includes('pdf')) {
    return {
      color: iconColor,
      bgColor: '#E2E8F0',
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
      bgColor: '#E2E8F0',
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
      bgColor: '#E2E8F0',
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
      bgColor: '#E2E8F0',
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
      bgColor: '#E2E8F0',
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
      bgColor: '#E2E8F0',
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
      bgColor: '#E2E8F0',
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
      bgColor: '#E2E8F0',
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
    bgColor: '#E2E8F0',
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
  const [activeIntegration, setActiveIntegration] = useState<string | null>(null)
  const [connectedIntegrations, setConnectedIntegrations] = useState<ConnectedIntegration[]>([])
  const [integrationSliderPosition, setIntegrationSliderPosition] = useState(0)

  // Smart folders state (backend-persisted)
  const [smartFolders, setSmartFolders] = useState<{id: string, name: string, description?: string, color: string, document_ids: string[], document_count: number}[]>([])
  const [activeCustomFolder, setActiveCustomFolder] = useState<string | null>(null)
  const [showNewFolderModal, setShowNewFolderModal] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [newFolderDescription, setNewFolderDescription] = useState('')
  const [newFolderColor, setNewFolderColor] = useState('#B8A394')
  // Smart folder creation flow
  const [folderCreationStep, setFolderCreationStep] = useState<'create' | 'preview'>('create')
  const [folderCandidates, setFolderCandidates] = useState<{id: string, name: string, source_type?: string, score: number, selected: boolean}[]>([])
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [pendingProjectId, setPendingProjectId] = useState<string | null>(null)

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [selectedUploadFolder, setSelectedUploadFolder] = useState<string>('')

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
  const searchParams = useSearchParams()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const gapsMenuRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)
  const integrationSliderRef = useRef<HTMLDivElement>(null)

  // Track if we've loaded documents to prevent infinite loops
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    // Load documents when token is ready (only once per session)
    if (token && !hasLoadedRef.current) {
      hasLoadedRef.current = true
      loadDocuments()
      loadIntegrations()
      loadSmartFolders()
    }
  }, [token])

  // Auto-open a specific document when navigated from Knowledge Gaps
  const highlightHandledRef = useRef(false)
  useEffect(() => {
    const highlightId = searchParams.get('highlight')
    if (highlightId && hasLoadedRef.current && authHeaders?.Authorization && !highlightHandledRef.current) {
      highlightHandledRef.current = true
      viewDocument(highlightId)
    }
  }, [searchParams, authHeaders, documents])

  // Load smart folders from backend
  const loadSmartFolders = async () => {
    try {
      const response = await axios.get(`${API_BASE}/projects`, { headers: authHeaders })
      if (response.data.success) {
        setSmartFolders(response.data.projects || [])
      }
    } catch (e) {
      console.error('Error loading smart folders:', e)
    }
  }

  // Step 1: Submit folder name + description to get candidates
  const createSmartFolder = async () => {
    if (!newFolderName.trim()) return
    setCreatingFolder(true)
    try {
      const response = await axios.post(`${API_BASE}/projects/smart-create`, {
        name: newFolderName.trim(),
        description: newFolderDescription.trim(),
        color: newFolderColor,
      }, { headers: authHeaders })

      if (response.data.success) {
        setPendingProjectId(response.data.project.id)
        const candidates = (response.data.candidates || []).map((c: any) => ({
          ...c,
          selected: true, // All selected by default
        }))
        setFolderCandidates(candidates)
        setFolderCreationStep('preview')
      }
    } catch (e: any) {
      console.error('Error creating smart folder:', e)
      alert(e.response?.data?.error || 'Failed to create folder')
    } finally {
      setCreatingFolder(false)
    }
  }

  // Step 2: Confirm selected documents
  const confirmSmartFolder = async () => {
    if (!pendingProjectId) return
    const selectedIds = folderCandidates.filter(c => c.selected).map(c => c.id)

    setCreatingFolder(true)
    try {
      const response = await axios.post(
        `${API_BASE}/projects/${pendingProjectId}/confirm`,
        { document_ids: selectedIds },
        { headers: authHeaders }
      )

      if (response.data.success) {
        // Reload folders and close modal
        await loadSmartFolders()
        resetFolderModal()
      }
    } catch (e: any) {
      console.error('Error confirming folder:', e)
      alert(e.response?.data?.error || 'Failed to confirm folder')
    } finally {
      setCreatingFolder(false)
    }
  }

  // Delete a smart folder
  const deleteSmartFolder = async (folderId: string) => {
    try {
      await axios.delete(`${API_BASE}/projects/${folderId}`, { headers: authHeaders })
      setSmartFolders(smartFolders.filter(f => f.id !== folderId))
      if (activeCustomFolder === folderId) {
        setActiveCustomFolder(null)
      }
    } catch (e) {
      console.error('Error deleting folder:', e)
    }
  }

  // Add documents to a smart folder
  const addDocumentsToFolder = async (folderId: string, docIds: string[]) => {
    try {
      await axios.post(
        `${API_BASE}/projects/${folderId}/confirm`,
        { document_ids: docIds },
        { headers: authHeaders }
      )
      await loadSmartFolders()
    } catch (e) {
      console.error('Error adding documents to folder:', e)
    }
  }

  // Reset folder creation modal (and clean up abandoned project if needed)
  const resetFolderModal = async () => {
    // If user cancels during preview step, delete the empty project
    if (pendingProjectId && folderCreationStep === 'preview') {
      try {
        await axios.delete(`${API_BASE}/projects/${pendingProjectId}`, { headers: authHeaders })
      } catch (e) {
        // Ignore cleanup errors
      }
    }
    setShowNewFolderModal(false)
    setFolderCreationStep('create')
    setNewFolderName('')
    setNewFolderDescription('')
    setNewFolderColor('#B8A394')
    setFolderCandidates([])
    setPendingProjectId(null)
    setCreatingFolder(false)
  }


  // Load integration statuses
  const loadIntegrations = async () => {
    try {
      const response = await axios.get(`${API_BASE}/integrations`, {
        headers: authHeaders
      })
      if (response.data.success) {
        const apiIntegrations = response.data.integrations || []
        // Map API integrations to our connected integrations list
        const connected: ConnectedIntegration[] = INTEGRATION_CONFIG
          .filter(config => {
            const apiInt = apiIntegrations.find((i: any) =>
              i.type === config.id || config.sourceTypes.includes(i.type)
            )
            return apiInt && apiInt.status === 'connected'
          })
          .map(config => ({
            ...config,
            connected: true
          }))
        setConnectedIntegrations(connected)
      }
    } catch (error) {
      console.error('Error loading integrations:', error)
    }
  }

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

    // Filter by smart folder if selected
    if (activeCustomFolder) {
      const folder = smartFolders.find(f => f.id === activeCustomFolder)
      if (folder) {
        filtered = filtered.filter(d => folder.document_ids.includes(d.id))
      }
    }
    // Filter by integration source if selected
    else if (activeIntegration) {
      const integrationConfig = INTEGRATION_CONFIG.find(i => i.id === activeIntegration)
      if (integrationConfig) {
        filtered = filtered.filter(d =>
          integrationConfig.sourceTypes.some(st =>
            d.source_type?.toLowerCase() === st.toLowerCase()
          )
        )
      }
    } else if (activeCategory !== 'All Items') {
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
  }, [documents, activeCategory, activeIntegration, activeCustomFolder, smartFolders, sourceFilter, searchQuery, sortField, sortDirection])

  // Calculate document counts per integration AND get integrations that have documents
  const { integrationCounts, integrationsWithDocs } = useMemo(() => {
    const counts: Record<string, number> = {}
    const withDocs: ConnectedIntegration[] = []

    INTEGRATION_CONFIG.forEach(config => {
      // Count documents that match ANY of the sourceTypes for this integration
      const count = documents.filter(d =>
        config.sourceTypes.some(st =>
          d.source_type?.toLowerCase() === st.toLowerCase()
        )
      ).length
      counts[config.id] = count

      // Add to list if this integration has documents
      if (count > 0) {
        withDocs.push({ ...config, connected: true })
      }
    })
    return { integrationCounts: counts, integrationsWithDocs: withDocs }
  }, [documents])

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

  // Handle file selection - just store files when modal is open
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    if (showUploadModal) {
      // Modal is open - just store files for later upload
      setUploadFiles(Array.from(files))
      if (fileInputRef.current) fileInputRef.current.value = ''
    } else {
      // Direct upload (no modal) - upload immediately
      uploadFiles_internal(Array.from(files))
    }
  }

  // Internal upload function
  const uploadFiles_internal = async (files: File[]) => {
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
        // Add uploaded documents to selected smart folder if any
        const docIds = response.data.document_ids || response.data.documents?.map((d: any) => d.id) || []
        if (selectedUploadFolder && docIds.length > 0) {
          try {
            await axios.post(`${API_BASE}/projects/${selectedUploadFolder}/confirm`, { document_ids: docIds }, { headers: authHeaders })
            await loadSmartFolders()
          } catch (e) {
            console.error('Error adding uploaded docs to folder:', e)
          }
        }
        loadDocuments()
        setShowUploadModal(false)
        setUploadFiles([])
        setSelectedUploadFolder('')
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

  // Upload the files that were selected in the modal
  const handleUploadFromModal = () => {
    if (uploadFiles.length > 0) {
      uploadFiles_internal(uploadFiles)
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
    const iconColor = active ? colors.primaryHover : '#64748B'
    const bgColor = active ? colors.primaryLight : '#F1F5F9'

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
          backgroundColor: active ? colors.primaryLight : '#F1F5F9',
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

  // Integration Folder Card Component - shows integration logo and only appears when connected
  const IntegrationFolderCard = ({ integration, count, active, onClick }: {
    integration: ConnectedIntegration
    count: number
    active: boolean
    onClick: () => void
  }) => (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
        padding: '16px 20px',
        backgroundColor: active ? colors.primaryLight : '#F1F5F9',
        border: `2px solid ${active ? colors.primary : colors.border}`,
        borderRadius: '12px',
        cursor: 'pointer',
        transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        minWidth: '180px',
        flexShrink: 0,
        boxShadow: active ? `0 4px 12px rgba(37, 99, 235, 0.2)` : shadows.sm,
        transform: active ? 'scale(1.02)' : 'scale(1)',
      }}
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.borderColor = colors.primary
          e.currentTarget.style.backgroundColor = colors.primaryLight
          e.currentTarget.style.transform = 'scale(1.02)'
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.borderColor = colors.border
          e.currentTarget.style.backgroundColor = '#F1F5F9'
          e.currentTarget.style.transform = 'scale(1)'
        }
      }}
    >
      <div style={{
        width: '40px',
        height: '40px',
        backgroundColor: '#fff',
        borderRadius: '10px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        overflow: 'hidden',
      }}>
        <Image
          src={integration.logo}
          alt={integration.name}
          width={28}
          height={28}
          style={{ objectFit: 'contain' }}
        />
      </div>
      <div style={{ textAlign: 'left' }}>
        <div style={{
          fontSize: '14px',
          fontWeight: 600,
          color: colors.textPrimary,
          marginBottom: '2px',
        }}>
          {integration.name}
        </div>
        <div style={{
          fontSize: '12px',
          color: colors.textMuted,
        }}>
          {count} {count === 1 ? 'file' : 'files'}
        </div>
      </div>
    </button>
  )

  // Slider scroll handler
  const handleSliderScroll = (direction: 'left' | 'right') => {
    if (integrationSliderRef.current) {
      const scrollAmount = 200
      const newPosition = direction === 'left'
        ? Math.max(0, integrationSliderPosition - scrollAmount)
        : integrationSliderPosition + scrollAmount
      integrationSliderRef.current.scrollTo({
        left: newPosition,
        behavior: 'smooth'
      })
      setIntegrationSliderPosition(newPosition)
    }
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
      <div style={{ position: 'relative', zIndex: 10 }} ref={openMenuId === docId ? menuRef : null}>
        <button
          onClick={(e) => {
            e.stopPropagation()
            e.preventDefault()
            setOpenMenuId(openMenuId === docId ? null : docId)
          }}
          style={{
            width: '40px',
            height: '40px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'background-color 0.15s ease',
            position: 'relative',
            zIndex: 10,
            pointerEvents: 'auto',
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill={colors.textMuted} style={{ pointerEvents: 'none' }}>
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
            zIndex: 9999,
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
            {/* Smart Folders first */}
            {smartFolders.map((folder) => (
              <button
                key={folder.id}
                onClick={(e) => { e.stopPropagation(); addDocumentsToFolder(folder.id, [docId]); setOpenMenuId(null) }}
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
                <svg width="16" height="16" viewBox="0 0 24 24" fill={folder.color}>
                  <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
                </svg>
                {folder.name}
              </button>
            ))}
            {smartFolders.length > 0 && (
              <div style={{ height: '1px', backgroundColor: colors.border, margin: '4px 0' }} />
            )}
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
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: colors.pageBg }}>
      {/* Top Navigation */}
      <TopNav userName={user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'User'} />

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
                            // For emails, always show in modal viewer
                            const isEmail = doc.source_type === 'email' || doc.source_type === 'email_attachment'
                            if (isEmail) {
                              viewDocument(doc.id)
                            } else if (doc.url) {
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
              onClick={() => setShowUploadModal(true)}
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

        {/* Integration Folders Section - Shows All + Integration-based folders */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <h2 style={{
                fontSize: '16px',
                fontWeight: 600,
                color: colors.textPrimary,
                margin: 0,
              }}>
                Sources
              </h2>
              <button
                onClick={() => setShowNewFolderModal(true)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  backgroundColor: 'transparent',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  color: colors.textSecondary,
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14"/>
                </svg>
                New Folder
              </button>
            </div>
            {(integrationsWithDocs.length + smartFolders.length) > 4 && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => handleSliderScroll('left')}
                  style={{
                    width: '32px',
                    height: '32px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: colors.cardBg,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '8px',
                    cursor: 'pointer',
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={colors.textSecondary} strokeWidth="2">
                    <path d="M15 18l-6-6 6-6"/>
                  </svg>
                </button>
                <button
                  onClick={() => handleSliderScroll('right')}
                  style={{
                    width: '32px',
                    height: '32px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: colors.cardBg,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '8px',
                    cursor: 'pointer',
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={colors.textSecondary} strokeWidth="2">
                    <path d="M9 18l6-6-6-6"/>
                  </svg>
                </button>
              </div>
            )}
          </div>

          <div
            ref={integrationSliderRef}
            onScroll={(e) => setIntegrationSliderPosition(e.currentTarget.scrollLeft)}
            style={{
              display: 'flex',
              gap: '16px',
              overflowX: 'auto',
              paddingBottom: '8px',
              scrollBehavior: 'smooth',
              scrollbarWidth: 'none',
              msOverflowStyle: 'none',
            }}
          >
            {/* All Documents Card */}
            <button
              onClick={() => { setActiveIntegration(null); setActiveCategory('All Items'); setActiveCustomFolder(null) }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                padding: '20px 28px',
                backgroundColor: (!activeIntegration && !activeCustomFolder) ? colors.primaryLight : '#F1F5F9',
                border: `2px solid ${!activeIntegration ? colors.primary : colors.border}`,
                borderRadius: '16px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                minWidth: '240px',
                flexShrink: 0,
                boxShadow: !activeIntegration ? '0 4px 12px rgba(37, 99, 235, 0.15)' : shadows.sm,
              }}
            >
              <div style={{
                width: '44px',
                height: '44px',
                backgroundColor: !activeIntegration ? colors.primaryLight : '#E2E8F0',
                borderRadius: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={!activeIntegration ? colors.primary : '#64748B'} strokeWidth="1.5">
                  <rect x="3" y="3" width="7" height="7" rx="1.5"/>
                  <rect x="14" y="3" width="7" height="7" rx="1.5"/>
                  <rect x="3" y="14" width="7" height="7" rx="1.5"/>
                  <rect x="14" y="14" width="7" height="7" rx="1.5"/>
                </svg>
              </div>
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: '15px', fontWeight: 600, color: colors.textPrimary, marginBottom: '4px' }}>
                  All Documents
                </div>
                <div style={{ fontSize: '13px', color: colors.textMuted }}>
                  {totalCount} files
                </div>
              </div>
            </button>

            {/* Smart Folder Cards - shown first */}
            {smartFolders.map((folder) => {
              const isActive = activeCustomFolder === folder.id
              return (
                <button
                  key={folder.id}
                  onClick={() => { setActiveCustomFolder(folder.id); setActiveIntegration(null); setActiveCategory('') }}
                  onMouseEnter={(e) => {
                    const deleteBtn = e.currentTarget.querySelector('[data-delete-btn]') as HTMLElement
                    if (deleteBtn) deleteBtn.style.opacity = '1'
                  }}
                  onMouseLeave={(e) => {
                    const deleteBtn = e.currentTarget.querySelector('[data-delete-btn]') as HTMLElement
                    if (deleteBtn) deleteBtn.style.opacity = '0'
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    padding: '20px 28px',
                    backgroundColor: isActive ? colors.primaryLight : '#F1F5F9',
                    border: `2px solid ${isActive ? colors.primary : colors.border}`,
                    borderRadius: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    minWidth: '240px',
                    flexShrink: 0,
                    boxShadow: isActive ? '0 4px 12px rgba(37, 99, 235, 0.15)' : shadows.sm,
                    position: 'relative',
                  }}
                >
                  <div style={{
                    width: '44px',
                    height: '44px',
                    backgroundColor: (folder.color || '#B8A394') + '20',
                    borderRadius: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill={folder.color || '#B8A394'}>
                      <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
                    </svg>
                  </div>
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: colors.textPrimary, marginBottom: '4px' }}>
                      {folder.name}
                    </div>
                    <div style={{ fontSize: '13px', color: colors.textMuted }}>
                      {folder.document_count} files
                    </div>
                  </div>
                  {/* Delete button - only visible on hover */}
                  <button
                    data-delete-btn
                    onClick={(e) => { e.stopPropagation(); if(confirm(`Delete folder "${folder.name}"?`)) deleteSmartFolder(folder.id) }}
                    title="Delete folder"
                    style={{
                      position: 'absolute',
                      top: '10px',
                      right: '10px',
                      width: '28px',
                      height: '28px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: '#E2E8F0',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      opacity: 0,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#D4C4BE' }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#E2E8F0' }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B7355" strokeWidth="2.5">
                      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z"/>
                    </svg>
                  </button>
                </button>
              )
            })}

            {/* Integration-based Folder Cards */}
            {integrationsWithDocs.map((integration) => {
              const isActive = activeIntegration === integration.id
              const iconColor = isActive ? colors.primary : '#64748B'

              // Clean, modern icons for each integration type
              const getIcon = () => {
                switch (integration.id) {
                  case 'gmail':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                      </svg>
                    )
                  case 'outlook':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.5L18.5 7 12 9.5 5.5 7 12 4.5zM4 8.5l7 3.5v7l-7-3.5v-7zm9 10.5v-7l7-3.5v7l-7 3.5z"/>
                      </svg>
                    )
                  case 'email-forwarding':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2">
                        <path d="M22 12h-6m6 0l-3-3m3 3l-3 3"/>
                        <rect x="2" y="5" width="14" height="14" rx="2"/>
                        <path d="M2 7l7 5 7-5"/>
                      </svg>
                    )
                  case 'slack':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.124 2.521a2.528 2.528 0 0 1 2.52-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.52V8.834zm-1.271 0a2.528 2.528 0 0 1-2.521 2.521 2.528 2.528 0 0 1-2.521-2.521V2.522A2.528 2.528 0 0 1 15.166 0a2.528 2.528 0 0 1 2.521 2.522v6.312zm-2.521 10.124a2.528 2.528 0 0 1 2.521 2.52A2.528 2.528 0 0 1 15.166 24a2.528 2.528 0 0 1-2.521-2.522v-2.52h2.521zm0-1.271a2.528 2.528 0 0 1-2.521-2.521 2.528 2.528 0 0 1 2.521-2.521h6.312A2.528 2.528 0 0 1 24 15.166a2.528 2.528 0 0 1-2.522 2.521h-6.312z"/>
                      </svg>
                    )
                  case 'github':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
                      </svg>
                    )
                  case 'webscraper':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M2 12h20"/>
                        <path d="M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20"/>
                      </svg>
                    )
                  case 'gdrive':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M8.267 14.68l-1.6 2.76H1.6l1.6-2.76h5.067zm7.466-9.36L19.2 12H8.267l3.467-6.68h4zm-1.6 2.76L10.8 14.68H2.667L6 8.08h8.133zM22.4 12l-3.467 6H9.867l3.466-6H22.4z"/>
                      </svg>
                    )
                  case 'onedrive':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M19.35 10.04A7.49 7.49 0 0 0 12 4C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z"/>
                      </svg>
                    )
                  case 'box':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M21 4H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-9 14l-7-7 1.41-1.41L12 15.17l7.59-7.59L21 9l-9 9z"/>
                      </svg>
                    )
                  case 'notion':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2h11A2.5 2.5 0 0 1 20 4.5v15a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 19.5v-15zM7 7v2h10V7H7zm0 4v2h10v-2H7zm0 4v2h6v-2H7z"/>
                      </svg>
                    )
                  case 'zotero':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm2 4v2h6l-6 6v2h10v-2h-6l6-6V7H7z"/>
                      </svg>
                    )
                  case 'pubmed':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2">
                        <path d="M12 6.5a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0z"/>
                        <path d="M7 11v6h1v4h4v-4h1v-6"/>
                        <path d="M15 8h6M15 12h6M15 16h4"/>
                      </svg>
                    )
                  case 'upload':
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                      </svg>
                    )
                  default:
                    return (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill={iconColor}>
                        <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm4 18H6V4h7v5h5v11z"/>
                      </svg>
                    )
                }
              }

              // Get document IDs for this integration
              const integrationConfig = INTEGRATION_CONFIG.find(c => c.id === integration.id)
              const integrationDocIds = integrationConfig
                ? documents.filter(d => integrationConfig.sourceTypes.some(st => d.source_type?.toLowerCase() === st.toLowerCase())).map(d => d.id)
                : []

              const handleDeleteIntegrationDocs = async () => {
                if (!confirm(`Delete all ${integrationCounts[integration.id]} documents from ${integration.name}?`)) return
                for (const docId of integrationDocIds) {
                  try {
                    await axios.delete(`${API_BASE}/documents/${docId}`, { headers: authHeaders })
                  } catch (err) {
                    console.error('Error deleting doc:', err)
                  }
                }
                loadDocuments()
                if (activeIntegration === integration.id) setActiveIntegration(null)
              }

              return (
                <button
                  key={integration.id}
                  onClick={() => { setActiveIntegration(integration.id); setActiveCategory('') }}
                  onMouseEnter={(e) => {
                    const deleteBtn = e.currentTarget.querySelector('[data-delete-btn]') as HTMLElement
                    if (deleteBtn) deleteBtn.style.opacity = '1'
                  }}
                  onMouseLeave={(e) => {
                    const deleteBtn = e.currentTarget.querySelector('[data-delete-btn]') as HTMLElement
                    if (deleteBtn) deleteBtn.style.opacity = '0'
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    padding: '20px 28px',
                    backgroundColor: isActive ? colors.primaryLight : '#F1F5F9',
                    border: `2px solid ${isActive ? colors.primary : colors.border}`,
                    borderRadius: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    minWidth: '240px',
                    flexShrink: 0,
                    boxShadow: isActive ? '0 4px 12px rgba(37, 99, 235, 0.15)' : shadows.sm,
                    position: 'relative',
                  }}
                >
                  <div style={{
                    width: '44px',
                    height: '44px',
                    backgroundColor: isActive ? colors.primaryLight : '#E2E8F0',
                    borderRadius: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    {getIcon()}
                  </div>
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: colors.textPrimary, marginBottom: '4px' }}>
                      {integration.name}
                    </div>
                    <div style={{ fontSize: '13px', color: colors.textMuted }}>
                      {integrationCounts[integration.id]} files
                    </div>
                  </div>
                  {/* Delete button - only visible on hover */}
                  <button
                    data-delete-btn
                    onClick={(e) => { e.stopPropagation(); handleDeleteIntegrationDocs() }}
                    title={`Delete all ${integration.name} documents`}
                    style={{
                      position: 'absolute',
                      top: '10px',
                      right: '10px',
                      width: '28px',
                      height: '28px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: '#E2E8F0',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      opacity: 0,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#D4C4BE' }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#E2E8F0' }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8B7355" strokeWidth="2.5">
                      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z"/>
                    </svg>
                  </button>
                </button>
              )
            })}

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
          overflow: 'visible',
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
                        if (e.target.value.startsWith('folder_')) {
                          // Move to custom folder
                          const folderId = e.target.value.replace('folder_', '')
                          addDocumentsToFolder(folderId, Array.from(selectedDocs))
                          setSelectedDocs(new Set())
                        } else {
                          handleBulkMoveToCategory(e.target.value)
                        }
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
                    {smartFolders.length > 0 && (
                      <optgroup label="Smart Folders">
                        {smartFolders.map(folder => (
                          <option key={folder.id} value={`folder_${folder.id}`}>{folder.name}</option>
                        ))}
                      </optgroup>
                    )}
                    <optgroup label="Categories">
                      {MOVE_CATEGORIES.map(cat => (
                        <option key={cat.value} value={cat.value}>{cat.label}</option>
                      ))}
                    </optgroup>
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
                gridTemplateColumns: '36px 2fr 1fr 1fr 1fr 60px',
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
                        gridTemplateColumns: '36px 2fr 1fr 1fr 1fr 60px',
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
                        // For emails, always show in modal viewer
                        const isEmail = doc.source_type === 'email' || doc.source_type === 'email_attachment'
                        if (isEmail) {
                          viewDocument(doc.id)
                        } else if (doc.url) {
                          window.open(doc.url, '_blank', 'noopener,noreferrer')
                        } else {
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
                      <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: '100%',
                          height: '100%',
                          position: 'relative',
                          zIndex: 5,
                          pointerEvents: 'auto',
                        }}
                      >
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
        onChange={handleFileSelect}
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

      {/* Smart Folder Modal */}
      {showNewFolderModal && (
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
          onClick={() => resetFolderModal()}
        >
          <div
            style={{
              backgroundColor: colors.cardBg,
              borderRadius: '16px',
              padding: '24px',
              width: folderCreationStep === 'preview' ? '600px' : '440px',
              maxWidth: '90%',
              maxHeight: '80vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: shadows.lg,
              transition: 'width 0.2s ease',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {folderCreationStep === 'create' ? (
              <>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 6px 0' }}>
                  Create Smart Folder
                </h3>
                <p style={{ fontSize: '13px', color: colors.textMuted, margin: '0 0 20px 0' }}>
                  We'll find matching documents based on your folder name and description.
                </p>
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: colors.textSecondary, marginBottom: '8px' }}>
                    Folder Name
                  </label>
                  <input
                    type="text"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder="e.g., Marketing Campaigns"
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      fontSize: '14px',
                      border: `1px solid ${colors.border}`,
                      borderRadius: '8px',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                    autoFocus
                  />
                </div>
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: colors.textSecondary, marginBottom: '8px' }}>
                    Description
                  </label>
                  <textarea
                    value={newFolderDescription}
                    onChange={(e) => setNewFolderDescription(e.target.value)}
                    placeholder="Briefly describe what documents belong here..."
                    rows={3}
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      fontSize: '14px',
                      border: `1px solid ${colors.border}`,
                      borderRadius: '8px',
                      outline: 'none',
                      boxSizing: 'border-box',
                      resize: 'vertical',
                      fontFamily: 'inherit',
                    }}
                  />
                </div>
                <div style={{ marginBottom: '20px' }}>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: colors.textSecondary, marginBottom: '8px' }}>
                    Color
                  </label>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {['#B8A394', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#EF4444', '#14B8A6'].map((color) => (
                      <button
                        key={color}
                        onClick={() => setNewFolderColor(color)}
                        style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '8px',
                          backgroundColor: color,
                          border: newFolderColor === color ? '3px solid #000' : '2px solid transparent',
                          cursor: 'pointer',
                        }}
                      />
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                  <button
                    onClick={() => resetFolderModal()}
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
                    onClick={createSmartFolder}
                    disabled={!newFolderName.trim() || creatingFolder}
                    style={{
                      padding: '10px 20px',
                      fontSize: '14px',
                      fontWeight: 500,
                      backgroundColor: (!newFolderName.trim() || creatingFolder) ? colors.textMuted : colors.primary,
                      border: 'none',
                      borderRadius: '8px',
                      color: '#fff',
                      cursor: (!newFolderName.trim() || creatingFolder) ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    {creatingFolder && (
                      <div style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.6s linear infinite' }} />
                    )}
                    {creatingFolder ? 'Finding documents...' : 'Find Documents'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                    Review Matches
                  </h3>
                  <span style={{ fontSize: '13px', color: colors.textMuted }}>
                    {folderCandidates.filter(c => c.selected).length} of {folderCandidates.length} selected
                  </span>
                </div>
                <p style={{ fontSize: '13px', color: colors.textMuted, margin: '0 0 16px 0' }}>
                  These documents match <strong style={{ color: colors.textPrimary }}>"{newFolderName}"</strong>. Uncheck any you don't want.
                </p>

                {/* Select/Deselect all */}
                <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
                  <button
                    onClick={() => setFolderCandidates(folderCandidates.map(c => ({ ...c, selected: true })))}
                    style={{ fontSize: '12px', color: colors.primary, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500 }}
                  >
                    Select All
                  </button>
                  <button
                    onClick={() => setFolderCandidates(folderCandidates.map(c => ({ ...c, selected: false })))}
                    style={{ fontSize: '12px', color: colors.textMuted, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500 }}
                  >
                    Deselect All
                  </button>
                </div>

                {/* Candidates list */}
                <div style={{ flex: 1, overflowY: 'auto', marginBottom: '16px', maxHeight: '400px' }}>
                  {folderCandidates.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px 20px', color: colors.textMuted }}>
                      <p style={{ fontSize: '14px', margin: 0 }}>No matching documents found.</p>
                      <p style={{ fontSize: '13px', margin: '8px 0 0 0' }}>Try a different name or description.</p>
                    </div>
                  ) : (
                    folderCandidates.map((candidate) => (
                      <label
                        key={candidate.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                          padding: '10px 12px',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          backgroundColor: candidate.selected ? colors.primaryLight : 'transparent',
                          transition: 'background-color 0.15s ease',
                          marginBottom: '2px',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={candidate.selected}
                          onChange={() => {
                            setFolderCandidates(folderCandidates.map(c =>
                              c.id === candidate.id ? { ...c, selected: !c.selected } : c
                            ))
                          }}
                          style={{ width: '16px', height: '16px', accentColor: colors.primary, flexShrink: 0 }}
                        />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: '14px', fontWeight: 500, color: colors.textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {candidate.name}
                          </div>
                          {candidate.source_type && (
                            <div style={{ fontSize: '12px', color: colors.textMuted, marginTop: '2px' }}>
                              {candidate.source_type}
                            </div>
                          )}
                        </div>
                        <div style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          color: candidate.score > 0.5 ? '#10B981' : candidate.score > 0.3 ? '#F59E0B' : colors.textMuted,
                          backgroundColor: candidate.score > 0.5 ? '#10B98115' : candidate.score > 0.3 ? '#F59E0B15' : colors.border,
                          padding: '3px 8px',
                          borderRadius: '6px',
                          flexShrink: 0,
                        }}>
                          {Math.round(candidate.score * 100)}%
                        </div>
                      </label>
                    ))
                  )}
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'space-between' }}>
                  <button
                    onClick={() => setFolderCreationStep('create')}
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
                    Back
                  </button>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <button
                      onClick={() => resetFolderModal()}
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
                      onClick={confirmSmartFolder}
                      disabled={creatingFolder || folderCandidates.filter(c => c.selected).length === 0}
                      style={{
                        padding: '10px 20px',
                        fontSize: '14px',
                        fontWeight: 500,
                        backgroundColor: (creatingFolder || folderCandidates.filter(c => c.selected).length === 0) ? colors.textMuted : colors.primary,
                        border: 'none',
                        borderRadius: '8px',
                        color: '#fff',
                        cursor: (creatingFolder || folderCandidates.filter(c => c.selected).length === 0) ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      {creatingFolder && (
                        <div style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.6s linear infinite' }} />
                      )}
                      {creatingFolder ? 'Creating...' : `Create Folder (${folderCandidates.filter(c => c.selected).length})`}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Upload Modal with Folder Selection */}
      {showUploadModal && (
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
          onClick={() => { setShowUploadModal(false); setUploadFiles([]); setSelectedUploadFolder('') }}
        >
          <div
            style={{
              backgroundColor: colors.cardBg,
              borderRadius: '16px',
              padding: '24px',
              width: '500px',
              maxWidth: '90%',
              boxShadow: shadows.lg,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 20px 0' }}>
              Add Documents
            </h3>

            {/* File Selection */}
            <div
              style={{
                border: `2px dashed ${colors.border}`,
                borderRadius: '12px',
                padding: '32px',
                textAlign: 'center',
                marginBottom: '20px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={colors.textMuted} strokeWidth="1.5" style={{ margin: '0 auto 12px' }}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              {uploadFiles.length > 0 ? (
                <div style={{ fontSize: '14px', color: colors.textPrimary }}>
                  {uploadFiles.length} file{uploadFiles.length > 1 ? 's' : ''} selected
                </div>
              ) : (
                <>
                  <div style={{ fontSize: '14px', color: colors.textPrimary, marginBottom: '4px' }}>
                    Click to select files
                  </div>
                  <div style={{ fontSize: '12px', color: colors.textMuted }}>
                    PDF, DOC, TXT, CSV, Excel
                  </div>
                </>
              )}
            </div>

            {/* Folder Selection */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: colors.textSecondary, marginBottom: '8px' }}>
                Add to Folder (optional)
              </label>
              <select
                value={selectedUploadFolder}
                onChange={(e) => setSelectedUploadFolder(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  fontSize: '14px',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  outline: 'none',
                  backgroundColor: colors.cardBg,
                  color: colors.textPrimary,
                  cursor: 'pointer',
                }}
              >
                <option value="">No folder (All Documents)</option>
                {smartFolders.map((folder) => (
                  <option key={folder.id} value={folder.id}>{folder.name}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setShowUploadModal(false); setUploadFiles([]); setSelectedUploadFolder('') }}
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
                onClick={() => {
                  if (uploadFiles.length > 0) {
                    handleUploadFromModal()
                  } else {
                    fileInputRef.current?.click()
                  }
                }}
                disabled={uploading}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  fontWeight: 500,
                  backgroundColor: uploading ? colors.textMuted : colors.primary,
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  cursor: uploading ? 'not-allowed' : 'pointer',
                }}
              >
                {uploading ? 'Uploading...' : uploadFiles.length > 0 ? 'Upload' : 'Select Files'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
