'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api/reproducibility'

const theme = {
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  glassBg: 'rgba(250, 249, 247, 0.95)',
  ink: '#1A1A1A',
  body: '#525252',
  muted: '#8A8A8A',
  accent: '#C9A598',
  accentHover: '#B8948A',
  accentLight: '#FBF4F1',
  forest: '#7BA374',
  forestLight: 'rgba(123, 163, 116, 0.12)',
  border: '#E8E6E3',
}

const space = {
  xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px',
  '2xl': '48px', '3xl': '64px', '4xl': '96px',
}

const text = {
  xs: '12px', sm: '14px', base: '16px', lg: '18px', xl: '24px',
  '2xl': '32px', '3xl': '48px',
}

const radius = { sm: '4px', md: '8px', lg: '12px', full: '9999px' }

const fonts = {
  serif: '"Source Serif 4", Georgia, "Times New Roman", serif',
  sans: '"Source Sans 3", "Helvetica Neue", Arial, sans-serif',
  mono: '"IBM Plex Mono", Menlo, monospace',
}

interface Experiment {
  id: string
  title: string
  category: string
  hypothesis: string
  what_failed: string
  why_failed: string
  sample_size: number
  upvotes: number
  view_count: number
  created_at: string
  comment_count: number
}

interface Stats {
  total_experiments: number
  total_comments: number
  total_upvotes: number
}

export default function ReproducibilityArchivePage() {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState('recent')
  const [categories, setCategories] = useState<{name: string, experiment_count: number}[]>([])

  useEffect(() => {
    loadData()
  }, [category, sort])

  const loadData = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      if (category) params.append('category', category)
      if (sort) params.append('sort', sort)
      params.append('per_page', '50')

      const [expRes, statsRes, catRes] = await Promise.all([
        axios.get(`${API_BASE}/experiments?${params}`),
        axios.get(`${API_BASE}/stats`),
        axios.get(`${API_BASE}/categories`)
      ])

      if (expRes.data.success) setExperiments(expRes.data.experiments)
      if (statsRes.data.success) setStats(statsRes.data.stats)
      if (catRes.data.success) setCategories(catRes.data.categories)
    } catch (error) {
      console.error('Error loading data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!search.trim()) { loadData(); return }
    try {
      setLoading(true)
      const res = await axios.get(`${API_BASE}/experiments?search=${encodeURIComponent(search)}`)
      if (res.data.success) setExperiments(res.data.experiments)
    } catch (error) {
      console.error('Search error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUpvote = async (id: string, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      const res = await axios.post(`${API_BASE}/experiments/${id}/upvote`)
      if (res.data.success) {
        setExperiments(prev => prev.map(exp =>
          exp.id === id ? { ...exp, upvotes: res.data.upvotes } : exp
        ))
      }
    } catch (error) {
      console.error('Upvote error:', error)
    }
  }

  const filteredExperiments = experiments.filter(exp =>
    !search || exp.title.toLowerCase().includes(search.toLowerCase()) ||
    exp.what_failed.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div style={{ minHeight: '100vh', background: theme.pageBg }}>
      {/* Navigation */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: theme.glassBg, backdropFilter: 'blur(20px)',
        borderBottom: `1px solid ${theme.border}`,
        padding: `${space.md} ${space['2xl']}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: space.md }}>
          <span style={{ fontSize: text.xl }}>📚</span>
          <span style={{ fontFamily: fonts.serif, fontSize: text.lg, fontWeight: 600, color: theme.ink }}>
            Reproducibility Archive
          </span>
          <span style={{
            padding: `${space.xs} ${space.sm}`, background: theme.accentLight,
            color: theme.accent, fontSize: text.xs, fontWeight: 600,
            borderRadius: radius.full, textTransform: 'uppercase', letterSpacing: '0.5px',
          }}>Psychology</span>
        </div>
        <Link href="/reproducibility-archive/submit" style={{
          padding: `${space.sm} ${space.lg}`, background: theme.accent,
          color: 'white', fontSize: text.sm, fontWeight: 600, borderRadius: radius.md,
        }}>
          Submit Experiment
        </Link>
      </nav>

      {/* Hero */}
      <section style={{
        padding: `${space['4xl']} ${space['2xl']}`, textAlign: 'center',
        maxWidth: '880px', margin: '0 auto',
      }}>
        <h1 style={{
          fontFamily: fonts.serif, fontSize: text['3xl'], fontWeight: 400,
          color: theme.ink, lineHeight: 1.15, marginBottom: space.lg,
        }}>
          Learn from what <em style={{ fontStyle: 'italic', color: theme.accent }}>didn&apos;t</em> work
        </h1>
        <p style={{
          fontSize: text.lg, color: theme.body, maxWidth: '560px',
          margin: `0 auto ${space.xl}`, lineHeight: 1.6,
        }}>
          An anonymous repository of failed experiments and null results in psychology.
          Share what didn&apos;t work so others don&apos;t repeat the same mistakes.
        </p>

        {/* Search */}
        <div style={{ display: 'flex', gap: space.sm, maxWidth: '520px', margin: '0 auto' }}>
          <input
            type="text" placeholder="Search failed experiments..."
            value={search} onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            style={{
              flex: 1, padding: `${space.md} ${space.lg}`, fontSize: text.base,
              border: `1px solid ${theme.border}`, borderRadius: radius.md,
              background: 'white', outline: 'none', fontFamily: fonts.sans,
            }}
          />
          <button onClick={handleSearch} style={{
            padding: `${space.md} ${space.xl}`, background: theme.accent,
            color: 'white', border: 'none', borderRadius: radius.md,
            fontSize: text.base, fontWeight: 600, cursor: 'pointer', fontFamily: fonts.sans,
          }}>Search</button>
        </div>

        {/* Stats */}
        {stats && (
          <div style={{
            display: 'flex', justifyContent: 'center', gap: space['3xl'], marginTop: space['2xl'],
          }}>
            <div>
              <div style={{ fontFamily: fonts.mono, fontSize: text['2xl'], fontWeight: 600, color: theme.accent }}>
                {stats.total_experiments}
              </div>
              <div style={{ fontSize: text.xs, color: theme.muted, marginTop: space.xs }}>Failed Experiments</div>
            </div>
            <div>
              <div style={{ fontFamily: fonts.mono, fontSize: text['2xl'], fontWeight: 600, color: theme.forest }}>
                {stats.total_comments}
              </div>
              <div style={{ fontSize: text.xs, color: theme.muted, marginTop: space.xs }}>Comments</div>
            </div>
            <div>
              <div style={{ fontFamily: fonts.mono, fontSize: text['2xl'], fontWeight: 600, color: theme.ink }}>
                {stats.total_upvotes}
              </div>
              <div style={{ fontSize: text.xs, color: theme.muted, marginTop: space.xs }}>Upvotes</div>
            </div>
          </div>
        )}
      </section>

      {/* Filters */}
      <div style={{
        padding: `0 ${space['2xl']} ${space.lg}`, maxWidth: '1200px', margin: '0 auto',
        display: 'flex', gap: space.md, alignItems: 'center', flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: text.xs, color: theme.muted, fontWeight: 600, letterSpacing: '0.5px' }}>FILTER</span>
        <select value={category} onChange={(e) => setCategory(e.target.value)} style={{
          padding: `${space.sm} ${space.md}`, border: `1px solid ${theme.border}`,
          borderRadius: radius.md, fontSize: text.sm, background: 'white',
          color: theme.ink, cursor: 'pointer', fontFamily: fonts.sans,
        }}>
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat.name} value={cat.name}>{cat.name} ({cat.experiment_count})</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} style={{
          padding: `${space.sm} ${space.md}`, border: `1px solid ${theme.border}`,
          borderRadius: radius.md, fontSize: text.sm, background: 'white',
          color: theme.ink, cursor: 'pointer', fontFamily: fonts.sans,
        }}>
          <option value="recent">Most Recent</option>
          <option value="popular">Most Upvoted</option>
          <option value="views">Most Viewed</option>
        </select>
      </div>

      {/* Experiments Grid */}
      <main style={{ padding: `0 ${space['2xl']} ${space['4xl']}`, maxWidth: '1200px', margin: '0 auto' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: space['4xl'] }}>
            <div style={{
              width: space['2xl'], height: space['2xl'],
              border: `2px solid ${theme.border}`, borderTopColor: theme.accent,
              borderRadius: radius.full, margin: '0 auto',
              animation: 'spin 1s linear infinite',
            }} />
            <style jsx>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        ) : filteredExperiments.length === 0 ? (
          <div style={{ textAlign: 'center', padding: space['4xl'] }}>
            <p style={{ fontSize: text.lg, color: theme.muted }}>No experiments found.</p>
            <Link href="/reproducibility-archive/submit" style={{
              display: 'inline-block', marginTop: space.lg,
              padding: `${space.sm} ${space.lg}`, background: theme.accent,
              color: 'white', borderRadius: radius.md, fontWeight: 600,
            }}>Submit the first one</Link>
          </div>
        ) : (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: space.lg,
          }}>
            {filteredExperiments.map(exp => (
              <Link
                key={exp.id} href={`/reproducibility-archive/experiment/${exp.id}`}
                style={{
                  background: theme.cardBg, border: `1px solid ${theme.border}`,
                  borderRadius: radius.lg, padding: space.lg, display: 'block',
                  transition: 'border-color 0.15s ease',
                }}
              >
                <div style={{ marginBottom: space.md }}>
                  <span style={{
                    padding: `${space.xs} ${space.sm}`, background: theme.accentLight,
                    color: theme.accent, fontSize: text.xs, fontWeight: 600,
                    borderRadius: radius.full, textTransform: 'uppercase', letterSpacing: '0.3px',
                  }}>{exp.category || 'Psychology'}</span>
                </div>
                <h3 style={{
                  fontFamily: fonts.serif, fontSize: text.lg, fontWeight: 600,
                  color: theme.ink, marginBottom: space.sm, lineHeight: 1.35,
                }}>{exp.title}</h3>
                <p style={{
                  fontSize: text.sm, color: theme.body, lineHeight: 1.55,
                  marginBottom: space.md, display: '-webkit-box',
                  WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                }}>{exp.what_failed}</p>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: space.md,
                  paddingTop: space.md, borderTop: `1px solid ${theme.border}`,
                }}>
                  <button onClick={(e) => handleUpvote(exp.id, e)} style={{
                    display: 'flex', alignItems: 'center', gap: space.xs,
                    padding: `${space.xs} ${space.sm}`, background: theme.forestLight,
                    border: 'none', borderRadius: radius.sm, color: theme.forest,
                    fontSize: text.sm, fontWeight: 600, cursor: 'pointer', fontFamily: fonts.sans,
                  }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M12 19V5M5 12l7-7 7 7"/>
                    </svg>
                    {exp.upvotes}
                  </button>
                  <span style={{ fontSize: text.xs, color: theme.muted, fontFamily: fonts.mono }}>
                    {exp.comment_count} comments
                  </span>
                  {exp.sample_size && (
                    <span style={{ fontSize: text.xs, color: theme.muted, fontFamily: fonts.mono }}>
                      n={exp.sample_size}
                    </span>
                  )}
                  <span style={{ fontSize: text.xs, color: theme.muted, marginLeft: 'auto', fontFamily: fonts.mono }}>
                    {exp.view_count} views
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{
        padding: space['2xl'], borderTop: `1px solid ${theme.border}`, textAlign: 'center',
      }}>
        <p style={{ fontSize: text.sm, color: theme.muted }}>
          Reproducibility Archive — Because null results matter.
        </p>
        <p style={{ fontSize: text.xs, color: theme.muted, marginTop: space.sm }}>
          An open repository for replication failures. Built at UCLA.
        </p>
      </footer>
    </div>
  )
}
