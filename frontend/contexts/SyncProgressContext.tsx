'use client'

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'

// Phase-aware sync progress interface
export interface SyncProgress {
  syncId: string
  connectorType: string
  status: 'connecting' | 'fetching' | 'syncing' | 'saving' | 'extracting' | 'embedding' | 'parsing' | 'complete' | 'completed' | 'error'
  stage: string
  totalItems: number
  processedItems: number
  failedItems: number
  currentItem?: string
  errorMessage?: string
  percentComplete: number
  // Phase-aware fields from backend
  phase: string
  phaseNumber: number
  totalPhases: number
  phaseLabel: string
  phasePercent: number
  // UI state
  emailWhenDone: boolean
  dismissed: boolean
  startedAt: number
}

interface SyncProgressContextType {
  activeSyncs: Map<string, SyncProgress>
  startSync: (syncId: string, connectorType: string, emailWhenDone?: boolean) => void
  dismissSync: (syncId: string) => void
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

const STORAGE_KEY = '2ndbrain_active_syncs'
const POLL_INTERVAL = 2000 // 2 seconds

// Map backend JSON to SyncProgress interface
function mapBackendSync(data: any, existing?: Partial<SyncProgress>): SyncProgress {
  return {
    syncId: data.sync_id || existing?.syncId || '',
    connectorType: data.connector_type || existing?.connectorType || '',
    status: data.status || existing?.status || 'connecting',
    stage: data.stage || data.phase_label || existing?.stage || 'Connecting...',
    totalItems: data.total_items ?? existing?.totalItems ?? 0,
    processedItems: data.processed_items ?? existing?.processedItems ?? 0,
    failedItems: data.failed_items ?? existing?.failedItems ?? 0,
    currentItem: data.current_item || existing?.currentItem,
    errorMessage: data.error_message || existing?.errorMessage,
    percentComplete: data.overall_percent ?? data.percent_complete ?? existing?.percentComplete ?? 0,
    phase: data.phase || existing?.phase || 'connecting',
    phaseNumber: data.phase_number ?? existing?.phaseNumber ?? 0,
    totalPhases: data.total_phases ?? existing?.totalPhases ?? 3,
    phaseLabel: data.phase_label || existing?.phaseLabel || 'Connecting...',
    phasePercent: data.phase_percent ?? existing?.phasePercent ?? 0,
    emailWhenDone: existing?.emailWhenDone ?? false,
    dismissed: existing?.dismissed ?? false,
    startedAt: existing?.startedAt ?? Date.now(),
  }
}

// localStorage helpers
function saveToStorage(syncs: Map<string, SyncProgress>) {
  try {
    const data: Record<string, { syncId: string; connectorType: string; startedAt: number }> = {}
    syncs.forEach((sync, id) => {
      if (sync.status !== 'complete' && sync.status !== 'completed' && sync.status !== 'error' && !sync.dismissed) {
        data[id] = { syncId: sync.syncId, connectorType: sync.connectorType, startedAt: sync.startedAt }
      }
    })
    if (Object.keys(data).length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch { /* ignore storage errors */ }
}

function loadFromStorage(): Record<string, { syncId: string; connectorType: string; startedAt: number }> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return {}
}

export function SyncProgressProvider({ children }: { children: React.ReactNode }) {
  const [activeSyncs, setActiveSyncs] = useState<Map<string, SyncProgress>>(new Map())
  const pollTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map())
  const mountedRef = useRef(true)

  // Poll a single sync via GET /api/syncs/{syncId}
  const pollSync = useCallback((syncId: string) => {
    const poll = async () => {
      if (!mountedRef.current) return

      try {
        const token = localStorage.getItem('accessToken')
        if (!token) return

        const response = await fetch(`${API_BASE}/syncs/${syncId}`, {
          headers: { Authorization: `Bearer ${token}` }
        })

        if (response.status === 404) {
          // Sync cleaned up from backend - mark as complete
          setActiveSyncs(prev => {
            const next = new Map(prev)
            const existing = next.get(syncId)
            if (existing && existing.status !== 'complete' && existing.status !== 'completed') {
              next.set(syncId, { ...existing, status: 'complete', stage: 'Sync complete', percentComplete: 100, phase: 'complete', phaseLabel: 'Sync complete', phaseNumber: 3 })
            }
            return next
          })
          // Stop polling
          const timer = pollTimersRef.current.get(syncId)
          if (timer) clearInterval(timer)
          pollTimersRef.current.delete(syncId)
          return
        }

        if (!response.ok) return

        const json = await response.json()
        if (!json.success || !json.sync) return

        const data = json.sync

        setActiveSyncs(prev => {
          const next = new Map(prev)
          const existing = next.get(syncId)
          const updated = mapBackendSync(data, existing)
          next.set(syncId, updated)

          // Persist to localStorage
          saveToStorage(next)

          return next
        })

        // Stop polling if sync is done
        if (data.status === 'complete' || data.status === 'completed' || data.status === 'error') {
          const timer = pollTimersRef.current.get(syncId)
          if (timer) clearInterval(timer)
          pollTimersRef.current.delete(syncId)
        }
      } catch (err) {
        console.error('[SyncContext] Poll error:', err)
      }
    }

    // Poll immediately, then every POLL_INTERVAL
    poll()
    const timer = setInterval(poll, POLL_INTERVAL)
    pollTimersRef.current.set(syncId, timer)
  }, [])

  // Start tracking a sync
  const startSync = useCallback((syncId: string, connectorType: string, emailWhenDone = false) => {
    console.log('[SyncContext] Starting sync:', syncId, connectorType)

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
        phase: 'connecting',
        phaseNumber: 0,
        totalPhases: 3,
        phaseLabel: 'Connecting to service',
        phasePercent: 0,
        emailWhenDone,
        dismissed: false,
        startedAt: Date.now()
      })
      saveToStorage(next)
      return next
    })

    // Start polling
    pollSync(syncId)
  }, [pollSync])

  // Dismiss a completed/errored sync (user clicked X)
  const dismissSync = useCallback((syncId: string) => {
    const timer = pollTimersRef.current.get(syncId)
    if (timer) {
      clearInterval(timer)
      pollTimersRef.current.delete(syncId)
    }
    setActiveSyncs(prev => {
      const next = new Map(prev)
      next.delete(syncId)
      saveToStorage(next)
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

    // Subscribe email on backend
    if (value) {
      const token = localStorage.getItem('accessToken')
      if (token) {
        fetch(`${API_BASE}/sync-progress/${syncId}/subscribe-email`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
        }).catch(err => console.error('[SyncContext] Email subscribe error:', err))
      }
    }
  }, [])

  // Recovery on mount: check backend for active syncs + localStorage
  useEffect(() => {
    mountedRef.current = true

    const recover = async () => {
      const token = localStorage.getItem('accessToken')
      if (!token) return

      try {
        // 1. Check backend for active syncs
        const response = await fetch(`${API_BASE}/syncs/active`, {
          headers: { Authorization: `Bearer ${token}` }
        })

        if (response.ok) {
          const json = await response.json()
          if (json.success && json.syncs && json.syncs.length > 0) {
            const recovered = new Map<string, SyncProgress>()
            for (const s of json.syncs) {
              const sync = mapBackendSync(s)
              recovered.set(s.sync_id, sync)
              // Start polling for active syncs
              if (s.status !== 'complete' && s.status !== 'completed' && s.status !== 'error') {
                pollSync(s.sync_id)
              }
            }
            setActiveSyncs(recovered)
            saveToStorage(recovered)
            return
          }
        }

        // 2. Fallback: check localStorage for syncs that may still be running
        const stored = loadFromStorage()
        for (const [syncId, info] of Object.entries(stored)) {
          // Only recover syncs less than 1 hour old
          if (Date.now() - info.startedAt < 3600000) {
            pollSync(syncId)
          }
        }
      } catch (err) {
        console.error('[SyncContext] Recovery error:', err)
      }
    }

    recover()

    return () => {
      mountedRef.current = false
      // Clean up all poll timers
      pollTimersRef.current.forEach(timer => clearInterval(timer))
      pollTimersRef.current.clear()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <SyncProgressContext.Provider value={{ activeSyncs, startSync, dismissSync, setEmailWhenDone }}>
      {children}
    </SyncProgressContext.Provider>
  )
}
