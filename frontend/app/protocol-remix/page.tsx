'use client'

import React, { useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5002'

const theme = {
  bg: '#FAF9F7',
  surface: '#FFFFFF',
  primary: '#C9A598',
  primaryHover: '#B8948A',
  text: '#2D2D2D',
  textSec: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
  successBg: '#F0F7EE',
  warning: '#E2A336',
  warningBg: '#FEF7E8',
  error: '#D97373',
  errorBg: '#FEF0F0',
  font: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
}

interface Adaptation {
  protocol_title: string
  source: string
  similarity: number
  original_steps: string[]
  original_reagents: string[]
  adaptation_for_target: string
  confidence: 'high' | 'medium'
}

interface ProtocolMatch {
  title: string
  source: string
  similarity: number
  num_steps: number
}

interface RemixResult {
  success: boolean
  source_organism: string
  target_organism: string
  technique: string
  protocols_found: number
  adaptations: Adaptation[]
  all_matches: ProtocolMatch[]
  message?: string
}

export default function ProtocolRemixPage() {
  const [sourceOrganism, setSourceOrganism] = useState('')
  const [targetOrganism, setTargetOrganism] = useState('')
  const [technique, setTechnique] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RemixResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleRemix = async () => {
    if (!targetOrganism.trim() || !technique.trim()) {
      setError('Please enter target organism and technique')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch(`${API_URL}/api/research-tools/protocol-remix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_organism: sourceOrganism.trim(),
          target_organism: targetOrganism.trim(),
          technique: technique.trim(),
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to find protocols')
      }

      setResult(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const commonOrganisms = ['Mouse', 'Zebrafish', 'Drosophila', 'C. elegans', 'Human cells', 'Rat', 'Yeast', 'E. coli']
  const commonTechniques = ['Immunofluorescence', 'Western blot', 'PCR', 'CRISPR', 'Cell culture', 'RNA extraction', 'Tissue staining', 'Protein purification']

  return (
    <div style={{ minHeight: '100vh', background: theme.bg, fontFamily: theme.font }}>
      {/* Header */}
      <header style={{
        padding: '20px 32px',
        borderBottom: `1px solid ${theme.border}`,
        background: theme.surface,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: theme.primary,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
            <polyline points="22,6 12,13 2,6" />
          </svg>
        </div>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: theme.text, margin: 0 }}>
            Protocol Remix
          </h1>
          <p style={{ fontSize: 12, color: theme.textMuted, margin: 0 }}>
            Adapt protocols across organisms and techniques
          </p>
        </div>
      </header>

      <main style={{ maxWidth: 900, margin: '0 auto', padding: '32px' }}>
        {/* Input Section */}
        {!result && (
          <div style={{
            background: theme.surface,
            borderRadius: 16,
            padding: 32,
            border: `1px solid ${theme.border}`,
          }}>
            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500, color: theme.text }}>
                Source Organism <span style={{ color: theme.textMuted, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="text"
                value={sourceOrganism}
                onChange={(e) => setSourceOrganism(e.target.value)}
                placeholder="e.g., Mouse"
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: 10,
                  border: `1px solid ${theme.border}`,
                  fontSize: 14,
                  fontFamily: theme.font,
                }}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                {commonOrganisms.slice(0, 4).map((org) => (
                  <button
                    key={org}
                    onClick={() => setSourceOrganism(org)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      border: `1px solid ${theme.border}`,
                      background: sourceOrganism === org ? theme.primary : theme.surface,
                      color: sourceOrganism === org ? '#fff' : theme.textSec,
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    {org}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500, color: theme.text }}>
                Target Organism <span style={{ color: theme.error }}>*</span>
              </label>
              <input
                type="text"
                value={targetOrganism}
                onChange={(e) => setTargetOrganism(e.target.value)}
                placeholder="e.g., Zebrafish"
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: 10,
                  border: `1px solid ${theme.border}`,
                  fontSize: 14,
                  fontFamily: theme.font,
                }}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                {commonOrganisms.slice(0, 4).map((org) => (
                  <button
                    key={org}
                    onClick={() => setTargetOrganism(org)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      border: `1px solid ${theme.border}`,
                      background: targetOrganism === org ? theme.primary : theme.surface,
                      color: targetOrganism === org ? '#fff' : theme.textSec,
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    {org}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500, color: theme.text }}>
                Technique <span style={{ color: theme.error }}>*</span>
              </label>
              <input
                type="text"
                value={technique}
                onChange={(e) => setTechnique(e.target.value)}
                placeholder="e.g., Cardiac tissue imaging"
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: 10,
                  border: `1px solid ${theme.border}`,
                  fontSize: 14,
                  fontFamily: theme.font,
                }}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                {commonTechniques.slice(0, 4).map((tech) => (
                  <button
                    key={tech}
                    onClick={() => setTechnique(tech)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      border: `1px solid ${theme.border}`,
                      background: technique === tech ? theme.primary : theme.surface,
                      color: technique === tech ? '#fff' : theme.textSec,
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    {tech}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={handleRemix}
              disabled={loading}
              style={{
                width: '100%',
                padding: '14px 24px',
                borderRadius: 10,
                border: 'none',
                background: loading ? theme.textMuted : theme.primary,
                color: '#fff',
                fontSize: 15,
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? 'Finding protocols...' : 'Find & Adapt Protocols'}
            </button>

            {error && (
              <div style={{
                marginTop: 16,
                padding: 16,
                borderRadius: 10,
                background: theme.errorBg,
                color: theme.error,
              }}>
                {error}
              </div>
            )}
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div>
            {/* Summary */}
            <div style={{
              background: theme.surface,
              borderRadius: 16,
              padding: 24,
              marginBottom: 24,
              border: `1px solid ${theme.border}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: theme.text }}>
                    {result.source_organism || 'General'} → {result.target_organism}
                  </h2>
                  <p style={{ color: theme.textMuted, fontSize: 13, margin: '4px 0 0' }}>
                    Technique: {result.technique}
                  </p>
                </div>
                <div style={{
                  padding: '12px 20px',
                  borderRadius: 12,
                  background: result.protocols_found > 0 ? theme.successBg : theme.warningBg,
                  textAlign: 'center',
                }}>
                  <div style={{
                    fontSize: 28,
                    fontWeight: 700,
                    color: result.protocols_found > 0 ? theme.success : theme.warning,
                  }}>
                    {result.protocols_found}
                  </div>
                  <div style={{ fontSize: 11, color: theme.textMuted }}>Protocols Found</div>
                </div>
              </div>

              {result.message && (
                <div style={{
                  padding: 12,
                  borderRadius: 8,
                  background: theme.warningBg,
                  color: theme.warning,
                  fontSize: 13,
                }}>
                  {result.message}
                </div>
              )}
            </div>

            {/* Adaptations */}
            {result.adaptations && result.adaptations.length > 0 && (
              <div style={{
                background: theme.surface,
                borderRadius: 16,
                padding: 24,
                marginBottom: 24,
                border: `1px solid ${theme.border}`,
              }}>
                <h3 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 16px', color: theme.text }}>
                  Adaptation Suggestions
                </h3>
                {result.adaptations.map((adaptation, i) => (
                  <div key={i} style={{
                    padding: 20,
                    borderRadius: 12,
                    background: theme.bg,
                    marginBottom: 16,
                    border: `1px solid ${theme.border}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                      <div>
                        <div style={{ fontWeight: 600, color: theme.text, fontSize: 15 }}>
                          {adaptation.protocol_title}
                        </div>
                        <div style={{ fontSize: 12, color: theme.textMuted, marginTop: 2 }}>
                          Source: {adaptation.source} &bull; Similarity: {(adaptation.similarity * 100).toFixed(0)}%
                        </div>
                      </div>
                      <span style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        background: adaptation.confidence === 'high' ? theme.success : theme.warning,
                        color: '#fff',
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                      }}>
                        {adaptation.confidence}
                      </span>
                    </div>

                    {/* Original steps/reagents */}
                    <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
                      {adaptation.original_steps?.length > 0 && (
                        <div style={{ flex: 1, minWidth: 200 }}>
                          <div style={{ fontSize: 11, color: theme.textMuted, marginBottom: 4, textTransform: 'uppercase' }}>
                            Key Steps
                          </div>
                          <div style={{ fontSize: 12, color: theme.textSec }}>
                            {adaptation.original_steps.slice(0, 5).join(', ')}
                          </div>
                        </div>
                      )}
                      {adaptation.original_reagents?.length > 0 && (
                        <div style={{ flex: 1, minWidth: 200 }}>
                          <div style={{ fontSize: 11, color: theme.textMuted, marginBottom: 4, textTransform: 'uppercase' }}>
                            Reagents
                          </div>
                          <div style={{ fontSize: 12, color: theme.textSec }}>
                            {adaptation.original_reagents.slice(0, 5).join(', ')}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Adaptation suggestions */}
                    <div style={{
                      padding: 16,
                      borderRadius: 8,
                      background: theme.surface,
                      border: `1px solid ${theme.border}`,
                    }}>
                      <div style={{ fontSize: 11, color: theme.primary, marginBottom: 8, fontWeight: 600, textTransform: 'uppercase' }}>
                        Adaptation for {result.target_organism}
                      </div>
                      <div style={{ fontSize: 13, color: theme.text, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                        {adaptation.adaptation_for_target}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* All Matches */}
            {result.all_matches && result.all_matches.length > 0 && (
              <div style={{
                background: theme.surface,
                borderRadius: 16,
                padding: 24,
                marginBottom: 24,
                border: `1px solid ${theme.border}`,
              }}>
                <h3 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 16px', color: theme.text }}>
                  All Matching Protocols
                </h3>
                <div style={{ display: 'grid', gap: 12 }}>
                  {result.all_matches.map((match, i) => (
                    <div key={i} style={{
                      padding: 12,
                      borderRadius: 8,
                      background: theme.bg,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}>
                      <div>
                        <div style={{ fontWeight: 500, color: theme.text, fontSize: 13 }}>
                          {match.title}
                        </div>
                        <div style={{ fontSize: 11, color: theme.textMuted }}>
                          {match.source} &bull; {match.num_steps} steps
                        </div>
                      </div>
                      <div style={{
                        padding: '4px 8px',
                        borderRadius: 4,
                        background: match.similarity > 0.3 ? theme.successBg : theme.bg,
                        color: match.similarity > 0.3 ? theme.success : theme.textMuted,
                        fontSize: 11,
                        fontWeight: 600,
                      }}>
                        {(match.similarity * 100).toFixed(0)}% match
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => { setResult(null); setSourceOrganism(''); setTargetOrganism(''); setTechnique('') }}
              style={{
                padding: '12px 24px',
                borderRadius: 10,
                border: `1px solid ${theme.border}`,
                background: theme.surface,
                color: theme.text,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Search Again
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
