'use client'

import React, { useState, useRef, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import TopNav from '@/components/shared/TopNav'
import { useAuth } from '@/contexts/AuthContext'
import { useSyncProgress } from '@/contexts/SyncProgressContext'

// ---------- constants ----------
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

const ACCEPTED_EXTENSIONS = [
  '.pdf', '.doc', '.docx', '.txt', '.csv', '.tsv', '.xlsx', '.xls',
  '.pptx', '.ppt', '.rtf', '.json', '.xml', '.html', '.md',
  '.r', '.rmd', '.rdata',
  '.png', '.jpg', '.jpeg', '.gif', '.heic', '.heif', '.tif', '.tiff', '.bmp',
  '.mp4', '.mov', '.wav', '.mp3', '.m4a', '.webm',
  '.zip',
]

// Files to silently skip (system/junk files) — never show as errors
const SILENT_SKIP_PATTERNS = [
  '.ds_store', '.rhistory', '.gitignore', '.gitattributes',
  'thumbs.db', '.spotlight-v100', '.trashes', '.fseventsd',
]

const ACCEPTED_MIME_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/csv',
  'text/tab-separated-values',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.ms-powerpoint',
  'application/rtf',
  'application/json',
  'application/xml', 'text/xml',
  'text/html',
  'text/markdown',
  'image/png', 'image/jpeg', 'image/gif', 'image/heic', 'image/heif', 'image/tiff',
  'video/mp4', 'video/quicktime',
  'audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/x-m4a', 'audio/webm',
  'video/webm',
  'application/zip',
].join(',')

// ---------- design tokens ----------
const COLORS = {
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  accent: '#C9A598',
  accentLightBg: '#FBF4F1',
  border: '#F0EEEC',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  success: '#9CB896',
  successLightBg: '#F4F8F3',
  error: '#D97B7B',
  errorLightBg: '#FDF2F2',
}

const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"
const DISPLAY_FONT = "'Instrument Serif', Georgia, serif"

// ---------- types ----------
interface FileEntry {
  file: File
  id: string
  status: 'pending' | 'uploading' | 'done' | 'error'
  progress?: number
  error?: string
}

// ---------- helpers ----------
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i]
}

function isAcceptedFile(file: File): boolean {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  return ACCEPTED_EXTENSIONS.includes(ext)
}

// ---------- component ----------
export default function DragDropUploadPage() {
  const router = useRouter()
  const { token } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { activeSyncs, addLocalSync, updateSync, removeSync } = useSyncProgress()

  const [files, setFiles] = useState<FileEntry[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [phase, setPhase] = useState<'idle' | 'uploading' | 'complete'>('idle')
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Track the current upload's ID in the global sync context
  const uploadSyncIdRef = useRef<string | null>(null)

  // Counter to track nested drag events
  const dragCounterRef = useRef(0)
  const folderInputRef = useRef<HTMLInputElement>(null)

  // Restore upload state from global context when navigating back to this page
  useEffect(() => {
    for (const sync of Array.from(activeSyncs.values())) {
      if (sync.connectorType !== 'manual_upload') continue

      uploadSyncIdRef.current = sync.syncId
      const isComplete = sync.status === 'complete' || sync.status === 'completed'
      const isError = sync.status === 'error'

      if (isComplete) {
        setPhase('complete')
      } else if (isError) {
        setPhase('idle')
        setUploadError(sync.errorMessage || 'Upload failed')
      } else {
        setPhase('uploading')
      }
      break // only handle one manual upload at a time
    }
    // Only run on mount to restore state
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---------- file handling ----------
  const addFiles = useCallback((incoming: FileList | File[]) => {
    const accepted: FileEntry[] = []
    const rejected: string[] = []

    Array.from(incoming).forEach((file) => {
      const nameLower = file.name.toLowerCase()
      // Silently skip system/junk files — don't show as errors
      if (SILENT_SKIP_PATTERNS.some(p => nameLower === p || nameLower.endsWith(p))) {
        return
      }
      if (isAcceptedFile(file)) {
        accepted.push({
          file,
          id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
          status: 'pending',
        })
      } else {
        rejected.push(file.name)
      }
    })

    if (rejected.length > 0) {
      setUploadError(`Unsupported file type(s): ${rejected.join(', ')}`)
    } else {
      setUploadError(null)
    }

    if (accepted.length > 0) {
      setFiles((prev) => [...prev, ...accepted])
    }
  }, [])

  // ---------- drag events ----------
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current++
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragOver(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) {
      setIsDragOver(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
    dragCounterRef.current = 0

    // Try to read directory entries (folder drag-and-drop)
    const items = e.dataTransfer.items
    if (items && items.length > 0) {
      const allFiles: File[] = []

      const readEntry = (entry: FileSystemEntry): Promise<File[]> => {
        return new Promise((resolve) => {
          if (entry.isFile) {
            (entry as FileSystemFileEntry).file((f) => {
              // Skip hidden files and macOS resource forks
              if (!f.name.startsWith('.') && !entry.fullPath.includes('__MACOSX')) {
                resolve([f])
              } else {
                resolve([])
              }
            }, () => resolve([]))
          } else if (entry.isDirectory) {
            const reader = (entry as FileSystemDirectoryEntry).createReader()
            const readAll = (entries: FileSystemEntry[]): Promise<File[]> => {
              return new Promise((resolve2) => {
                reader.readEntries(async (batch) => {
                  if (batch.length === 0) {
                    const results = await Promise.all(entries.map(readEntry))
                    resolve2(results.flat())
                  } else {
                    readAll([...entries, ...batch]).then(resolve2)
                  }
                }, () => resolve2([]))
              })
            }
            readAll([]).then(resolve)
          } else {
            resolve([])
          }
        })
      }

      const entries: FileSystemEntry[] = []
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry?.()
        if (entry) entries.push(entry)
      }

      if (entries.length > 0) {
        const results = await Promise.all(entries.map(readEntry))
        allFiles.push(...results.flat())
      }

      if (allFiles.length > 0) {
        addFiles(allFiles)
      } else if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files)
      }
    } else if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files)
    }
  }, [addFiles])

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files)
      // Reset the input so the same file can be selected again
      e.target.value = ''
    }
  }, [addFiles])

  const handleClickDropZone = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  // ---------- remove a file ----------
  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }, [])

  // ---------- upload (chunked batches) ----------
  const BATCH_SIZE = 50

  const handleUpload = useCallback(async () => {
    if (files.length === 0 || !token) return

    setPhase('uploading')
    setUploadError(null)

    const sessionId = `manual_upload_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    uploadSyncIdRef.current = sessionId

    const totalBatches = Math.ceil(files.length / BATCH_SIZE)

    addLocalSync(sessionId, 'manual_upload', {
      status: 'syncing',
      stage: `Uploading ${files.length} file${files.length !== 1 ? 's' : ''} (batch 1/${totalBatches})...`,
      totalItems: files.length,
      processedItems: 0,
      percentComplete: 0
    })

    // Mark all pending as uploading
    setFiles((prev) =>
      prev.map((f) => (f.status === 'pending' ? { ...f, status: 'uploading' as const, progress: 0 } : f))
    )

    let totalProcessed = 0
    let totalErrors: string[] = []
    let allDocs: Array<{ id: string; title: string; status: string }> = []

    // Send files in batches of BATCH_SIZE
    for (let batchIdx = 0; batchIdx < totalBatches; batchIdx++) {
      const start = batchIdx * BATCH_SIZE
      const end = Math.min(start + BATCH_SIZE, files.length)
      const batchFiles = files.slice(start, end)

      const formData = new FormData()
      batchFiles.forEach((entry) => formData.append('files', entry.file))
      formData.append('batch_index', String(batchIdx))
      formData.append('total_batches', String(totalBatches))
      formData.append('upload_session_id', sessionId)

      try {
        const resp = await fetch(`${API_BASE}/documents/upload-batch`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData,
        })

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({ error: `Batch ${batchIdx + 1} failed (${resp.status})` }))
          throw new Error(errData.error || `Batch ${batchIdx + 1} failed`)
        }

        const data = await resp.json()
        totalProcessed += data.batch_count || 0
        if (data.errors) totalErrors.push(...data.errors)
        if (data.documents) allDocs.push(...data.documents)

        // Update per-file progress for this batch
        const batchFileIds = new Set(batchFiles.map(f => f.id))
        setFiles((prev) =>
          prev.map((f) => batchFileIds.has(f.id) ? { ...f, status: 'done' as const, progress: 100 } : f)
        )

        // Update global progress
        const pct = Math.round(((batchIdx + 1) / totalBatches) * 100)
        updateSync(sessionId, {
          percentComplete: pct,
          processedItems: totalProcessed,
          stage: batchIdx < totalBatches - 1
            ? `Uploading batch ${batchIdx + 2}/${totalBatches} (${totalProcessed} files done)...`
            : `Processing ${totalProcessed} files...`
        })
      } catch (err: any) {
        // Mark remaining batch files as error
        const batchFileIds = new Set(batchFiles.map(f => f.id))
        setFiles((prev) =>
          prev.map((f) => batchFileIds.has(f.id) && f.status === 'uploading'
            ? { ...f, status: 'error' as const, error: err.message }
            : f
          )
        )
        totalErrors.push(err.message)
        // Continue with next batch instead of stopping entirely
      }
    }

    // All batches done
    if (totalProcessed > 0) {
      setPhase('complete')
      updateSync(sessionId, {
        status: 'complete',
        stage: `${totalProcessed} file${totalProcessed !== 1 ? 's' : ''} uploaded${totalErrors.length > 0 ? ` (${totalErrors.length} errors)` : ''}`,
        percentComplete: 100,
        processedItems: totalProcessed
      })
    } else {
      setUploadError(totalErrors.join('; ') || 'All files failed to upload')
      setPhase('idle')
      updateSync(sessionId, {
        status: 'error',
        stage: 'Upload failed',
        errorMessage: totalErrors[0] || 'Unknown error'
      })
    }

    setTimeout(() => {
      removeSync(sessionId)
      uploadSyncIdRef.current = null
    }, 5000)
  }, [files, token, addLocalSync, updateSync, removeSync])

  // ---------- reset ----------
  const handleReset = useCallback(() => {
    // Clean up global sync context if there's an active upload entry
    if (uploadSyncIdRef.current) {
      removeSync(uploadSyncIdRef.current)
      uploadSyncIdRef.current = null
    }
    setFiles([])
    setPhase('idle')
    setUploadError(null)
    dragCounterRef.current = 0
  }, [removeSync])

  // ---------- status icon for file list ----------
  const statusIcon = (status: FileEntry['status']) => {
    switch (status) {
      case 'pending':
        return (
          <div style={{
            width: 18, height: 18, borderRadius: '50%',
            border: `2px solid ${COLORS.border}`,
            flexShrink: 0,
          }} />
        )
      case 'uploading':
        return (
          <div style={{
            width: 18, height: 18, borderRadius: '50%',
            border: `2px solid ${COLORS.accent}`,
            borderTopColor: 'transparent',
            animation: 'spin 0.8s linear infinite',
            flexShrink: 0,
          }} />
        )
      case 'done':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={COLORS.success} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )
      case 'error':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={COLORS.error} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        )
    }
  }

  // ---------- render ----------
  const showDropZone = phase === 'idle' && files.length === 0
  const showFileList = files.length > 0

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: COLORS.pageBg,
      fontFamily: FONT,
    }}>
      <TopNav />

      {/* Keyframes */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes successPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.02); }
        }
      `}</style>

      <div style={{
        maxWidth: '720px',
        margin: '0 auto',
        padding: '48px 24px 64px',
        animation: 'fadeIn 0.3s ease-out',
      }}>
        {/* Page heading */}
        <h1 style={{
          fontFamily: FONT,
          fontSize: '28px',
          fontWeight: 700,
          color: COLORS.textPrimary,
          marginBottom: '8px',
          letterSpacing: '-0.3px',
        }}>
          Upload Files
        </h1>
        <p style={{
          fontSize: '15px',
          color: COLORS.textSecondary,
          marginBottom: '32px',
          lineHeight: '1.5',
        }}>
          Add documents, images, audio, and video to your knowledge base.
        </p>

        {/* Error banner */}
        {uploadError && (
          <div style={{
            padding: '14px 18px',
            backgroundColor: COLORS.errorLightBg,
            border: `1px solid ${COLORS.error}`,
            borderRadius: '12px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            animation: 'fadeIn 0.2s ease-out',
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={COLORS.error} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span style={{ fontSize: '14px', color: COLORS.error, fontWeight: 500 }}>
              {uploadError}
            </span>
          </div>
        )}

        {/* Success banner */}
        {phase === 'complete' && (
          <div style={{
            padding: '20px 24px',
            backgroundColor: COLORS.successLightBg,
            border: `1px solid ${COLORS.success}`,
            borderRadius: '16px',
            marginBottom: '24px',
            textAlign: 'center',
            animation: 'fadeIn 0.3s ease-out',
          }}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke={COLORS.success} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ margin: '0 auto 10px' }}>
              <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <p style={{
              fontSize: '17px',
              fontWeight: 600,
              color: COLORS.textPrimary,
              marginBottom: '4px',
            }}>
              All files uploaded successfully
            </p>
            <p style={{
              fontSize: '14px',
              color: COLORS.textSecondary,
            }}>
              {files.length} file{files.length !== 1 ? 's' : ''} added to your knowledge base.
            </p>
          </div>
        )}

        {/* Drop zone (shown when no files added yet) */}
        {showDropZone && (
          <div
            onClick={handleClickDropZone}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 'calc(100vh - 260px)',
              padding: '64px 32px',
              border: `2px dashed ${isDragOver ? COLORS.accent : COLORS.border}`,
              borderRadius: '16px',
              backgroundColor: isDragOver ? COLORS.accentLightBg : COLORS.cardBg,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke={COLORS.accent} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>

            <p style={{
              marginTop: '20px',
              fontSize: '17px',
              fontWeight: 500,
              color: COLORS.textPrimary,
            }}>
              {isDragOver ? 'Drop files or folders here' : 'Drag & drop files or folders here, or click to browse'}
            </p>
            <p style={{
              marginTop: '8px',
              fontSize: '13px',
              color: COLORS.textMuted,
              textAlign: 'center',
              lineHeight: '1.5',
              maxWidth: '420px',
            }}>
              PDF, DOC, TXT, CSV, XLSX, PPTX, RTF, JSON, XML, HTML, MD, images, audio, video, ZIP
            </p>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); folderInputRef.current?.click() }}
              style={{
                marginTop: '12px',
                padding: '8px 20px',
                fontSize: '13px',
                fontWeight: 500,
                color: COLORS.accent,
                background: 'transparent',
                border: `1px solid ${COLORS.accent}`,
                borderRadius: '8px',
                cursor: 'pointer',
                fontFamily: FONT,
              }}
            >
              Or select a folder
            </button>
          </div>
        )}

        {/* File list + drop zone combo (shown when files are staged or uploading) */}
        {showFileList && (
          <div
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            style={{
              backgroundColor: COLORS.cardBg,
              border: `1px solid ${isDragOver ? COLORS.accent : COLORS.border}`,
              borderRadius: '16px',
              overflow: 'hidden',
              transition: 'border-color 0.2s ease',
            }}
          >
            {/* File rows */}
            {files.map((entry, index) => (
              <div
                key={entry.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '14px 20px',
                  borderBottom: index < files.length - 1 ? `1px solid ${COLORS.border}` : 'none',
                  animation: 'fadeIn 0.2s ease-out',
                }}
              >
                {statusIcon(entry.status)}

                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{
                    fontSize: '14px',
                    fontWeight: 500,
                    color: entry.status === 'error' ? COLORS.error : COLORS.textPrimary,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    margin: 0,
                  }}>
                    {entry.file.name}
                  </p>
                  {entry.status === 'uploading' && typeof entry.progress === 'number' && (
                    <div style={{ marginTop: '6px', width: '100%', height: '4px', borderRadius: '2px', background: COLORS.border }}>
                      <div style={{
                        width: `${entry.progress}%`,
                        height: '100%',
                        borderRadius: '2px',
                        background: COLORS.accent,
                        transition: 'width 0.2s ease',
                      }} />
                    </div>
                  )}
                  {entry.error && (
                    <p style={{ fontSize: '12px', color: COLORS.error, margin: '2px 0 0' }}>
                      {entry.error}
                    </p>
                  )}
                </div>

                <span style={{
                  fontSize: '13px',
                  color: COLORS.textMuted,
                  flexShrink: 0,
                }}>
                  {formatFileSize(entry.file.size)}
                </span>

                {/* Remove button (only when not uploading) */}
                {(entry.status === 'pending' || entry.status === 'error') && (
                  <button
                    onClick={() => removeFile(entry.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 28,
                      height: 28,
                      border: 'none',
                      backgroundColor: 'transparent',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      flexShrink: 0,
                      transition: 'background 0.15s ease',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = COLORS.pageBg }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
                    title="Remove file"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={COLORS.textMuted} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                )}
              </div>
            ))}

            {/* Add more area (click/drop) - only in idle phase */}
            {phase === 'idle' && (
              <div
                onClick={handleClickDropZone}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '16px 20px',
                  borderTop: `1px solid ${COLORS.border}`,
                  cursor: 'pointer',
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = COLORS.pageBg }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={COLORS.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span style={{ fontSize: '14px', color: COLORS.accent, fontWeight: 500 }}>
                  Add more files
                </span>
              </div>
            )}
          </div>
        )}

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_MIME_TYPES}
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
        />

        {/* Hidden folder input */}
        <input
          ref={folderInputRef}
          type="file"
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          {...({ webkitdirectory: '', directory: '' } as any)}
          multiple
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
        />

        {/* Action buttons */}
        {phase === 'idle' && files.length > 0 && (
          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '12px',
            marginTop: '20px',
          }}>
            <button
              onClick={handleReset}
              style={{
                padding: '12px 24px',
                fontSize: '14px',
                fontWeight: 500,
                color: COLORS.textSecondary,
                backgroundColor: 'transparent',
                border: `1px solid ${COLORS.border}`,
                borderRadius: '12px',
                cursor: 'pointer',
                fontFamily: FONT,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = COLORS.pageBg }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              Clear All
            </button>
            <button
              onClick={handleUpload}
              style={{
                padding: '12px 28px',
                fontSize: '14px',
                fontWeight: 600,
                color: '#FFFFFF',
                backgroundColor: COLORS.accent,
                border: 'none',
                borderRadius: '12px',
                cursor: 'pointer',
                fontFamily: FONT,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.9' }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
            >
              Upload {files.length} file{files.length !== 1 ? 's' : ''}
            </button>
          </div>
        )}

        {/* Uploading indicator */}
        {phase === 'uploading' && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            marginTop: '20px',
            padding: '14px',
          }}>
            <div style={{
              width: 18, height: 18, borderRadius: '50%',
              border: `2px solid ${COLORS.accent}`,
              borderTopColor: 'transparent',
              animation: 'spin 0.8s linear infinite',
            }} />
            <span style={{ fontSize: '14px', color: COLORS.textSecondary, fontWeight: 500 }}>
              {(() => {
                const count = files.length || (() => {
                  const sync = Array.from(activeSyncs.values()).find(s => s.connectorType === 'manual_upload')
                  return sync?.totalItems || 0
                })()
                const sync = Array.from(activeSyncs.values()).find(s => s.connectorType === 'manual_upload')
                const pct = sync?.percentComplete ?? 0
                return count > 0
                  ? `Uploading ${count} file${count !== 1 ? 's' : ''}... ${pct > 0 ? `${pct}%` : ''}`
                  : `Upload in progress... ${pct > 0 ? `${pct}%` : ''}`
              })()}
            </span>
          </div>
        )}

        {/* Post-upload buttons */}
        {phase === 'complete' && (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '12px',
            marginTop: '24px',
          }}>
            <button
              onClick={handleReset}
              style={{
                padding: '12px 24px',
                fontSize: '14px',
                fontWeight: 500,
                color: COLORS.textSecondary,
                backgroundColor: 'transparent',
                border: `1px solid ${COLORS.border}`,
                borderRadius: '12px',
                cursor: 'pointer',
                fontFamily: FONT,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = COLORS.pageBg }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              Add More
            </button>
            <button
              onClick={() => router.push('/documents')}
              style={{
                padding: '12px 28px',
                fontSize: '14px',
                fontWeight: 600,
                color: '#FFFFFF',
                backgroundColor: COLORS.accent,
                border: 'none',
                borderRadius: '12px',
                cursor: 'pointer',
                fontFamily: FONT,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.9' }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
            >
              Go to Documents
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
