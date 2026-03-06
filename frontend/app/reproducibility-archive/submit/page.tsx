'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api/reproducibility'

const theme = {
  pageBg: '#FAF9F7', cardBg: '#FFFFFF', glassBg: 'rgba(250, 249, 247, 0.95)',
  ink: '#1A1A1A', body: '#525252', muted: '#8A8A8A',
  accent: '#C9A598', accentLight: '#FBF4F1', forest: '#7BA374', border: '#E8E6E3',
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
}

const CATEGORIES = [
  'Social Psychology', 'Cognitive Psychology', 'Developmental Psychology',
  'Clinical Psychology', 'Personality Psychology', 'Neuroscience',
  'Educational Psychology', 'Industrial-Organizational', 'Health Psychology', 'Other',
]

export default function SubmitPage() {
  const router = useRouter()
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  const [form, setForm] = useState({
    title: '', category: '', hypothesis: '', sample_size: '',
    design_type: '', methodology: '', what_failed: '', why_failed: '',
    lessons_learned: '', original_study_doi: '', original_study_citation: '',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.title || !form.what_failed) {
      alert('Please fill in at least the title and what failed')
      return
    }
    setSubmitting(true)
    try {
      const data = { ...form, sample_size: form.sample_size ? parseInt(form.sample_size) : null }
      const res = await axios.post(`${API_BASE}/experiments`, data)
      if (res.data.success) {
        setSuccess(true)
        setTimeout(() => router.push(`/reproducibility-archive/experiment/${res.data.experiment.id}`), 2000)
      }
    } catch (error) {
      console.error('Submit error:', error)
      alert('Failed to submit. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <div style={{ minHeight: '100vh', background: theme.pageBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: space['3xl'], height: space['3xl'], background: theme.forest,
            borderRadius: radius.full, display: 'flex', alignItems: 'center',
            justifyContent: 'center', margin: `0 auto ${space.lg}`,
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <path d="M20 6L9 17l-5-5"/>
            </svg>
          </div>
          <h2 style={{ fontFamily: fonts.serif, fontSize: text.xl, color: theme.ink, marginBottom: space.sm }}>
            Submitted anonymously!
          </h2>
          <p style={{ color: theme.body, fontSize: text.base }}>Redirecting to your experiment...</p>
        </div>
      </div>
    )
  }

  const inputStyle = {
    width: '100%', padding: space.md, fontSize: text.base,
    border: `1px solid ${theme.border}`, borderRadius: radius.md, fontFamily: fonts.sans,
  }

  const textareaStyle = { ...inputStyle, resize: 'vertical' as const }

  const labelStyle = {
    display: 'block' as const, fontSize: text.sm, fontWeight: 600,
    color: theme.ink, marginBottom: space.sm,
  }

  return (
    <div style={{ minHeight: '100vh', background: theme.pageBg }}>
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
      </nav>

      <main style={{ padding: `${space['3xl']} ${space['2xl']}`, maxWidth: '720px', margin: '0 auto' }}>
        <div style={{ marginBottom: space['2xl'] }}>
          <h1 style={{ fontFamily: fonts.serif, fontSize: text['2xl'], color: theme.ink, marginBottom: space.md }}>
            Share Your Failed Experiment
          </h1>
          <p style={{ fontSize: text.base, color: theme.body, lineHeight: 1.6 }}>
            Your submission is <strong>completely anonymous</strong>. No login required, no email stored.
            Help other researchers avoid repeating the same mistakes.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: space.lg }}>
            <label style={labelStyle}>Title *</label>
            <input name="title" value={form.title} onChange={handleChange}
              placeholder="e.g., Failed Replication: Ego Depletion Effect" style={inputStyle} />
          </div>

          <div style={{ marginBottom: space.lg }}>
            <label style={labelStyle}>Category</label>
            <select name="category" value={form.category} onChange={handleChange}
              style={{ ...inputStyle, background: 'white' }}>
              <option value="">Select a category...</option>
              {CATEGORIES.map(cat => <option key={cat} value={cat}>{cat}</option>)}
            </select>
          </div>

          <div style={{ marginBottom: space.lg }}>
            <label style={labelStyle}>Hypothesis</label>
            <textarea name="hypothesis" value={form.hypothesis} onChange={handleChange}
              placeholder="What did you expect to find?" rows={3} style={textareaStyle} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: space.lg, marginBottom: space.lg }}>
            <div>
              <label style={labelStyle}>Sample Size</label>
              <input name="sample_size" type="number" value={form.sample_size}
                onChange={handleChange} placeholder="e.g., 120" style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Design Type</label>
              <input name="design_type" value={form.design_type} onChange={handleChange}
                placeholder="e.g., Between-subjects" style={inputStyle} />
            </div>
          </div>

          <div style={{ marginBottom: space.lg }}>
            <label style={labelStyle}>Methodology</label>
            <textarea name="methodology" value={form.methodology} onChange={handleChange}
              placeholder="Brief description of your experimental procedure..." rows={4} style={textareaStyle} />
          </div>

          <div style={{ marginBottom: space.lg, padding: space.lg, background: theme.accentLight, borderRadius: radius.lg }}>
            <label style={{ ...labelStyle, color: theme.accent }}>What Failed? *</label>
            <textarea name="what_failed" value={form.what_failed} onChange={handleChange}
              placeholder="Describe what didn't work. Be specific about the null results, failed replication, or unexpected findings..."
              rows={4} style={{ ...textareaStyle, border: `2px solid ${theme.accent}` }} />
          </div>

          <div style={{ marginBottom: space.lg }}>
            <label style={labelStyle}>Why Do You Think It Failed?</label>
            <textarea name="why_failed" value={form.why_failed} onChange={handleChange}
              placeholder="Your analysis: methodological issues, underpowered, theoretical problems, etc."
              rows={4} style={textareaStyle} />
          </div>

          <div style={{ marginBottom: space.lg }}>
            <label style={labelStyle}>Lessons Learned</label>
            <textarea name="lessons_learned" value={form.lessons_learned} onChange={handleChange}
              placeholder="What should other researchers know? What would you do differently?"
              rows={3} style={textareaStyle} />
          </div>

          <div style={{ marginBottom: space.xl }}>
            <label style={labelStyle}>Original Study (if replication)</label>
            <input name="original_study_doi" value={form.original_study_doi} onChange={handleChange}
              placeholder="DOI (e.g., 10.1037/0022-3514.74.5.1252)"
              style={{ ...inputStyle, marginBottom: space.sm }} />
            <input name="original_study_citation" value={form.original_study_citation} onChange={handleChange}
              placeholder="Full citation (e.g., Baumeister et al., 1998)" style={inputStyle} />
          </div>

          <button type="submit" disabled={submitting} style={{
            width: '100%', padding: space.md,
            background: submitting ? theme.muted : theme.accent,
            color: 'white', border: 'none', borderRadius: radius.md,
            fontSize: text.base, fontWeight: 600,
            cursor: submitting ? 'not-allowed' : 'pointer', fontFamily: fonts.sans,
          }}>
            {submitting ? 'Submitting...' : 'Submit Anonymously'}
          </button>

          <p style={{ textAlign: 'center', fontSize: text.xs, color: theme.muted, marginTop: space.md }}>
            Your submission is anonymous. No account required.
          </p>
        </form>
      </main>
    </div>
  )
}
