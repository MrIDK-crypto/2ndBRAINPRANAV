'use client'

import { useState } from 'react'
import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5006/api'

interface WebsiteBuilderModalProps {
  isOpen: boolean
  onClose: () => void
  hasConnectedIntegrations: boolean
  getAuthToken: () => string | null
}

interface GenerationResult {
  website_id: string
  preview_url: string
  download_url: string
  download_zip_url: string
  stats: {
    team_members: number
    publications: number
    projects: number
    research_areas: number
    news_updates: number
  }
  html_length: number
  generation_time_ms: number
}

// Theme options with colors for visual preview
const THEMES = [
  { value: 'blue', label: 'Blue', primary: '#2563EB', secondary: '#3B82F6' },
  { value: 'green', label: 'Green', primary: '#059669', secondary: '#10B981' },
  { value: 'purple', label: 'Purple', primary: '#7C3AED', secondary: '#8B5CF6' },
  { value: 'dark', label: 'Dark', primary: '#1F2937', secondary: '#374151' },
  { value: 'minimal', label: 'Minimal', primary: '#18181B', secondary: '#3F3F46' }
]

// Avatar styles
const AVATAR_STYLES = [
  { value: 'notionists', label: 'Notion Style', description: 'Playful illustrated avatars' },
  { value: 'lorelei', label: 'Lorelei', description: 'Minimalist line art' },
  { value: 'avataaars', label: 'Avataaars', description: 'Colorful cartoon style' },
  { value: 'personas', label: 'Personas', description: 'Modern illustrated people' },
  { value: 'micah', label: 'Micah', description: 'Simple geometric faces' }
]

export default function WebsiteBuilderModal({
  isOpen,
  onClose,
  hasConnectedIntegrations,
  getAuthToken
}: WebsiteBuilderModalProps) {
  const [labName, setLabName] = useState('')
  const [focusAreas, setFocusAreas] = useState('')
  const [theme, setTheme] = useState('blue')
  const [avatarStyle, setAvatarStyle] = useState('notionists')
  const [isLoading, setIsLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<GenerationResult | null>(null)

  if (!isOpen) return null

  const handleSubmit = async () => {
    if (!labName.trim()) {
      setError('Lab name is required')
      return
    }

    setIsLoading(true)
    setError(null)
    setLoadingStep('Extracting information from knowledge base...')

    try {
      const token = getAuthToken()
      if (!token) {
        setError('Please log in to use this feature')
        setIsLoading(false)
        return
      }

      const payload: any = {
        lab_name: labName.trim(),
        theme: theme,
        avatar_style: avatarStyle
      }

      // Parse focus areas (comma-separated)
      if (focusAreas.trim()) {
        payload.focus_areas = focusAreas.split(',').map(s => s.trim()).filter(Boolean)
      }

      // Simulate progress updates
      setTimeout(() => setLoadingStep('Synthesizing lab information...'), 3000)
      setTimeout(() => setLoadingStep('Generating website HTML/CSS/JS...'), 8000)
      setTimeout(() => setLoadingStep('Finalizing your website...'), 15000)

      const response = await axios.post(
        `${API_BASE}/website/generate`,
        payload,
        {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 120000 // 2 minute timeout
        }
      )

      if (response.data.success) {
        setResult(response.data)
      } else {
        setError(response.data.error || 'Failed to generate website')
      }
    } catch (err: any) {
      console.error('Website generation error:', err)
      setError(err.response?.data?.error || err.message || 'Failed to generate website')
    } finally {
      setIsLoading(false)
      setLoadingStep('')
    }
  }

  const handlePreview = () => {
    if (result?.preview_url) {
      // Open preview in new tab - use full URL
      window.open(`${API_BASE.replace('/api', '')}${result.preview_url}`, '_blank')
    }
  }

  const handleDownload = () => {
    if (result?.download_url) {
      // Trigger download
      window.location.href = `${API_BASE.replace('/api', '')}${result.download_url}`
    }
  }

  const handleDownloadZip = () => {
    if (result?.download_zip_url) {
      // Trigger ZIP download
      window.location.href = `${API_BASE.replace('/api', '')}${result.download_zip_url}`
    }
  }

  const resetAndClose = () => {
    setLabName('')
    setFocusAreas('')
    setTheme('blue')
    setAvatarStyle('notionists')
    setError(null)
    setResult(null)
    setLoadingStep('')
    onClose()
  }

  const totalExtracted = result?.stats ?
    ((result.stats.team_members || 0) + (result.stats.publications || 0) +
     (result.stats.projects || 0) + (result.stats.research_areas || 0) + (result.stats.news_updates || 0)) : 0

  return (
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
        zIndex: 1000
      }}
      onClick={resetAndClose}
    >
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          padding: '32px',
          maxWidth: '600px',
          width: '90%',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="3" y1="9" x2="21" y2="9"/>
              <line x1="9" y1="21" x2="9" y2="9"/>
            </svg>
          </div>
          <div>
            <h2 style={{
              fontFamily: 'Avenir, \'Avenir Next\', \'DM Sans\', system-ui, sans-serif',
              fontSize: '20px',
              fontWeight: 600,
              margin: 0,
              color: '#111827'
            }}>
              AI Website Builder
            </h2>
            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
              color: '#71717A',
              margin: 0
            }}>
              Generate a complete lab website from your knowledge base
            </p>
          </div>
        </div>

        {/* No integrations warning */}
        {!hasConnectedIntegrations && !result && (
          <div style={{
            padding: '16px',
            backgroundColor: '#FEF3C7',
            borderRadius: '8px',
            marginTop: '20px',
            marginBottom: '20px',
            border: '1px solid #F59E0B'
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <div>
                <p style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#92400E',
                  margin: '0 0 4px 0'
                }}>
                  No integrations connected
                </p>
                <p style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '13px',
                  color: '#92400E',
                  margin: 0
                }}>
                  Connect integrations like Gmail, Slack, or Web Scraper first to populate your website with real content.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div style={{
            padding: '40px 20px',
            textAlign: 'center',
            marginTop: '20px'
          }}>
            <div style={{
              width: '60px',
              height: '60px',
              margin: '0 auto 20px',
              border: '4px solid #E5E7EB',
              borderTopColor: '#8B5CF6',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }} />
            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '16px',
              fontWeight: 500,
              color: '#374151',
              marginBottom: '8px'
            }}>
              Generating Your Website...
            </p>
            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
              color: '#6B7280'
            }}>
              {loadingStep || 'This may take 30-60 seconds'}
            </p>
          </div>
        )}

        {/* Success Result */}
        {result && !isLoading && (
          <div style={{
            padding: '24px',
            backgroundColor: '#ECFDF5',
            borderRadius: '12px',
            marginTop: '20px',
            border: '1px solid #10B981'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              <span style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '18px',
                fontWeight: 600,
                color: '#065F46'
              }}>
                Website Generated Successfully!
              </span>
            </div>

            {/* Stats */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '12px',
              marginBottom: '20px'
            }}>
              <div style={{
                padding: '12px',
                backgroundColor: 'rgba(255,255,255,0.7)',
                borderRadius: '8px',
                textAlign: 'center'
              }}>
                <p style={{ fontSize: '24px', fontWeight: 700, color: '#065F46', margin: 0 }}>
                  {result.stats?.team_members || 0}
                </p>
                <p style={{ fontSize: '12px', color: '#047857', margin: 0 }}>Team Members</p>
              </div>
              <div style={{
                padding: '12px',
                backgroundColor: 'rgba(255,255,255,0.7)',
                borderRadius: '8px',
                textAlign: 'center'
              }}>
                <p style={{ fontSize: '24px', fontWeight: 700, color: '#065F46', margin: 0 }}>
                  {result.stats?.publications || 0}
                </p>
                <p style={{ fontSize: '12px', color: '#047857', margin: 0 }}>Publications</p>
              </div>
              <div style={{
                padding: '12px',
                backgroundColor: 'rgba(255,255,255,0.7)',
                borderRadius: '8px',
                textAlign: 'center'
              }}>
                <p style={{ fontSize: '24px', fontWeight: 700, color: '#065F46', margin: 0 }}>
                  {result.stats?.research_areas || 0}
                </p>
                <p style={{ fontSize: '12px', color: '#047857', margin: 0 }}>Research Areas</p>
              </div>
            </div>

            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
              color: '#065F46',
              marginBottom: '20px',
              textAlign: 'center'
            }}>
              Generated {((result.html_length || 0) / 1024).toFixed(1)} KB in {((result.generation_time_ms || 0) / 1000).toFixed(1)}s
            </p>

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
              <button
                onClick={handlePreview}
                style={{
                  flex: 1,
                  padding: '14px 24px',
                  borderRadius: '10px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)',
                  color: '#fff',
                  fontSize: '15px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
                Preview Website
              </button>
            </div>

            {/* Download Buttons */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={handleDownload}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  borderRadius: '10px',
                  border: '2px solid #059669',
                  backgroundColor: 'white',
                  color: '#059669',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                HTML
              </button>
              <button
                onClick={handleDownloadZip}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  borderRadius: '10px',
                  border: '2px solid #2563EB',
                  backgroundColor: 'white',
                  color: '#2563EB',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                ZIP Package
              </button>
            </div>
          </div>
        )}

        {/* Form - only show if no result yet and not loading */}
        {!result && !isLoading && (
          <>
            {/* Lab Name */}
            <div style={{ marginTop: '20px', marginBottom: '20px' }}>
              <label style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                display: 'block',
                marginBottom: '8px'
              }}>
                Lab Name *
              </label>
              <input
                type="text"
                value={labName}
                onChange={e => setLabName(e.target.value)}
                placeholder='e.g., "Pellegrini Lab", "Smith Research Group"'
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: '8px',
                  border: '1px solid #D4D4D8',
                  fontSize: '14px',
                  fontFamily: 'Inter, sans-serif',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            {/* Focus Areas */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                display: 'block',
                marginBottom: '8px'
              }}>
                Research Focus Areas
              </label>
              <input
                type="text"
                value={focusAreas}
                onChange={e => setFocusAreas(e.target.value)}
                placeholder='e.g., "Bioinformatics, Genomics, Machine Learning"'
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: '8px',
                  border: '1px solid #D4D4D8',
                  fontSize: '14px',
                  fontFamily: 'Inter, sans-serif',
                  boxSizing: 'border-box'
                }}
              />
              <p style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '12px',
                color: '#71717A',
                marginTop: '4px'
              }}>
                Comma-separated list of research areas to emphasize
              </p>
            </div>

            {/* Theme Selector */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                display: 'block',
                marginBottom: '8px'
              }}>
                Color Theme
              </label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {THEMES.map(t => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setTheme(t.value)}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '8px',
                      border: theme === t.value ? '2px solid #2563EB' : '1px solid #D4D4D8',
                      backgroundColor: theme === t.value ? '#EFF6FF' : '#fff',
                      fontSize: '13px',
                      fontFamily: 'Inter, sans-serif',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      transition: 'all 0.2s'
                    }}
                  >
                    <div style={{
                      width: '16px',
                      height: '16px',
                      borderRadius: '4px',
                      background: `linear-gradient(135deg, ${t.primary} 0%, ${t.secondary} 100%)`
                    }} />
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Avatar Style Selector */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                display: 'block',
                marginBottom: '8px'
              }}>
                Avatar Style
              </label>
              <select
                value={avatarStyle}
                onChange={e => setAvatarStyle(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: '8px',
                  border: '1px solid #D4D4D8',
                  fontSize: '14px',
                  fontFamily: 'Inter, sans-serif',
                  backgroundColor: '#fff',
                  cursor: 'pointer',
                  boxSizing: 'border-box'
                }}
              >
                {AVATAR_STYLES.map(s => (
                  <option key={s.value} value={s.value}>
                    {s.label} - {s.description}
                  </option>
                ))}
              </select>
              <div style={{ marginTop: '8px', display: 'flex', gap: '4px', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: '#6B7280' }}>Preview:</span>
                {['Alice', 'Bob', 'Carol'].map(name => (
                  <img
                    key={name}
                    src={`https://api.dicebear.com/7.x/${avatarStyle}/svg?seed=${name}&size=32`}
                    alt={name}
                    style={{ width: '32px', height: '32px', borderRadius: '50%', border: '2px solid #E5E7EB' }}
                  />
                ))}
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div style={{
                padding: '12px',
                backgroundColor: '#FEE2E2',
                borderRadius: '8px',
                marginBottom: '20px',
                border: '1px solid #EF4444'
              }}>
                <p style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '13px',
                  color: '#B91C1C',
                  margin: 0
                }}>
                  {error}
                </p>
              </div>
            )}

            {/* Info Box */}
            <div style={{
              padding: '12px',
              backgroundColor: '#DBEAFE',
              borderRadius: '8px',
              marginBottom: '20px'
            }}>
              <p style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '13px',
                color: '#1E40AF',
                margin: 0
              }}>
                <strong>AI-Powered Templates:</strong> We extract information from your knowledge base and generate a professional website using curated templates with beautiful images and Notion-style avatars.
              </p>
            </div>

            {/* Buttons */}
            <div style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px'
            }}>
              <button
                onClick={resetAndClose}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: '1px solid #D4D4D8',
                  backgroundColor: '#fff',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!labName.trim() || isLoading}
                style={{
                  padding: '10px 24px',
                  borderRadius: '8px',
                  border: 'none',
                  background: !labName.trim() || isLoading
                    ? '#9ca3af'
                    : 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)',
                  color: '#fff',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: !labName.trim() || isLoading ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
                Generate Website
              </button>
            </div>
          </>
        )}

        {/* Close button for result view */}
        {result && !isLoading && (
          <div style={{ marginTop: '20px', textAlign: 'center' }}>
            <button
              onClick={resetAndClose}
              style={{
                padding: '10px 24px',
                borderRadius: '8px',
                border: '1px solid #D4D4D8',
                backgroundColor: '#fff',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer'
              }}
            >
              Close
            </button>
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
