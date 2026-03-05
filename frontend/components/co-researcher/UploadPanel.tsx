'use client'

import React, { useState, useRef } from 'react'

interface UploadPanelProps {
  onUpload: (myResearch: File, papers: File[]) => void
}

export default function UploadPanel({ onUpload }: UploadPanelProps) {
  const [targetFile, setTargetFile] = useState<File | null>(null)
  const [paperFiles, setPaperFiles] = useState<File[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const targetRef = useRef<HTMLInputElement>(null)
  const paperRef = useRef<HTMLInputElement>(null)

  const ACCEPTED = '.pdf,.docx,.doc'

  const isAccepted = (name: string) => /\.(pdf|docx|doc)$/i.test(name)

  const handleDrop = (setter: 'target' | 'papers') => (e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files).filter(f => isAccepted(f.name))
    if (setter === 'target' && files[0]) setTargetFile(files[0])
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

  const handleSubmit = () => {
    if (!targetFile || paperFiles.length === 0) return
    setIsUploading(true)
    onUpload(targetFile, paperFiles)
  }

  const ready = targetFile && paperFiles.length > 0 && !isUploading

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '48px 0 0' }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: '0.1em',
          textTransform: 'uppercase', color: '#ea580c', marginBottom: 16,
        }}>Research Translator</div>
        <h1 style={{
          fontSize: 28, fontWeight: 500, color: '#1c1917',
          letterSpacing: '-0.02em', margin: '0 0 12px', lineHeight: 1.3,
        }}>
          Translate Research Ideas Into Your Work
        </h1>
        <p style={{
          fontSize: 15, color: '#57534e', lineHeight: 1.6,
          maxWidth: 540, margin: '0 auto',
        }}>
          Upload your research and papers you want to learn from. The system decomposes their
          methods into transferable principles, maps them to your domain, and stress-tests
          each translation.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 20, marginBottom: 24 }}>
        {/* My Research */}
        <div
          style={{
            flex: 1, minHeight: 200, borderRadius: 14,
            border: `2px dashed ${targetFile ? '#ea580c' : '#d6d3d1'}`,
            background: targetFile ? '#fff7ed' : '#fafaf9',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', transition: 'all 0.2s', padding: 32,
          }}
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop('target')}
          onClick={() => targetRef.current?.click()}
        >
          <input
            ref={targetRef} type="file" accept={ACCEPTED} style={{ display: 'none' }}
            onChange={e => e.target.files?.[0] && setTargetFile(e.target.files[0])}
          />
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: targetFile ? '#fed7aa' : '#e7e5e4',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 14,
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={targetFile ? '#ea580c' : '#a8a29e'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {targetFile ? (
                <path d="M20 6L9 17l-5-5" />
              ) : (
                <>
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </>
              )}
            </svg>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#1c1917', marginBottom: 4 }}>
            My Research
          </div>
          {targetFile ? (
            <div style={{ color: '#ea580c', fontSize: 13 }}>{targetFile.name}</div>
          ) : (
            <div style={{ color: '#a8a29e', fontSize: 13, textAlign: 'center' }}>
              Your paper or research description<br />
              <span style={{ fontSize: 11 }}>PDF or DOCX</span>
            </div>
          )}
        </div>

        {/* Papers I Read */}
        <div
          style={{
            flex: 1, minHeight: 200, borderRadius: 14,
            border: `2px dashed ${paperFiles.length > 0 ? '#ea580c' : '#d6d3d1'}`,
            background: paperFiles.length > 0 ? '#fff7ed' : '#fafaf9',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', transition: 'all 0.2s', padding: 24,
          }}
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop('papers')}
          onClick={() => paperRef.current?.click()}
        >
          <input
            ref={paperRef} type="file" accept={ACCEPTED} multiple style={{ display: 'none' }}
            onChange={e => { addPapers(e.target.files); e.target.value = '' }}
          />
          {paperFiles.length === 0 ? (
            <>
              <div style={{
                width: 44, height: 44, borderRadius: 12, background: '#e7e5e4',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 14,
              }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a8a29e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
                </svg>
              </div>
              <div style={{ fontSize: 14, fontWeight: 500, color: '#1c1917', marginBottom: 4 }}>
                Papers I Want to Learn From
              </div>
              <div style={{ color: '#a8a29e', fontSize: 13, textAlign: 'center' }}>
                1-5 papers from any field<br />
                <span style={{ fontSize: 11 }}>PDF or DOCX</span>
              </div>
            </>
          ) : (
            <div style={{ width: '100%' }} onClick={e => e.stopPropagation()}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#ea580c' }}>
                  {paperFiles.length} paper{paperFiles.length !== 1 ? 's' : ''}
                </div>
                {paperFiles.length < 5 && (
                  <button
                    onClick={e => { e.stopPropagation(); paperRef.current?.click() }}
                    style={{
                      padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 500,
                      background: '#fff7ed', border: '1px solid #fed7aa', color: '#ea580c',
                      cursor: 'pointer',
                    }}
                  >+ Add</button>
                )}
              </div>
              {paperFiles.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 10px', marginBottom: 4, borderRadius: 8,
                  background: '#fafaf9', border: '1px solid #e7e5e4',
                }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ea580c" strokeWidth="2.5">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                  <span style={{
                    flex: 1, fontSize: 12, color: '#57534e',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{f.name}</span>
                  <button
                    onClick={e => { e.stopPropagation(); removePaper(i) }}
                    style={{
                      width: 18, height: 18, borderRadius: 4, border: 'none',
                      background: 'transparent', color: '#a8a29e', cursor: 'pointer',
                      fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >&times;</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{ textAlign: 'center' }}>
        <button
          onClick={handleSubmit}
          disabled={!ready}
          style={{
            padding: '12px 32px', borderRadius: 10,
            background: ready ? '#ea580c' : '#e7e5e4', border: 'none',
            color: ready ? '#fff' : '#a8a29e',
            fontSize: 14, fontWeight: 500,
            cursor: ready ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s', letterSpacing: '-0.01em',
          }}
        >
          {isUploading ? 'Starting Analysis...' : 'Translate Ideas'}
        </button>
      </div>
    </div>
  )
}
