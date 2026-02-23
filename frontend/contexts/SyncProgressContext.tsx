'use client'

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'

interface SyncProgress {
  syncId: string
  connectorType: string
  status: 'connecting' | 'syncing' | 'parsing' | 'extracting' | 'embedding' | 'complete' | 'completed' | 'error' | 'awaiting_selection'
  stage: string
  totalItems: number
  processedItems: number
  failedItems: number
  currentItem?: string
  errorMessage?: string
  percentComplete: number
  emailWhenDone: boolean
  startedAt: number
  documents?: Array<{ id: string; title: string; source_type: string; doc_type: string; size: number | null; date: string | null }>
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

// Track polling intervals per sync (outside component to persist across renders)
interface SyncResources {
  eventSource: EventSource | null
  pollInterval: NodeJS.Timeout | null
  pollTimeout: NodeJS.Timeout | null
}

// Storage key for persisting sync IDs
const SYNC_STORAGE_KEY = 'pendingSyncs'

export function SyncProgressProvider({ children }: { children: React.ReactNode }) {
  const [activeSyncs, setActiveSyncs] = useState<Map<string, SyncProgress>>(new Map())
  const hasRestoredRef = useRef(false)

  // Use refs to track resources per sync_id
  const syncResourcesRef = useRef<Map<string, SyncResources>>(new Map())
  const emailSentRef = useRef<Set<string>>(new Set())

  // Cleanup resources for a specific sync
  const cleanupSync = useCallback((syncId: string) => {
    const resources = syncResourcesRef.current.get(syncId)
    if (resources) {
      if (resources.eventSource) {
        resources.eventSource.close()
      }
      if (resources.pollInterval) {
        clearInterval(resources.pollInterval)
      }
      if (resources.pollTimeout) {
        clearTimeout(resources.pollTimeout)
      }
      syncResourcesRef.current.delete(syncId)
    }
  }, [])

  // Send email notification (backend handles this now)
  const sendEmailNotification = useCallback(async (syncId: string, connectorType: string) => {
    console.log('[GlobalSync] Email will be sent by backend for', syncId)
    emailSentRef.current.add(syncId)
  }, [])

  // Poll for sync status - extracted as reusable function
  const pollSyncStatus = useCallback(async (syncId: string, connectorType: string) => {
    const currentToken = localStorage.getItem('accessToken')
    if (!currentToken) return

    try {
      const response = await fetch(
        `${API_BASE}/sync-progress/${syncId}/status`,
        { headers: { Authorization: `Bearer ${currentToken}` } }
      )
      if (response.ok) {
        const data = await response.json()
        console.log(`[GlobalSync] Poll response for ${syncId}:`, { status: data.status, success: data.success, stage: data.stage })
        if (data.success) {
          setActiveSyncs(prev => {
            const next = new Map(prev)
            const existing = next.get(syncId)
            if (existing) {
              const status = data.status === 'completed' ? 'complete' : data.status
              const update: SyncProgress = {
                ...existing,
                status,
                stage: data.stage || data.current_item || 'Processing...',
                totalItems: data.total_items ?? existing.totalItems,
                processedItems: data.processed_items ?? existing.processedItems,
                percentComplete: data.overall_percent ?? data.percent_complete ?? existing.percentComplete
              }
              // Carry documents list for awaiting_selection status
              if (data.documents) {
                update.documents = data.documents
              }
              next.set(syncId, update)
            }
            return next
          })

          if (data.status === 'completed' || data.status === 'complete' || data.status === 'error') {
            const r = syncResourcesRef.current.get(syncId)
            if (r?.pollInterval) {
              clearInterval(r.pollInterval)
              r.pollInterval = null
            }

            // Check if email should be sent
            setActiveSyncs(prev => {
              const sync = prev.get(syncId)
              if (sync?.emailWhenDone && !emailSentRef.current.has(syncId)) {
                sendEmailNotification(syncId, connectorType)
              }
              return prev
            })

            // Auto-remove after delay
            setTimeout(() => {
              console.log(`[GlobalSync] Auto-removing completed sync ${syncId}`)
              cleanupSync(syncId)
              setActiveSyncs(prev => {
                const next = new Map(prev)
                next.delete(syncId)
                console.log(`[GlobalSync] Removed sync ${syncId}. Remaining:`, Array.from(next.keys()))
                return next
              })
            }, 5000)
          }
        }
      }
    } catch (err) {
      console.error('[GlobalSync] Poll error for', syncId, ':', err)
    }
  }, [cleanupSync, sendEmailNotification])

  // Start tracking a sync
  const startSync = useCallback((syncId: string, connectorType: string, emailWhenDone = false) => {
    console.log('[GlobalSync] Starting sync:', syncId, connectorType)

    // Check if this sync is already being tracked
    if (syncResourcesRef.current.has(syncId)) {
      console.log('[GlobalSync] Sync already tracked:', syncId)
      return
    }

    const token = localStorage.getItem('accessToken')
    if (!token) {
      console.error('[GlobalSync] No token available')
      return
    }

    // Initialize resources for this sync
    const resources: SyncResources = {
      eventSource: null,
      pollInterval: null,
      pollTimeout: null
    }
    syncResourcesRef.current.set(syncId, resources)

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
      console.log(`[GlobalSync] Added sync ${syncId} (${connectorType}). Total active:`, Array.from(next.keys()))
      return next
    })

    // Do immediate status check (don't rely only on SSE)
    pollSyncStatus(syncId, connectorType)

    // Setup SSE connection
    const es = new EventSource(
      `${API_BASE}/sync-progress/${syncId}/stream?token=${encodeURIComponent(token)}`,
      { withCredentials: true }
    )
    resources.eventSource = es

    const handleEvent = (e: MessageEvent) => {
      try {
        if (!e.data || e.data === 'undefined' || e.data === 'null') return
        const data = JSON.parse(e.data)
        setActiveSyncs(prev => {
          const next = new Map(prev)
          const existing = next.get(syncId)
          if (existing) {
            const update: SyncProgress = {
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
            }
            // Carry documents list for awaiting_selection status
            if (data.documents) {
              update.documents = data.documents
            }
            next.set(syncId, update)
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
      console.log(`[GlobalSync] !!!!! SSE 'complete' event received for ${syncId} !!!!!`)
      handleEvent(e)

      // Clear polling resources using the ref
      const res = syncResourcesRef.current.get(syncId)
      if (res) {
        if (res.pollInterval) {
          clearInterval(res.pollInterval)
          res.pollInterval = null
        }
        if (res.pollTimeout) {
          clearTimeout(res.pollTimeout)
          res.pollTimeout = null
        }
      }

      // Check if email should be sent
      setActiveSyncs(prev => {
        const sync = prev.get(syncId)
        if (sync?.emailWhenDone && !emailSentRef.current.has(syncId)) {
          sendEmailNotification(syncId, connectorType)
        }
        return prev
      })

      // Auto-remove after delay
      setTimeout(() => {
        console.log(`[GlobalSync] SSE complete - removing sync ${syncId}`)
        cleanupSync(syncId)
        setActiveSyncs(prev => {
          const next = new Map(prev)
          next.delete(syncId)
          console.log(`[GlobalSync] Removed sync ${syncId} after SSE complete. Remaining:`, Array.from(next.keys()))
          return next
        })
      }, 5000)
    })
    es.addEventListener('error', (e: MessageEvent) => {
      console.log(`[GlobalSync] !!!!! SSE 'error' event received for ${syncId} !!!!!`)
      handleEvent(e)
    })

    // Handle SSE connection errors - start polling fallback IMMEDIATELY
    es.onerror = () => {
      const res = syncResourcesRef.current.get(syncId)
      if (!res) return

      // Only start polling if not already polling
      if (res.pollInterval) return
      console.log('[GlobalSync] SSE connection issue for', syncId, '- starting polling fallback')

      // Start polling immediately (no delay) - SSE often fails
      pollSyncStatus(syncId, connectorType)
      res.pollInterval = setInterval(() => pollSyncStatus(syncId, connectorType), 2000)
    }

  }, [cleanupSync, sendEmailNotification, pollSyncStatus])

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
    console.log(`[GlobalSync] removeSync called for ${syncId}`)
    cleanupSync(syncId)
    setActiveSyncs(prev => {
      const next = new Map(prev)
      next.delete(syncId)
      console.log(`[GlobalSync] removeSync - Remaining syncs:`, Array.from(next.keys()))
      return next
    })
  }, [cleanupSync])

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

  // Cleanup all on unmount
  useEffect(() => {
    return () => {
      syncResourcesRef.current.forEach((resources, syncId) => {
        if (resources.eventSource) resources.eventSource.close()
        if (resources.pollInterval) clearInterval(resources.pollInterval)
        if (resources.pollTimeout) clearTimeout(resources.pollTimeout)
      })
      syncResourcesRef.current.clear()
    }
  }, [])

  // Store pollSyncStatus in ref so restore effect can use it without dependency
  const pollSyncStatusRef = useRef(pollSyncStatus)
  pollSyncStatusRef.current = pollSyncStatus

  // Save active syncs to localStorage (only after restore is done)
  useEffect(() => {
    if (!hasRestoredRef.current) return
    const syncs: Array<{syncId: string, connectorType: string, startedAt: number}> = []
    Array.from(activeSyncs.entries()).forEach(([syncId, sync]) => {
      if (sync.status !== 'complete' && sync.status !== 'completed' && sync.status !== 'error') {
        syncs.push({ syncId, connectorType: sync.connectorType, startedAt: sync.startedAt })
      }
    })
    if (syncs.length > 0) {
      localStorage.setItem(SYNC_STORAGE_KEY, JSON.stringify(syncs))
    } else {
      localStorage.removeItem(SYNC_STORAGE_KEY)
    }
  }, [activeSyncs])

  // Restore syncs from localStorage on mount (runs once)
  useEffect(() => {
    if (hasRestoredRef.current) return
    hasRestoredRef.current = true

    const stored = localStorage.getItem(SYNC_STORAGE_KEY)
    if (!stored) return

    try {
      const syncs = JSON.parse(stored) as Array<{syncId: string, connectorType: string, startedAt: number}>
      const now = Date.now()

      for (const { syncId, connectorType, startedAt } of syncs) {
        if (now - startedAt > 30 * 60 * 1000) continue // Skip stale (>30 min)
        if (syncResourcesRef.current.has(syncId)) continue

        // Add to state
        setActiveSyncs(prev => {
          const next = new Map(prev)
          next.set(syncId, {
            syncId, connectorType, status: 'syncing', stage: 'Reconnecting...',
            totalItems: 0, processedItems: 0, failedItems: 0,
            percentComplete: 0, emailWhenDone: false, startedAt
          })
          return next
        })

        // Start polling
        const resources: SyncResources = { eventSource: null, pollInterval: null, pollTimeout: null }
        syncResourcesRef.current.set(syncId, resources)
        pollSyncStatusRef.current(syncId, connectorType)
        resources.pollInterval = setInterval(() => pollSyncStatusRef.current(syncId, connectorType), 2000)
      }
    } catch (e) {
      localStorage.removeItem(SYNC_STORAGE_KEY)
    }
  }, [])

  return (
    <SyncProgressContext.Provider value={{ activeSyncs, startSync, updateSync, removeSync, setEmailWhenDone }}>
      {children}
    </SyncProgressContext.Provider>
  )
}
