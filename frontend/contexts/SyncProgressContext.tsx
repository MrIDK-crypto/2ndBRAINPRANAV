'use client'

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'

interface SyncProgress {
  syncId: string
  connectorType: string
  status: 'connecting' | 'syncing' | 'parsing' | 'embedding' | 'complete' | 'completed' | 'error'
  stage: string
  totalItems: number
  processedItems: number
  failedItems: number
  currentItem?: string
  errorMessage?: string
  percentComplete: number
  emailWhenDone: boolean
  startedAt: number
}

interface SyncProgressContextType {
  activeSyncs: Map<string, SyncProgress>
  startSync: (syncId: string, connectorType: string, emailWhenDone?: boolean) => void
  updateSync: (syncId: string, updates: Partial<SyncProgress>) => void
  removeSync: (syncId: string) => void
  setEmailWhenDone: (syncId: string, value: boolean) => void
}

const SyncProgressContext = createContext<SyncProgressContextType | null>(null)

export function useSyncProgress() {
  const context = useContext(SyncProgressContext)
  if (!context) {
    throw new Error('useSyncProgress must be used within SyncProgressProvider')
  }
  return context
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5006/api'

export function SyncProgressProvider({ children }: { children: React.ReactNode }) {
  const [activeSyncs, setActiveSyncs] = useState<Map<string, SyncProgress>>(new Map())
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map())
  const emailSentRef = useRef<Set<string>>(new Set())

  // Send email notification
  const sendEmailNotification = useCallback(async (syncId: string, connectorType: string) => {
    if (emailSentRef.current.has(syncId)) return

    const sync = activeSyncs.get(syncId)
    if (!sync?.emailWhenDone) return

    try {
      const token = localStorage.getItem('accessToken')
      if (!token) return

      console.log('[GlobalSync] Sending email notification for', syncId)
      const response = await fetch(`${API_BASE}/sync-progress/${syncId}/notify`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      const data = await response.json()
      if (response.ok && data.success) {
        console.log('[GlobalSync] Email sent successfully')
        emailSentRef.current.add(syncId)
      } else {
        console.error('[GlobalSync] Email failed:', data.error)
      }
    } catch (err) {
      console.error('[GlobalSync] Email error:', err)
    }
  }, [activeSyncs])

  // Start tracking a sync
  const startSync = useCallback((syncId: string, connectorType: string, emailWhenDone = false) => {
    console.log('[GlobalSync] Starting sync:', syncId, connectorType)

    setActiveSyncs(prev => {
      const next = new Map(prev)
      next.set(syncId, {
        syncId,
        connectorType,
        status: 'connecting',
        stage: 'Connecting...',
        totalItems: 0,
        processedItems: 0,
        failedItems: 0,
        percentComplete: 0,
        emailWhenDone,
        startedAt: Date.now()
      })
      return next
    })

    // Setup SSE connection
    const token = localStorage.getItem('accessToken')
    if (!token) return

    const es = new EventSource(
      `${API_BASE}/sync-progress/${syncId}/stream?token=${encodeURIComponent(token)}`,
      { withCredentials: true }
    )

    const handleEvent = (e: MessageEvent) => {
      try {
        if (!e.data || e.data === 'undefined' || e.data === 'null') return
        const data = JSON.parse(e.data)
        setActiveSyncs(prev => {
          const next = new Map(prev)
          const existing = next.get(syncId)
          if (existing) {
            next.set(syncId, {
              ...existing,
              status: data.status,
              stage: data.stage || existing.stage,
              totalItems: data.total_items ?? existing.totalItems,
              processedItems: data.processed_items ?? existing.processedItems,
              failedItems: data.failed_items ?? existing.failedItems,
              currentItem: data.current_item,
              errorMessage: data.error_message,
              percentComplete: data.overall_percent ?? data.percent_complete ?? (
                data.total_items > 0
                  ? Math.round((data.processed_items / data.total_items) * 100)
                  : existing.percentComplete
              )
            })
          }
          return next
        })
      } catch (err) {
        console.error('[GlobalSync] Parse error:', err)
      }
    }

    es.addEventListener('current_state', handleEvent)
    es.addEventListener('started', handleEvent)
    es.addEventListener('progress', handleEvent)
    es.addEventListener('complete', (e: MessageEvent) => {
      handleEvent(e)
      // Send email notification
      const sync = activeSyncs.get(syncId)
      if (sync?.emailWhenDone && !emailSentRef.current.has(syncId)) {
        sendEmailNotification(syncId, connectorType)
      }
      // Auto-remove after delay
      if (pollInterval) clearInterval(pollInterval)
      if (pollTimeout) clearTimeout(pollTimeout)
      setTimeout(() => {
        es.close()
        eventSourcesRef.current.delete(syncId)
        setActiveSyncs(prev => {
          const next = new Map(prev)
          next.delete(syncId)
          return next
        })
      }, 5000)
    })
    es.addEventListener('error', handleEvent)

    eventSourcesRef.current.set(syncId, es)

    // Only start polling as fallback if SSE connection fails
    let pollInterval: NodeJS.Timeout | null = null
    let pollTimeout: NodeJS.Timeout | null = null

    es.onerror = () => {
      // SSE failed - start polling fallback (but only if not already polling)
      if (pollInterval) return
      console.log('[GlobalSync] SSE connection lost, starting polling fallback')

      const poll = async () => {
        try {
          const response = await fetch(
            `${API_BASE}/integrations/${connectorType}/sync/status`,
            { headers: { Authorization: `Bearer ${token}` } }
          )
          if (response.ok) {
            const data = await response.json()
            if (data.success && data.status) {
              setActiveSyncs(prev => {
                const next = new Map(prev)
                const existing = next.get(syncId)
                if (existing) {
                  const status = data.status.status === 'completed' ? 'complete' : data.status.status
                  next.set(syncId, {
                    ...existing,
                    status,
                    stage: data.status.current_file || data.status.status || 'Processing...',
                    totalItems: data.status.documents_found || existing.totalItems,
                    processedItems: data.status.documents_parsed || existing.processedItems,
                    percentComplete: data.status.progress || existing.percentComplete
                  })
                }
                return next
              })

              if (data.status.status === 'completed' || data.status.status === 'error') {
                if (pollInterval) clearInterval(pollInterval)
                pollInterval = null
              }
            }
          }
        } catch (err) {
          console.error('[GlobalSync] Poll error:', err)
        }
      }

      pollTimeout = setTimeout(() => {
        poll()
        pollInterval = setInterval(poll, 5000) // Poll every 5s, not 2s
      }, 3000)
    }

  }, [activeSyncs, sendEmailNotification])

  // Update sync
  const updateSync = useCallback((syncId: string, updates: Partial<SyncProgress>) => {
    setActiveSyncs(prev => {
      const next = new Map(prev)
      const existing = next.get(syncId)
      if (existing) {
        next.set(syncId, { ...existing, ...updates })
      }
      return next
    })
  }, [])

  // Remove sync
  const removeSync = useCallback((syncId: string) => {
    const es = eventSourcesRef.current.get(syncId)
    if (es) {
      es.close()
      eventSourcesRef.current.delete(syncId)
    }
    setActiveSyncs(prev => {
      const next = new Map(prev)
      next.delete(syncId)
      return next
    })
  }, [])

  // Set email preference
  const setEmailWhenDone = useCallback((syncId: string, value: boolean) => {
    setActiveSyncs(prev => {
      const next = new Map(prev)
      const existing = next.get(syncId)
      if (existing) {
        next.set(syncId, { ...existing, emailWhenDone: value })
      }
      return next
    })
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      eventSourcesRef.current.forEach(es => es.close())
    }
  }, [])

  return (
    <SyncProgressContext.Provider value={{ activeSyncs, startSync, updateSync, removeSync, setEmailWhenDone }}>
      {children}
    </SyncProgressContext.Provider>
  )
}
