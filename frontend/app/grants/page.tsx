'use client'

import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import Sidebar from '@/components/shared/Sidebar'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

// Wellspring warm theme (matching existing app)
const theme = {
  pageBg: '#FAF9F6',
  cardBg: '#FFFFFE',
  glassBg: 'rgba(250, 249, 246, 0.92)',
  ink: '#2D2D2D',
  body: '#4A4A4A',
  muted: '#6B6B6B',
  subtle: '#9A9A9A',
  accent: '#C9A598',
  accentHover: '#B8948A',
  accentLight: '#FBF4F1',
  border: '#F0EEEC',
  borderMed: '#E8E5E2',
  green: '#22C55E',
  greenBg: 'rgba(34, 197, 94, 0.08)',
  yellow: '#D97706',
  yellowBg: 'rgba(217, 119, 6, 0.08)',
  red: '#EF4444',
  redBg: 'rgba(239, 68, 68, 0.06)',
  grayBadge: '#9CA3AF',
}

const fonts = {
  serif: '"Merriweather", Georgia, "Times New Roman", serif',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  mono: '"JetBrains Mono", "Fira Code", monospace',
}

interface GrantResult {
  id: string
  source: 'nih_reporter' | 'grants_gov'
  title: string
  abstract: string
  agency: string
  agency_full: string
  pi_name: string
  pi_title: string
  organization: string
  org_location: string
  award_amount: number
  start_date: string
  end_date: string
  deadline: string | null
  activity_code: string
  project_num: string
  status: string
  url: string
  fit_score: number
  fit_reasons: string[]
  matching_docs: { id: string; title: string; similarity: number }[]
}

interface LabProfile {
  research_areas: string[]
  keywords: string[]
  department: string
  institution: string
  preferred_agencies: string[]
  budget_range: { min: number; max: number }
  activity_codes: string[]
  auto_generated: boolean
  last_updated: string
}

const AGENCIES = ['NIH', 'NSF', 'DOE', 'DOD', 'NASA', 'USDA']
const ACTIVITY_CODES = [
  { code: 'R01', label: 'Research Project' },
  { code: 'R21', label: 'Exploratory/Dev' },
  { code: 'R03', label: 'Small Grant' },
  { code: 'R35', label: 'Outstanding Investigator' },
  { code: 'R41', label: 'SBIR Phase I' },
  { code: 'R42', label: 'SBIR Phase II' },
  { code: 'K99', label: 'Pathway to Independence' },
  { code: 'F32', label: 'Postdoc Fellowship' },
  { code: 'T32', label: 'Training Grant' },
  { code: 'U01', label: 'Cooperative Agreement' },
  { code: 'P01', label: 'Program Project' },
]

const COMING_SOON_FEATURES = [
  {
    title: 'Talking Points Generator',
    description: 'Generate key arguments and impact statements from your lab\'s publications for grant narratives',
    icon: '💬',
  },
  {
    title: 'Budget Template Helper',
    description: 'Pre-fill budget justifications based on similar funded grants in your field',
    icon: '📊',
  },
  {
    title: 'Compliance Checklist',
    description: 'NIH/NSF-specific submission requirements with auto-check against your documents',
    icon: '✅',
  },
  {
    title: 'Prior Art Finder',
    description: 'Surface relevant papers and preliminary data from your lab\'s collection',
    icon: '🔍',
  },
  {
    title: 'Application Draft Assistant',
    description: 'AI-assisted specific aims, significance sections, and research strategy drafts',
    icon: '✍️',
  },
]

function formatCurrency(amount: number): string {
  if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`
  if (amount >= 1000) return `$${(amount / 1000).toFixed(0)}K`
  if (amount > 0) return `$${amount.toLocaleString()}`
  return ''
}

function getScoreColor(score: number) {
  if (score >= 70) return { color: theme.green, bg: theme.greenBg, label: 'Strong Match' }
  if (score >= 40) return { color: theme.yellow, bg: theme.yellowBg, label: 'Moderate Match' }
  return { color: theme.grayBadge, bg: 'rgba(156, 163, 175, 0.08)', label: 'Low Match' }
}

function getDeadlineUrgency(deadline: string | null) {
  if (!deadline) return null
  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  if (days < 0) return { color: theme.subtle, label: 'Closed', urgent: false }
  if (days <= 7) return { color: theme.red, label: `${days}d left`, urgent: true }
  if (days <= 30) return { color: theme.yellow, label: `${days}d left`, urgent: true }
  return { color: theme.muted, label: `${days}d left`, urgent: false }
}

function timeAgo(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const days = Math.floor(diffMs / 86400000)
  if (days < 1) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days}d ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

// ─── Fit Score Ring ─────────────────────────────────────────────────
function FitScoreRing({ score, size = 52 }: { score: number; size?: number }) {
  const scoreStyle = getScoreColor(score)
  const radius = (size - 6) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={theme.border} strokeWidth="3"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={scoreStyle.color} strokeWidth="3"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: fonts.mono, fontSize: size > 44 ? '13px' : '11px',
        fontWeight: 600, color: scoreStyle.color, letterSpacing: '-0.02em',
      }}>
        {score}
      </div>
    </div>
  )
}

// ─── Filter Chip ────────────────────────────────────────────────────
function Chip({
  label, active, onClick, small
}: { label: string; active: boolean; onClick: () => void; small?: boolean }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: small ? '3px 10px' : '5px 14px',
        borderRadius: '20px',
        border: `1px solid ${active ? theme.accent : theme.borderMed}`,
        backgroundColor: active ? theme.accentLight : 'transparent',
        color: active ? theme.accentHover : theme.body,
        fontFamily: fonts.sans,
        fontSize: small ? '11px' : '12.5px',
        fontWeight: active ? 600 : 400,
        cursor: 'pointer',
        transition: 'all 0.15s ease',
        whiteSpace: 'nowrap' as const,
        letterSpacing: '0.01em',
      }}
    >
      {label}
    </button>
  )
}

// ─── Editable Tag ───────────────────────────────────────────────────
function EditableTag({
  label, onRemove
}: { label: string; onRemove: () => void }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 8px 3px 10px', borderRadius: '14px',
      backgroundColor: theme.accentLight,
      color: theme.accentHover, fontSize: '11.5px', fontFamily: fonts.sans,
      fontWeight: 500, letterSpacing: '0.01em',
    }}>
      {label}
      <button
        onClick={onRemove}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: theme.accent, fontSize: '13px', lineHeight: 1,
          padding: '0 1px', opacity: 0.7,
        }}
      >
        ×
      </button>
    </span>
  )
}


// ─── MAIN PAGE ──────────────────────────────────────────────────────
export default function GrantFinderPage() {
  const { user } = useAuth()
  const authHeaders = useAuthHeaders()

  // Search state
  const [query, setQuery] = useState('')
  const [selectedAgencies, setSelectedAgencies] = useState<string[]>([])
  const [selectedCodes, setSelectedCodes] = useState<string[]>([])
  const [amountMin, setAmountMin] = useState('')
  const [amountMax, setAmountMax] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  // Results state
  const [results, setResults] = useState<GrantResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [sourceCounts, setSourceCounts] = useState<{ nih_reporter: number; grants_gov: number }>({ nih_reporter: 0, grants_gov: 0 })
  const [expandedAbstract, setExpandedAbstract] = useState<string | null>(null)
  const [expandedReasons, setExpandedReasons] = useState<string | null>(null)

  // Profile state
  const [profile, setProfile] = useState<LabProfile | null>(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [showProfile, setShowProfile] = useState(true)
  const [editingProfile, setEditingProfile] = useState(false)
  const [newKeyword, setNewKeyword] = useState('')
  const [newArea, setNewArea] = useState('')

  // Error state
  const [error, setError] = useState('')

  // Load profile on mount
  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/grants/profile`, { headers: authHeaders })
      if (resp.data.success && resp.data.profile && Object.keys(resp.data.profile).length > 0) {
        setProfile(resp.data.profile)
      }
    } catch (err) {
      // Profile not set yet — that's fine
    }
  }

  const autoGenerateProfile = async () => {
    setProfileLoading(true)
    try {
      const resp = await axios.post(`${API_BASE}/grants/auto-profile`, {}, { headers: authHeaders })
      if (resp.data.success) {
        setProfile(resp.data.profile)
      }
    } catch (err) {
      console.error('Failed to generate profile:', err)
    }
    setProfileLoading(false)
  }

  const saveProfile = async (updatedProfile: LabProfile) => {
    try {
      const resp = await axios.put(`${API_BASE}/grants/profile`, updatedProfile, { headers: authHeaders })
      if (resp.data.success) {
        setProfile(resp.data.profile)
        setEditingProfile(false)
      }
    } catch (err) {
      console.error('Failed to save profile:', err)
    }
  }

  const searchGrants = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setSearched(true)
    try {
      const params = new URLSearchParams({ q: query.trim() })
      if (selectedAgencies.length) params.set('agencies', selectedAgencies.join(','))
      if (selectedCodes.length) params.set('activity_codes', selectedCodes.join(','))
      if (amountMin) params.set('amount_min', amountMin)
      if (amountMax) params.set('amount_max', amountMax)
      params.set('limit', '25')

      const resp = await axios.get(`${API_BASE}/grants/search?${params.toString()}`, { headers: authHeaders })
      if (resp.data.success) {
        setResults(resp.data.results || [])
        setSourceCounts(resp.data.sources || { nih_reporter: 0, grants_gov: 0 })
      } else {
        setError(resp.data.error || 'Search failed')
        setResults([])
      }
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Failed to search grants. Please try again.')
      setResults([])
    }
    setLoading(false)
  }, [query, selectedAgencies, selectedCodes, amountMin, amountMax, authHeaders])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') searchGrants()
  }

  const toggleAgency = (agency: string) => {
    setSelectedAgencies(prev =>
      prev.includes(agency) ? prev.filter(a => a !== agency) : [...prev, agency]
    )
  }

  const toggleCode = (code: string) => {
    setSelectedCodes(prev =>
      prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
    )
  }

  const removeProfileKeyword = (kw: string) => {
    if (!profile) return
    const updated = { ...profile, keywords: profile.keywords.filter(k => k !== kw) }
    setProfile(updated)
    saveProfile(updated)
  }

  const removeProfileArea = (area: string) => {
    if (!profile) return
    const updated = { ...profile, research_areas: profile.research_areas.filter(a => a !== area) }
    setProfile(updated)
    saveProfile(updated)
  }

  const addProfileKeyword = () => {
    if (!profile || !newKeyword.trim()) return
    const updated = { ...profile, keywords: [...profile.keywords, newKeyword.trim()] }
    setProfile(updated)
    saveProfile(updated)
    setNewKeyword('')
  }

  const addProfileArea = () => {
    if (!profile || !newArea.trim()) return
    const updated = { ...profile, research_areas: [...profile.research_areas, newArea.trim()] }
    setProfile(updated)
    saveProfile(updated)
    setNewArea('')
  }

  const toggleProfileAgency = (agency: string) => {
    if (!profile) return
    const agencies = profile.preferred_agencies.includes(agency)
      ? profile.preferred_agencies.filter(a => a !== agency)
      : [...profile.preferred_agencies, agency]
    const updated = { ...profile, preferred_agencies: agencies }
    setProfile(updated)
    saveProfile(updated)
  }

  // ═══════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar userName={user?.full_name || 'User'} />
      <div style={{
        flex: 1, backgroundColor: theme.pageBg,
        overflowY: 'auto', maxHeight: '100vh',
      }}>
        {/* ─── Header ─────────────────────────────────────── */}
        <div style={{
          padding: '32px 40px 0',
          maxWidth: '1400px', margin: '0 auto',
        }}>
          <div style={{ marginBottom: '6px' }}>
            <h1 style={{
              fontFamily: fonts.serif, fontSize: '26px', fontWeight: 700,
              color: theme.ink, margin: 0, letterSpacing: '-0.02em',
            }}>
              Grant Finder
            </h1>
            <p style={{
              fontFamily: fonts.sans, fontSize: '13.5px', color: theme.muted,
              margin: '6px 0 0', lineHeight: 1.5,
            }}>
              Search NIH, NSF, and federal grants — scored against your lab&apos;s knowledge base
            </p>
          </div>

          {/* ─── Search Bar ────────────────────────────────── */}
          <div style={{
            display: 'flex', gap: '10px', marginTop: '24px', alignItems: 'stretch',
          }}>
            <div style={{
              flex: 1, position: 'relative',
            }}>
              <div style={{
                position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)',
                color: theme.subtle, pointerEvents: 'none',
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              </div>
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search grants (e.g., 'CRISPR drug discovery', 'machine learning proteomics')"
                style={{
                  width: '100%', padding: '13px 16px 13px 42px',
                  border: `1.5px solid ${theme.borderMed}`,
                  borderRadius: '12px', backgroundColor: theme.cardBg,
                  fontFamily: fonts.sans, fontSize: '14px', color: theme.ink,
                  outline: 'none', transition: 'border-color 0.15s ease',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
                }}
                onFocus={e => e.target.style.borderColor = theme.accent}
                onBlur={e => e.target.style.borderColor = theme.borderMed}
              />
            </div>
            <button
              onClick={searchGrants}
              disabled={loading || !query.trim()}
              style={{
                padding: '0 28px', borderRadius: '12px', border: 'none',
                backgroundColor: loading ? theme.borderMed : theme.accent,
                color: '#fff', fontFamily: fonts.sans, fontSize: '14px',
                fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease', letterSpacing: '0.01em',
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                display: 'flex', alignItems: 'center', gap: '8px',
              }}
            >
              {loading ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)',
                    borderTopColor: '#fff', borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                  }} />
                  Searching...
                </span>
              ) : 'Search'}
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              style={{
                padding: '0 16px', borderRadius: '12px',
                border: `1.5px solid ${showFilters ? theme.accent : theme.borderMed}`,
                backgroundColor: showFilters ? theme.accentLight : theme.cardBg,
                color: showFilters ? theme.accentHover : theme.muted,
                fontFamily: fonts.sans, fontSize: '13px', cursor: 'pointer',
                transition: 'all 0.15s ease',
                display: 'flex', alignItems: 'center', gap: '6px',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="8" y1="12" x2="16" y2="12" />
                <line x1="11" y1="18" x2="13" y2="18" />
              </svg>
              Filters
            </button>
          </div>

          {/* ─── Filters Panel ─────────────────────────────── */}
          {showFilters && (
            <div style={{
              marginTop: '14px', padding: '18px 20px',
              backgroundColor: theme.cardBg, borderRadius: '12px',
              border: `1px solid ${theme.border}`,
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}>
              <div style={{ marginBottom: '14px' }}>
                <div style={{
                  fontFamily: fonts.sans, fontSize: '11.5px', fontWeight: 600,
                  color: theme.muted, textTransform: 'uppercase' as const,
                  letterSpacing: '0.06em', marginBottom: '8px',
                }}>
                  Agency
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' as const }}>
                  {AGENCIES.map(a => (
                    <Chip key={a} label={a} active={selectedAgencies.includes(a)} onClick={() => toggleAgency(a)} />
                  ))}
                </div>
              </div>

              <div style={{ marginBottom: '14px' }}>
                <div style={{
                  fontFamily: fonts.sans, fontSize: '11.5px', fontWeight: 600,
                  color: theme.muted, textTransform: 'uppercase' as const,
                  letterSpacing: '0.06em', marginBottom: '8px',
                }}>
                  Activity Code
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' as const }}>
                  {ACTIVITY_CODES.map(ac => (
                    <Chip
                      key={ac.code}
                      label={`${ac.code} — ${ac.label}`}
                      active={selectedCodes.includes(ac.code)}
                      onClick={() => toggleCode(ac.code)}
                      small
                    />
                  ))}
                </div>
              </div>

              <div>
                <div style={{
                  fontFamily: fonts.sans, fontSize: '11.5px', fontWeight: 600,
                  color: theme.muted, textTransform: 'uppercase' as const,
                  letterSpacing: '0.06em', marginBottom: '8px',
                }}>
                  Award Amount Range
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <input
                    type="number"
                    placeholder="Min ($)"
                    value={amountMin}
                    onChange={e => setAmountMin(e.target.value)}
                    style={{
                      width: '140px', padding: '8px 12px', borderRadius: '8px',
                      border: `1px solid ${theme.borderMed}`, fontFamily: fonts.mono,
                      fontSize: '12.5px', color: theme.ink, backgroundColor: theme.pageBg,
                      outline: 'none',
                    }}
                  />
                  <span style={{ color: theme.subtle, fontSize: '13px' }}>to</span>
                  <input
                    type="number"
                    placeholder="Max ($)"
                    value={amountMax}
                    onChange={e => setAmountMax(e.target.value)}
                    style={{
                      width: '140px', padding: '8px 12px', borderRadius: '8px',
                      border: `1px solid ${theme.borderMed}`, fontFamily: fonts.mono,
                      fontSize: '12.5px', color: theme.ink, backgroundColor: theme.pageBg,
                      outline: 'none',
                    }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ─── Main Content ────────────────────────────────── */}
        <div style={{
          display: 'flex', gap: '24px',
          padding: '24px 40px 40px', maxWidth: '1400px', margin: '0 auto',
          alignItems: 'flex-start',
        }}>
          {/* ─── Results Column ──────────────────────────── */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Source counts */}
            {searched && !loading && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: '16px',
                marginBottom: '16px', fontFamily: fonts.sans, fontSize: '12.5px',
              }}>
                <span style={{ color: theme.muted }}>
                  {results.length} results
                </span>
                {sourceCounts.nih_reporter > 0 && (
                  <span style={{
                    padding: '2px 10px', borderRadius: '10px',
                    backgroundColor: 'rgba(59, 130, 246, 0.08)',
                    color: '#3B82F6', fontSize: '11px', fontWeight: 600,
                  }}>
                    NIH {sourceCounts.nih_reporter}
                  </span>
                )}
                {sourceCounts.grants_gov > 0 && (
                  <span style={{
                    padding: '2px 10px', borderRadius: '10px',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    color: '#10B981', fontSize: '11px', fontWeight: 600,
                  }}>
                    Grants.gov {sourceCounts.grants_gov}
                  </span>
                )}
              </div>
            )}

            {/* Loading state */}
            {loading && (
              <div style={{
                display: 'flex', flexDirection: 'column' as const, alignItems: 'center',
                justifyContent: 'center', padding: '80px 20px', gap: '16px',
              }}>
                <div style={{
                  width: '36px', height: '36px',
                  border: `3px solid ${theme.border}`,
                  borderTopColor: theme.accent, borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }} />
                <p style={{
                  fontFamily: fonts.sans, fontSize: '14px', color: theme.muted,
                  margin: 0,
                }}>
                  Searching NIH RePORTER &amp; Grants.gov...
                </p>
                <p style={{
                  fontFamily: fonts.sans, fontSize: '12px', color: theme.subtle,
                  margin: 0,
                }}>
                  Scoring results against your knowledge base
                </p>
              </div>
            )}

            {/* Error state */}
            {error && (
              <div style={{
                padding: '16px 20px', borderRadius: '10px',
                backgroundColor: theme.redBg, border: `1px solid ${theme.red}20`,
                fontFamily: fonts.sans, fontSize: '13px', color: theme.red,
                marginBottom: '16px',
              }}>
                {error}
              </div>
            )}

            {/* Empty state (before search) */}
            {!searched && !loading && (
              <div style={{
                display: 'flex', flexDirection: 'column' as const, alignItems: 'center',
                justifyContent: 'center', padding: '80px 20px', textAlign: 'center' as const,
              }}>
                <div style={{
                  width: '72px', height: '72px', borderRadius: '20px',
                  backgroundColor: theme.accentLight, display: 'flex',
                  alignItems: 'center', justifyContent: 'center', marginBottom: '20px',
                }}>
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={theme.accent} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    <path d="M11 8v6" />
                    <path d="M8 11h6" />
                  </svg>
                </div>
                <h3 style={{
                  fontFamily: fonts.serif, fontSize: '18px', color: theme.ink,
                  margin: '0 0 8px', fontWeight: 600,
                }}>
                  Find Grants for Your Research
                </h3>
                <p style={{
                  fontFamily: fonts.sans, fontSize: '13.5px', color: theme.muted,
                  margin: 0, maxWidth: '420px', lineHeight: 1.6,
                }}>
                  Search across NIH RePORTER and Grants.gov. Each result is scored against
                  your lab&apos;s documents to show how well it matches your research.
                </p>
                {!profile && (
                  <button
                    onClick={autoGenerateProfile}
                    disabled={profileLoading}
                    style={{
                      marginTop: '24px', padding: '10px 24px', borderRadius: '10px',
                      border: `1.5px solid ${theme.accent}`, backgroundColor: 'transparent',
                      color: theme.accent, fontFamily: fonts.sans, fontSize: '13px',
                      fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s ease',
                    }}
                  >
                    {profileLoading ? 'Generating...' : 'Generate Lab Profile for Better Matching'}
                  </button>
                )}
              </div>
            )}

            {/* No results state */}
            {searched && !loading && results.length === 0 && !error && (
              <div style={{
                display: 'flex', flexDirection: 'column' as const, alignItems: 'center',
                padding: '60px 20px', textAlign: 'center' as const,
              }}>
                <p style={{
                  fontFamily: fonts.serif, fontSize: '16px', color: theme.body,
                  margin: '0 0 8px',
                }}>
                  No grants found for &ldquo;{query}&rdquo;
                </p>
                <p style={{
                  fontFamily: fonts.sans, fontSize: '13px', color: theme.muted,
                  margin: 0,
                }}>
                  Try broader keywords or remove some filters
                </p>
              </div>
            )}

            {/* ─── Results List ───────────────────────────── */}
            {!loading && results.map((grant, idx) => {
              const scoreStyle = getScoreColor(grant.fit_score)
              const deadline = getDeadlineUrgency(grant.deadline)
              const isAbstractExpanded = expandedAbstract === grant.id
              const isReasonsExpanded = expandedReasons === grant.id

              return (
                <div
                  key={grant.id}
                  style={{
                    padding: '20px 22px', marginBottom: '12px',
                    backgroundColor: theme.cardBg, borderRadius: '14px',
                    border: `1px solid ${theme.border}`,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
                    transition: 'box-shadow 0.15s ease',
                    animation: `fadeSlideUp 0.3s ease ${idx * 0.03}s both`,
                  }}
                  onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 3px 12px rgba(0,0,0,0.06)')}
                  onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.03)')}
                >
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                    {/* Score ring */}
                    <FitScoreRing score={grant.fit_score} />

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* Title row */}
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '6px' }}>
                        <a
                          href={grant.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            fontFamily: fonts.serif, fontSize: '15px', fontWeight: 600,
                            color: theme.ink, textDecoration: 'none', lineHeight: 1.4,
                            flex: 1,
                          }}
                          onMouseEnter={e => (e.currentTarget.style.color = theme.accent)}
                          onMouseLeave={e => (e.currentTarget.style.color = theme.ink)}
                        >
                          {grant.title}
                        </a>
                      </div>

                      {/* Badges row */}
                      <div style={{
                        display: 'flex', flexWrap: 'wrap' as const, gap: '6px',
                        alignItems: 'center', marginBottom: '8px',
                      }}>
                        {/* Source badge */}
                        <span style={{
                          padding: '2px 8px', borderRadius: '6px', fontSize: '10.5px',
                          fontFamily: fonts.mono, fontWeight: 600, letterSpacing: '0.02em',
                          backgroundColor: grant.source === 'nih_reporter' ? 'rgba(59,130,246,0.08)' : 'rgba(16,185,129,0.08)',
                          color: grant.source === 'nih_reporter' ? '#3B82F6' : '#10B981',
                        }}>
                          {grant.source === 'nih_reporter' ? 'NIH' : 'Grants.gov'}
                        </span>

                        {/* Agency */}
                        <span style={{
                          padding: '2px 8px', borderRadius: '6px', fontSize: '10.5px',
                          fontFamily: fonts.sans, fontWeight: 600,
                          backgroundColor: theme.accentLight, color: theme.accentHover,
                        }}>
                          {grant.agency}
                        </span>

                        {/* Activity code */}
                        {grant.activity_code && (
                          <span style={{
                            padding: '2px 8px', borderRadius: '6px', fontSize: '10.5px',
                            fontFamily: fonts.mono, fontWeight: 500,
                            backgroundColor: `${theme.border}`, color: theme.body,
                          }}>
                            {grant.activity_code}
                          </span>
                        )}

                        {/* Award amount */}
                        {grant.award_amount > 0 && (
                          <span style={{
                            fontFamily: fonts.mono, fontSize: '12px', fontWeight: 600,
                            color: theme.ink,
                          }}>
                            {formatCurrency(grant.award_amount)}
                          </span>
                        )}

                        {/* Deadline */}
                        {deadline && (
                          <span style={{
                            padding: '2px 8px', borderRadius: '6px', fontSize: '10.5px',
                            fontFamily: fonts.sans, fontWeight: 600,
                            backgroundColor: deadline.urgent ? `${deadline.color}12` : 'transparent',
                            color: deadline.color,
                          }}>
                            {deadline.label}
                          </span>
                        )}

                        {/* Fit label */}
                        <span style={{
                          marginLeft: 'auto', padding: '2px 10px', borderRadius: '8px',
                          fontSize: '10.5px', fontFamily: fonts.sans, fontWeight: 600,
                          backgroundColor: scoreStyle.bg, color: scoreStyle.color,
                        }}>
                          {scoreStyle.label}
                        </span>
                      </div>

                      {/* PI + Organization */}
                      {(grant.pi_name || grant.organization) && (
                        <div style={{
                          fontFamily: fonts.sans, fontSize: '12.5px', color: theme.muted,
                          marginBottom: '6px', lineHeight: 1.4,
                        }}>
                          {grant.pi_name && grant.pi_name !== 'Unknown PI' && (
                            <span style={{ fontWeight: 500 }}>{grant.pi_name}</span>
                          )}
                          {grant.pi_name && grant.pi_name !== 'Unknown PI' && grant.organization && ' · '}
                          {grant.organization && <span>{grant.organization}</span>}
                          {grant.org_location && <span style={{ color: theme.subtle }}> · {grant.org_location}</span>}
                        </div>
                      )}

                      {/* Abstract */}
                      {grant.abstract && (
                        <div style={{ marginBottom: '6px' }}>
                          <p style={{
                            fontFamily: fonts.sans, fontSize: '12.5px', color: theme.body,
                            lineHeight: 1.6, margin: 0,
                            display: '-webkit-box',
                            WebkitLineClamp: isAbstractExpanded ? 999 : 3,
                            WebkitBoxOrient: 'vertical' as const,
                            overflow: 'hidden',
                          }}>
                            {grant.abstract}
                          </p>
                          {grant.abstract.length > 200 && (
                            <button
                              onClick={() => setExpandedAbstract(isAbstractExpanded ? null : grant.id)}
                              style={{
                                background: 'none', border: 'none', cursor: 'pointer',
                                fontFamily: fonts.sans, fontSize: '11.5px', color: theme.accent,
                                padding: '2px 0', fontWeight: 500,
                              }}
                            >
                              {isAbstractExpanded ? 'Show less' : 'Read more'}
                            </button>
                          )}
                        </div>
                      )}

                      {/* Fit reasons + Matching docs */}
                      {(grant.fit_reasons.length > 0 || grant.matching_docs.length > 0) && (
                        <div>
                          <button
                            onClick={() => setExpandedReasons(isReasonsExpanded ? null : grant.id)}
                            style={{
                              background: 'none', border: 'none', cursor: 'pointer',
                              fontFamily: fonts.sans, fontSize: '11.5px', color: theme.accent,
                              padding: '2px 0', fontWeight: 500,
                              display: 'flex', alignItems: 'center', gap: '4px',
                            }}
                          >
                            <svg
                              width="12" height="12" viewBox="0 0 24 24" fill="none"
                              stroke="currentColor" strokeWidth="2.5"
                              style={{
                                transition: 'transform 0.15s ease',
                                transform: isReasonsExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                              }}
                            >
                              <polyline points="9 18 15 12 9 6" />
                            </svg>
                            Why this matches ({grant.fit_reasons.length + grant.matching_docs.length})
                          </button>
                          {isReasonsExpanded && (
                            <div style={{
                              marginTop: '8px', padding: '12px 14px',
                              backgroundColor: theme.pageBg, borderRadius: '10px',
                              border: `1px solid ${theme.border}`,
                            }}>
                              {grant.fit_reasons.map((reason, i) => (
                                <div key={i} style={{
                                  fontFamily: fonts.sans, fontSize: '12px', color: theme.body,
                                  lineHeight: 1.5, padding: '3px 0',
                                  display: 'flex', gap: '6px', alignItems: 'flex-start',
                                }}>
                                  <span style={{ color: theme.green, flexShrink: 0, marginTop: '2px' }}>●</span>
                                  {reason}
                                </div>
                              ))}
                              {grant.matching_docs.map((doc, i) => (
                                <div key={`doc-${i}`} style={{
                                  fontFamily: fonts.sans, fontSize: '12px', color: theme.muted,
                                  lineHeight: 1.5, padding: '3px 0',
                                  display: 'flex', gap: '6px', alignItems: 'flex-start',
                                }}>
                                  <span style={{ color: theme.accent, flexShrink: 0, marginTop: '2px' }}>◇</span>
                                  Related: &ldquo;{doc.title}&rdquo; ({Math.round(doc.similarity * 100)}% similar)
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* View on source link */}
                      <div style={{ marginTop: '8px' }}>
                        <a
                          href={grant.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            fontFamily: fonts.sans, fontSize: '11.5px', fontWeight: 500,
                            color: theme.accent, textDecoration: 'none',
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                          }}
                        >
                          View on {grant.source === 'nih_reporter' ? 'NIH RePORTER' : 'Grants.gov'}
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
                            <polyline points="15 3 21 3 21 9" />
                            <line x1="10" y1="14" x2="21" y2="3" />
                          </svg>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}

            {/* ─── Coming Soon Section ──────────────────────── */}
            <div style={{
              marginTop: searched && results.length > 0 ? '40px' : '24px',
              paddingTop: '24px',
              borderTop: searched && results.length > 0 ? `1px solid ${theme.border}` : 'none',
            }}>
              <div style={{ marginBottom: '18px' }}>
                <h2 style={{
                  fontFamily: fonts.serif, fontSize: '18px', fontWeight: 600,
                  color: theme.ink, margin: '0 0 4px', letterSpacing: '-0.01em',
                }}>
                  Application Assistance
                </h2>
                <p style={{
                  fontFamily: fonts.sans, fontSize: '12.5px', color: theme.muted, margin: 0,
                }}>
                  Tools to help you write stronger grant applications — coming soon
                </p>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                gap: '12px',
              }}>
                {COMING_SOON_FEATURES.map((feature, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '18px', borderRadius: '12px',
                      backgroundColor: theme.cardBg, border: `1px solid ${theme.border}`,
                      opacity: 0.7, position: 'relative',
                      transition: 'opacity 0.15s ease',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
                    onMouseLeave={e => (e.currentTarget.style.opacity = '0.7')}
                  >
                    {/* Lock + Coming Soon badge */}
                    <div style={{
                      position: 'absolute', top: '12px', right: '12px',
                      padding: '2px 8px', borderRadius: '6px',
                      backgroundColor: theme.accentLight,
                      fontFamily: fonts.sans, fontSize: '9.5px', fontWeight: 700,
                      color: theme.accent, textTransform: 'uppercase' as const,
                      letterSpacing: '0.08em',
                    }}>
                      Coming Soon
                    </div>

                    <div style={{ fontSize: '22px', marginBottom: '10px' }}>
                      {feature.icon}
                    </div>
                    <h4 style={{
                      fontFamily: fonts.sans, fontSize: '13.5px', fontWeight: 600,
                      color: theme.ink, margin: '0 0 6px',
                    }}>
                      {feature.title}
                    </h4>
                    <p style={{
                      fontFamily: fonts.sans, fontSize: '11.5px', color: theme.muted,
                      margin: 0, lineHeight: 1.5,
                    }}>
                      {feature.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ─── Profile Sidebar ────────────────────────────── */}
          {showProfile && (
            <div style={{
              width: '300px', flexShrink: 0,
              position: 'sticky', top: '24px',
            }}>
              <div style={{
                padding: '20px', borderRadius: '14px',
                backgroundColor: theme.cardBg, border: `1px solid ${theme.border}`,
                boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  marginBottom: '16px',
                }}>
                  <h3 style={{
                    fontFamily: fonts.serif, fontSize: '15px', fontWeight: 600,
                    color: theme.ink, margin: 0,
                  }}>
                    Lab Profile
                  </h3>
                  <button
                    onClick={() => setShowProfile(false)}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: theme.subtle, fontSize: '16px', padding: '0 2px',
                    }}
                  >
                    ×
                  </button>
                </div>

                {!profile ? (
                  <div style={{ textAlign: 'center' as const, padding: '20px 0' }}>
                    <p style={{
                      fontFamily: fonts.sans, fontSize: '12.5px', color: theme.muted,
                      margin: '0 0 14px', lineHeight: 1.5,
                    }}>
                      Generate a research profile from your documents for better grant matching.
                    </p>
                    <button
                      onClick={autoGenerateProfile}
                      disabled={profileLoading}
                      style={{
                        padding: '9px 20px', borderRadius: '10px', border: 'none',
                        backgroundColor: theme.accent, color: '#fff',
                        fontFamily: fonts.sans, fontSize: '12.5px', fontWeight: 600,
                        cursor: profileLoading ? 'not-allowed' : 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {profileLoading ? 'Generating...' : 'Auto-Generate Profile'}
                    </button>
                  </div>
                ) : (
                  <>
                    {/* Research Areas */}
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{
                        fontFamily: fonts.sans, fontSize: '10.5px', fontWeight: 700,
                        color: theme.muted, textTransform: 'uppercase' as const,
                        letterSpacing: '0.08em', marginBottom: '8px',
                      }}>
                        Research Areas
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '5px' }}>
                        {profile.research_areas.map(area => (
                          <EditableTag key={area} label={area} onRemove={() => removeProfileArea(area)} />
                        ))}
                      </div>
                      <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                        <input
                          type="text"
                          value={newArea}
                          onChange={e => setNewArea(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && addProfileArea()}
                          placeholder="Add area..."
                          style={{
                            flex: 1, padding: '4px 8px', borderRadius: '6px',
                            border: `1px solid ${theme.border}`, fontSize: '11px',
                            fontFamily: fonts.sans, color: theme.ink, outline: 'none',
                          }}
                        />
                      </div>
                    </div>

                    {/* Keywords */}
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{
                        fontFamily: fonts.sans, fontSize: '10.5px', fontWeight: 700,
                        color: theme.muted, textTransform: 'uppercase' as const,
                        letterSpacing: '0.08em', marginBottom: '8px',
                      }}>
                        Keywords
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '5px' }}>
                        {profile.keywords.slice(0, 10).map(kw => (
                          <EditableTag key={kw} label={kw} onRemove={() => removeProfileKeyword(kw)} />
                        ))}
                        {profile.keywords.length > 10 && (
                          <span style={{
                            fontFamily: fonts.sans, fontSize: '11px', color: theme.subtle,
                            padding: '3px 0',
                          }}>
                            +{profile.keywords.length - 10} more
                          </span>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                        <input
                          type="text"
                          value={newKeyword}
                          onChange={e => setNewKeyword(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && addProfileKeyword()}
                          placeholder="Add keyword..."
                          style={{
                            flex: 1, padding: '4px 8px', borderRadius: '6px',
                            border: `1px solid ${theme.border}`, fontSize: '11px',
                            fontFamily: fonts.sans, color: theme.ink, outline: 'none',
                          }}
                        />
                      </div>
                    </div>

                    {/* Preferred Agencies */}
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{
                        fontFamily: fonts.sans, fontSize: '10.5px', fontWeight: 700,
                        color: theme.muted, textTransform: 'uppercase' as const,
                        letterSpacing: '0.08em', marginBottom: '8px',
                      }}>
                        Preferred Agencies
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '5px' }}>
                        {AGENCIES.map(a => (
                          <Chip
                            key={a}
                            label={a}
                            active={profile.preferred_agencies.includes(a)}
                            onClick={() => toggleProfileAgency(a)}
                            small
                          />
                        ))}
                      </div>
                    </div>

                    {/* Institution */}
                    {profile.institution && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{
                          fontFamily: fonts.sans, fontSize: '10.5px', fontWeight: 700,
                          color: theme.muted, textTransform: 'uppercase' as const,
                          letterSpacing: '0.08em', marginBottom: '4px',
                        }}>
                          Institution
                        </div>
                        <div style={{
                          fontFamily: fonts.sans, fontSize: '12.5px', color: theme.body,
                        }}>
                          {profile.institution}
                        </div>
                      </div>
                    )}

                    {/* Regenerate */}
                    <button
                      onClick={autoGenerateProfile}
                      disabled={profileLoading}
                      style={{
                        width: '100%', padding: '8px', borderRadius: '8px',
                        border: `1px solid ${theme.borderMed}`,
                        backgroundColor: 'transparent', color: theme.muted,
                        fontFamily: fonts.sans, fontSize: '11.5px', fontWeight: 500,
                        cursor: profileLoading ? 'not-allowed' : 'pointer',
                        transition: 'all 0.15s ease', marginTop: '4px',
                      }}
                    >
                      {profileLoading ? 'Regenerating...' : 'Regenerate from Documents'}
                    </button>

                    {profile.last_updated && (
                      <div style={{
                        fontFamily: fonts.sans, fontSize: '10px', color: theme.subtle,
                        marginTop: '8px', textAlign: 'center' as const,
                      }}>
                        Updated {timeAgo(profile.last_updated)}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Toggle profile back */}
            </div>
          )}

          {/* Show profile toggle when hidden */}
          {!showProfile && (
            <button
              onClick={() => setShowProfile(true)}
              style={{
                position: 'fixed', right: '20px', bottom: '20px',
                padding: '10px 16px', borderRadius: '10px',
                backgroundColor: theme.cardBg, border: `1px solid ${theme.borderMed}`,
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                fontFamily: fonts.sans, fontSize: '12px', color: theme.body,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
                zIndex: 10,
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              Lab Profile
            </button>
          )}
        </div>

        {/* ─── Keyframe animations ────────────────────────── */}
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          @keyframes fadeSlideUp {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
    </div>
  )
}
