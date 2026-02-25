'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../shared/Sidebar'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

type AtomType = 'concept' | 'decision' | 'process' | 'fact' | 'insight' | 'definition'

interface Atom {
  id: string
  title: string
  content: string
  atom_type: AtomType
  source_document_id: string | null
  is_manual: boolean
  extraction_confidence: number | null
  project_id: string | null
  is_pinned: boolean
  view_count: number
  created_at: string
  outgoing_links?: Link[]
  incoming_links?: Link[]
}

interface Link {
  id: string
  source_atom_id: string
  target_atom_id: string
  link_type: string
  confidence: number
  is_manual: boolean
  reason: string | null
  source_title: string | null
  target_title: string | null
}

interface AtomStats {
  [key: string]: number
}

const ATOM_TYPE_CONFIG: Record<AtomType, { label: string; icon: string; color: string; bg: string; border: string }> = {
  concept: { label: 'Concept', icon: '💡', color: '#2563EB', bg: '#EFF6FF', border: '#93C5FD' },
  decision: { label: 'Decision', icon: '⚖️', color: '#7C3AED', bg: '#F5F3FF', border: '#C4B5FD' },
  process: { label: 'Process', icon: '⚙️', color: '#059669', bg: '#ECFDF5', border: '#6EE7B7' },
  fact: { label: 'Fact', icon: '📌', color: '#DC2626', bg: '#FEF2F2', border: '#FCA5A5' },
  insight: { label: 'Insight', icon: '✨', color: '#D97706', bg: '#FFFBEB', border: '#FCD34D' },
  definition: { label: 'Definition', icon: '📖', color: '#6B7280', bg: '#F3F4F6', border: '#D1D5DB' },
}

const LINK_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  related: { label: 'Related', color: '#6B7280' },
  supports: { label: 'Supports', color: '#059669' },
  contradicts: { label: 'Contradicts', color: '#DC2626' },
  elaborates: { label: 'Elaborates', color: '#2563EB' },
  depends_on: { label: 'Depends on', color: '#7C3AED' },
  supersedes: { label: 'Supersedes', color: '#D97706' },
}

const AtomTypeBadge = ({ type }: { type: AtomType }) => {
  const cfg = ATOM_TYPE_CONFIG[type] || ATOM_TYPE_CONFIG.concept
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '2px 10px', borderRadius: '12px',
      backgroundColor: cfg.bg, border: `1px solid ${cfg.border}`,
      color: cfg.color, fontFamily: 'Inter, sans-serif',
      fontSize: '11px', fontWeight: 500,
    }}>
      <span style={{ fontSize: '10px' }}>{cfg.icon}</span>
      {cfg.label}
    </span>
  )
}

const AtomCard = ({
  atom,
  onClick,
}: {
  atom: Atom
  onClick: () => void
}) => {
  const cfg = ATOM_TYPE_CONFIG[atom.atom_type] || ATOM_TYPE_CONFIG.concept

  return (
    <div
      onClick={onClick}
      style={{
        backgroundColor: '#FFF',
        border: '1px solid #E5E7EB',
        borderLeft: `3px solid ${cfg.color}`,
        borderRadius: '10px',
        padding: '16px 18px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <h3 style={{
          margin: 0, fontFamily: '"Work Sans", sans-serif',
          fontSize: '15px', fontWeight: 600, color: '#18181B',
          lineHeight: '1.4', flex: 1, paddingRight: '8px',
        }}>
          {atom.is_pinned && <span style={{ marginRight: '4px' }}>📌</span>}
          {atom.title}
        </h3>
        <AtomTypeBadge type={atom.atom_type} />
      </div>
      <p style={{
        margin: 0, fontFamily: 'Inter, sans-serif',
        fontSize: '13px', color: '#6B7280', lineHeight: '1.5',
        overflow: 'hidden', display: '-webkit-box',
        WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any,
      }}>
        {atom.content}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '10px' }}>
        {atom.is_manual && (
          <span style={{ fontSize: '11px', color: '#9CA3AF', fontFamily: 'Inter', fontStyle: 'italic' }}>manual</span>
        )}
        {atom.extraction_confidence != null && !atom.is_manual && (
          <span style={{ fontSize: '11px', color: '#9CA3AF', fontFamily: 'Inter' }}>
            {Math.round(atom.extraction_confidence * 100)}% conf.
          </span>
        )}
        <span style={{ fontSize: '11px', color: '#D1D5DB', fontFamily: 'Inter' }}>
          {new Date(atom.created_at).toLocaleDateString()}
        </span>
      </div>
    </div>
  )
}

const AtomDetail = ({
  atom,
  onClose,
  onNavigate,
}: {
  atom: Atom
  onClose: () => void
  onNavigate: (id: string) => void
}) => {
  const cfg = ATOM_TYPE_CONFIG[atom.atom_type] || ATOM_TYPE_CONFIG.concept
  const allLinks = [...(atom.outgoing_links || []), ...(atom.incoming_links || [])]

  return (
    <div
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#FAF9F7', borderRadius: '16px',
          maxWidth: '700px', width: '100%', maxHeight: '85vh',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid #E5E7EB',
          backgroundColor: cfg.bg,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, paddingRight: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <span style={{ fontSize: '24px' }}>{cfg.icon}</span>
                <AtomTypeBadge type={atom.atom_type} />
                {atom.is_manual && (
                  <span style={{ fontSize: '11px', color: '#9CA3AF', fontStyle: 'italic' }}>Manual</span>
                )}
              </div>
              <h2 style={{
                margin: 0, fontFamily: '"Work Sans", sans-serif',
                fontSize: '20px', fontWeight: 600, color: '#18181B', lineHeight: '1.3',
              }}>
                {atom.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              style={{
                width: '36px', height: '36px', borderRadius: '8px',
                backgroundColor: '#E5E7EB', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '20px', color: '#6B7280',
              }}
            >
              x
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
          <div style={{
            backgroundColor: '#FFF', border: '1px solid #E5E7EB', borderRadius: '10px',
            padding: '16px 18px', marginBottom: '20px',
          }}>
            <p style={{
              margin: 0, fontFamily: 'Inter, sans-serif',
              fontSize: '14px', color: '#374151', lineHeight: '1.7',
              whiteSpace: 'pre-wrap',
            }}>
              {atom.content}
            </p>
          </div>

          {/* Metadata */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px',
            marginBottom: '20px',
          }}>
            <div>
              <p style={{ margin: '0 0 2px', fontSize: '11px', color: '#9CA3AF', fontFamily: 'Inter', fontWeight: 500 }}>Confidence</p>
              <p style={{ margin: 0, fontSize: '14px', color: '#18181B', fontFamily: '"Work Sans"', fontWeight: 500 }}>
                {atom.extraction_confidence != null ? `${Math.round(atom.extraction_confidence * 100)}%` : '---'}
              </p>
            </div>
            <div>
              <p style={{ margin: '0 0 2px', fontSize: '11px', color: '#9CA3AF', fontFamily: 'Inter', fontWeight: 500 }}>Views</p>
              <p style={{ margin: 0, fontSize: '14px', color: '#18181B', fontFamily: '"Work Sans"', fontWeight: 500 }}>
                {atom.view_count}
              </p>
            </div>
            <div>
              <p style={{ margin: '0 0 2px', fontSize: '11px', color: '#9CA3AF', fontFamily: 'Inter', fontWeight: 500 }}>Created</p>
              <p style={{ margin: 0, fontSize: '14px', color: '#18181B', fontFamily: '"Work Sans"', fontWeight: 500 }}>
                {new Date(atom.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>

          {/* Links */}
          {allLinks.length > 0 && (
            <div>
              <h3 style={{
                margin: '0 0 12px', fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px', fontWeight: 600, color: '#18181B',
              }}>
                Connections ({allLinks.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {allLinks.map((link) => {
                  const isOutgoing = link.source_atom_id === atom.id
                  const linkedTitle = isOutgoing ? link.target_title : link.source_title
                  const linkedId = isOutgoing ? link.target_atom_id : link.source_atom_id
                  const linkCfg = LINK_TYPE_LABELS[link.link_type] || LINK_TYPE_LABELS.related

                  return (
                    <div
                      key={link.id}
                      onClick={() => onNavigate(linkedId)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '10px',
                        padding: '10px 14px', borderRadius: '8px',
                        backgroundColor: '#FFF', border: '1px solid #E5E7EB',
                        cursor: 'pointer', transition: 'background-color 0.15s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#F9FAFB'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#FFF'}
                    >
                      <span style={{
                        fontSize: '11px', fontWeight: 500, color: linkCfg.color,
                        padding: '2px 8px', borderRadius: '10px',
                        backgroundColor: `${linkCfg.color}15`,
                        fontFamily: 'Inter',
                      }}>
                        {isOutgoing ? '' : ''} {linkCfg.label}
                      </span>
                      <span style={{
                        fontSize: '13px', color: '#374151', fontFamily: 'Inter', fontWeight: 500,
                        flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {linkedTitle || 'Untitled'}
                      </span>
                      <span style={{ fontSize: '12px', color: '#D1D5DB' }}>{'>'}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {allLinks.length === 0 && (
            <p style={{ color: '#9CA3AF', fontSize: '13px', fontFamily: 'Inter', fontStyle: 'italic' }}>
              No connections yet.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default function KnowledgeAtoms() {
  const { user } = useAuth()
  const [activeItem, setActiveItem] = useState('Knowledge')
  const [atoms, setAtoms] = useState<Atom[]>([])
  const [totalAtoms, setTotalAtoms] = useState(0)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeType, setActiveType] = useState<'all' | AtomType>('all')
  const [stats, setStats] = useState<AtomStats>({})
  const [totalLinks, setTotalLinks] = useState(0)
  const [selectedAtom, setSelectedAtom] = useState<Atom | null>(null)
  const [extracting, setExtracting] = useState(false)

  useEffect(() => {
    loadAtoms()
    loadStats()
  }, [])

  useEffect(() => {
    loadAtoms()
  }, [activeType, searchQuery])

  const loadAtoms = async () => {
    try {
      const params = new URLSearchParams()
      if (activeType !== 'all') params.set('type', activeType)
      if (searchQuery) params.set('search', searchQuery)
      params.set('limit', '100')

      const response = await axios.get(`${API_BASE}/atoms?${params.toString()}`)
      if (response.data.atoms) {
        setAtoms(response.data.atoms)
        setTotalAtoms(response.data.total || 0)
      }
    } catch (error) {
      console.error('Error loading atoms:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/atoms/stats`)
      if (response.data.stats) {
        setStats(response.data.stats)
        setTotalLinks(response.data.total_links || 0)
      }
    } catch (error) {
      console.error('Error loading atom stats:', error)
    }
  }

  const loadAtomDetail = async (atomId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/atoms/${atomId}`)
      if (response.data.atom) {
        setSelectedAtom(response.data.atom)
      }
    } catch (error) {
      console.error('Error loading atom detail:', error)
    }
  }

  const handleExtract = async () => {
    setExtracting(true)
    try {
      await axios.post(`${API_BASE}/atoms/extract`, {})
      await loadAtoms()
      await loadStats()
    } catch (error) {
      console.error('Error extracting atoms:', error)
    } finally {
      setExtracting(false)
    }
  }

  const totalAllAtoms = Object.values(stats).reduce((s, v) => s + v, 0)

  return (
    <div className="flex h-screen bg-primary overflow-hidden">
      <Sidebar activeItem={activeItem} onItemClick={setActiveItem} userName={user?.full_name?.split(' ')[0] || 'User'} />

      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 bg-primary">
          <div>
            <h1 style={{
              color: '#18181B', fontFamily: '"Work Sans", sans-serif',
              fontSize: '28px', fontWeight: 600, letterSpacing: '-0.56px', marginBottom: '8px',
            }}>
              Knowledge
            </h1>
            <p style={{
              color: '#71717A', fontFamily: 'Inter, sans-serif',
              fontSize: '15px', lineHeight: '22px',
            }}>
              Atomic concepts, decisions, and processes extracted from your documents
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              onClick={handleExtract}
              disabled={extracting}
              style={{
                padding: '10px 18px', borderRadius: '8px',
                backgroundColor: extracting ? '#E5E7EB' : '#2563EB',
                color: '#FFF', border: 'none',
                cursor: extracting ? 'not-allowed' : 'pointer',
                fontFamily: 'Inter, sans-serif', fontSize: '13px', fontWeight: 500,
              }}
            >
              {extracting ? 'Extracting...' : 'Extract Atoms'}
            </button>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '24px',
              padding: '16px 24px', backgroundColor: '#FFE2BF', borderRadius: '12px',
            }}>
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600, margin: 0 }}>
                  {totalAllAtoms}
                </p>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: 0 }}>Atoms</p>
              </div>
              <div style={{ width: '1px', height: '40px', backgroundColor: '#D4D4D8' }} />
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#F97316', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600, margin: 0 }}>
                  {totalLinks}
                </p>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: 0 }}>Links</p>
              </div>
            </div>
          </div>
        </div>

        {/* Type Tabs + Search */}
        <div className="px-8 pb-4 bg-primary">
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <button
                onClick={() => setActiveType('all')}
                style={{
                  padding: '8px 16px', borderRadius: '8px',
                  backgroundColor: activeType === 'all' ? '#18181B' : '#FFF',
                  border: `1px solid ${activeType === 'all' ? '#18181B' : '#D4D4D8'}`,
                  color: activeType === 'all' ? '#FFF' : '#18181B',
                  fontFamily: 'Inter, sans-serif', fontSize: '13px', fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                All ({totalAllAtoms})
              </button>
              {(Object.keys(ATOM_TYPE_CONFIG) as AtomType[]).map((type) => {
                const cfg = ATOM_TYPE_CONFIG[type]
                const count = stats[type] || 0
                const isActive = activeType === type
                return (
                  <button
                    key={type}
                    onClick={() => setActiveType(type)}
                    style={{
                      padding: '8px 14px', borderRadius: '8px',
                      backgroundColor: isActive ? cfg.bg : '#FFF',
                      border: `1px solid ${isActive ? cfg.border : '#D4D4D8'}`,
                      color: isActive ? cfg.color : '#71717A',
                      fontFamily: 'Inter, sans-serif', fontSize: '13px',
                      fontWeight: isActive ? 500 : 400, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '5px',
                    }}
                  >
                    <span style={{ fontSize: '12px' }}>{cfg.icon}</span>
                    {cfg.label}
                    <span style={{
                      backgroundColor: isActive ? cfg.color : '#E5E7EB',
                      color: isActive ? '#FFF' : '#71717A',
                      padding: '1px 7px', borderRadius: '10px',
                      fontSize: '11px', fontWeight: 600,
                    }}>
                      {count}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
          <input
            type="text"
            placeholder="Search knowledge atoms..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '320px', height: '42px', padding: '0 16px',
              borderRadius: '8px', border: '1px solid #D4D4D8',
              backgroundColor: '#FFF', outline: 'none',
              fontFamily: 'Inter, sans-serif', fontSize: '14px',
            }}
          />
        </div>

        {/* Atom Grid */}
        <div className="flex-1 overflow-y-auto px-8 py-4 bg-primary">
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
              <p style={{ fontFamily: 'Inter', fontSize: '14px', color: '#71717A' }}>Loading knowledge atoms...</p>
            </div>
          ) : atoms.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '300px',
            }}>
              <div style={{
                width: '80px', height: '80px', borderRadius: '50%',
                backgroundColor: activeType !== 'all' ? ATOM_TYPE_CONFIG[activeType].bg : '#FFE2BF',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: '16px',
              }}>
                <span style={{ fontSize: '32px' }}>
                  {activeType !== 'all' ? ATOM_TYPE_CONFIG[activeType].icon : '💡'}
                </span>
              </div>
              <h3 style={{
                color: '#18181B', fontFamily: '"Work Sans"',
                fontSize: '18px', fontWeight: 600, marginBottom: '8px',
              }}>
                No knowledge atoms found
              </h3>
              <p style={{
                color: '#71717A', fontFamily: 'Inter', fontSize: '14px',
                textAlign: 'center', maxWidth: '400px',
              }}>
                {searchQuery
                  ? 'Try adjusting your search.'
                  : 'Click "Extract Atoms" to extract knowledge from your synced documents.'}
              </p>
            </div>
          ) : (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
              gap: '14px', maxWidth: '1200px',
            }}>
              {atoms.map((atom) => (
                <AtomCard
                  key={atom.id}
                  atom={atom}
                  onClick={() => loadAtomDetail(atom.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {selectedAtom && (
        <AtomDetail
          atom={selectedAtom}
          onClose={() => setSelectedAtom(null)}
          onNavigate={(id) => {
            setSelectedAtom(null)
            loadAtomDetail(id)
          }}
        />
      )}
    </div>
  )
}
