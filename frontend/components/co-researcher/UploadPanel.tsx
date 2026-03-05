'use client'

import React, { useState, useRef } from 'react'

interface UploadPanelProps {
  onUpload: (protocol: File, paper: File) => void
}

export default function UploadPanel({ onUpload }: UploadPanelProps) {
  const [protocolFile, setProtocolFile] = useState<File | null>(null)
  const [paperFile, setPaperFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const protocolRef = useRef<HTMLInputElement>(null)
  const paperRef = useRef<HTMLInputElement>(null)

  const handleDrop = (setter: (f: File) => void) => (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.name.toLowerCase().endsWith('.pdf')) {
      setter(file)
    }
  }

  const handleSubmit = async () => {
    if (!protocolFile || !paperFile) return
    setIsUploading(true)
    onUpload(protocolFile, paperFile)
  }

  const dropZoneStyle = (hasFile: boolean): React.CSSProperties => ({
    flex: 1,
    minHeight: 220,
    borderRadius: 16,
    border: `2px dashed ${hasFile ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.1)'}`,
    background: hasFile ? 'rgba(99,102,241,0.04)' : 'rgba(255,255,255,0.02)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'all 0.2s',
    padding: 32,
  })

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div style={{
          color: '#fff', fontSize: 32, fontWeight: 700,
          letterSpacing: '-0.03em', marginBottom: 12,
        }}>
          Integrate Research Into Your Protocol
        </div>
        <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 16, maxWidth: 600, margin: '0 auto' }}>
          Upload your protocol and a research paper. Our 6 specialist AI agents will generate
          and debate integration hypotheses in a live tournament.
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24, marginBottom: 32 }}>
        <div
          style={dropZoneStyle(!!protocolFile)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop(setProtocolFile)}
          onClick={() => protocolRef.current?.click()}
        >
          <input
            ref={protocolRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={(e) => e.target.files?.[0] && setProtocolFile(e.target.files[0])}
          />
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: protocolFile ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16, fontSize: 20,
            color: protocolFile ? '#818CF8' : 'rgba(255,255,255,0.3)',
          }}>
            {protocolFile ? 'P' : '+'}
          </div>
          <div style={{ color: '#fff', fontSize: 15, fontWeight: 500, marginBottom: 4 }}>
            Your Protocol
          </div>
          {protocolFile ? (
            <div style={{ color: '#818CF8', fontSize: 13 }}>{protocolFile.name}</div>
          ) : (
            <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>
              Drop PDF here or click to browse
            </div>
          )}
        </div>

        <div
          style={dropZoneStyle(!!paperFile)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop(setPaperFile)}
          onClick={() => paperRef.current?.click()}
        >
          <input
            ref={paperRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={(e) => e.target.files?.[0] && setPaperFile(e.target.files[0])}
          />
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: paperFile ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16, fontSize: 20,
            color: paperFile ? '#818CF8' : 'rgba(255,255,255,0.3)',
          }}>
            {paperFile ? 'R' : '+'}
          </div>
          <div style={{ color: '#fff', fontSize: 15, fontWeight: 500, marginBottom: 4 }}>
            Research Paper
          </div>
          {paperFile ? (
            <div style={{ color: '#818CF8', fontSize: 13 }}>{paperFile.name}</div>
          ) : (
            <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>
              Drop PDF here or click to browse
            </div>
          )}
        </div>
      </div>

      <div style={{ textAlign: 'center' }}>
        <button
          onClick={handleSubmit}
          disabled={!protocolFile || !paperFile || isUploading}
          style={{
            padding: '14px 36px', borderRadius: 12,
            background: protocolFile && paperFile && !isUploading
              ? 'linear-gradient(135deg, #6366F1, #8B5CF6)'
              : 'rgba(255,255,255,0.06)',
            border: 'none',
            color: protocolFile && paperFile ? '#fff' : 'rgba(255,255,255,0.3)',
            fontSize: 15, fontWeight: 500,
            cursor: protocolFile && paperFile && !isUploading ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s',
          }}
        >
          {isUploading ? 'Starting Analysis...' : 'Analyze & Generate Hypotheses'}
        </button>
      </div>
    </div>
  )
}
