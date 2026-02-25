'use client'

import React, { useState, useEffect, useRef } from 'react'
import Sidebar from '../shared/Sidebar'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

type PARACategory = 'projects' | 'areas' | 'resources' | 'archives'

interface Project {
  id: string
  name: string
  description: string
  document_count: number
  status: string
  para_category: PARACategory
  ai_classification_confidence: number | null
  user_override_category: boolean
}

interface PARAStats {
  projects: number
  areas: number
  resources: number
  archives: number
}

const PARA_CONFIG: Record<PARACategory, { label: string; icon: string; color: string; bg: string; border: string; description: string }> = {
  projects: {
    label: 'Projects',
    icon: '🎯',
    color: '#2563EB',
    bg: '#EFF6FF',
    border: '#93C5FD',
    description: 'Time-bound deliverables with deadlines',
  },
  areas: {
    label: 'Areas',
    icon: '🔄',
    color: '#059669',
    bg: '#ECFDF5',
    border: '#6EE7B7',
    description: 'Ongoing responsibilities & standards',
  },
  resources: {
    label: 'Resources',
    icon: '📚',
    color: '#D97706',
    bg: '#FFFBEB',
    border: '#FCD34D',
    description: 'Reference material & knowledge',
  },
  archives: {
    label: 'Archives',
    icon: '🗄️',
    color: '#6B7280',
    bg: '#F3F4F6',
    border: '#D1D5DB',
    description: 'Completed or inactive items',
  },
}

const PARABadge = ({ category }: { category: PARACategory }) => {
  const config = PARA_CONFIG[category] || PARA_CONFIG.resources
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 10px',
        borderRadius: '12px',
        backgroundColor: config.bg,
        border: `1px solid ${config.border}`,
        color: config.color,
        fontFamily: 'Inter, sans-serif',
        fontSize: '11px',
        fontWeight: 500,
      }}
    >
      <span style={{ fontSize: '10px' }}>{config.icon}</span>
      {config.label}
    </span>
  )
}

const CategoryMenu = ({
  currentCategory,
  onSelect,
  onClose,
}: {
  currentCategory: PARACategory
  onSelect: (cat: PARACategory) => void
  onClose: () => void
}) => {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  return (
    <div
      ref={ref}
      style={{
        position: 'absolute',
        right: 0,
        top: '100%',
        marginTop: '4px',
        backgroundColor: '#FFF',
        border: '1px solid #E5E7EB',
        borderRadius: '10px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
        zIndex: 50,
        minWidth: '200px',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #F3F4F6' }}>
        <p style={{ fontFamily: 'Inter', fontSize: '11px', color: '#9CA3AF', fontWeight: 500, margin: 0 }}>
          Move to...
        </p>
      </div>
      {(Object.keys(PARA_CONFIG) as PARACategory[]).map((cat) => {
        const cfg = PARA_CONFIG[cat]
        const isActive = cat === currentCategory
        return (
          <button
            key={cat}
            onClick={() => { onSelect(cat); onClose() }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              width: '100%',
              padding: '10px 14px',
              backgroundColor: isActive ? cfg.bg : 'transparent',
              border: 'none',
              cursor: isActive ? 'default' : 'pointer',
              textAlign: 'left',
              transition: 'background-color 0.15s',
            }}
            onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.backgroundColor = '#F9FAFB' }}
            onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.backgroundColor = 'transparent' }}
            disabled={isActive}
          >
            <span style={{ fontSize: '14px' }}>{cfg.icon}</span>
            <div>
              <p style={{ margin: 0, fontFamily: 'Inter', fontSize: '13px', fontWeight: 500, color: isActive ? cfg.color : '#18181B' }}>
                {cfg.label}
              </p>
              <p style={{ margin: 0, fontFamily: 'Inter', fontSize: '11px', color: '#9CA3AF' }}>
                {cfg.description}
              </p>
            </div>
            {isActive && (
              <span style={{ marginLeft: 'auto', fontSize: '12px', color: cfg.color }}>✓</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

const ProjectCard = ({
  project,
  isExpanded,
  onToggle,
  onCategoryChange,
}: {
  project: Project
  isExpanded: boolean
  onToggle: () => void
  onCategoryChange: (id: string, cat: PARACategory) => void
}) => {
  const [showMenu, setShowMenu] = useState(false)
  const config = PARA_CONFIG[project.para_category] || PARA_CONFIG.resources

  return (
    <div
      style={{
        borderRadius: '12px',
        border: '1px solid #D4D4D8',
        backgroundColor: '#FFF',
        overflow: 'hidden',
        marginBottom: '12px',
      }}
    >
      {/* Project Header */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px',
          backgroundColor: isExpanded ? '#FFF9F2' : '#FFF',
          cursor: 'pointer',
          transition: 'background-color 0.2s',
          borderLeft: `3px solid ${config.color}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
          <span style={{ fontSize: '20px' }}>{config.icon}</span>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
              <h3
                style={{
                  color: '#18181B',
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '16px',
                  fontWeight: 600,
                  margin: 0,
                }}
              >
                {project.name}
              </h3>
              <PARABadge category={project.para_category} />
              {project.user_override_category && (
                <span
                  style={{
                    fontSize: '10px',
                    color: '#9CA3AF',
                    fontFamily: 'Inter',
                    fontStyle: 'italic',
                  }}
                >
                  (manual)
                </span>
              )}
            </div>
            {project.description && (
              <p
                style={{
                  color: '#71717A',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '13px',
                  lineHeight: '18px',
                  margin: 0,
                }}
              >
                {project.description}
              </p>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              backgroundColor: '#FFE2BF',
              padding: '6px 12px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span style={{ fontSize: '12px' }}>📄</span>
            <span
              style={{
                color: '#F97316',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 600,
              }}
            >
              {project.document_count}
            </span>
          </div>
          {/* Move-to menu trigger */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={(e) => { e.stopPropagation(); setShowMenu(!showMenu) }}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                border: '1px solid #E5E7EB',
                backgroundColor: '#FFF',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '14px',
                color: '#9CA3AF',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={(e) => e.currentTarget.style.borderColor = '#9CA3AF'}
              onMouseLeave={(e) => e.currentTarget.style.borderColor = '#E5E7EB'}
              title="Move to category"
            >
              ⋮
            </button>
            {showMenu && (
              <CategoryMenu
                currentCategory={project.para_category}
                onSelect={(cat) => onCategoryChange(project.id, cat)}
                onClose={() => setShowMenu(false)}
              />
            )}
          </div>
          <span style={{ fontSize: '12px', color: '#9CA3AF' }}>
            {isExpanded ? '▲' : '▼'}
          </span>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div
          style={{
            padding: '20px',
            borderTop: '1px solid #E5E7EB',
            backgroundColor: '#FAFAFA',
          }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
            <div>
              <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: '0 0 4px' }}>
                Documents
              </p>
              <p style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '14px', fontWeight: 500, margin: 0 }}>
                {project.document_count}
              </p>
            </div>
            <div>
              <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: '0 0 4px' }}>
                Category
              </p>
              <PARABadge category={project.para_category} />
            </div>
            <div>
              <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: '0 0 4px' }}>
                Confidence
              </p>
              <p style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '14px', fontWeight: 500, margin: 0 }}>
                {project.ai_classification_confidence != null
                  ? `${Math.round(project.ai_classification_confidence * 100)}%`
                  : '—'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Projects() {
  const { user } = useAuth()
  const [activeItem, setActiveItem] = useState('Projects')
  const [projects, setProjects] = useState<Project[]>([])
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState<'all' | PARACategory>('all')
  const [paraStats, setParaStats] = useState<PARAStats>({ projects: 0, areas: 0, resources: 0, archives: 0 })
  const [classifying, setClassifying] = useState(false)

  useEffect(() => {
    loadProjects()
    loadParaStats()
  }, [])

  // Reload when category tab changes
  useEffect(() => {
    loadProjects()
  }, [activeCategory])

  const loadProjects = async () => {
    try {
      const params = new URLSearchParams()
      if (activeCategory !== 'all') {
        params.set('category', activeCategory)
      }
      if (activeCategory === 'archives') {
        params.set('include_archived', 'true')
      }
      const url = `${API_BASE}/projects${params.toString() ? '?' + params.toString() : ''}`
      const response = await axios.get(url)

      if (response.data.projects) {
        const projectList: Project[] = response.data.projects.map((p: any) => ({
          id: p.id || `project_${Math.random().toString(36).substr(2, 9)}`,
          name: p.name,
          description: p.description || '',
          document_count: p.document_count || 0,
          status: p.status || 'active',
          para_category: p.para_category || 'resources',
          ai_classification_confidence: p.ai_classification_confidence,
          user_override_category: p.user_override_category || false,
        }))
        setProjects(projectList)
      }
    } catch (error) {
      console.error('Error loading projects:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadParaStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/projects/para-stats`)
      if (response.data.stats) {
        setParaStats(response.data.stats)
      }
    } catch (error) {
      console.error('Error loading PARA stats:', error)
    }
  }

  const handleCategoryChange = async (projectId: string, newCategory: PARACategory) => {
    try {
      await axios.put(`${API_BASE}/projects/${projectId}/category`, { category: newCategory })
      // Optimistic update
      setProjects((prev) =>
        prev.map((p) =>
          p.id === projectId
            ? { ...p, para_category: newCategory, user_override_category: true }
            : p
        )
      )
      loadParaStats()
    } catch (error) {
      console.error('Error updating category:', error)
    }
  }

  const handleAutoClassify = async () => {
    setClassifying(true)
    try {
      await axios.post(`${API_BASE}/projects/auto-classify`, { use_ai: true })
      await loadProjects()
      await loadParaStats()
    } catch (error) {
      console.error('Error auto-classifying:', error)
    } finally {
      setClassifying(false)
    }
  }

  const toggleProject = (projectId: string) => {
    setExpandedProjects((prev) => {
      const next = new Set(prev)
      if (next.has(projectId)) {
        next.delete(projectId)
      } else {
        next.add(projectId)
      }
      return next
    })
  }

  // Filter projects by search
  const filteredProjects = projects.filter((p) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const matchesName = p.name.toLowerCase().includes(query)
      const matchesDescription = p.description.toLowerCase().includes(query)
      if (!matchesName && !matchesDescription) return false
    }
    return true
  })

  const totalAll = paraStats.projects + paraStats.areas + paraStats.resources + paraStats.archives
  const totalDocuments = projects.reduce((sum, p) => sum + p.document_count, 0)

  return (
    <div className="flex h-screen bg-primary overflow-hidden">
      <Sidebar activeItem={activeItem} onItemClick={setActiveItem} userName={user?.full_name?.split(' ')[0] || 'User'} />

      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 bg-primary">
          <div>
            <h1
              style={{
                color: '#18181B',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '28px',
                fontWeight: 600,
                letterSpacing: '-0.56px',
                marginBottom: '8px',
              }}
            >
              Projects
            </h1>
            <p
              style={{
                color: '#71717A',
                fontFamily: 'Inter, sans-serif',
                fontSize: '15px',
                lineHeight: '22px',
              }}
            >
              Content-based project discovery using LLM clustering
            </p>
          </div>

          {/* Stats */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              onClick={handleAutoClassify}
              disabled={classifying}
              style={{
                padding: '10px 18px',
                borderRadius: '8px',
                backgroundColor: classifying ? '#E5E7EB' : '#2563EB',
                color: '#FFF',
                border: 'none',
                cursor: classifying ? 'not-allowed' : 'pointer',
                fontFamily: 'Inter, sans-serif',
                fontSize: '13px',
                fontWeight: 500,
                transition: 'background-color 0.15s',
              }}
            >
              {classifying ? 'Classifying...' : 'Auto-Classify'}
            </button>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '24px',
                padding: '16px 24px',
                backgroundColor: '#FFE2BF',
                borderRadius: '12px',
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600, margin: 0 }}>
                  {totalAll}
                </p>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: 0 }}>Total</p>
              </div>
              <div style={{ width: '1px', height: '40px', backgroundColor: '#D4D4D8' }} />
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#F97316', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600, margin: 0 }}>
                  {totalDocuments}
                </p>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: 0 }}>Documents</p>
              </div>
            </div>
          </div>
        </div>

        {/* PARA Tabs + Search */}
        <div className="px-8 pb-4 bg-primary">
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            {/* PARA category tabs */}
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                onClick={() => setActiveCategory('all')}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  backgroundColor: activeCategory === 'all' ? '#18181B' : '#FFF',
                  border: '1px solid ' + (activeCategory === 'all' ? '#18181B' : '#D4D4D8'),
                  color: activeCategory === 'all' ? '#FFF' : '#18181B',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                All ({totalAll})
              </button>
              {(Object.keys(PARA_CONFIG) as PARACategory[]).map((cat) => {
                const cfg = PARA_CONFIG[cat]
                const count = paraStats[cat] || 0
                const isActive = activeCategory === cat
                return (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      backgroundColor: isActive ? cfg.bg : '#FFF',
                      border: `1px solid ${isActive ? cfg.border : '#D4D4D8'}`,
                      color: isActive ? cfg.color : '#71717A',
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '13px',
                      fontWeight: isActive ? 500 : 400,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.15s',
                    }}
                  >
                    <span style={{ fontSize: '12px' }}>{cfg.icon}</span>
                    {cfg.label}
                    <span
                      style={{
                        backgroundColor: isActive ? cfg.color : '#E5E7EB',
                        color: isActive ? '#FFF' : '#71717A',
                        padding: '1px 7px',
                        borderRadius: '10px',
                        fontSize: '11px',
                        fontWeight: 600,
                      }}
                    >
                      {count}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Search */}
          <input
            type="text"
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '320px',
              height: '42px',
              padding: '0 16px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              backgroundColor: '#FFF',
              outline: 'none',
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
            }}
          />
        </div>

        {/* Projects List */}
        <div className="flex-1 overflow-y-auto px-8 py-4 bg-primary">
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
              <p style={{ fontFamily: 'Inter', fontSize: '14px', color: '#71717A' }}>
                Loading projects...
              </p>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px' }}>
              <div
                style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '50%',
                  backgroundColor: activeCategory !== 'all' ? PARA_CONFIG[activeCategory].bg : '#FFE2BF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '16px',
                }}
              >
                <span style={{ fontSize: '32px' }}>
                  {activeCategory !== 'all' ? PARA_CONFIG[activeCategory].icon : '📁'}
                </span>
              </div>
              <h3 style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
                {activeCategory !== 'all'
                  ? `No ${PARA_CONFIG[activeCategory].label.toLowerCase()} found`
                  : 'No projects found'}
              </h3>
              <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '14px', textAlign: 'center', maxWidth: '400px' }}>
                {searchQuery
                  ? 'Try adjusting your search.'
                  : activeCategory !== 'all'
                    ? PARA_CONFIG[activeCategory].description
                    : 'No projects available yet.'}
              </p>
            </div>
          ) : (
            <div style={{ maxWidth: '1000px' }}>
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  isExpanded={expandedProjects.has(project.id)}
                  onToggle={() => toggleProject(project.id)}
                  onCategoryChange={handleCategoryChange}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
