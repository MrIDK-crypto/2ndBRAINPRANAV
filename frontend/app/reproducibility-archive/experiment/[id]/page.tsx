'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api/reproducibility'

const theme = {
  pageBg: '#FAF9F7', cardBg: '#FFFFFF', glassBg: 'rgba(250, 249, 247, 0.95)',
  ink: '#1A1A1A', body: '#525252', muted: '#8A8A8A',
  accent: '#C9A598', accentHover: '#B8948A', accentLight: '#FBF4F1',
  forest: '#7BA374', forestLight: 'rgba(123, 163, 116, 0.12)', border: '#E8E6E3',
}

const space = {
  xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px',
  '2xl': '48px', '3xl': '64px', '4xl': '96px',
}

const text = {
  xs: '12px', sm: '14px', base: '16px', lg: '18px', xl: '24px', '2xl': '32px',
}

const radius = { sm: '4px', md: '8px', lg: '12px', full: '9999px' }

const fonts = {
  serif: '"Source Serif 4", Georgia, "Times New Roman", serif',
  sans: '"Source Sans 3", "Helvetica Neue", Arial, sans-serif',
  mono: '"IBM Plex Mono", Menlo, monospace',
}

interface Comment {
  id: string
  content: string
  upvotes: number
  created_at: string
}

interface Experiment {
  id: string
  title: string
  category: string
  hypothesis: string
  sample_size: number
  design_type: string
  methodology: string
  materials: string
  what_failed: string
  why_failed: string
  lessons_learned: string
  original_study_doi: string
  original_study_citation: string
  source_url: string
  is_seeded: boolean
  upvotes: number
  view_count: number
  created_at: string
  comments: Comment[]
}

export default function ExperimentPage() {
  const params = useParams()
  const id = params.id as string

  const [experiment, setExperiment] = useState<Experiment | null>(null)
  const [loading, setLoading] = useState(true)
  const [newComment, setNewComment] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)

  useEffect(() => { loadExperiment() }, [id])

  const loadExperiment = async () => {
    try {
      const res = await axios.get(`${API_BASE}/experiments/${id}`)
      if (res.data.success) setExperiment(res.data.experiment)
    } catch (error) {
      console.error('Error loading experiment:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUpvote = async () => {
    try {
      const res = await axios.post(`${API_BASE}/experiments/${id}/upvote`)
      if (res.data.success && experiment) {
        setExperiment({ ...experiment, upvotes: res.data.upvotes })
      }
    } catch (error) {
      console.error('Upvote error:', error)
    }
  }

  const handleSubmitComment = async () => {
    if (!newComment.trim()) return
    setSubmittingComment(true)
    try {
      const res = await axios.post(`${API_BASE}/experiments/${id}/comments`, { content: newComment })
      if (res.data.success && experiment) {
        setExperiment({ ...experiment, comments: [res.data.comment, ...experiment.comments] })
        setNewComment('')
      }
    } catch (error) {
      console.error('Comment error:', error)
    } finally {
      setSubmittingComment(false)
    }
  }

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: theme.pageBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: space['2xl'], height: space['2xl'],
          border: `2px solid ${theme.border}`, borderTopColor: theme.accent,
          borderRadius: radius.full, animation: 'spin 1s linear infinite',
        }} />
        <style jsx>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (!experiment) {
    return (
      <div style={{ minHeight: '100vh', background: theme.pageBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ fontFamily: fonts.serif, fontSize: text.xl, color: theme.ink }}>Experiment not found</h2>
          <Link href="/reproducibility-archive" style={{ color: theme.accent, marginTop: space.md, display: 'inline-block', fontSize: text.sm }}>
            Go back home
          </Link>
        </div>
      </div>
    )
  }

  const sectionStyle = {
    background: theme.cardBg, border: `1px solid ${theme.border}`,
    borderRadius: radius.lg, padding: space.lg,
  }

  const sectionLabel = {
    fontSize: text.xs, fontWeight: 600, color: theme.muted,
    marginBottom: space.sm, textTransform: 'uppercase' as const, letterSpacing: '0.5px',
  }

  return (
    <div style={{ minHeight: '100vh', background: theme.pageBg }}>
      {/* Nav */}
      <nav style={{
        background: theme.glassBg, backdropFilter: 'blur(20px)',
        borderBottom: `1px solid ${theme.border}`,
        padding: `${space.md} ${space['2xl']}`, display: 'flex',
        alignItems: 'center', justifyContent: 'space-between',
      }}>
        <Link href="/reproducibility-archive" style={{ display: 'flex', alignItems: 'center', gap: space.md }}>
          <span style={{ fontSize: text.xl }}>📚</span>
          <span style={{ fontFamily: fonts.serif, fontSize: text.lg, fontWeight: 600, color: theme.ink }}>
            Reproducibility Archive
          </span>
        </Link>
        <Link href="/reproducibility-archive/submit" style={{
          padding: `${space.sm} ${space.lg}`, background: theme.accent,
          color: 'white', fontSize: text.sm, fontWeight: 600, borderRadius: radius.md,
        }}>Submit Your Own</Link>
      </nav>

      <main style={{ padding: `${space['3xl']} ${space['2xl']}`, maxWidth: '880px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: space.xl }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: space.md, marginBottom: space.md }}>
            <span style={{
              padding: `${space.xs} ${space.sm}`, background: theme.accentLight,
              color: theme.accent, fontSize: text.xs, fontWeight: 600,
              borderRadius: radius.full, textTransform: 'uppercase', letterSpacing: '0.3px',
            }}>{experiment.category || 'Psychology'}</span>
            {experiment.sample_size && (
              <span style={{ fontSize: text.xs, color: theme.muted, fontFamily: fonts.mono }}>n={experiment.sample_size}</span>
            )}
            {experiment.design_type && (
              <span style={{ fontSize: text.xs, color: theme.muted }}>{experiment.design_type}</span>
            )}
          </div>

          <h1 style={{
            fontFamily: fonts.serif, fontSize: text['2xl'], fontWeight: 400,
            color: theme.ink, lineHeight: 1.25, marginBottom: space.lg,
          }}>{experiment.title}</h1>

          <div style={{ display: 'flex', alignItems: 'center', gap: space.md }}>
            <button onClick={handleUpvote} style={{
              display: 'flex', alignItems: 'center', gap: space.sm,
              padding: `${space.sm} ${space.md}`, background: theme.forestLight,
              border: 'none', borderRadius: radius.md, color: theme.forest,
              fontSize: text.sm, fontWeight: 600, cursor: 'pointer', fontFamily: fonts.sans,
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 19V5M5 12l7-7 7 7"/>
              </svg>
              Upvote ({experiment.upvotes})
            </button>
            <span style={{ fontSize: text.xs, color: theme.muted, fontFamily: fonts.mono }}>
              {experiment.view_count} views
            </span>
          </div>
        </div>

        {/* Content Sections */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: space.lg }}>
          {experiment.hypothesis && (
            <section style={sectionStyle}>
              <h2 style={sectionLabel}>Hypothesis</h2>
              <p style={{ fontSize: text.base, color: theme.ink, lineHeight: 1.6 }}>{experiment.hypothesis}</p>
            </section>
          )}

          {experiment.methodology && (
            <section style={sectionStyle}>
              <h2 style={sectionLabel}>Methodology</h2>
              <p style={{ fontSize: text.base, color: theme.ink, lineHeight: 1.6 }}>{experiment.methodology}</p>
            </section>
          )}

          {/* What Failed - Highlighted */}
          <section style={{
            background: theme.accentLight, border: `2px solid ${theme.accent}`,
            borderRadius: radius.lg, padding: space.lg,
          }}>
            <h2 style={{ ...sectionLabel, color: theme.accent }}>What Failed</h2>
            <p style={{ fontSize: text.base, color: theme.ink, lineHeight: 1.6 }}>{experiment.what_failed}</p>
          </section>

          {experiment.why_failed && (
            <section style={sectionStyle}>
              <h2 style={sectionLabel}>Why It Failed (Analysis)</h2>
              <p style={{ fontSize: text.base, color: theme.ink, lineHeight: 1.6 }}>{experiment.why_failed}</p>
            </section>
          )}

          {experiment.lessons_learned && (
            <section style={{
              background: theme.forestLight, border: `1px solid ${theme.forest}`,
              borderRadius: radius.lg, padding: space.lg,
            }}>
              <h2 style={{ ...sectionLabel, color: theme.forest }}>Lessons Learned</h2>
              <p style={{ fontSize: text.base, color: theme.ink, lineHeight: 1.6 }}>{experiment.lessons_learned}</p>
            </section>
          )}

          {/* Verified Source */}
          {experiment.source_url && (
            <section style={{
              background: 'rgba(123, 163, 116, 0.08)', border: `2px solid ${theme.forest}`,
              borderRadius: radius.lg, padding: space.lg,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: space.sm, marginBottom: space.sm }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={theme.forest} strokeWidth="2.5">
                  <path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/>
                </svg>
                <h2 style={{ ...sectionLabel, color: theme.forest, marginBottom: 0 }}>Verified Source</h2>
              </div>
              <a href={experiment.source_url} target="_blank" rel="noopener noreferrer"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: space.sm,
                  fontSize: text.sm, color: theme.forest, fontFamily: fonts.mono, wordBreak: 'break-all',
                }}>
                {experiment.source_url}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                  <polyline points="15,3 21,3 21,9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            </section>
          )}

          {/* Original Study */}
          {(experiment.original_study_doi || experiment.original_study_citation) && (
            <section style={sectionStyle}>
              <h2 style={sectionLabel}>Original Study Reference</h2>
              {experiment.original_study_citation && (
                <p style={{ fontSize: text.sm, color: theme.ink, lineHeight: 1.6, marginBottom: space.sm }}>
                  {experiment.original_study_citation}
                </p>
              )}
              {experiment.original_study_doi && (
                <a href={`https://doi.org/${experiment.original_study_doi}`} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: text.sm, color: theme.accent, fontFamily: fonts.mono }}>
                  DOI: {experiment.original_study_doi}
                </a>
              )}
            </section>
          )}
        </div>

        {/* Comments */}
        <div style={{ marginTop: space['3xl'] }}>
          <h2 style={{ fontFamily: fonts.serif, fontSize: text.xl, color: theme.ink, marginBottom: space.lg }}>
            Discussion ({experiment.comments.length})
          </h2>

          <div style={{ ...sectionStyle, marginBottom: space.lg }}>
            <textarea value={newComment} onChange={(e) => setNewComment(e.target.value)}
              placeholder="Add to the discussion (anonymous)..." rows={3}
              style={{
                width: '100%', padding: space.md, fontSize: text.sm,
                border: `1px solid ${theme.border}`, borderRadius: radius.md,
                fontFamily: fonts.sans, resize: 'vertical', marginBottom: space.sm,
              }} />
            <button onClick={handleSubmitComment} disabled={submittingComment || !newComment.trim()}
              style={{
                padding: `${space.sm} ${space.lg}`,
                background: newComment.trim() ? theme.accent : theme.muted,
                color: 'white', border: 'none', borderRadius: radius.md,
                fontSize: text.sm, fontWeight: 600,
                cursor: newComment.trim() ? 'pointer' : 'not-allowed', fontFamily: fonts.sans,
              }}>
              {submittingComment ? 'Posting...' : 'Post Anonymously'}
            </button>
          </div>

          {experiment.comments.length === 0 ? (
            <p style={{ color: theme.muted, textAlign: 'center', padding: space.xl, fontSize: text.sm }}>
              No comments yet. Be the first to discuss!
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: space.md }}>
              {experiment.comments.map(comment => (
                <div key={comment.id} style={sectionStyle}>
                  <p style={{ fontSize: text.sm, color: theme.ink, lineHeight: 1.6, marginBottom: space.sm }}>
                    {comment.content}
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: space.md }}>
                    <span style={{ fontSize: text.xs, color: theme.muted }}>Anonymous</span>
                    <span style={{ fontSize: text.xs, color: theme.muted, fontFamily: fonts.mono }}>
                      {new Date(comment.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      <footer style={{
        padding: space['2xl'], borderTop: `1px solid ${theme.border}`,
        textAlign: 'center', marginTop: space['4xl'],
      }}>
        <p style={{ fontSize: text.sm, color: theme.muted }}>
          Reproducibility Archive — Because null results matter.
        </p>
      </footer>
    </div>
  )
}
