'use client'

import React, { useState, useRef } from 'react'

// Wellspring Warm theme - matching 2nd Brain design system
const theme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  success: '#9CB896',
  amber: '#E2A336',
  error: '#D97B7B',
}

const font = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface UploadPanelProps {
  onUpload: (myResearch: File | null, papers: File[], researchDescription?: string, paperUrls?: string[]) => void
}

// Sample papers for quick start
const SAMPLE_PAPERS = [
  {
    title: "CRISPR-Cas9 Gene Editing",
    url: "https://arxiv.org/pdf/1301.0001.pdf",
    field: "Molecular Biology"
  },
  {
    title: "Single-Cell RNA Sequencing",
    url: "https://arxiv.org/pdf/1401.0001.pdf",
    field: "Genomics"
  },
  {
    title: "AlphaFold Protein Structure",
    url: "https://arxiv.org/pdf/2107.00001.pdf",
    field: "Computational Biology"
  },
]

export default function UploadPanel({ onUpload }: UploadPanelProps) {
  const [researchDescription, setResearchDescription] = useState('')
  const [targetFile, setTargetFile] = useState<File | null>(null)
  const [inputMode, setInputMode] = useState<'describe' | 'upload'>('describe')

  // Papers can be files OR URLs
  const [paperFiles, setPaperFiles] = useState<File[]>([])
  const [paperUrls, setPaperUrls] = useState<string[]>([])
  const [urlInput, setUrlInput] = useState('')
  const [paperInputMode, setPaperInputMode] = useState<'file' | 'url'>('url')

  const [isUploading, setIsUploading] = useState(false)
  const [showExamples, setShowExamples] = useState(false)

  const targetRef = useRef<HTMLInputElement>(null)
  const paperRef = useRef<HTMLInputElement>(null)

  const ACCEPTED = '.pdf,.docx,.doc'
  const isAccepted = (name: string) => /\.(pdf|docx|doc)$/i.test(name)

  const handleDrop = (setter: 'target' | 'papers') => (e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files).filter(f => isAccepted(f.name))
    if (setter === 'target' && files[0]) {
      setTargetFile(files[0])
      setInputMode('upload')
    }
    if (setter === 'papers' && files.length > 0) {
      setPaperFiles(prev => [...prev, ...files].slice(0, 5))
    }
  }

  const addPapers = (files: FileList | null) => {
    if (!files) return
    const valid = Array.from(files).filter(f => isAccepted(f.name))
    setPaperFiles(prev => [...prev, ...valid].slice(0, 5))
  }

  const removePaper = (i: number) => setPaperFiles(prev => prev.filter((_, idx) => idx !== i))
  const removeUrl = (i: number) => setPaperUrls(prev => prev.filter((_, idx) => idx !== i))

  const addUrl = () => {
    const url = urlInput.trim()
    if (!url) return

    // Accept DOI, arXiv, PubMed, or direct URLs
    const isValid = url.startsWith('http') ||
                    url.startsWith('10.') || // DOI
                    url.includes('arxiv.org') ||
                    url.includes('doi.org') ||
                    url.includes('pubmed')

    if (isValid && paperUrls.length + paperFiles.length < 5) {
      // Convert DOI to URL if needed
      let finalUrl = url
      if (url.startsWith('10.') && !url.includes('doi.org')) {
        finalUrl = `https://doi.org/${url}`
      }
      setPaperUrls(prev => [...prev, finalUrl])
      setUrlInput('')
    }
  }

  const addSamplePaper = (url: string) => {
    if (paperUrls.length + paperFiles.length < 5) {
      setPaperUrls(prev => [...prev, url])
    }
    setShowExamples(false)
  }

  const handleSubmit = () => {
    const hasResearch = inputMode === 'upload' ? targetFile : researchDescription.trim().length > 20
    const hasPapers = paperFiles.length > 0 || paperUrls.length > 0
    if (!hasResearch || !hasPapers) return

    setIsUploading(true)
    onUpload(
      inputMode === 'upload' ? targetFile : null,
      paperFiles,
      inputMode === 'describe' ? researchDescription : undefined,
      paperUrls.length > 0 ? paperUrls : undefined
    )
  }

  const hasValidResearch = inputMode === 'upload' ? targetFile : researchDescription.trim().length > 20
  const totalPapers = paperFiles.length + paperUrls.length
  const ready = hasValidResearch && totalPapers > 0 && !isUploading

  // Spacing scale (base: 4px)
  const sp = (n: number) => n * 4

  return (
    <div style={{
      maxWidth: 720,
      margin: '0 auto',
      padding: `${sp(12)}px ${sp(6)}px`,
      fontFamily: font,
    }}>
      {/* Header */}
      <div style={{ marginBottom: sp(10) }}>
        <p style={{
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: theme.primary,
          marginBottom: sp(2),
        }}>Research Translator</p>
        <h1 style={{
          fontSize: 24,
          fontWeight: 500,
          color: theme.textPrimary,
          letterSpacing: '-0.02em',
          margin: 0,
          lineHeight: 1.3,
        }}>
          Translate Ideas From Any Paper
        </h1>
        <p style={{
          fontSize: 14,
          color: theme.textSecondary,
          lineHeight: 1.6,
          marginTop: sp(2),
          maxWidth: 520,
        }}>
          Describe your research, add papers to learn from, and get actionable insights tailored to your work.
        </p>
      </div>

      {/* Step 1: Your Research */}
      <div style={{ marginBottom: sp(8) }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: sp(2),
          marginBottom: sp(3),
        }}>
          <span style={{
            width: 22,
            height: 22,
            borderRadius: '50%',
            background: theme.primary,
            color: '#fff',
            fontSize: 11,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>1</span>
          <span style={{
            fontSize: 13,
            fontWeight: 600,
            color: theme.textPrimary,
          }}>What are you working on?</span>
        </div>

        {/* Mode toggle */}
        <div style={{
          display: 'inline-flex',
          gap: 1,
          marginBottom: sp(3),
          background: theme.border,
          borderRadius: 8,
          padding: 2,
        }}>
          {(['describe', 'upload'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => setInputMode(mode)}
              style={{
                padding: `${sp(1.5)}px ${sp(4)}px`,
                borderRadius: 6,
                border: 'none',
                background: inputMode === mode ? theme.cardBg : 'transparent',
                boxShadow: inputMode === mode ? '0 1px 2px rgba(0,0,0,0.04)' : 'none',
                color: inputMode === mode ? theme.textPrimary : theme.textMuted,
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s',
                fontFamily: font,
              }}
            >
              {mode === 'describe' ? 'Describe it' : 'Upload paper'}
            </button>
          ))}
        </div>

        {inputMode === 'describe' ? (
          <div style={{
            borderRadius: 10,
            border: `1px solid ${researchDescription.trim().length > 20 ? theme.primary : theme.border}`,
            background: researchDescription.trim().length > 20 ? theme.primaryLight : theme.cardBg,
            padding: sp(4),
            transition: 'all 0.2s',
          }}>
            <textarea
              value={researchDescription}
              onChange={e => setResearchDescription(e.target.value)}
              placeholder="Example: I study cardiac regeneration in zebrafish using CRISPR knockouts, confocal imaging, and single-cell sequencing. I want to learn techniques from other model organisms..."
              style={{
                width: '100%',
                minHeight: 100,
                padding: 0,
                border: 'none',
                background: 'transparent',
                fontSize: 14,
                lineHeight: 1.65,
                color: theme.textPrimary,
                resize: 'vertical',
                fontFamily: font,
                outline: 'none',
              }}
            />
            <div style={{
              fontSize: 11,
              color: researchDescription.trim().length > 20 ? theme.success : theme.textMuted,
              marginTop: sp(2),
              display: 'flex',
              alignItems: 'center',
              gap: sp(1),
            }}>
              {researchDescription.trim().length > 20 ? (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                  Ready
                </>
              ) : (
                `${researchDescription.trim().length}/20 characters minimum`
              )}
            </div>
          </div>
        ) : (
          <div
            style={{
              borderRadius: 10,
              minHeight: 100,
              border: `1px dashed ${targetFile ? theme.primary : theme.borderDark}`,
              background: targetFile ? theme.primaryLight : theme.cardBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s',
              padding: sp(6),
            }}
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop('target')}
            onClick={() => targetRef.current?.click()}
          >
            <input
              ref={targetRef}
              type="file"
              accept={ACCEPTED}
              style={{ display: 'none' }}
              onChange={e => e.target.files?.[0] && setTargetFile(e.target.files[0])}
            />
            {targetFile ? (
              <div style={{ textAlign: 'center' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2.5" style={{ marginBottom: sp(1) }}>
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                <div style={{ fontSize: 13, color: theme.primary, fontWeight: 500 }}>{targetFile.name}</div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: theme.textMuted }}>
                <div style={{ fontSize: 13, marginBottom: sp(1) }}>Drop your paper here or click to browse</div>
                <div style={{ fontSize: 11 }}>PDF or DOCX</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Step 2: Papers to Learn From */}
      <div style={{ marginBottom: sp(8) }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: sp(3),
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: sp(2) }}>
            <span style={{
              width: 22,
              height: 22,
              borderRadius: '50%',
              background: theme.primary,
              color: '#fff',
              fontSize: 11,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>2</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: theme.textPrimary }}>
              Add papers to learn from
            </span>
            <span style={{ fontSize: 11, color: theme.textMuted }}>(up to 5)</span>
          </div>
          <button
            onClick={() => setShowExamples(!showExamples)}
            style={{
              padding: `${sp(1)}px ${sp(3)}px`,
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 500,
              background: 'transparent',
              border: `1px solid ${theme.border}`,
              color: theme.textSecondary,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: sp(1),
              fontFamily: font,
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
            Try examples
          </button>
        </div>

        {/* Example papers dropdown */}
        {showExamples && (
          <div style={{
            marginBottom: sp(3),
            padding: sp(3),
            borderRadius: 10,
            background: theme.pageBg,
            border: `1px solid ${theme.border}`,
          }}>
            <div style={{ fontSize: 11, color: theme.textMuted, marginBottom: sp(2) }}>
              Click to add a sample paper:
            </div>
            <div style={{ display: 'flex', gap: sp(2), flexWrap: 'wrap' }}>
              {SAMPLE_PAPERS.map((paper, i) => (
                <button
                  key={i}
                  onClick={() => addSamplePaper(paper.url)}
                  style={{
                    padding: `${sp(1.5)}px ${sp(3)}px`,
                    borderRadius: 6,
                    fontSize: 11,
                    background: theme.cardBg,
                    border: `1px solid ${theme.border}`,
                    color: theme.textPrimary,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: sp(1.5),
                    fontFamily: font,
                  }}
                >
                  <span style={{ fontWeight: 500 }}>{paper.title}</span>
                  <span style={{ color: theme.textMuted }}>({paper.field})</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Paper input mode toggle */}
        <div style={{
          display: 'inline-flex',
          gap: 1,
          marginBottom: sp(3),
          background: theme.border,
          borderRadius: 8,
          padding: 2,
        }}>
          {(['url', 'file'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => setPaperInputMode(mode)}
              style={{
                padding: `${sp(1.5)}px ${sp(4)}px`,
                borderRadius: 6,
                border: 'none',
                background: paperInputMode === mode ? theme.cardBg : 'transparent',
                boxShadow: paperInputMode === mode ? '0 1px 2px rgba(0,0,0,0.04)' : 'none',
                color: paperInputMode === mode ? theme.textPrimary : theme.textMuted,
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s',
                fontFamily: font,
              }}
            >
              {mode === 'url' ? 'Paste URL/DOI' : 'Upload files'}
            </button>
          ))}
        </div>

        {paperInputMode === 'url' ? (
          <div style={{ display: 'flex', gap: sp(2), marginBottom: sp(3) }}>
            <input
              type="text"
              value={urlInput}
              onChange={e => setUrlInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addUrl()}
              placeholder="Paste DOI (10.1234/...), arXiv URL, or paper URL"
              style={{
                flex: 1,
                padding: `${sp(2.5)}px ${sp(4)}px`,
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                fontSize: 13,
                outline: 'none',
                fontFamily: font,
                color: theme.textPrimary,
                background: theme.cardBg,
              }}
            />
            <button
              onClick={addUrl}
              disabled={totalPapers >= 5}
              style={{
                padding: `${sp(2.5)}px ${sp(5)}px`,
                borderRadius: 8,
                border: 'none',
                background: totalPapers >= 5 ? theme.border : theme.primary,
                color: '#fff',
                fontSize: 13,
                fontWeight: 500,
                cursor: totalPapers >= 5 ? 'not-allowed' : 'pointer',
                fontFamily: font,
              }}
            >
              Add
            </button>
          </div>
        ) : (
          <div
            style={{
              borderRadius: 10,
              minHeight: 80,
              border: `1px dashed ${theme.borderDark}`,
              background: theme.cardBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: totalPapers >= 5 ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              padding: sp(5),
              marginBottom: sp(3),
              opacity: totalPapers >= 5 ? 0.5 : 1,
            }}
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop('papers')}
            onClick={() => totalPapers < 5 && paperRef.current?.click()}
          >
            <input
              ref={paperRef}
              type="file"
              accept={ACCEPTED}
              multiple
              style={{ display: 'none' }}
              onChange={e => { addPapers(e.target.files); e.target.value = '' }}
            />
            <div style={{ textAlign: 'center', color: theme.textMuted }}>
              <div style={{ fontSize: 13, marginBottom: sp(1) }}>Drop PDF/DOCX files here or click to browse</div>
              <div style={{ fontSize: 11 }}>
                {totalPapers >= 5 ? 'Maximum 5 papers reached' : `${5 - totalPapers} more paper${5 - totalPapers !== 1 ? 's' : ''} allowed`}
              </div>
            </div>
          </div>
        )}

        {/* List of added papers */}
        {totalPapers > 0 && (
          <div style={{
            borderRadius: 10,
            border: `1px solid ${theme.border}`,
            background: theme.primaryLight,
            padding: sp(3),
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: theme.primary, marginBottom: sp(2) }}>
              {totalPapers} paper{totalPapers !== 1 ? 's' : ''} added
            </div>
            {paperFiles.map((f, i) => (
              <div key={`file-${i}`} style={{
                display: 'flex',
                alignItems: 'center',
                gap: sp(2),
                padding: `${sp(1.5)}px ${sp(3)}px`,
                marginBottom: sp(1),
                borderRadius: 6,
                background: theme.cardBg,
                border: `1px solid ${theme.border}`,
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                  <polyline points="14,2 14,8 20,8" />
                </svg>
                <span style={{
                  flex: 1,
                  fontSize: 12,
                  color: theme.textSecondary,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>{f.name}</span>
                <button
                  onClick={() => removePaper(i)}
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 4,
                    border: 'none',
                    background: 'transparent',
                    color: theme.textMuted,
                    cursor: 'pointer',
                    fontSize: 16,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >&times;</button>
              </div>
            ))}
            {paperUrls.map((url, i) => (
              <div key={`url-${i}`} style={{
                display: 'flex',
                alignItems: 'center',
                gap: sp(2),
                padding: `${sp(1.5)}px ${sp(3)}px`,
                marginBottom: sp(1),
                borderRadius: 6,
                background: theme.cardBg,
                border: `1px solid ${theme.border}`,
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2">
                  <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
                </svg>
                <span style={{
                  flex: 1,
                  fontSize: 12,
                  color: theme.textSecondary,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>{url}</span>
                <button
                  onClick={() => removeUrl(i)}
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 4,
                    border: 'none',
                    background: 'transparent',
                    color: theme.textMuted,
                    cursor: 'pointer',
                    fontSize: 16,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >&times;</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Submit button */}
      <div style={{ textAlign: 'center' }}>
        <button
          onClick={handleSubmit}
          disabled={!ready}
          style={{
            padding: `${sp(3.5)}px ${sp(10)}px`,
            borderRadius: 10,
            background: ready ? theme.primary : theme.border,
            border: 'none',
            color: ready ? '#fff' : theme.textMuted,
            fontSize: 15,
            fontWeight: 500,
            cursor: ready ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s',
            letterSpacing: '-0.01em',
            fontFamily: font,
          }}
        >
          {isUploading ? 'Starting Analysis...' : 'Translate Ideas'}
        </button>
        {!ready && (
          <div style={{ fontSize: 11, color: theme.textMuted, marginTop: sp(3) }}>
            {!hasValidResearch && 'Describe your research or upload a paper'}
            {hasValidResearch && totalPapers === 0 && 'Add at least one paper to learn from'}
          </div>
        )}
      </div>
    </div>
  )
}
