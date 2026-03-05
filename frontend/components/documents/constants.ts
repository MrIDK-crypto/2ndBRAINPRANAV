// ============================================================================
// SHARED CONSTANTS — Documents Page
// Single source of truth for categories, source types, colors, etc.
// ============================================================================

// Design System — Wellspring Warm Palette
export const colors = {
  // Primary - Warm brown accent
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',

  // Backgrounds - Warm neutrals
  pageBg: '#FAF9F7',
  cardBg: '#F7F5F3',

  // Text - Warm tones
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',

  // Borders & Dividers - Warm
  border: '#F0EEEC',
  borderLight: '#F7F5F3',

  // Status Colors - Wellspring Warm Palette
  statusActive: '#C9A598',
  statusSuccess: '#9CB896',
  statusPending: '#F0EEEC',
  statusArchived: '#9A9A9A',
  statusAccent: '#FBF4F1',

  // Searchable status
  searchableActiveBg: '#F0F7EE',
  searchableActiveDot: '#9CB896',
  searchableActiveText: '#5A7D54',
  searchableInactiveBg: '#FBF4F1',
  searchableInactiveDot: '#C9A598',
  searchableInactiveText: '#B8948A',

  // Classification badges
  classificationWork: '#9CB896',
  classificationPersonal: '#F59E0B',
  classificationSpam: '#C9A598',
  classificationUnknown: '#9A9A9A',
}

export const shadows = {
  sm: '0 1px 3px 0 rgba(0, 0, 0, 0.04)',
  md: '0 4px 12px -2px rgba(0, 0, 0, 0.06)',
  lg: '0 8px 24px -4px rgba(0, 0, 0, 0.08)',
}

export const Z_INDEX = {
  dropdown: 100,
  modal: 1000,
}

// Pagination
export const DISPLAY_PAGE_SIZE = 50
export const API_FETCH_LIMIT = 10000

// Summary truncation
export const SUMMARY_WORD_LIMIT = 8

// File upload accepted types
export const ACCEPTED_FILE_TYPES = '.pdf,.doc,.docx,.txt,.csv,.tsv,.xlsx,.xls,.xlsm,.xlsb,.pptx,.ppt,.rtf,.ods,.numbers,.json,.xml,.html,.htm,.md,.zip,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.mp4,.mov,.wav,.mp3,.m4a,.webm'

// ============================================================================
// CATEGORIES
// ============================================================================

export interface CategoryDef {
  label: string
  value: string
  iconType: 'all' | 'work' | 'code' | 'web' | 'personal'
}

export const CATEGORIES: CategoryDef[] = [
  { label: 'Documents', value: 'Documents', iconType: 'work' },
  { label: 'Code', value: 'Code', iconType: 'code' },
  { label: 'Meetings', value: 'Meetings', iconType: 'work' },
  { label: 'Web Scraper', value: 'Web Scraper', iconType: 'web' },
  { label: 'Personal Items', value: 'Personal Items', iconType: 'personal' },
  { label: 'Other Items', value: 'Other Items', iconType: 'personal' },
]

// For the "Move to" menu options
export const MOVE_CATEGORIES = CATEGORIES.map(c => ({ label: c.label, value: c.value }))

// Map category values to backend classification values for the API
export const CATEGORY_TO_CLASSIFICATION: Record<string, string> = {
  'Documents': 'work',
  'Code': 'work',
  'Meetings': 'work',
  'Web Scraper': 'work',
  'Personal Items': 'personal',
  'Other Items': 'unknown',
}

// ============================================================================
// CODE FILE EXTENSIONS
// ============================================================================

export const CODE_EXTENSIONS = new Set([
  'js', 'ts', 'jsx', 'tsx', 'py', 'java', 'cpp', 'c', 'h',
  'css', 'html', 'json', 'xml', 'yaml', 'yml', 'md', 'sh',
  'rb', 'go', 'rs', 'swift', 'kt', 'scala', 'php', 'r',
  'sql', 'vue', 'svelte',
])

// Regex version for testing filenames
export const CODE_EXTENSIONS_REGEX = new RegExp(
  `\\.(${Array.from(CODE_EXTENSIONS).join('|')})$`, 'i'
)

// ============================================================================
// MEETING KEYWORDS
// ============================================================================

export const MEETING_KEYWORDS = /meeting|schedule|agenda|discussion|standup|sync|1:1|retrospective|sprint|planning|retro|kickoff|review meeting/i

// ============================================================================
// SOURCE TYPE MAP
// Used by both Documents.tsx and DocumentViewer.tsx
// ============================================================================

export interface SourceTypeInfo {
  label: string
  icon: string
  color: string
  docType: string
}

export const SOURCE_TYPE_MAP: Record<string, SourceTypeInfo> = {
  github:     { label: 'GitHub',        icon: '💻', color: '#0F172A', docType: 'Code' },
  webscraper: { label: 'Web Page',      icon: '🌐', color: '#6B8F9A', docType: 'Web Page' },
  firecrawl:  { label: 'Web Page',      icon: '🌐', color: '#6B8F9A', docType: 'Web Page' },
  email:      { label: 'Gmail',         icon: '✉️', color: '#B8948A', docType: 'Email' },
  gmail:      { label: 'Gmail',         icon: '✉️', color: '#B8948A', docType: 'Email' },
  slack:      { label: 'Slack',         icon: '💬', color: '#9A7B9A', docType: 'Slack Message' },
  box:        { label: 'Box',           icon: '📦', color: '#6B8F9A', docType: 'Box File' },
  notion:     { label: 'Notion',        icon: '📝', color: '#0F172A', docType: 'Notion Page' },
  gdrive:     { label: 'Google Drive',  icon: '📁', color: '#6B9A6B', docType: 'Google Drive' },
  zotero:     { label: 'Zotero',        icon: '📚', color: '#B8948A', docType: 'Zotero' },
  outlook:    { label: 'Outlook',       icon: '📧', color: '#6B8F9A', docType: 'Outlook Email' },
  onedrive:   { label: 'OneDrive',      icon: '☁️', color: '#6B8F9A', docType: 'OneDrive File' },
  file:       { label: 'Upload',        icon: '📄', color: '#94A3B8', docType: 'Document' },
  manual_upload: { label: 'Upload',     icon: '📄', color: '#94A3B8', docType: 'Document' },
  manual_paste:  { label: 'Paste',      icon: '📋', color: '#94A3B8', docType: 'Document' },
}

export const DEFAULT_SOURCE_INFO: SourceTypeInfo = {
  label: 'Document',
  icon: '📄',
  color: '#94A3B8',
  docType: 'Document',
}

export function getSourceTypeInfo(sourceType?: string): SourceTypeInfo {
  if (!sourceType) return DEFAULT_SOURCE_INFO
  return SOURCE_TYPE_MAP[sourceType.toLowerCase()] || { ...DEFAULT_SOURCE_INFO, label: sourceType }
}

// ============================================================================
// FILE SIZE FORMATTING
// ============================================================================

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}
