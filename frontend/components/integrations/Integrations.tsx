'use client'

import React, { useState, useEffect, useRef } from 'react'
import Sidebar from '../shared/Sidebar'
import Image from 'next/image'
import axios from 'axios'
import SyncProgressModal from './SyncProgressModal'
import EmailForwardingCard from './EmailForwardingCard'
import { useAuth } from '@/contexts/AuthContext'
import { useSyncProgress } from '@/contexts/SyncProgressContext'
import { FileText, Clock, FolderGit2, Mail, CheckCircle2 } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5003/api'

interface Integration {
  id: string
  name: string
  logo: string
  description: string
  category: string
  connected: boolean
  isOAuth?: boolean
}

interface SlackChannel {
  id: string
  name: string
  is_private: boolean
  is_member: boolean
  member_count: number
  selected: boolean
}

// Channel Selection Modal Component
const ChannelSelectionModal = ({
  isOpen,
  onClose,
  channels,
  onSave,
  isLoading
}: {
  isOpen: boolean
  onClose: () => void
  channels: SlackChannel[]
  onSave: (selectedIds: string[]) => void
  isLoading: boolean
}) => {
  const [selectedChannels, setSelectedChannels] = useState<Set<string>>(new Set())

  useEffect(() => {
    // Initialize with already selected channels
    const selected = new Set(channels.filter(c => c.selected).map(c => c.id))
    setSelectedChannels(selected)
  }, [channels])

  const toggleChannel = (id: string) => {
    setSelectedChannels(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  const selectAll = () => {
    setSelectedChannels(new Set(channels.map(c => c.id)))
  }

  const selectNone = () => {
    setSelectedChannels(new Set())
  }

  if (!isOpen) return null

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
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          padding: '32px',
          maxWidth: '500px',
          width: '90%',
          maxHeight: '80vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        }}
        onClick={e => e.stopPropagation()}
      >
        <h2 style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontSize: '24px',
          fontWeight: 600,
          marginBottom: '8px',
          color: '#111827'
        }}>
          Select Slack Channels
        </h2>
        <p style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          color: '#71717A',
          marginBottom: '16px'
        }}>
          Choose which channels to sync to your knowledge base. Only messages from selected channels will be imported.
        </p>

        {/* Quick select buttons */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <button
            onClick={selectAll}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #D4D4D8',
              backgroundColor: '#fff',
              fontSize: '12px',
              cursor: 'pointer'
            }}
          >
            Select All
          </button>
          <button
            onClick={selectNone}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #D4D4D8',
              backgroundColor: '#fff',
              fontSize: '12px',
              cursor: 'pointer'
            }}
          >
            Select None
          </button>
          <span style={{
            marginLeft: 'auto',
            fontSize: '12px',
            color: '#71717A',
            alignSelf: 'center'
          }}>
            {selectedChannels.size} of {channels.length} selected
          </span>
        </div>

        {/* Channel list */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          border: '1px solid #D4D4D8',
          borderRadius: '8px',
          backgroundColor: '#fff'
        }}>
          {channels.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#71717A' }}>
              {isLoading ? 'Loading channels...' : 'No channels found'}
            </div>
          ) : (
            channels.map(channel => (
              <div
                key={channel.id}
                onClick={() => toggleChannel(channel.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '12px 16px',
                  borderBottom: '1px solid #E4E4E7',
                  cursor: 'pointer',
                  backgroundColor: selectedChannels.has(channel.id) ? '#E0F2FE' : 'transparent'
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedChannels.has(channel.id)}
                  onChange={() => {}}
                  style={{ marginRight: '12px', cursor: 'pointer' }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '14px',
                    fontWeight: 500,
                    color: '#18181B'
                  }}>
                    {channel.is_private ? '🔒' : '#'} {channel.name}
                  </div>
                  <div style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '12px',
                    color: '#71717A'
                  }}>
                    {channel.member_count} members
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Action buttons */}
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '12px',
          marginTop: '24px'
        }}>
          <button
            onClick={onClose}
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
            onClick={() => onSave(Array.from(selectedChannels))}
            disabled={selectedChannels.size === 0}
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: selectedChannels.size === 0 ? '#9ca3af' : '#2563EB',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 500,
              cursor: selectedChannels.size === 0 ? 'not-allowed' : 'pointer'
            }}
          >
            Save & Sync ({selectedChannels.size} channels)
          </button>
        </div>
      </div>
    </div>
  )
}

// Sync Progress Modal Component
interface SyncProgress {
  integration: string
  status: 'starting' | 'syncing' | 'parsing' | 'embedding' | 'completed' | 'error'
  progress: number
  documentsFound: number
  documentsParsed: number
  documentsEmbedded: number
  currentFile?: string
  error?: string
  startTime?: number
}

// Helper to save/load sync state from localStorage
const SYNC_STATE_KEY = '2ndbrain_sync_state'
const CONNECTED_INTEGRATIONS_KEY = '2ndbrain_connected_integrations'

const saveSyncState = (state: {
  integration: string;
  startTime?: number;
  status?: string;
  progress?: number;
  documentsFound?: number;
  documentsParsed?: number;
  documentsEmbedded?: number;
  completedAt?: number;
} | null) => {
  if (typeof window === 'undefined') return
  if (state) {
    localStorage.setItem(SYNC_STATE_KEY, JSON.stringify(state))
  } else {
    localStorage.removeItem(SYNC_STATE_KEY)
  }
}

const loadSyncState = (): {
  integration: string;
  startTime?: number;
  status?: string;
  progress?: number;
  documentsFound?: number;
  documentsParsed?: number;
  documentsEmbedded?: number;
  completedAt?: number;
} | null => {
  if (typeof window === 'undefined') return null
  try {
    const saved = localStorage.getItem(SYNC_STATE_KEY)
    return saved ? JSON.parse(saved) : null
  } catch {
    return null
  }
}

// Save/load connected integrations to localStorage for persistence
const saveConnectedIntegrations = (connectedIds: string[]) => {
  if (typeof window === 'undefined') return
  localStorage.setItem(CONNECTED_INTEGRATIONS_KEY, JSON.stringify(connectedIds))
}

const loadConnectedIntegrations = (): string[] => {
  if (typeof window === 'undefined') return []
  try {
    const saved = localStorage.getItem(CONNECTED_INTEGRATIONS_KEY)
    return saved ? JSON.parse(saved) : []
  } catch {
    return []
  }
}

// Animated counter component
const AnimatedCounter = ({ value, label }: { value: number; label: string }) => {
  const [displayValue, setDisplayValue] = useState(value)
  const [isAnimating, setIsAnimating] = useState(false)

  useEffect(() => {
    if (value !== displayValue) {
      setIsAnimating(true)
      // Animate the counter
      const duration = 300
      const startValue = displayValue
      const startTime = Date.now()

      const animate = () => {
        const elapsed = Date.now() - startTime
        const progress = Math.min(elapsed / duration, 1)
        const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
        const current = Math.round(startValue + (value - startValue) * eased)
        setDisplayValue(current)

        if (progress < 1) {
          requestAnimationFrame(animate)
        } else {
          setIsAnimating(false)
        }
      }
      requestAnimationFrame(animate)
    }
  }, [value, displayValue])

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        fontFamily: '"Work Sans", sans-serif',
        fontSize: '20px',
        fontWeight: 600,
        color: '#18181B',
        transform: isAnimating ? 'scale(1.1)' : 'scale(1)',
        transition: 'transform 0.15s ease-out'
      }}>
        {displayValue}
      </div>
      <div style={{
        fontFamily: '"Work Sans", sans-serif',
        fontSize: '11px',
        color: '#9CA3AF',
        textTransform: 'uppercase',
        letterSpacing: '0.5px'
      }}>
        {label}
      </div>
    </div>
  )
}

const PollingProgressModal = ({
  isOpen,
  onClose,
  progress,
  onMinimize,
  onCancel,
  syncStartTime
}: {
  isOpen: boolean
  onClose: () => void
  progress: SyncProgress | null
  onMinimize?: () => void
  onCancel?: () => void
  syncStartTime?: number
}) => {
  // Track progress history for better time estimation
  const [progressHistory, setProgressHistory] = useState<{time: number, progress: number}[]>([])
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null)
  const [emailWhenComplete, setEmailWhenComplete] = useState(false)

  // Update progress history when progress changes
  useEffect(() => {
    if (progress && progress.progress > 0) {
      const now = Date.now()
      setProgressHistory(prev => {
        const newHistory = [...prev, { time: now, progress: progress.progress }]
        // Keep last 10 data points for smoothing
        return newHistory.slice(-10)
      })
    }
  }, [progress?.progress])

  // Calculate estimated time with phase-aware timing
  // Progress phases (backend):
  // 0-40%: syncing (fast - fetching files)
  // 40-70%: parsing (medium - saving to DB)
  // 70-95%: embedding (SLOW - GPT extraction + Pinecone)
  // 95-100%: finishing
  useEffect(() => {
    if (!progress || progress.status === 'completed' || progress.status === 'error') {
      setEstimatedSeconds(null)
      return
    }

    // Phase-specific time multipliers (seconds per 1% progress)
    const getPhaseMultiplier = (currentProgress: number, status: string): number => {
      // Embedding phase is much slower due to GPT extraction calls
      if (status === 'embedding' || currentProgress >= 70) {
        // Each percent in embedding phase takes ~5-10 seconds (GPT + Pinecone)
        return 6.0
      }
      // Parsing phase is moderate
      if (status === 'parsing' || currentProgress >= 40) {
        return 1.5
      }
      // Syncing phase is fast
      return 0.5
    }

    // Early estimate for starting
    if (progress.status === 'starting' || progress.progress < 3) {
      // Better initial estimate based on typical full sync
      const docsFound = progress.documentsFound || 10
      // Estimate: syncing 40% fast + parsing 30% medium + embedding 25% slow
      const estimatedTotal = (40 * 0.5) + (30 * 1.5) + (25 * 6.0 * (docsFound / 10))
      setEstimatedSeconds(Math.max(estimatedTotal, 60))
      return
    }

    const currentProgress = progress.progress || 0
    const remaining = 100 - currentProgress

    // Calculate remaining time based on phase-aware estimates
    let estimatedRemaining = 0

    if (currentProgress < 40) {
      // In syncing phase
      const syncRemaining = 40 - currentProgress
      const parseRemaining = 30
      const embedRemaining = 25
      const docsFound = progress.documentsFound || 10
      estimatedRemaining = (syncRemaining * 0.5) + (parseRemaining * 1.5) + (embedRemaining * 6.0 * Math.max(1, docsFound / 10))
    } else if (currentProgress < 70) {
      // In parsing phase
      const parseRemaining = 70 - currentProgress
      const embedRemaining = 25
      const docsFound = progress.documentsFound || 10
      estimatedRemaining = (parseRemaining * 1.5) + (embedRemaining * 6.0 * Math.max(1, docsFound / 10))
    } else if (currentProgress < 95) {
      // In embedding phase (slowest)
      const embedRemaining = 95 - currentProgress
      const docsFound = progress.documentsFound || 10
      // GPT extraction is about 3-5 seconds per doc, embedding is 1-2 seconds per doc
      estimatedRemaining = embedRemaining * 6.0 * Math.max(1, docsFound / 10)
    } else {
      // Finishing up
      estimatedRemaining = (100 - currentProgress) * 0.5
    }

    // Use history for rate-based refinement if available
    if (progressHistory.length >= 3) {
      const oldest = progressHistory[0]
      const newest = progressHistory[progressHistory.length - 1]
      const timeDiff = (newest.time - oldest.time) / 1000
      const progressDiff = newest.progress - oldest.progress

      if (timeDiff > 2 && progressDiff > 0) {
        const observedRate = progressDiff / timeDiff
        const phaseMultiplier = getPhaseMultiplier(currentProgress, progress.status)
        const adjustedRate = observedRate / phaseMultiplier

        // Weight observed rate against phase-based estimate
        if (adjustedRate > 0) {
          const rateBasedEstimate = remaining / adjustedRate
          // Blend: 60% phase-based, 40% observed rate
          estimatedRemaining = estimatedRemaining * 0.6 + rateBasedEstimate * 0.4
        }
      }
    }

    // Smooth transitions to avoid jumpy numbers
    if (estimatedRemaining > 0 && estimatedRemaining < 86400) {
      setEstimatedSeconds(prev => {
        if (prev === null) return estimatedRemaining
        return prev * 0.7 + estimatedRemaining * 0.3
      })
    }
  }, [progressHistory, progress])

  if (!isOpen || !progress) return null

  const getStatusText = () => {
    switch (progress.status) {
      case 'starting':
        return 'Connecting...'
      case 'syncing':
        return 'Fetching files...'
      case 'parsing':
        return 'Processing documents...'
      case 'embedding':
        return 'Indexing for search...'
      case 'completed':
        return 'All done!'
      case 'error':
        return progress.error || 'Something went wrong'
      default:
        return 'Processing...'
    }
  }

  // Format estimated time
  const getEstimatedTimeText = () => {
    if (estimatedSeconds === null) {
      return 'Estimating...'
    }

    const seconds = Math.round(estimatedSeconds)

    if (seconds < 10) {
      return 'Almost done...'
    } else if (seconds < 60) {
      return `~${seconds}s remaining`
    } else if (seconds < 3600) {
      const mins = Math.ceil(seconds / 60)
      return `~${mins} min remaining`
    } else {
      const hours = Math.round(seconds / 3600 * 10) / 10
      return `~${hours}h remaining`
    }
  }

  const isInProgress = progress.status !== 'completed' && progress.status !== 'error'
  const integrationName = progress.integration.charAt(0).toUpperCase() + progress.integration.slice(1)

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        backdropFilter: 'blur(4px)'
      }}
      onClick={isInProgress ? undefined : onClose}
    >
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '20px',
          padding: '28px',
          maxWidth: '380px',
          width: '90%',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          position: 'relative',
          margin: 'auto'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Close/Minimize Button */}
        {isInProgress && (
          <button
            onClick={onMinimize || onClose}
            style={{
              position: 'absolute',
              top: '16px',
              right: '16px',
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              border: 'none',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#9CA3AF',
              transition: 'all 0.2s'
            }}
            onMouseEnter={e => {
              e.currentTarget.style.backgroundColor = '#F3F4F6'
              e.currentTarget.style.color = '#6B7280'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.backgroundColor = 'transparent'
              e.currentTarget.style.color = '#9CA3AF'
            }}
            title="Close - sync will continue in background"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M1 1l12 12M13 1L1 13" />
            </svg>
          </button>
        )}

        {/* Header with Icon */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '16px',
              backgroundColor: progress.status === 'completed' ? '#3B82F6' :
                               progress.status === 'error' ? '#64748B' : '#2563EB',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
              boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)'
            }}
          >
            {progress.status === 'completed' ? (
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : progress.status === 'error' ? (
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            ) : (
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                style={{ animation: 'spin 1s linear infinite' }}
              >
                <path d="M21 12a9 9 0 11-6.219-8.56" />
              </svg>
            )}
          </div>

          <h2 style={{
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '18px',
            fontWeight: 600,
            color: '#18181B',
            margin: '0 0 4px 0'
          }}>
            {progress.status === 'completed' ? 'Sync Complete' :
             progress.status === 'error' ? 'Sync Failed' :
             `Syncing ${integrationName}`}
          </h2>
          <p style={{
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '13px',
            color: '#71717A',
            margin: 0
          }}>
            {getStatusText()}
          </p>
        </div>

        {/* Progress Section */}
        {isInProgress && (
          <>
            {/* Progress Bar */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '8px'
              }}>
                <span style={{
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '12px',
                  color: '#9CA3AF',
                  fontWeight: 500
                }}>
                  {Math.round(progress.progress)}% complete
                </span>
                <span style={{
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '12px',
                  color: '#9CA3AF'
                }}>
                  {getEstimatedTimeText()}
                </span>
              </div>
              <div style={{
                width: '100%',
                height: '6px',
                backgroundColor: '#E5E7EB',
                borderRadius: '3px',
                overflow: 'hidden'
              }}>
                <div
                  style={{
                    width: `${progress.progress}%`,
                    height: '100%',
                    backgroundColor: '#2563EB',
                    borderRadius: '3px',
                    transition: 'width 0.5s ease-out'
                  }}
                />
              </div>
            </div>

            {/* Stats Row */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-around',
              padding: '16px 0',
              borderTop: '1px solid #F3F4F6',
              borderBottom: '1px solid #F3F4F6',
              marginBottom: '16px'
            }}>
              <AnimatedCounter value={progress.documentsFound} label="Found" />
              <div style={{ width: '1px', backgroundColor: '#F3F4F6' }} />
              <AnimatedCounter value={progress.documentsParsed} label="Processed" />
              <div style={{ width: '1px', backgroundColor: '#F3F4F6' }} />
              <AnimatedCounter value={progress.documentsEmbedded} label="Indexed" />
            </div>

            {/* Background sync info */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 14px',
              backgroundColor: '#F0FDF4',
              borderRadius: '10px',
              border: '1px solid #BFDBFE',
              marginBottom: '12px'
            }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="#3B82F6" strokeWidth="1.5" />
                <path d="M8 5v3M8 10h.01" stroke="#3B82F6" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <span style={{
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '12px',
                color: '#1E40AF',
                lineHeight: '1.4'
              }}>
                You can close this window. Sync continues in the background.
              </span>
            </div>

            {/* Email Notification Option */}
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '12px 14px',
              backgroundColor: emailWhenComplete ? '#EFF6FF' : '#F9FAFB',
              borderRadius: '10px',
              border: emailWhenComplete ? '1px solid #3B82F6' : '1px solid #E5E7EB',
              marginBottom: '12px',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}>
              <input
                type="checkbox"
                checked={emailWhenComplete}
                onChange={(e) => setEmailWhenComplete(e.target.checked)}
                style={{
                  width: 18,
                  height: 18,
                  accentColor: '#3B82F6',
                  cursor: 'pointer'
                }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
                <Mail size={16} color={emailWhenComplete ? '#3B82F6' : '#6B7280'} />
                <span style={{
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '13px',
                  color: emailWhenComplete ? '#1D4ED8' : '#374151',
                  fontWeight: 500
                }}>
                  Email me when complete
                </span>
              </div>
              {emailWhenComplete && (
                <CheckCircle2 size={16} color="#3B82F6" />
              )}
            </label>

            {/* Stop Sync Button */}
            <button
              onClick={onCancel || onClose}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '10px',
                border: '1px solid #64748B',
                backgroundColor: '#FEFEFE',
                color: '#64748B',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = '#F1F5F9'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor = '#FEFEFE'
              }}
            >
              Stop Sync
            </button>
          </>
        )}

        {/* Completed State */}
        {progress.status === 'completed' && (
          <>
            <div style={{
              display: 'flex',
              justifyContent: 'space-around',
              padding: '20px 0',
              marginBottom: '20px'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '24px',
                  fontWeight: 600,
                  color: '#3B82F6'
                }}>
                  {progress.documentsFound}
                </div>
                <div style={{
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '12px',
                  color: '#6B7280'
                }}>
                  documents synced
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '10px',
                border: 'none',
                backgroundColor: '#3B82F6',
                color: '#fff',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = '#2563EB'}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = '#3B82F6'}
            >
              Done
            </button>
          </>
        )}

        {/* Error State */}
        {progress.status === 'error' && (
          <>
            <div style={{
              padding: '16px',
              backgroundColor: '#FEF2F2',
              borderRadius: '10px',
              marginBottom: '20px'
            }}>
              <p style={{
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '13px',
                color: '#991B1B',
                margin: 0,
                lineHeight: '1.5'
              }}>
                {progress.error || 'An unexpected error occurred. Please try again.'}
              </p>
            </div>
            <button
              onClick={onClose}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '10px',
                border: 'none',
                backgroundColor: '#6B7280',
                color: '#fff',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = '#4B5563'}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = '#6B7280'}
            >
              Close
            </button>
          </>
        )}
      </div>

      {/* CSS animation for spinner */}
      <style jsx global>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

// Slack Token Input Modal Component
const SlackTokenModal = ({
  isOpen,
  onClose,
  onSubmit,
  isLoading
}: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (token: string) => void
  isLoading: boolean
}) => {
  const [token, setToken] = useState('')

  if (!isOpen) return null

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
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          padding: '32px',
          maxWidth: '500px',
          width: '90%',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        }}
        onClick={e => e.stopPropagation()}
      >
        <h2 style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontSize: '20px',
          fontWeight: 600,
          marginBottom: '8px',
          color: '#111827'
        }}>
          Connect Slack
        </h2>

        <p style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          color: '#71717A',
          marginBottom: '20px'
        }}>
          Enter your Slack Bot User OAuth Token. You can find this in your Slack App under
          <strong> OAuth & Permissions → Bot User OAuth Token</strong>.
        </p>

        <div style={{ marginBottom: '20px' }}>
          <label style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 500,
            display: 'block',
            marginBottom: '8px'
          }}>
            Bot User OAuth Token
          </label>
          <input
            type="password"
            value={token}
            onChange={e => setToken(e.target.value)}
            placeholder="xoxb-..."
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              fontSize: '14px',
              fontFamily: 'monospace'
            }}
          />
        </div>

        <div style={{
          padding: '12px',
          backgroundColor: '#FEF3C7',
          borderRadius: '8px',
          marginBottom: '20px'
        }}>
          <p style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '13px',
            color: '#92400E',
            margin: 0
          }}>
            <strong>Required scopes:</strong> channels:read, channels:history, groups:read, groups:history, users:read, team:read
          </p>
        </div>

        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '12px'
        }}>
          <button
            onClick={onClose}
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
            onClick={() => onSubmit(token)}
            disabled={!token.startsWith('xoxb-') || isLoading}
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: !token.startsWith('xoxb-') ? '#9ca3af' : '#2563EB',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 500,
              cursor: !token.startsWith('xoxb-') ? 'not-allowed' : 'pointer'
            }}
          >
            {isLoading ? 'Connecting...' : 'Connect'}
          </button>
        </div>
      </div>
    </div>
  )
}

// PubMed Configuration Modal Component
const PubMedConfigModal = ({
  isOpen,
  onClose,
  onSubmit,
  isLoading
}: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (config: {
    searchQuery: string
    maxResults: number
    dateRangeYears: number
    apiKey: string
  }) => void
  isLoading: boolean
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [maxResults, setMaxResults] = useState(100)
  const [dateRangeYears, setDateRangeYears] = useState(5)
  const [apiKey, setApiKey] = useState('')

  if (!isOpen) return null

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
      onClick={onClose}
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
        <h2 style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontSize: '20px',
          fontWeight: 600,
          marginBottom: '8px',
          color: '#111827'
        }}>
          Configure PubMed Search
        </h2>

        <p style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          color: '#71717A',
          marginBottom: '20px'
        }}>
          Search biomedical literature from NCBI PubMed. Enter a search query to find and sync research papers.
        </p>

        {/* Search Query */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 500,
            display: 'block',
            marginBottom: '8px'
          }}>
            Search Query *
          </label>
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder='e.g., "NICU[Title] AND outcomes", "diabetes treatment 2020:2024[pdat]"'
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              fontSize: '14px',
              fontFamily: 'Inter, sans-serif'
            }}
          />
          <p style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '12px',
            color: '#71717A',
            marginTop: '4px'
          }}>
            Use PubMed search syntax. <a href="https://pubmed.ncbi.nlm.nih.gov/help/" target="_blank" rel="noopener" style={{color: '#3B82F6', textDecoration: 'underline'}}>Learn more</a>
          </p>
        </div>

        {/* Max Results */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 500,
            display: 'block',
            marginBottom: '8px'
          }}>
            Maximum Results
          </label>
          <input
            type="number"
            value={maxResults}
            onChange={e => setMaxResults(Math.max(1, Math.min(500, parseInt(e.target.value) || 100)))}
            min="1"
            max="500"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              fontSize: '14px',
              fontFamily: 'Inter, sans-serif'
            }}
          />
          <p style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '12px',
            color: '#71717A',
            marginTop: '4px'
          }}>
            Maximum papers to fetch (1-500, default: 100)
          </p>
        </div>

        {/* Date Range */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 500,
            display: 'block',
            marginBottom: '8px'
          }}>
            Date Range (Years)
          </label>
          <select
            value={dateRangeYears}
            onChange={e => setDateRangeYears(parseInt(e.target.value))}
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              fontSize: '14px',
              fontFamily: 'Inter, sans-serif'
            }}
          >
            <option value="0">All time</option>
            <option value="1">Last year</option>
            <option value="2">Last 2 years</option>
            <option value="5">Last 5 years (default)</option>
            <option value="10">Last 10 years</option>
          </select>
        </div>

        {/* API Key (Optional) */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 500,
            display: 'block',
            marginBottom: '8px'
          }}>
            NCBI API Key (Optional)
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="Optional - increases rate limit to 10 req/sec"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              fontSize: '14px',
              fontFamily: 'monospace'
            }}
          />
          <p style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '12px',
            color: '#71717A',
            marginTop: '4px'
          }}>
            Get an API key from <a href="https://www.ncbi.nlm.nih.gov/account/settings/" target="_blank" rel="noopener" style={{color: '#3B82F6', textDecoration: 'underline'}}>NCBI Account Settings</a>
          </p>
        </div>

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
            <strong>Note:</strong> Only papers with abstracts will be synced. Full-text articles require institutional access.
          </p>
        </div>

        {/* Buttons */}
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '12px'
        }}>
          <button
            onClick={onClose}
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
            onClick={() => onSubmit({
              searchQuery,
              maxResults,
              dateRangeYears,
              apiKey
            })}
            disabled={!searchQuery.trim() || isLoading}
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: !searchQuery.trim() ? '#9ca3af' : '#3B82F6',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 500,
              cursor: !searchQuery.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            {isLoading ? 'Configuring...' : 'Search & Sync'}
          </button>
        </div>
      </div>
    </div>
  )
}

// WebScraper Configuration Modal Component
const WebScraperConfigModal = ({
  isOpen,
  onClose,
  onSubmit,
  isLoading,
  existingUrl
}: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (config: {
    startUrl: string
    priorityPaths: string[]
  }) => void
  isLoading: boolean
  existingUrl?: string
}) => {
  const [startUrl, setStartUrl] = useState(existingUrl || '')
  const [priorityPaths, setPriorityPaths] = useState('')
  const [urlError, setUrlError] = useState<string | null>(null)

  // Update startUrl when existingUrl changes (for editing)
  React.useEffect(() => {
    if (existingUrl) {
      setStartUrl(existingUrl)
    }
  }, [existingUrl])

  // Validate URL
  const validateUrl = (url: string): boolean => {
    if (!url.trim()) {
      setUrlError('URL is required')
      return false
    }

    // Add https if missing
    let testUrl = url.trim()
    if (!testUrl.startsWith('http://') && !testUrl.startsWith('https://')) {
      testUrl = 'https://' + testUrl
    }

    try {
      const parsed = new URL(testUrl)
      if (!parsed.hostname || !parsed.hostname.includes('.')) {
        setUrlError('Please enter a valid domain (e.g., example.com)')
        return false
      }
      setUrlError(null)
      return true
    } catch {
      setUrlError('Please enter a valid URL')
      return false
    }
  }

  const handleSubmit = () => {
    if (!validateUrl(startUrl)) return

    const paths = priorityPaths
      .split(',')
      .map(p => p.trim())
      .filter(p => p.length > 0)

    onSubmit({
      startUrl: startUrl.trim(),
      priorityPaths: paths,
    })
  }

  if (!isOpen) return null

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
      onClick={onClose}
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
        <h2 style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontSize: '20px',
          fontWeight: 600,
          marginBottom: '8px',
          color: '#111827'
        }}>
          Configure Website Scraper
        </h2>

        <p style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          color: '#71717A',
          marginBottom: '20px'
        }}>
          Crawl websites to extract protocols, documentation, and resources. Perfect for lab websites!
        </p>

        {/* Start URL */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 500,
            display: 'block',
            marginBottom: '8px'
          }}>
            Website URL *
          </label>
          <input
            type="text"
            value={startUrl}
            onChange={e => {
              setStartUrl(e.target.value)
              if (urlError) setUrlError(null)
            }}
            onBlur={() => startUrl && validateUrl(startUrl)}
            placeholder="https://example.com or example.com"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: `1px solid ${urlError ? '#64748B' : '#D4D4D8'}`,
              fontSize: '14px',
              fontFamily: 'Inter, sans-serif',
              outline: 'none'
            }}
          />
          {urlError && (
            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '12px',
              color: '#64748B',
              marginTop: '4px'
            }}>
              {urlError}
            </p>
          )}
        </div>

        {/* Priority Paths */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 500,
            display: 'block',
            marginBottom: '8px'
          }}>
            Priority Paths (Optional)
          </label>
          <input
            type="text"
            value={priorityPaths}
            onChange={e => setPriorityPaths(e.target.value)}
            placeholder="/resources/, /protocols/"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid #D4D4D8',
              fontSize: '14px',
              fontFamily: 'Inter, sans-serif'
            }}
          />
          <p style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '12px',
            color: '#71717A',
            marginTop: '4px'
          }}>
            Comma-separated paths to crawl first (e.g., /resources/, /protocols/)
          </p>
        </div>

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
            margin: 0,
            lineHeight: '1.5'
          }}>
            <strong>How it works:</strong><br />
            - Automatically crawls all subpages (up to 50)<br />
            - Extracts text, images, tables, and icons<br />
            - Same-domain only, sitemap-aware<br />
            - Content appears on your Documents page
          </p>
        </div>

        {/* Buttons */}
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '12px'
        }}>
          <button
            onClick={onClose}
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
            disabled={!startUrl.trim() || isLoading || !!urlError}
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: (!startUrl.trim() || !!urlError) ? '#9ca3af' : '#3B82F6',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 500,
              cursor: !startUrl.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            {isLoading ? 'Configuring...' : 'Start Crawling'}
          </button>
        </div>
      </div>
    </div>
  )
}

// Integration Details Modal Component
const IntegrationDetailsModal = ({
  isOpen,
  onClose,
  integration,
  onConnect,
  onDisconnect,
  onSync
}: {
  isOpen: boolean
  onClose: () => void
  integration: Integration | null
  onConnect: (id: string) => void
  onDisconnect: (id: string) => void
  onSync: (id: string) => void
}) => {
  if (!isOpen || !integration) return null

  const integrationDetails: Record<string, {
    fullDescription: string
    features: string[]
    dataTypes: string[]
    setupSteps: string[]
    brandColor: string
    docsUrl: string
  }> = {
    slack: {
      fullDescription: 'Slack is a channel-based messaging platform. Connect Slack to automatically import messages, threads, and shared files from your workspace channels into your knowledge base.',
      features: [
        'Import messages from public and private channels',
        'Capture threaded conversations',
        'Index shared files and documents',
        'Real-time sync with configurable intervals'
      ],
      dataTypes: ['Messages', 'Threads', 'Files', 'User mentions'],
      setupSteps: [
        'Enter your Slack Bot User OAuth Token',
        'Select channels to sync',
        'Configure sync frequency',
        'Start initial sync'
      ],
      brandColor: '#4A154B',
      docsUrl: 'https://api.slack.com/docs'
    },
    gmail: {
      fullDescription: 'Gmail integration allows you to import emails and attachments into your knowledge base. Capture important communications, decisions, and documents shared via email.',
      features: [
        'Import emails from specific labels or all mail',
        'Extract and index attachments',
        'Smart filtering by sender or subject',
        'Continuous sync for new emails'
      ],
      dataTypes: ['Emails', 'Attachments', 'Contacts', 'Labels'],
      setupSteps: [
        'Authenticate with Google OAuth',
        'Select labels or folders to sync',
        'Configure filters (optional)',
        'Start synchronization'
      ],
      brandColor: '#EA4335',
      docsUrl: 'https://developers.google.com/gmail/api'
    },
    box: {
      fullDescription: 'Box is a cloud content management platform. Connect Box to import documents, spreadsheets, presentations, and other files stored in your Box folders.',
      features: [
        'Sync files from selected folders',
        'Support for 100+ file types',
        'Automatic parsing and text extraction',
        'Version history tracking'
      ],
      dataTypes: ['Documents', 'Spreadsheets', 'Presentations', 'PDFs', 'Images'],
      setupSteps: [
        'Authenticate with Box OAuth',
        'Select folders to sync',
        'Configure file type filters',
        'Begin document import'
      ],
      brandColor: '#0061D5',
      docsUrl: 'https://developer.box.com/docs'
    },
    github: {
      fullDescription: 'GitHub integration imports code repositories, documentation, issues, and pull requests. Perfect for capturing technical knowledge and development decisions.',
      features: [
        'Import README and documentation files',
        'Index code comments and discussions',
        'Capture issue and PR conversations',
        'Track repository wikis'
      ],
      dataTypes: ['Code', 'Documentation', 'Issues', 'Pull Requests', 'Wikis'],
      setupSteps: [
        'Authenticate with GitHub OAuth',
        'Select repositories to sync',
        'Choose content types to import',
        'Start repository scan'
      ],
      brandColor: '#24292F',
      docsUrl: 'https://docs.github.com/en/rest'
    },
    zotero: {
      fullDescription: 'Zotero is a free, open-source reference management tool. Connect Zotero to import your research papers, PDFs, citations, and notes directly into your knowledge base.',
      features: [
        'Import research papers and citations',
        'Extract text from PDF attachments',
        'Sync library metadata (authors, DOIs, abstracts)',
        'Incremental sync for new items'
      ],
      dataTypes: ['Papers', 'PDFs', 'Citations', 'Notes', 'Tags'],
      setupSteps: [
        'Authenticate with Zotero OAuth',
        'Authorize access to your library',
        'Start library synchronization',
        'Review imported documents'
      ],
      brandColor: '#CC2936',
      docsUrl: 'https://www.zotero.org/support/dev/web_api/v3/start'
    },
    powerpoint: {
      fullDescription: 'Import Microsoft PowerPoint presentations to capture knowledge from slides, speaker notes, and embedded content. Great for onboarding materials and company presentations.',
      features: [
        'Extract text from all slides',
        'Capture speaker notes',
        'Index embedded images and charts',
        'Maintain slide structure'
      ],
      dataTypes: ['Slides', 'Speaker Notes', 'Images', 'Charts'],
      setupSteps: [
        'Connect Microsoft 365 account',
        'Select OneDrive folders',
        'Choose presentation files',
        'Begin import process'
      ],
      brandColor: '#D24726',
      docsUrl: 'https://docs.microsoft.com/en-us/office/dev/add-ins/'
    },
    excel: {
      fullDescription: 'Microsoft Excel integration imports spreadsheet data, formulas, and structured information. Ideal for capturing data-driven knowledge and business metrics.',
      features: [
        'Import spreadsheet data and tables',
        'Preserve data relationships',
        'Extract charts and visualizations',
        'Support for complex workbooks'
      ],
      dataTypes: ['Spreadsheets', 'Tables', 'Charts', 'Formulas'],
      setupSteps: [
        'Connect Microsoft 365 account',
        'Select OneDrive folders',
        'Choose Excel files',
        'Configure import settings'
      ],
      brandColor: '#217346',
      docsUrl: 'https://docs.microsoft.com/en-us/office/dev/add-ins/'
    },
    pubmed: {
      fullDescription: 'PubMed is a free search engine accessing the MEDLINE database of references and abstracts on life sciences and biomedical topics. Import research papers, citations, and medical literature into your knowledge base.',
      features: [
        'Search 35+ million citations and abstracts',
        'Import full paper metadata and abstracts',
        'Track citation relationships',
        'Access MeSH term classifications'
      ],
      dataTypes: ['Papers', 'Abstracts', 'Citations', 'Authors', 'MeSH Terms'],
      setupSteps: [
        'Connect with NCBI API key (optional)',
        'Configure search queries or topics',
        'Select papers to import',
        'Start literature sync'
      ],
      brandColor: '#326599',
      docsUrl: 'https://pubmed.ncbi.nlm.nih.gov/help/'
    },
    researchgate: {
      fullDescription: 'ResearchGate is a professional network for scientists and researchers. Connect to import publications, access research datasets, and capture insights from the scientific community.',
      features: [
        'Import your publications and papers',
        'Access shared research datasets',
        'Track research metrics and citations',
        'Capture Q&A discussions'
      ],
      dataTypes: ['Publications', 'Datasets', 'Preprints', 'Q&A', 'Profiles'],
      setupSteps: [
        'Authenticate with ResearchGate',
        'Select publications to import',
        'Configure dataset access',
        'Begin research sync'
      ],
      brandColor: '#00D0AF',
      docsUrl: 'https://www.researchgate.net/help'
    },
    googlescholar: {
      fullDescription: 'Google Scholar provides a simple way to broadly search for scholarly literature. Import academic papers, theses, books, and conference papers from across all disciplines.',
      features: [
        'Search across multiple disciplines',
        'Import papers with full citations',
        'Track citation counts and metrics',
        'Access related articles and authors'
      ],
      dataTypes: ['Papers', 'Theses', 'Books', 'Patents', 'Court Opinions'],
      setupSteps: [
        'Configure search preferences',
        'Set up topic alerts',
        'Select papers to import',
        'Enable continuous monitoring'
      ],
      brandColor: '#4285F4',
      docsUrl: 'https://scholar.google.com/intl/en/scholar/help.html'
    }
  }

  const details = integrationDetails[integration.id] || {
    fullDescription: integration.description,
    features: ['Feature details coming soon'],
    dataTypes: ['Various'],
    setupSteps: ['Connect to get started'],
    brandColor: '#6B7280',
    docsUrl: '#'
  }

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
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#FFF8F0',
          borderRadius: '20px',
          width: '90%',
          maxWidth: '640px',
          maxHeight: '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '24px 32px',
            borderBottom: '1px solid #E5E5E5',
            display: 'flex',
            alignItems: 'center',
            gap: '16px'
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '12px',
              backgroundColor: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid #E5E5E5'
            }}
          >
            <Image
              src={integration.logo}
              alt={integration.name}
              width={36}
              height={36}
              style={{ objectFit: 'contain' }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <h2 style={{
              fontFamily: 'Geist, sans-serif',
              fontSize: '24px',
              fontWeight: 600,
              color: '#18181B',
              margin: 0
            }}>
              {integration.name}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <span
                style={{
                  padding: '4px 10px',
                  borderRadius: '100px',
                  backgroundColor: integration.connected ? '#D1FAE5' : '#F3F4F6',
                  color: integration.connected ? '#059669' : '#6B7280',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500
                }}
              >
                {integration.connected ? '● Connected' : '○ Not Connected'}
              </span>
              <span
                style={{
                  padding: '4px 10px',
                  borderRadius: '100px',
                  backgroundColor: '#F3F4F6',
                  color: '#6B7280',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500
                }}
              >
                {integration.category}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: '#F3F4F6',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px 32px', overflowY: 'auto', flex: 1 }}>
          {/* Description */}
          <div style={{ marginBottom: '24px' }}>
            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '15px',
              color: '#52525B',
              lineHeight: '1.6',
              margin: 0
            }}>
              {details.fullDescription}
            </p>
          </div>

          {/* Features */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{
              fontFamily: 'Geist, sans-serif',
              fontSize: '14px',
              fontWeight: 600,
              color: '#18181B',
              marginBottom: '12px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Features
            </h3>
            <div style={{
              backgroundColor: '#fff',
              borderRadius: '12px',
              border: '1px solid #E5E5E5',
              overflow: 'hidden'
            }}>
              {details.features.map((feature, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px 16px',
                    borderBottom: idx < details.features.length - 1 ? '1px solid #F3F4F6' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px'
                  }}
                >
                  <div style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    backgroundColor: details.brandColor + '15',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={details.brandColor} strokeWidth="3">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                  <span style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '14px',
                    color: '#3F3F46'
                  }}>
                    {feature}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Data Types */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{
              fontFamily: 'Geist, sans-serif',
              fontSize: '14px',
              fontWeight: 600,
              color: '#18181B',
              marginBottom: '12px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Supported Data Types
            </h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {details.dataTypes.map((type, idx) => (
                <span
                  key={idx}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    backgroundColor: '#fff',
                    border: '1px solid #E5E5E5',
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '13px',
                    color: '#52525B'
                  }}
                >
                  {type}
                </span>
              ))}
            </div>
          </div>

          {/* Setup Steps */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{
              fontFamily: 'Geist, sans-serif',
              fontSize: '14px',
              fontWeight: 600,
              color: '#18181B',
              marginBottom: '12px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Setup Steps
            </h3>
            <div style={{
              backgroundColor: '#fff',
              borderRadius: '12px',
              border: '1px solid #E5E5E5',
              padding: '16px'
            }}>
              {details.setupSteps.map((step, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    marginBottom: idx < details.setupSteps.length - 1 ? '12px' : 0
                  }}
                >
                  <div style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: details.brandColor,
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '12px',
                    fontWeight: 600,
                    flexShrink: 0
                  }}>
                    {idx + 1}
                  </div>
                  <span style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '14px',
                    color: '#3F3F46',
                    paddingTop: '2px'
                  }}>
                    {step}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Documentation Link */}
          <a
            href={details.docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
              color: details.brandColor,
              textDecoration: 'none'
            }}
          >
            View Documentation
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          </a>
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '20px 32px',
            borderTop: '1px solid #E5E5E5',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '12px',
            backgroundColor: '#FAFAFA'
          }}
        >
          {integration.connected ? (
            <>
              <button
                onClick={() => onDisconnect(integration.id)}
                style={{
                  padding: '10px 20px',
                  borderRadius: '10px',
                  border: '1px solid #E5E5E5',
                  backgroundColor: '#fff',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: '#64748B',
                  cursor: 'pointer'
                }}
              >
                Disconnect
              </button>
              <button
                onClick={() => {
                  onSync(integration.id)
                  onClose()
                }}
                style={{
                  padding: '10px 20px',
                  borderRadius: '10px',
                  border: 'none',
                  backgroundColor: details.brandColor,
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12a9 9 0 11-6.219-8.56" />
                </svg>
                Sync Now
              </button>
            </>
          ) : (
            <button
              onClick={() => {
                onConnect(integration.id)
                onClose()
              }}
              style={{
                padding: '10px 24px',
                borderRadius: '10px',
                border: 'none',
                backgroundColor: details.brandColor,
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              Connect {integration.name}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

const integrations: Integration[] = [
  {
    id: 'webscraper',
    name: 'Website Scraper',
    logo: '/docs.png',
    description: 'Crawl lab websites and extract protocols, documentation, and resources.',
    category: 'Research',
    connected: false
  },
  {
    id: 'email-forwarding',
    name: 'Email Forwarding',
    logo: '/email-forward.png',
    description: 'Forward emails to beatatucla@gmail.com to import them into your knowledge base.',
    category: 'Conversations',
    connected: false,
    isOAuth: false
  },
  {
    id: 'slack',
    name: 'Slack',
    logo: '/slack.png',
    description: 'Sync messages from all your Slack channels into your knowledge base.',
    category: 'Conversations',
    connected: false,
    isOAuth: true
  },
  {
    id: 'box',
    name: 'Box',
    logo: '/box.png',
    description: 'Connect Box to import documents, files, and folders into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: true
  },
  {
    id: 'github',
    name: 'Github',
    logo: '/github.png',
    description: 'Connect GitHub to import repositories, issues, PRs, and documentation into your knowledge base.',
    category: 'Coding',
    connected: false,
    isOAuth: true
  },
  {
    id: 'onedrive',
    name: 'Microsoft 365',
    logo: '/outlook.png',
    description: 'Connect OneDrive to import PowerPoint, Excel, Word, and PDF files into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: true
  },
  {
    id: 'excel',
    name: 'Excel',
    logo: '/excel.png',
    description: 'Import Excel spreadsheets and workbooks into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: false
  },
  {
    id: 'powerpoint',
    name: 'PowerPoint',
    logo: '/powerpoint.png',
    description: 'Import PowerPoint presentations into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: false
  },
  {
    id: 'notion',
    name: 'Notion',
    logo: '/notion.png',
    description: 'Connect Notion to import pages and databases into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: true
  },
  {
    id: 'gdrive',
    name: 'Google Drive',
    logo: '/gdrive.png',
    description: 'Connect Google Drive to import all your files and folders into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: true
  },
  {
    id: 'gdocs',
    name: 'Google Docs',
    logo: '/gdocs.png',
    description: 'Connect Google Docs to import documents into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: true
  },
  {
    id: 'gsheets',
    name: 'Google Sheets',
    logo: '/gsheets.png',
    description: 'Connect Google Sheets to import spreadsheets into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: true
  },
  {
    id: 'gslides',
    name: 'Google Slides',
    logo: '/gslides.png',
    description: 'Connect Google Slides to import presentations into your knowledge base.',
    category: 'Documents & Recordings',
    connected: false,
    isOAuth: true
  },
  {
    id: 'pubmed',
    name: 'PubMed',
    logo: '/pubmed.png',
    description: 'Access millions of biomedical literature citations and abstracts from MEDLINE.',
    category: 'Research',
    connected: false
  },
  {
    id: 'researchgate',
    name: 'ResearchGate',
    logo: '/researchgate.png',
    description: 'Connect with researchers and access scientific publications and datasets.',
    category: 'Research',
    connected: false
  },
  {
    id: 'googlescholar',
    name: 'Google Scholar',
    logo: '/googlescholar.png',
    description: 'Search scholarly literature across disciplines and sources worldwide.',
    category: 'Research',
    connected: false
  },
  {
    id: 'gmail',
    name: 'Gmail',
    logo: '/gmail.png',
    description: 'Connect Gmail to import emails directly into your knowledge base via OAuth.',
    category: 'Conversations',
    connected: false,
    isOAuth: true
  },
  {
    id: 'zotero',
    name: 'Zotero',
    logo: '/zotero.webp',
    description: 'Connect Zotero to import research papers, PDFs, and citations into your knowledge base.',
    category: 'Research',
    connected: false,
    isOAuth: true
  }
]

const IntegrationCard = ({
  integration,
  onToggleConnect,
  onViewDetails,
  onSync,
  isSyncing,
  syncingIntegration
}: {
  integration: Integration;
  onToggleConnect: (id: string) => void;
  onViewDetails: (integration: Integration) => void;
  onSync?: (id: string) => void;
  isSyncing?: boolean;
  syncingIntegration?: string;
}) => {
  const isThisSyncing = syncingIntegration === integration.id;

  return (
    <div
      className="flex flex-col items-start gap-2"
      style={{
        width: '100%',
        padding: '32px',
        borderRight: '1px solid #E5E7EB',
        borderBottom: '1px solid #E5E7EB',
        margin: 0,
        boxSizing: 'border-box',
        backgroundColor: integration.connected ? '#EFF6FF' : '#FFFFFF'
      }}
    >
      {/* Logo */}
      <div style={{ width: '40px', height: '40px', flexShrink: 0 }}>
        <Image
          src={integration.logo}
          alt={integration.name}
          width={40}
          height={40}
          style={{ width: '40px', height: '40px', objectFit: 'contain' }}
        />
      </div>

      {/* Name */}
      <h3
        style={{
          color: '#18181B',
          fontFamily: 'Geist, sans-serif',
          fontSize: '18px',
          fontWeight: 500,
          marginTop: '8px'
        }}
      >
        {integration.name}
      </h3>

      {/* Description - 2 lines */}
      <p
        style={{
          width: '264px',
          color: '#71717A',
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          fontWeight: 400,
          lineHeight: '20px',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden'
        }}
      >
        {integration.description}
      </p>

      {/* Buttons */}
      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={() => {
            if (isThisSyncing) {
              // Allow clicking to cancel/stop sync
              onToggleConnect(integration.id)
            } else if (!isSyncing) {
              onToggleConnect(integration.id)
            }
          }}
          className={`flex items-center justify-center gap-[4px]`}
          style={{
            padding: '6px 10px',
            borderRadius: '375px',
            border: '0.75px solid #E5E7EB',
            backgroundColor: isThisSyncing ? '#DC2626' : isSyncing ? '#2563EB' : integration.connected ? '#2563EB' : '#FFFFFF',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
            cursor: (isSyncing && !isThisSyncing) ? 'default' : 'pointer',
            opacity: (isSyncing && !isThisSyncing) ? 0.9 : 1,
            flexShrink: 0
          }}
        >
          {isThisSyncing ? (
            <div
              style={{
                width: '8px',
                height: '8px',
                backgroundColor: '#FFFFFF',
                borderRadius: '1px'
              }}
            />
          ) : isSyncing ? (
            <div
              style={{
                width: '12px',
                height: '12px',
                border: '2px solid transparent',
                borderTopColor: '#FFFFFF',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }}
            />
          ) : null}
          <span
            style={{
              color: isSyncing || isThisSyncing ? '#FFFFFF' : integration.connected ? '#FFFFFF' : '#374151',
              fontFamily: 'Inter, sans-serif',
              fontSize: '12px',
              fontWeight: 500
            }}
          >
            {isSyncing && !isThisSyncing ? 'Connecting' : isThisSyncing ? 'Stop Sync' : integration.connected ? 'Connected' : 'Connect'}
          </span>
          {integration.connected && !isSyncing && !isThisSyncing && (
            <div
              style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: '#3B82F6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <span style={{ color: 'white', fontSize: '10px' }}>✓</span>
            </div>
          )}
        </button>

        {/* Sync button - shown when connected, is OAuth, and NOT currently syncing */}
        {integration.connected && integration.isOAuth && onSync && !isThisSyncing && (
          <button
            onClick={() => onSync(integration.id)}
            className="flex items-center justify-center gap-[4px]"
            style={{
              padding: '6px 10px',
              borderRadius: '375px',
              border: 'none',
              backgroundColor: '#3B82F6',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              flexShrink: 0
            }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2"
            >
              <path d="M21 12a9 9 0 11-6.219-8.56" />
            </svg>
            <span
              style={{
                color: '#FFFFFF',
                fontFamily: 'Inter, sans-serif',
                fontSize: '12px',
                fontWeight: 400
              }}
            >
              Sync
            </span>
          </button>
        )}

        <button
          onClick={() => onViewDetails(integration)}
          className="flex items-center gap-1 hover:opacity-70 transition-opacity"
          style={{
            color: '#1E293B',
            fontFamily: 'Inter, sans-serif',
            fontSize: '12px',
            fontWeight: 400,
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            whiteSpace: 'nowrap',
            flexShrink: 0
          }}
        >
          Integration details
          <span>→</span>
        </button>
      </div>
    </div>
  )
}

export default function Integrations() {
  const { user } = useAuth()
  const { startSync: globalStartSync } = useSyncProgress()
  const [activeItem, setActiveItem] = useState('Integrations')
  const [activeTab, setActiveTab] = useState('All Integrations')
  // Initialize without localStorage to avoid hydration mismatch
  const [integrationsState, setIntegrationsState] = useState(() =>
    integrations.map(int => ({
      ...int,
      connected: false
    }))
  )
  const [isHydrated, setIsHydrated] = useState(false)
  const [isConnecting, setIsConnecting] = useState<string | null>(null)
  const [syncStatus, setSyncStatus] = useState<string | null>(null)

  // Channel selection state
  const [showChannelModal, setShowChannelModal] = useState(false)
  const [slackChannels, setSlackChannels] = useState<SlackChannel[]>([])
  const [loadingChannels, setLoadingChannels] = useState(false)

  // Slack token modal state
  const [showSlackTokenModal, setShowSlackTokenModal] = useState(false)
  const [isSubmittingToken, setIsSubmittingToken] = useState(false)

  // Sync progress state
  const [showSyncProgress, setShowSyncProgress] = useState(false)
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null)
  // CRITICAL FIX: Use useRef instead of useState to avoid closure issues
  // useState causes the setInterval callback to capture stale state values
  const syncPollingInterval = useRef<NodeJS.Timeout | null>(null)

  // SSE-based sync progress modal state (new)
  const [syncId, setSyncId] = useState<string | null>(null)
  const [syncingConnector, setSyncingConnector] = useState<string | null>(null)
  const [syncEstimatedSeconds, setSyncEstimatedSeconds] = useState<number | null>(null)
  // Track syncs running in background (when modal is closed during active sync)
  // Maps connector type -> syncId so we can re-open the progress modal
  // Persisted to localStorage so state survives navigation
  const [backgroundSyncs, setBackgroundSyncs] = useState<{[connector: string]: string}>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('backgroundSyncs')
      if (saved) {
        try {
          return JSON.parse(saved)
        } catch (e) {
          return {}
        }
      }
    }
    return {}
  })

  // Integration details modal state
  const [showDetailsModal, setShowDetailsModal] = useState(false)
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null)

  // GitHub repository selection modal state
  const [showGitHubRepoModal, setShowGitHubRepoModal] = useState(false)
  const [githubRepos, setGithubRepos] = useState<Array<{full_name: string; description: string | null; updated_at: string; private: boolean}>>([])
  const [selectedRepos, setSelectedRepos] = useState<string[]>([])
  const [loadingRepos, setLoadingRepos] = useState(false)
  // Pre-scan state for showing estimated time before sync
  const [prescanResults, setPrescanResults] = useState<{[repo: string]: {file_count: number; expected_documents: number; estimated_time: string}} | null>(null)
  const [isScanning, setIsScanning] = useState(false)
  const [totalEstimate, setTotalEstimate] = useState<{files: number; time: string} | null>(null)
  // Demo mode for showing the full flow without OAuth
  const [isDemoMode, setIsDemoMode] = useState(false)
  const [demoStep, setDemoStep] = useState(0) // 0: not started, 1: repo modal, 2: scanning, 3: scan complete, 4: syncing

  // PubMed configuration modal state
  const [showPubMedModal, setShowPubMedModal] = useState(false)
  const [pubmedQuery, setPubmedQuery] = useState('')
  const [pubmedMaxResults, setPubmedMaxResults] = useState(100)
  const [pubmedDateRange, setPubmedDateRange] = useState(5)
  const [pubmedApiKey, setPubmedApiKey] = useState('')
  const [isConfiguringPubmed, setIsConfiguringPubmed] = useState(false)

  // WebScraper configuration modal state
  const [showWebScraperModal, setShowWebScraperModal] = useState(false)
  const [webscraperUrl, setWebscraperUrl] = useState('')
  const [webscraperPriorityPaths, setWebscraperPriorityPaths] = useState('')
  const [isConfiguringWebscraper, setIsConfiguringWebscraper] = useState(false)

  // Email Forwarding modal state
  const [showEmailForwardingModal, setShowEmailForwardingModal] = useState(false)

  // Disconnect confirmation modal state
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false)
  const [disconnectTarget, setDisconnectTarget] = useState<string | null>(null)
  const [disconnectCounts, setDisconnectCounts] = useState<{document_count: number; gap_count: number; chunk_count: number} | null>(null)
  const [isLoadingDisconnect, setIsLoadingDisconnect] = useState(false)

  // Load localStorage state after hydration to avoid mismatch
  useEffect(() => {
    setIsHydrated(true)
    const savedConnected = loadConnectedIntegrations()
    if (savedConnected.length > 0) {
      setIntegrationsState(prev => prev.map(int => ({
        ...int,
        connected: savedConnected.includes(int.id)
      })))
    }
  }, [])

  // Save connected integrations to localStorage whenever they change (only after hydration)
  useEffect(() => {
    if (!isHydrated) return
    const connectedIds = integrationsState.filter(int => int.connected).map(int => int.id)
    saveConnectedIntegrations(connectedIds)
  }, [integrationsState, isHydrated])

  const categories = ['All Integrations', 'Conversations', 'Coding', 'Documents & Recordings', 'Research']

  // Get auth token for API calls
  const getAuthToken = () => {
    return localStorage.getItem('accessToken')
  }

  // DISABLED: Auto-resume causes infinite polling loops
  // Users must manually start syncs - no auto-resume on page load
  useEffect(() => {
    // Clear any saved sync state to prevent auto-resume
    saveSyncState(null)

    // Also clear backgroundSyncs to prevent stale entries from blocking Connect buttons
    // This ensures a clean state on every page load
    localStorage.removeItem('backgroundSyncs')
    setBackgroundSyncs({})

    // CRITICAL: Cleanup function to stop polling when component unmounts
    return () => {
      if (syncPollingInterval.current) {
        clearInterval(syncPollingInterval.current)
        syncPollingInterval.current = null
      }
    }
  }, [])

  // Persist backgroundSyncs to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (Object.keys(backgroundSyncs).length > 0) {
        localStorage.setItem('backgroundSyncs', JSON.stringify(backgroundSyncs))
      } else {
        localStorage.removeItem('backgroundSyncs')
      }
    }
  }, [backgroundSyncs])

  // Save active sync to localStorage when navigating away (component unmount)
  useEffect(() => {
    return () => {
      // On unmount, if there's an active sync, save it to backgroundSyncs in localStorage
      if (syncId && syncingConnector) {
        const currentSyncs = JSON.parse(localStorage.getItem('backgroundSyncs') || '{}')
        currentSyncs[syncingConnector] = syncId
        localStorage.setItem('backgroundSyncs', JSON.stringify(currentSyncs))
        console.log(`[Sync] Saved active sync to localStorage on unmount: ${syncingConnector} -> ${syncId}`)
      }
    }
  }, [syncId, syncingConnector])

  // Poll for background sync completion
  useEffect(() => {
    if (Object.keys(backgroundSyncs).length === 0) return

    const pollBackgroundSyncs = async () => {
      const token = getAuthToken()
      if (!token) return

      for (const connectorId of Object.keys(backgroundSyncs)) {
        try {
          const response = await axios.get(
            `${API_BASE}/integrations/${connectorId}/sync/status`,
            { headers: { Authorization: `Bearer ${token}` } }
          )

          if (response.data.success) {
            const status = response.data.status?.status
            if (status === 'completed' || status === 'error' || status === 'idle' || !status) {
              // Sync finished, remove from background syncs
              setBackgroundSyncs(prev => {
                const next = { ...prev }
                delete next[connectorId]
                return next
              })
              // Refresh integration statuses
              checkIntegrationStatuses()
            }
          }
        } catch (err) {
          // If error checking status, assume sync is done
          setBackgroundSyncs(prev => {
            const next = { ...prev }
            delete next[connectorId]
            return next
          })
        }
      }
    }

    // Poll every 10 seconds (background syncs don't need aggressive polling)
    const interval = setInterval(pollBackgroundSyncs, 10000)
    // Also poll immediately
    pollBackgroundSyncs()

    return () => clearInterval(interval)
  }, [backgroundSyncs])

  // Check integration statuses on mount
  useEffect(() => {
    checkIntegrationStatuses()

    // Check URL params for OAuth callback results
    const urlParams = new URLSearchParams(window.location.search)
    const success = urlParams.get('success')
    const error = urlParams.get('error')

    if (success === 'slack') {
      setSyncStatus('Slack connected! Select which channels to sync.')
      setIntegrationsState(prev =>
        prev.map(int =>
          int.id === 'slack' ? { ...int, connected: true } : int
        )
      )
      // Clean URL and open channel selection modal
      window.history.replaceState({}, '', '/integrations')
      // Fetch channels and show modal
      fetchSlackChannels()
    } else if (success === 'gmail') {
      setSyncStatus('Gmail connected successfully! You can now sync your emails.')
      setIntegrationsState(prev =>
        prev.map(int =>
          int.id === 'gmail' ? { ...int, connected: true } : int
        )
      )
      window.history.replaceState({}, '', '/integrations')
    } else if (success === 'box') {
      setIntegrationsState(prev =>
        prev.map(int =>
          int.id === 'box' ? { ...int, connected: true } : int
        )
      )
      window.history.replaceState({}, '', '/integrations')
      // Auto-start sync with progress for Box
      setTimeout(() => startSyncWithProgress('box'), 500)
    } else if (success === 'github') {
      setIntegrationsState(prev =>
        prev.map(int =>
          int.id === 'github' ? { ...int, connected: true } : int
        )
      )
      window.history.replaceState({}, '', '/integrations')
      // Show repository selection modal instead of auto-starting sync
      setTimeout(() => fetchGitHubRepos(), 500)
    } else if (success === 'onedrive') {
      // Mark OneDrive and related Microsoft apps as connected
      setIntegrationsState(prev =>
        prev.map(int =>
          ['onedrive', 'excel', 'powerpoint'].includes(int.id) ? { ...int, connected: true } : int
        )
      )
      window.history.replaceState({}, '', '/integrations')
      // Auto-start sync with progress for OneDrive
      setTimeout(() => startSyncWithProgress('onedrive'), 500)
    } else if (success === 'notion') {
      setIntegrationsState(prev =>
        prev.map(int =>
          int.id === 'notion' ? { ...int, connected: true } : int
        )
      )
      window.history.replaceState({}, '', '/integrations')
      // Auto-start sync with progress for Notion
      setTimeout(() => startSyncWithProgress('notion'), 500)
    } else if (success === 'gdrive') {
      // Mark Google Drive and all related G Suite apps as connected
      setIntegrationsState(prev =>
        prev.map(int =>
          ['gdrive', 'gdocs', 'gsheets', 'gslides'].includes(int.id) ? { ...int, connected: true } : int
        )
      )
      window.history.replaceState({}, '', '/integrations')
      // Auto-start sync with progress for Google Drive
      setTimeout(() => startSyncWithProgress('gdrive'), 500)
    } else if (success === 'zotero') {
      setSyncStatus('Zotero connected successfully! Starting library sync...')
      setIntegrationsState(prev =>
        prev.map(int =>
          int.id === 'zotero' ? { ...int, connected: true } : int
        )
      )
      window.history.replaceState({}, '', '/integrations')
      // Auto-start sync with progress for Zotero
      setTimeout(() => startSyncWithProgress('zotero'), 500)
    } else if (error) {
      setSyncStatus(`Connection failed: ${error}`)
      window.history.replaceState({}, '', '/integrations')
    }

    // Listen for OAuth callback messages (for popup flow)
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'OAUTH_CONNECTED') {
        const integrationId = event.data.integration
        if (event.data.success) {
          setIntegrationsState(prev =>
            prev.map(int =>
              int.id === integrationId ? { ...int, connected: true } : int
            )
          )
          setSyncStatus(`${integrationId.charAt(0).toUpperCase() + integrationId.slice(1)} connected! You can now sync your data.`)
        } else {
          setSyncStatus(`Connection failed: ${event.data.error}`)
        }
        setIsConnecting(null)
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  const checkIntegrationStatuses = async () => {
    const token = getAuthToken()
    if (!token) return

    try {
      const response = await axios.get(`${API_BASE}/integrations`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      if (response.data.success) {
        const apiIntegrations = response.data.integrations
        // "connected" OR "syncing" both mean the integration is connected
        const gdriveStatus = apiIntegrations.find((a: any) => a.type === 'gdrive')?.status
        const gdriveConnected = gdriveStatus === 'connected' || gdriveStatus === 'syncing'
        const onedriveStatus = apiIntegrations.find((a: any) => a.type === 'onedrive')?.status
        const onedriveConnected = onedriveStatus === 'connected' || onedriveStatus === 'syncing'

        setIntegrationsState(prev =>
          prev.map(int => {
            // For G Suite apps, mirror gdrive connection status
            if (['gdocs', 'gsheets', 'gslides'].includes(int.id)) {
              return { ...int, connected: gdriveConnected }
            }
            // For Microsoft apps, mirror onedrive connection status
            if (['excel', 'powerpoint'].includes(int.id)) {
              return { ...int, connected: onedriveConnected }
            }
            const apiInt = apiIntegrations.find((a: any) => a.type === int.id)
            if (apiInt) {
              // "syncing" status also means connected (sync happens after connection)
              return { ...int, connected: apiInt.status === 'connected' || apiInt.status === 'syncing' }
            }
            return int
          })
        )

        // Auto-detect stuck syncing connectors:
        // If backend says "syncing" but frontend has no active sync for it, auto-cancel
        for (const apiInt of apiIntegrations) {
          if (apiInt.status === 'syncing') {
            const hasActiveFrontendSync = syncingConnector === apiInt.type || !!backgroundSyncs[apiInt.type]
            if (!hasActiveFrontendSync) {
              console.log(`[Sync] Detected stuck SYNCING connector: ${apiInt.type} — auto-resetting`)
              try {
                await axios.post(
                  `${API_BASE}/integrations/${apiInt.type}/sync/cancel`,
                  {},
                  { headers: { Authorization: `Bearer ${token}` } }
                )
                console.log(`[Sync] Auto-reset stuck connector: ${apiInt.type}`)
              } catch (resetErr) {
                console.error(`[Sync] Failed to auto-reset ${apiInt.type}:`, resetErr)
              }
            }
          }
        }

        // Store webscraper settings if configured
        const webscraper = apiIntegrations.find((a: any) => a.type === 'webscraper')
        if (webscraper?.settings?.start_url) {
          setWebscraperUrl(webscraper.settings.start_url)
        }
      }
    } catch (error) {
      console.error('Error checking integration statuses:', error)
    }
  }

  // Generic OAuth connect function
  const connectOAuth = async (integrationId: string) => {
    console.log(`[OAuth] Starting connection for: ${integrationId}`)
    setIsConnecting(integrationId)
    setSyncStatus(null)

    const token = getAuthToken()
    console.log(`[OAuth] Token exists: ${!!token}`)
    if (!token) {
      setSyncStatus('Please log in first')
      setIsConnecting(null)
      return
    }

    try {
      // Get auth URL from backend
      const url = `${API_BASE}/integrations/${integrationId}/auth`
      console.log(`[OAuth] Calling: ${url}`)
      const response = await axios.get(url, {
        headers: { Authorization: `Bearer ${token}` }
      })
      console.log(`[OAuth] Response:`, response.data)

      if (response.data.success && response.data.auth_url) {
        // Redirect to OAuth (Slack requires full page redirect, not popup)
        console.log(`[OAuth] Redirecting to: ${response.data.auth_url}`)
        window.location.href = response.data.auth_url
      } else {
        const errMsg = response.data.error || 'Failed to get authorization URL'
        console.error(`[OAuth] Error in response: ${errMsg}`)
        setSyncStatus(`Error: ${errMsg}`)
        setIsConnecting(null)
      }
    } catch (error: any) {
      console.error(`[OAuth] Exception:`, error)
      const errorMsg = error.response?.data?.error || error.message
      setSyncStatus(`Connection error: ${errorMsg}`)
      setIsConnecting(null)
    }
  }

  // Generic disconnect function - now with confirmation
  const disconnectIntegration = async (integrationId: string, forceConfirm: boolean = false) => {
    const token = getAuthToken()
    if (!token) return

    try {
      // If not forcing confirmation, first get preview counts
      if (!forceConfirm) {
        setIsLoadingDisconnect(true)
        try {
          const previewResponse = await axios.get(`${API_BASE}/integrations/${integrationId}/disconnect/preview`, {
            headers: { Authorization: `Bearer ${token}` }
          })

          if (previewResponse.data.success) {
            const counts = previewResponse.data.counts
            // If there's data to delete, show confirmation modal
            if (counts.document_count > 0 || counts.gap_count > 0) {
              setDisconnectTarget(integrationId)
              setDisconnectCounts(counts)
              setShowDisconnectConfirm(true)
              setIsLoadingDisconnect(false)
              return
            }
          }
        } catch (previewError) {
          // If preview fails (e.g., endpoint not available), proceed without confirmation
          console.log('Preview endpoint not available, proceeding with disconnect')
        }
        setIsLoadingDisconnect(false)
      }

      // Proceed with disconnect (with confirm flag if there was data)
      await axios.post(`${API_BASE}/integrations/${integrationId}/disconnect`,
        forceConfirm ? { confirm: true } : {},
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setIntegrationsState(prev =>
        prev.map(int =>
          int.id === integrationId ? { ...int, connected: false } : int
        )
      )

      // Clear confirmation state
      setShowDisconnectConfirm(false)
      setDisconnectTarget(null)
      setDisconnectCounts(null)

      setSyncStatus(`${integrationId.charAt(0).toUpperCase() + integrationId.slice(1)} disconnected.`)
    } catch (error: any) {
      console.error(`Error disconnecting ${integrationId}:`, error)
      // Check if it's a confirmation required response
      if (error.response?.data?.requires_confirmation) {
        const counts = error.response.data.counts
        setDisconnectTarget(integrationId)
        setDisconnectCounts(counts)
        setShowDisconnectConfirm(true)
      } else {
        setSyncStatus(`Error disconnecting: ${error.response?.data?.error || error.message}`)
      }
    }
  }

  // Confirm disconnect and delete all data
  const confirmDisconnect = async () => {
    if (!disconnectTarget) return
    setIsLoadingDisconnect(true)
    await disconnectIntegration(disconnectTarget, true)
    setIsLoadingDisconnect(false)
  }

  // Cancel disconnect
  const cancelDisconnect = () => {
    setShowDisconnectConfirm(false)
    setDisconnectTarget(null)
    setDisconnectCounts(null)
  }

  // Fetch Slack channels for selection
  const fetchSlackChannels = async () => {
    const token = getAuthToken()
    if (!token) return

    setLoadingChannels(true)
    try {
      const response = await axios.get(`${API_BASE}/integrations/slack/channels`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      if (response.data.success) {
        setSlackChannels(response.data.channels)
        setShowChannelModal(true)
      } else {
        setSyncStatus(`Error fetching channels: ${response.data.error}`)
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message
      setSyncStatus(`Error fetching channels: ${errorMsg}`)
    } finally {
      setLoadingChannels(false)
    }
  }

  // Fetch GitHub repositories for selection (lazy loading: first 10 fast, then more in background)
  const fetchGitHubRepos = async () => {
    const token = getAuthToken()
    if (!token) return

    setLoadingRepos(true)
    try {
      // Fetch first page (10 repos) immediately - this is FAST
      const response = await axios.get(`${API_BASE}/integrations/github/repositories`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { page: 1, per_page: 10 }
      })

      if (response.data.success) {
        setGithubRepos(response.data.repositories)
        // Pre-select the most recently updated repo
        if (response.data.repositories.length > 0) {
          setSelectedRepos([response.data.repositories[0].full_name])
        }
        // Show modal immediately with first 10 repos
        setShowGitHubRepoModal(true)
        setLoadingRepos(false)

        // If there are more repos, load them in background
        if (response.data.has_more) {
          loadMoreGitHubRepos(token, 2, response.data.repositories)
        }
      } else {
        setSyncStatus(`Error fetching repositories: ${response.data.error}`)
        setLoadingRepos(false)
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message
      setSyncStatus(`Error fetching repositories: ${errorMsg}`)
      setLoadingRepos(false)
    }
  }

  // Background loader for additional GitHub repos
  const loadMoreGitHubRepos = async (token: string, page: number, existingRepos: typeof githubRepos) => {
    try {
      const response = await axios.get(`${API_BASE}/integrations/github/repositories`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { page, per_page: 20 }  // Load 20 at a time for background
      })

      if (response.data.success && response.data.repositories.length > 0) {
        const newRepos = [...existingRepos, ...response.data.repositories]
        setGithubRepos(newRepos)

        // Continue loading if more available (up to 100 total for reasonable UX)
        if (response.data.has_more && newRepos.length < 100) {
          // Small delay to avoid hammering the API
          setTimeout(() => loadMoreGitHubRepos(token, page + 1, newRepos), 200)
        }
      }
    } catch (error) {
      // Silent fail for background loading - user already has first 10
      console.log('Background repo loading stopped:', error)
    }
  }

  // Pre-scan selected GitHub repositories to get file count and estimated time
  const prescanSelectedRepos = async () => {
    if (selectedRepos.length === 0) {
      setSyncStatus('Please select at least one repository to scan')
      return
    }

    const token = getAuthToken()
    if (!token) return

    setIsScanning(true)
    setPrescanResults(null)
    setTotalEstimate(null)

    const results: {[repo: string]: {file_count: number; expected_documents: number; estimated_time: string}} = {}
    let totalFiles = 0
    let totalSeconds = 0

    try {
      for (const repo of selectedRepos) {
        try {
          const response = await axios.post(
            `${API_BASE}/integrations/github/prescan`,
            { repository: repo },
            { headers: { Authorization: `Bearer ${token}` } }
          )

          if (response.data.success) {
            const fileCount = response.data.file_count || 0
            const expectedDocs = response.data.expected_documents || Math.min(12, fileCount)
            const estimatedTime = response.data.estimated_time_display || response.data.estimated_time || 'Unknown'
            results[repo] = { file_count: fileCount, expected_documents: expectedDocs, estimated_time: estimatedTime }
            totalFiles += expectedDocs  // Use expected documents for total, not raw files
            // Parse estimated time to seconds for total calculation
            const timeMatch = estimatedTime.match(/~?(\d+)\s*(second|minute)/i)
            if (timeMatch) {
              const value = parseInt(timeMatch[1])
              const unit = timeMatch[2].toLowerCase()
              totalSeconds += unit.startsWith('minute') ? value * 60 : value
            }
          }
        } catch (err: any) {
          const errorMsg = err.response?.data?.error || err.message || 'Unknown error'
          console.error(`Failed to prescan ${repo}:`, errorMsg, err)
          results[repo] = { file_count: 0, expected_documents: 0, estimated_time: `Error: ${errorMsg.slice(0, 30)}` }
        }
      }

      setPrescanResults(results)

      // Calculate total estimate
      let timeStr = ''
      if (totalSeconds >= 60) {
        const minutes = Math.ceil(totalSeconds / 60)
        timeStr = `~${minutes} minute${minutes > 1 ? 's' : ''}`
      } else {
        timeStr = `~${totalSeconds} seconds`
      }
      setTotalEstimate({ files: totalFiles, time: timeStr })

    } catch (error: any) {
      setSyncStatus(`Error scanning repositories: ${error.message}`)
    } finally {
      setIsScanning(false)
    }
  }

  // Demo function - simulates the full GitHub sync flow
  const runDemoFlow = async () => {
    setIsDemoMode(true)
    setDemoStep(1)

    // Step 1: Show repo selection modal
    setGithubRepos([
      { full_name: 'acme-corp/frontend-app', description: 'React frontend application with TypeScript', updated_at: '2026-02-07T10:00:00Z', private: false },
      { full_name: 'acme-corp/backend-api', description: 'Node.js REST API with Express', updated_at: '2026-02-06T15:30:00Z', private: true },
      { full_name: 'acme-corp/shared-utils', description: 'Shared utility functions and types', updated_at: '2026-01-20T08:00:00Z', private: false },
      { full_name: 'acme-corp/mobile-app', description: 'React Native mobile application', updated_at: '2026-02-05T12:00:00Z', private: true },
    ])
    setSelectedRepos(['acme-corp/frontend-app', 'acme-corp/backend-api'])
    setPrescanResults(null)
    setTotalEstimate(null)
    setShowGitHubRepoModal(true)
    setIntegrationsState(prev =>
      prev.map(int => int.id === 'github' ? { ...int, connected: true } : int)
    )
  }

  // Demo: Simulate scanning
  const demoScan = async () => {
    setDemoStep(2)
    setIsScanning(true)

    // Simulate scanning delay
    await new Promise(resolve => setTimeout(resolve, 2000))

    // Show scan results
    setPrescanResults({
      'acme-corp/frontend-app': { file_count: 127, expected_documents: 12, estimated_time: '~2-3 minutes' },
      'acme-corp/backend-api': { file_count: 89, expected_documents: 12, estimated_time: '~2-3 minutes' }
    })
    setTotalEstimate({ files: 24, time: '~4-5 minutes' })
    setIsScanning(false)
    setDemoStep(3)
  }

  // Demo: Start sync with animated progress
  const demoStartSync = async () => {
    setDemoStep(4)
    setShowGitHubRepoModal(false)
    setSyncingConnector('github')

    // Show SSE-style progress modal by setting syncId (but use demo data)
    // We'll use the polling modal instead for demo since it's easier to control
    let processed = 0
    const total = 216
    const startTime = Date.now()

    setSyncProgress({
      integration: 'github',
      status: 'syncing',
      progress: 0,
      documentsFound: total,
      documentsParsed: 0,
      documentsEmbedded: 0,
      startTime
    })
    setShowSyncProgress(true)

    // Animate progress
    const interval = setInterval(() => {
      processed += Math.floor(Math.random() * 15) + 5
      if (processed >= total) {
        processed = total
        clearInterval(interval)

        // Complete
        setSyncProgress(prev => prev ? {
          ...prev,
          status: 'completed',
          progress: 100,
          documentsParsed: total,
          documentsEmbedded: total
        } : null)

        setSyncingConnector(null)
        setIsDemoMode(false)
        setDemoStep(0)
      } else {
        setSyncProgress(prev => prev ? {
          ...prev,
          progress: Math.round((processed / total) * 100),
          documentsParsed: processed,
          documentsEmbedded: Math.floor(processed * 0.9)
        } : null)
      }
    }, 800)
  }

  // Start GitHub sync with selected repositories
  const startGitHubSync = async () => {
    // If in demo mode, run demo sync
    if (isDemoMode) {
      demoStartSync()
      return
    }

    if (selectedRepos.length === 0) {
      setSyncStatus('Please select at least one repository to sync')
      return
    }

    setShowGitHubRepoModal(false)

    // Send all repos in one sync call - backend handles them sequentially
    await startSyncWithProgress('github', undefined, selectedRepos)
  }

  // Save selected Slack channels and start sync
  const saveSlackChannels = async (channelIds: string[]) => {
    const token = getAuthToken()
    if (!token) return

    try {
      // Save channel selection
      await axios.put(`${API_BASE}/integrations/slack/channels`,
        { channels: channelIds },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      setShowChannelModal(false)
      setSyncStatus(`Saved ${channelIds.length} channels. Starting sync...`)

      // Start sync
      await syncIntegration('slack')
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message
      setSyncStatus(`Error saving channels: ${errorMsg}`)
    }
  }

  // Poll for sync status
  const pollSyncStatus = async (integrationId: string) => {
    console.log('[DEBUG] pollSyncStatus called for:', integrationId, 'interval:', syncPollingInterval.current)
    const token = getAuthToken()
    if (!token) return

    try {
      const response = await axios.get(`${API_BASE}/integrations/${integrationId}/sync/status`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      if (response.data.success) {
        const status = response.data.status
        setSyncProgress({
          integration: integrationId,
          status: status.status,
          progress: status.progress || 0,
          documentsFound: status.documents_found || 0,
          documentsParsed: status.documents_parsed || 0,
          documentsEmbedded: status.documents_embedded || 0,
          currentFile: status.current_file,
          error: status.error
        })

        // Stop polling if completed or error, but keep the completed state visible
        if (status.status === 'completed' || status.status === 'error') {
          if (syncPollingInterval.current) {
            clearInterval(syncPollingInterval.current)
            syncPollingInterval.current = null
          }

          // If completed, ensure integration is marked as connected
          if (status.status === 'completed') {
            setIntegrationsState(prev =>
              prev.map(int =>
                int.id === integrationId ? { ...int, connected: true } : int
              )
            )
          }

          // DISABLED: Don't save state - prevents auto-resume on page load
          // saveSyncState({
          //   integration: integrationId,
          //   status: status.status,
          //   progress: 100,
          //   documentsFound: status.documents_found || 0,
          //   documentsParsed: status.documents_parsed || 0,
          //   documentsEmbedded: status.documents_embedded || 0,
          //   completedAt: Date.now()
          // })
        }
      }
    } catch (error) {
      console.error('Error polling sync status:', error)
    }
  }

  // Start sync with progress tracking
  // Supports both single repository (legacy) and multiple repositories
  const startSyncWithProgress = async (integrationId: string, repository?: string, repositories?: string[]) => {
    console.log(`[Sync] Starting sync for: ${integrationId}${repository ? ` (repo: ${repository})` : ''}${repositories ? ` (${repositories.length} repos)` : ''}`)

    // Check if this connector has a sync running in background
    // If so, re-open the progress modal instead of starting a new sync
    const existingSyncId = backgroundSyncs[integrationId]
    if (existingSyncId) {
      console.log(`[Sync] Re-opening existing sync progress for ${integrationId}, syncId: ${existingSyncId}`)
      setSyncId(existingSyncId)
      setSyncingConnector(integrationId)
      // Remove from background syncs since we're showing modal again
      setBackgroundSyncs(prev => {
        const next = { ...prev }
        delete next[integrationId]
        return next
      })
      return
    }

    const token = getAuthToken()
    if (!token) {
      console.error('[Sync] No auth token found')
      return
    }

    const startTime = Date.now()

    try {
      // Start the sync - send repositories array if provided, otherwise single repository
      const url = `${API_BASE}/integrations/${integrationId}/sync`
      console.log(`[Sync] Calling: POST ${url}`)
      console.log(`[Sync] Token exists: ${!!token}, Token length: ${token?.length}`)
      const requestBody = repositories && repositories.length > 0
        ? { repositories }  // Multi-repo sync
        : repository ? { repository } : {}  // Single repo or auto-select
      const response = await axios.post(url, requestBody, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 60000  // 60 second timeout for initial sync request
      })
      console.log(`[Sync] Response status:`, response.status)
      console.log(`[Sync] Response:`, response.data)

      if (response.data.success) {
        // NEW: If sync_id is returned, use SSE-based progress modal
        if (response.data.sync_id) {
          // Show NEW SSE-based progress modal
          setSyncId(response.data.sync_id)
          setSyncingConnector(integrationId)

          // Register with global sync context for persistent progress across navigation
          globalStartSync(response.data.sync_id, integrationId)

          // Parse estimated time from prescan results if available (for GitHub)
          // Parse strings like "~45 seconds", "~2 minutes", "~1m 30s"
          const parseEstimatedTime = (str: string): number | null => {
            if (!str || str.includes('Error')) return null
            const minMatch = str.match(/(\d+)\s*m(?:in)?/i)
            const secMatch = str.match(/(\d+)\s*s(?:ec)?/i)
            let seconds = 0
            if (minMatch) seconds += parseInt(minMatch[1]) * 60
            if (secMatch) seconds += parseInt(secMatch[1])
            // If just a number, assume seconds
            if (!minMatch && !secMatch) {
              const numMatch = str.match(/(\d+)/)
              if (numMatch) seconds = parseInt(numMatch[1])
            }
            return seconds > 0 ? seconds : null
          }

          // Sum up estimated time for all repos (multi-repo sync)
          if (repositories && repositories.length > 0 && prescanResults) {
            let totalSeconds = 0
            for (const repo of repositories) {
              if (prescanResults[repo]) {
                const estSeconds = parseEstimatedTime(prescanResults[repo].estimated_time)
                if (estSeconds) totalSeconds += estSeconds
              }
            }
            if (totalSeconds > 0) {
              setSyncEstimatedSeconds(totalSeconds)
              console.log(`[Sync] Total estimated time for ${repositories.length} repos: ${totalSeconds}s`)
            } else {
              setSyncEstimatedSeconds(null)
            }
          } else if (repository && prescanResults && prescanResults[repository]) {
            // Single repo sync
            const estSeconds = parseEstimatedTime(prescanResults[repository].estimated_time)
            if (estSeconds) {
              setSyncEstimatedSeconds(estSeconds)
              console.log(`[Sync] Estimated time from prescan: ${estSeconds}s`)
            }
          } else {
            setSyncEstimatedSeconds(null)
          }

          // Close old modal if it was showing
          setShowSyncProgress(false)
          console.log('[SSE] Using new SSE-based sync progress:', response.data.sync_id)
        } else if (response.data.documents_found !== undefined) {
          // SYNCHRONOUS SYNC: Sync already completed (e.g., Zotero)
          // Show completion immediately without polling
          const docsFound = response.data.documents_found || 0
          const docsCreated = response.data.documents_created || 0
          const docsUpdated = response.data.documents_updated || 0

          setSyncProgress({
            integration: integrationId,
            status: 'completed',
            progress: 100,
            documentsFound: docsFound,
            documentsParsed: docsFound,
            documentsEmbedded: docsFound,
            startTime
          })
          setShowSyncProgress(true)
          setSyncStatus(null)

          // Mark integration as connected
          setIntegrationsState(prev =>
            prev.map(int =>
              int.id === integrationId ? { ...int, connected: true } : int
            )
          )

          console.log(`[Sync] Synchronous sync completed: ${docsCreated} created, ${docsUpdated} updated`)

          // Refresh integrations after a moment
          setTimeout(() => checkIntegrationStatuses(), 1000)
        } else {
          // FALLBACK: Use OLD polling-based progress modal
          setSyncProgress({
            integration: integrationId,
            status: 'starting',
            progress: 0,
            documentsFound: 0,
            documentsParsed: 0,
            documentsEmbedded: 0,
            startTime
          })
          setShowSyncProgress(true)
          setSyncStatus(null)
          syncPollingInterval.current = setInterval(() => pollSyncStatus(integrationId), 5000)
          console.log('[Polling] Using old polling-based progress')
        }
      } else {
        saveSyncState(null) // Clear saved state on error
        setSyncProgress(prev => prev ? {
          ...prev,
          status: 'error',
          error: response.data.error || 'Sync failed'
        } : null)
      }
    } catch (error: any) {
      console.error(`[Sync] Error:`, error)
      console.error(`[Sync] Error type:`, error.code || 'unknown')
      console.error(`[Sync] Error response:`, error.response)
      console.error(`[Sync] Error request:`, error.request ? 'Request was made' : 'No request')
      saveSyncState(null) // Clear saved state on error

      let errorMsg = 'Unknown error'
      if (error.code === 'ECONNABORTED') {
        errorMsg = 'Request timed out - the server took too long to respond'
      } else if (error.code === 'ERR_NETWORK') {
        errorMsg = 'Network error - check your connection or CORS settings'
      } else if (error.response?.data?.error) {
        errorMsg = error.response.data.error
      } else if (error.message) {
        errorMsg = error.message
      }

      console.error(`[Sync] Final error message: ${errorMsg}`)
      setSyncProgress(prev => prev ? {
        ...prev,
        status: 'error',
        error: errorMsg
      } : null)
      setSyncStatus(`Sync error: ${errorMsg}`)
    }
  }

  // Minimize sync progress modal - ALWAYS stop polling to prevent infinite loop
  const minimizeSyncProgress = () => {
    console.log('[DEBUG] minimizeSyncProgress called, syncPollingInterval:', syncPollingInterval.current)
    setShowSyncProgress(false)
    // CRITICAL FIX: Stop polling when minimizing to prevent infinite requests
    if (syncPollingInterval.current) {
      console.log('[DEBUG] Clearing interval:', syncPollingInterval.current)
      clearInterval(syncPollingInterval.current)
      syncPollingInterval.current = null
      console.log('[DEBUG] Interval cleared and set to null')
    } else {
      console.log('[DEBUG] WARNING: syncPollingInterval is null/undefined, nothing to clear!')
    }
    // Backend sync continues in background, but we stop checking status
  }

  // Close sync progress modal (hide modal but keep completed state for persistence)
  const closeSyncProgress = () => {
    setShowSyncProgress(false)
    // Don't clear syncProgress or saved state - keep it for next time modal opens
    // State will only be cleared when a new sync starts
    if (syncPollingInterval.current) {
      clearInterval(syncPollingInterval.current)
      syncPollingInterval.current = null
    }
  }

  // Smart close - minimize if in progress, full close if completed/error
  const handleSyncModalClose = () => {
    if (syncProgress && (syncProgress.status === 'completed' || syncProgress.status === 'error')) {
      closeSyncProgress()
    } else {
      minimizeSyncProgress()
    }
  }

  // Cancel sync - stop polling and reset state
  const cancelSync = () => {
    // Stop polling immediately
    if (syncPollingInterval.current) {
      clearInterval(syncPollingInterval.current)
      syncPollingInterval.current = null
    }

    // Clear saved state
    saveSyncState(null)

    // Reset progress to cancelled
    setSyncProgress(prev => prev ? {
      ...prev,
      status: 'error',
      error: 'Sync cancelled by user'
    } : null)

    setSyncStatus('Sync cancelled')
  }

  // Generic sync function (legacy - for sync buttons)
  const syncIntegration = async (integrationId: string) => {
    // For GitHub, show repository selection modal first
    if (integrationId === 'github') {
      fetchGitHubRepos()
      return
    }
    // For other integrations, use the new progress-tracking version directly
    await startSyncWithProgress(integrationId)
  }

  // Handle Slack token submission
  const submitSlackToken = async (token: string) => {
    setIsSubmittingToken(true)
    try {
      const authToken = getAuthToken()
      const response = await axios.post(
        `${API_BASE}/integrations/slack/token`,
        { access_token: token },
        { headers: { Authorization: `Bearer ${authToken}` } }
      )

      if (response.data.success) {
        setShowSlackTokenModal(false)
        setIntegrationsState(prev =>
          prev.map(int =>
            int.id === 'slack' ? { ...int, connected: true } : int
          )
        )
        setSyncStatus('Slack connected! Select channels to sync.')
        // Fetch channels and show modal
        fetchSlackChannels()
      } else {
        setSyncStatus(`Failed to connect: ${response.data.error}`)
      }
    } catch (error: any) {
      setSyncStatus(`Error: ${error.response?.data?.error || error.message}`)
    } finally {
      setIsSubmittingToken(false)
    }
  }

  const submitPubMedConfig = async (config: {
    searchQuery: string
    maxResults: number
    dateRangeYears: number
    apiKey: string
  }) => {
    setIsConfiguringPubmed(true)
    try {
      const authToken = getAuthToken()
      const response = await axios.post(
        `${API_BASE}/integrations/pubmed/configure`,
        {
          search_query: config.searchQuery,
          max_results: config.maxResults,
          date_range_years: config.dateRangeYears,
          include_abstracts_only: true,
          api_key: config.apiKey || undefined
        },
        { headers: { Authorization: `Bearer ${authToken}` } }
      )

      if (response.data.success) {
        setShowPubMedModal(false)
        setIntegrationsState(prev =>
          prev.map(int =>
            int.id === 'pubmed' ? { ...int, connected: true } : int
          )
        )
        setSyncStatus('PubMed configured! Searching and syncing papers...')
        // Auto-sync starts on backend, poll for progress
        setTimeout(() => startSyncWithProgress('pubmed'), 500)
      } else {
        setSyncStatus(`Failed to configure PubMed: ${response.data.error}`)
      }
    } catch (error: any) {
      setSyncStatus(`Error: ${error.response?.data?.error || error.message}`)
    } finally {
      setIsConfiguringPubmed(false)
    }
  }

  const submitWebScraperConfig = async (config: {
    startUrl: string
    priorityPaths: string[]
  }) => {
    setIsConfiguringWebscraper(true)
    try {
      const authToken = getAuthToken()
      const response = await axios.post(
        `${API_BASE}/integrations/webscraper/configure`,
        {
          start_url: config.startUrl,
          priority_paths: config.priorityPaths,
        },
        { headers: { Authorization: `Bearer ${authToken}` } }
      )

      if (response.data.success) {
        setShowWebScraperModal(false)
        // Update local state with configured URL
        setWebscraperUrl(config.startUrl)
        setIntegrationsState(prev =>
          prev.map(int =>
            int.id === 'webscraper' ? { ...int, connected: true } : int
          )
        )
        setSyncStatus('Website configured! Starting crawl...')
        // Auto-sync starts on backend, poll for progress
        setTimeout(() => startSyncWithProgress('webscraper'), 500)
      } else {
        setSyncStatus(`Failed to configure Website Scraper: ${response.data.error}`)
      }
    } catch (error: any) {
      setSyncStatus(`Error: ${error.response?.data?.error || error.message}`)
    } finally {
      setIsConfiguringWebscraper(false)
    }
  }

  const toggleConnect = async (id: string) => {
    const integration = integrationsState.find(i => i.id === id)

    // Handle CANCEL SYNC: if this integration is currently syncing, stop it
    // Only consider it "syncing" if it's actually connected - stale backgroundSyncs
    // entries should not block the Connect button for disconnected integrations
    const isSyncingThis = (syncingConnector === id || !!backgroundSyncs[id]) && integration?.connected
    if (isSyncingThis) {
      console.log(`[Sync] User clicked Stop Sync for: ${id}`)
      try {
        const token = getAuthToken()
        // Determine the actual connector type for the API call
        // (gdocs/gsheets/gslides use gdrive, excel/powerpoint use onedrive)
        let cancelType = id
        if (['gdocs', 'gsheets', 'gslides'].includes(id)) cancelType = 'gdrive'
        if (['excel', 'powerpoint'].includes(id)) cancelType = 'onedrive'

        await axios.post(
          `${API_BASE}/integrations/${cancelType}/sync/cancel`,
          {},
          { headers: { Authorization: `Bearer ${token}` } }
        )
        console.log(`[Sync] Cancel API called for ${cancelType}`)
      } catch (err) {
        console.error('[Sync] Cancel API error (non-fatal):', err)
      }

      // Reset frontend state
      if (syncingConnector === id) {
        setSyncId(null)
        setSyncingConnector(null)
        setSyncEstimatedSeconds(null)
      }

      // Clear from background syncs
      setBackgroundSyncs(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })

      // Clear saved sync state
      saveSyncState(null)

      // Stop polling if any
      if (syncPollingInterval.current) {
        clearInterval(syncPollingInterval.current)
        syncPollingInterval.current = null
      }

      setSyncStatus('Sync cancelled')
      setTimeout(() => setSyncStatus(null), 3000)

      // Refresh integration statuses to pick up the reset connector status
      setTimeout(() => checkIntegrationStatuses(), 500)
      return
    }

    // Handle Email Forwarding
    if (id === 'email-forwarding') {
      if (integration?.connected) {
        await disconnectIntegration(id)
      } else {
        setShowEmailForwardingModal(true)
      }
      return
    }

    // Handle PubMed configuration
    if (id === 'pubmed') {
      if (integration?.connected) {
        await disconnectIntegration(id)
      } else {
        setShowPubMedModal(true)
      }
      return
    }

    // Handle WebScraper configuration
    if (id === 'webscraper') {
      if (integration?.connected) {
        await disconnectIntegration(id)
      } else {
        setShowWebScraperModal(true)
      }
      return
    }

    // Handle ResearchGate and Google Scholar (not implemented)
    if (id === 'researchgate' || id === 'googlescholar') {
      const name = id === 'researchgate' ? 'ResearchGate' : 'Google Scholar'
      setSyncStatus(
        `${name} does not provide a public API. Please use PubMed or manual exports instead.`
      )
      setTimeout(() => setSyncStatus(null), 5000)
      return
    }

    // Handle Excel and PowerPoint - use Microsoft 365 (OneDrive) OAuth
    if (id === 'excel' || id === 'powerpoint') {
      if (integration?.connected) {
        await disconnectIntegration('onedrive') // Disconnect from OneDrive
      } else {
        await connectOAuth('onedrive') // Use OneDrive OAuth
      }
      return
    }

    // Handle Google Docs, Sheets, Slides - use Google Drive OAuth
    if (id === 'gdocs' || id === 'gsheets' || id === 'gslides') {
      if (integration?.connected) {
        await disconnectIntegration('gdrive') // Disconnect from gdrive
      } else {
        await connectOAuth('gdrive') // Use gdrive OAuth
      }
      return
    }

    // Handle OAuth integrations (Slack, Gmail, Box, etc.)
    if (integration?.isOAuth) {
      if (integration.connected) {
        await disconnectIntegration(id)
      } else {
        await connectOAuth(id)
      }
      return
    }

    // Handle other integrations (placeholder - show coming soon)
    setSyncStatus(`${integration?.name || id} integration coming soon!`)
  }
  
  // Open integration details modal
  const openDetailsModal = (integration: Integration) => {
    setSelectedIntegration(integration)
    setShowDetailsModal(true)
  }

  const getFilteredIntegrations = () => {
    if (activeTab === 'All Integrations') return integrationsState
    return integrationsState.filter(i => i.category === activeTab)
  }

  const filteredIntegrations = getFilteredIntegrations()

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#FFFFFF' }}>
      {/* Sidebar */}
      <Sidebar userName={user?.full_name?.split(' ')[0] || 'User'} />

      {/* Main Content */}
      <div style={{ flex: 1, padding: '32px 48px' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <h1
            style={{
              color: '#111827',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              fontSize: '32px',
              fontWeight: 700,
              lineHeight: '40px',
              marginBottom: '8px'
            }}
          >
            Integrations
          </h1>
          <p
            style={{
              color: '#6B7280',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              fontSize: '16px',
              fontWeight: 400,
              lineHeight: '24px'
            }}
          >
            Connect your tools and services to build your knowledge base
          </p>
          {/* Test Sync Button - for demo purposes */}
          <button
            onClick={async () => {
              const token = localStorage.getItem('accessToken')
              if (!token) {
                alert('Please login first')
                return
              }
              try {
                const response = await fetch(`${API_BASE}/sync-progress/test/start`, {
                  method: 'POST',
                  headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                  },
                  body: JSON.stringify({ connector_type: 'github' })
                })
                const data = await response.json()
                if (data.success && data.sync_id) {
                  globalStartSync(data.sync_id, 'github')
                  alert('Test sync started! Navigate to another page to see the persistent indicator.')
                }
              } catch (err) {
                console.error('Test sync error:', err)
              }
            }}
            style={{
              marginTop: '16px',
              padding: '10px 20px',
              borderRadius: '8px',
              border: '2px dashed #9CA3AF',
              backgroundColor: '#F9FAFB',
              color: '#6B7280',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Start Test Sync (Demo)
          </button>
        </div>

        {/* Tabs */}
        <div style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {categories.map(category => (
              <button
                key={category}
                onClick={() => setActiveTab(category)}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: activeTab === category ? '2px solid #2563EB' : '1px solid #E5E7EB',
                  backgroundColor: activeTab === category ? '#EFF6FF' : '#FFFFFF',
                  color: activeTab === category ? '#2563EB' : '#374151',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  fontSize: '14px',
                  fontWeight: activeTab === category ? 600 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                {category}
                {category === 'All Integrations' && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '24px',
                      height: '24px',
                      borderRadius: '12px',
                      backgroundColor: activeTab === category ? '#2563EB' : '#E5E7EB',
                      color: activeTab === category ? '#FFFFFF' : '#374151',
                      fontSize: '12px',
                      fontWeight: 600
                    }}
                  >
                    {integrationsState.length}
                  </span>
                )}
              </button>
            ))}

          </div>
        </div>

        {/* Integrations Grid */}
        <div>
          {/* Status Message */}
          {syncStatus && (
            <div
              className="mb-4 p-4 rounded-lg"
              style={{
                width: '100%',
                backgroundColor: syncStatus.includes('error') || syncStatus.includes('failed') || syncStatus.includes('Failed')
                  ? '#FEE2E2'
                  : syncStatus.includes('Syncing')
                    ? '#FEF3C7'
                    : '#D1FAE5',
                border: '1px solid',
                borderColor: syncStatus.includes('error') || syncStatus.includes('failed') || syncStatus.includes('Failed')
                  ? '#FCA5A5'
                  : syncStatus.includes('Syncing')
                    ? '#FCD34D'
                    : '#6EE7B7'
              }}
            >
              <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '14px' }}>
                {syncStatus}
              </p>
            </div>
          )}

          <div
            className="grid grid-cols-3 gap-0"
            style={{
              width: '100%',
              border: '1px solid #D4D4D8',
              borderRadius: '12px',
              overflow: 'hidden',
              display: 'grid'
            }}
          >
            {filteredIntegrations.map(integration => (
              <IntegrationCard
                key={integration.id}
                integration={integration}
                onToggleConnect={toggleConnect}
                onViewDetails={openDetailsModal}
                onSync={syncIntegration}
                isSyncing={syncProgress?.integration === integration.id && syncProgress?.status !== 'completed' && syncProgress?.status !== 'error'}
                syncingIntegration={syncingConnector || (backgroundSyncs[integration.id] ? integration.id : undefined) || (syncProgress?.status === 'syncing' ? syncProgress?.integration : undefined)}
              />
            ))}
          </div>

          {/* Terms and Conditions */}
          <div className="mt-12 text-center">
            <a
              href="/terms"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#71717A',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                textDecoration: 'underline'
              }}
            >
              Read our terms and Conditions ↗
            </a>
          </div>
        </div>
      </div>

      {/* Slack Token Input Modal */}
      <SlackTokenModal
        isOpen={showSlackTokenModal}
        onClose={() => setShowSlackTokenModal(false)}
        onSubmit={submitSlackToken}
        isLoading={isSubmittingToken}
      />

      {/* PubMed Configuration Modal */}
      <PubMedConfigModal
        isOpen={showPubMedModal}
        onClose={() => setShowPubMedModal(false)}
        onSubmit={submitPubMedConfig}
        isLoading={isConfiguringPubmed}
      />

      {/* WebScraper Configuration Modal */}
      <WebScraperConfigModal
        isOpen={showWebScraperModal}
        onClose={() => setShowWebScraperModal(false)}
        onSubmit={submitWebScraperConfig}
        isLoading={isConfiguringWebscraper}
        existingUrl={webscraperUrl}
      />

      {/* Email Forwarding Modal */}
      {showEmailForwardingModal && (
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
          onClick={() => setShowEmailForwardingModal(false)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              padding: '32px',
              maxWidth: '600px',
              width: '90%',
              maxHeight: '80vh',
              overflow: 'auto',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '24px', fontWeight: '600', color: '#111827' }}>Email Forwarding</h2>
              <button
                onClick={() => setShowEmailForwardingModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: '#71717A'
                }}
              >
                ×
              </button>
            </div>
            <EmailForwardingCard />
          </div>
        </div>
      )}

      {/* Slack Channel Selection Modal */}
      <ChannelSelectionModal
        isOpen={showChannelModal}
        onClose={() => setShowChannelModal(false)}
        channels={slackChannels}
        onSave={saveSlackChannels}
        isLoading={loadingChannels}
      />

      {/* GitHub Repository Selection Modal */}
      {showGitHubRepoModal && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            background: '#fff', borderRadius: 16,
            width: 500, maxWidth: '90vw', maxHeight: '80vh',
            boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
            overflow: 'hidden', display: 'flex', flexDirection: 'column'
          }}>
            {/* Header */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #E5E7EB' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <img src="/github.png" alt="GitHub" style={{ width: 32, height: 32 }} />
                  <div>
                    <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Select Repositories</h2>
                    <p style={{ margin: '2px 0 0', fontSize: 13, color: '#6B7280' }}>
                      Choose which repositories to sync
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowGitHubRepoModal(false)}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    border: '1px solid #E5E7EB', background: '#fff',
                    cursor: 'pointer', fontSize: 16, color: '#6B7280'
                  }}
                >
                  ×
                </button>
              </div>
            </div>

            {/* Repository List */}
            <div style={{ padding: '16px 24px', overflowY: 'auto', flex: 1 }}>
              {loadingRepos ? (
                <div style={{ textAlign: 'center', padding: 40, color: '#6B7280' }}>
                  Loading repositories...
                </div>
              ) : githubRepos.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 40, color: '#6B7280' }}>
                  No repositories found
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {/* Select All */}
                  <label style={{
                    display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
                    background: '#F9FAFB', borderRadius: 8, cursor: 'pointer',
                    border: '1px solid #E5E7EB'
                  }}>
                    <input
                      type="checkbox"
                      checked={selectedRepos.length === githubRepos.length}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedRepos(githubRepos.map(r => r.full_name))
                        } else {
                          setSelectedRepos([])
                        }
                      }}
                      style={{ width: 18, height: 18 }}
                    />
                    <span style={{ fontWeight: 600, fontSize: 14 }}>
                      Select All ({githubRepos.length} repositories)
                    </span>
                  </label>

                  {/* Repository Items */}
                  {githubRepos.map(repo => (
                    <label
                      key={repo.full_name}
                      style={{
                        display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 16px',
                        background: selectedRepos.includes(repo.full_name) ? '#EFF6FF' : '#fff',
                        borderRadius: 8, cursor: 'pointer',
                        border: selectedRepos.includes(repo.full_name) ? '1px solid #BFDBFE' : '1px solid #E5E7EB',
                        transition: 'all 0.15s'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedRepos.includes(repo.full_name)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedRepos(prev => [...prev, repo.full_name])
                          } else {
                            setSelectedRepos(prev => prev.filter(r => r !== repo.full_name))
                          }
                        }}
                        style={{ width: 18, height: 18, marginTop: 2 }}
                      />
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>
                            {repo.full_name}
                          </span>
                          {repo.private && (
                            <span style={{
                              fontSize: 11, padding: '2px 6px', borderRadius: 4,
                              background: '#FEF3C7', color: '#D97706'
                            }}>
                              Private
                            </span>
                          )}
                        </div>
                        {repo.description && (
                          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#6B7280' }}>
                            {repo.description}
                          </p>
                        )}
                        <p style={{ margin: '4px 0 0', fontSize: 11, color: '#9CA3AF' }}>
                          Updated {new Date(repo.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Scan Results / Estimated Time */}
            {totalEstimate && (
              <div style={{
                padding: '14px 24px', borderTop: '1px solid #E5E7EB',
                background: '#FAFBFC',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 28
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: 6,
                    background: '#3B82F6',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <FileText size={12} color="white" strokeWidth={2.5} />
                  </div>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: '#000' }}>{totalEstimate.files.toLocaleString()}</div>
                    <div style={{ fontSize: 10, color: '#6B7280', fontWeight: 500 }}>documents to create</div>
                  </div>
                </div>
                <div style={{ width: 1, height: 28, background: '#E5E7EB' }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: 6,
                    background: '#1E293B',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <Clock size={12} color="white" strokeWidth={2.5} />
                  </div>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: '#000' }}>{totalEstimate.time}</div>
                    <div style={{ fontSize: 10, color: '#6B7280', fontWeight: 500 }}>estimated time</div>
                  </div>
                </div>
              </div>
            )}

            {/* Per-repo scan results */}
            {prescanResults && Object.keys(prescanResults).length > 0 && (
              <div style={{ padding: '12px 24px', borderTop: '1px solid #E5E7EB', background: '#FAFAFA' }}>
                <div style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                  Per Repository
                </div>
                {Object.entries(prescanResults).map(([repo, data]) => (
                  <div key={repo} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    fontSize: 13, padding: '8px 12px', marginBottom: 4,
                    background: '#fff', borderRadius: 6, border: '1px solid #E5E7EB'
                  }}>
                    <span style={{ color: '#374151', fontWeight: 500 }}>{repo.split('/')[1]}</span>
                    <span style={{ color: '#6B7280', fontSize: 12 }}>
                      {data.expected_documents} documents • {data.estimated_time}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Footer */}
            <div style={{
              padding: '16px 24px', borderTop: '1px solid #E5E7EB',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <span style={{ fontSize: 13, color: '#6B7280' }}>
                {selectedRepos.length} selected
              </span>
              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  onClick={() => {
                    setShowGitHubRepoModal(false)
                    setPrescanResults(null)
                    setTotalEstimate(null)
                  }}
                  style={{
                    padding: '10px 20px', borderRadius: 8,
                    border: '1px solid #E5E7EB', background: '#fff',
                    cursor: 'pointer', fontSize: 14, fontWeight: 500
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={isDemoMode ? demoScan : prescanSelectedRepos}
                  disabled={selectedRepos.length === 0 || isScanning}
                  style={{
                    padding: '10px 20px', borderRadius: 8,
                    border: '1px solid #E5E7EB',
                    background: selectedRepos.length === 0 || isScanning ? '#F3F4F6' : '#fff',
                    color: selectedRepos.length === 0 || isScanning ? '#9CA3AF' : '#374151',
                    cursor: selectedRepos.length === 0 || isScanning ? 'not-allowed' : 'pointer',
                    fontSize: 14, fontWeight: 500,
                    display: 'flex', alignItems: 'center', gap: 8
                  }}
                >
                  {isScanning && (
                    <div style={{
                      width: 14, height: 14, borderRadius: '50%',
                      border: '2px solid #E5E7EB', borderTopColor: '#3B82F6',
                      animation: 'spin 1s linear infinite'
                    }} />
                  )}
                  {isScanning ? 'Estimating...' : 'Estimate Time'}
                </button>
                <button
                  onClick={startGitHubSync}
                  disabled={selectedRepos.length === 0 || !totalEstimate}
                  style={{
                    padding: '10px 20px', borderRadius: 8,
                    border: 'none',
                    background: selectedRepos.length === 0 || !totalEstimate ? '#9CA3AF' : '#2563EB',
                    color: '#fff',
                    cursor: selectedRepos.length === 0 || !totalEstimate ? 'not-allowed' : 'pointer',
                    fontSize: 14, fontWeight: 600
                  }}
                >
                  Start Sync
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sync Progress Modal (Polling-based - Legacy) */}
      <PollingProgressModal
        isOpen={showSyncProgress}
        onClose={handleSyncModalClose}
        progress={syncProgress}
        onMinimize={minimizeSyncProgress}
        onCancel={cancelSync}
      />

      {/* Integration Details Modal */}
      <IntegrationDetailsModal
        isOpen={showDetailsModal}
        onClose={() => setShowDetailsModal(false)}
        integration={selectedIntegration}
        onConnect={toggleConnect}
        onDisconnect={disconnectIntegration}
        onSync={syncIntegration}
      />

      {/* SSE-based Sync Progress Modal (New) */}
      {syncId && syncingConnector && (
        <SyncProgressModal
          syncId={syncId}
          connectorType={syncingConnector}
          initialEstimatedSeconds={syncEstimatedSeconds || undefined}
          onCloseWhileActive={() => {
            // User closed modal while sync is still running
            // Store connector -> syncId mapping so we can re-open the modal
            if (syncingConnector && syncId) {
              setBackgroundSyncs(prev => ({
                ...prev,
                [syncingConnector]: syncId
              }))
            }
          }}
          onClose={() => {
            // Remove from background syncs if it was there
            if (syncingConnector && backgroundSyncs[syncingConnector]) {
              setBackgroundSyncs(prev => {
                const next = { ...prev }
                delete next[syncingConnector]
                return next
              })
            }
            setSyncId(null)
            setSyncingConnector(null)
            setSyncEstimatedSeconds(null)
            // Reload integrations to refresh status
            checkIntegrationStatuses()
          }}
        />
      )}

      {/* Disconnect Confirmation Modal */}
      {showDisconnectConfirm && disconnectTarget && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 10000
        }}>
          <div style={{
            background: '#fff', borderRadius: 16,
            width: 440, maxWidth: '90vw',
            boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
            overflow: 'hidden'
          }}>
            {/* Header */}
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid #FEE2E2',
              background: '#FEF2F2'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 10,
                  background: '#FEE2E2',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth="2">
                    <path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: '#991B1B' }}>
                    Confirm Disconnect
                  </h2>
                  <p style={{ margin: '2px 0 0', fontSize: 13, color: '#B91C1C' }}>
                    This action cannot be undone
                  </p>
                </div>
              </div>
            </div>

            {/* Content */}
            <div style={{ padding: '20px 24px' }}>
              <p style={{ margin: '0 0 16px', fontSize: 14, color: '#374151' }}>
                Disconnecting <strong>{disconnectTarget.charAt(0).toUpperCase() + disconnectTarget.slice(1)}</strong> will permanently delete:
              </p>

              <div style={{
                background: '#F9FAFB',
                borderRadius: 8,
                padding: 16,
                marginBottom: 16
              }}>
                {disconnectCounts && (
                  <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: 14, color: '#4B5563' }}>
                    <li style={{ marginBottom: 8 }}>
                      <strong>{disconnectCounts.document_count}</strong> documents from your knowledge base
                    </li>
                    <li style={{ marginBottom: 8 }}>
                      <strong>{disconnectCounts.gap_count}</strong> knowledge gaps related to these documents
                    </li>
                    <li>
                      All associated embeddings from the vector store
                    </li>
                  </ul>
                )}
              </div>

              <p style={{ margin: 0, fontSize: 13, color: '#6B7280' }}>
                You can reconnect this integration later, but you will need to sync all data again.
              </p>
            </div>

            {/* Footer */}
            <div style={{
              padding: '16px 24px',
              borderTop: '1px solid #E5E7EB',
              display: 'flex', justifyContent: 'flex-end', gap: 12
            }}>
              <button
                onClick={cancelDisconnect}
                disabled={isLoadingDisconnect}
                style={{
                  padding: '10px 20px', borderRadius: 8,
                  border: '1px solid #D1D5DB', background: '#fff',
                  fontSize: 14, fontWeight: 500, cursor: 'pointer',
                  color: '#374151'
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmDisconnect}
                disabled={isLoadingDisconnect}
                style={{
                  padding: '10px 20px', borderRadius: 8,
                  border: 'none', background: '#DC2626',
                  fontSize: 14, fontWeight: 500, cursor: 'pointer',
                  color: '#fff',
                  opacity: isLoadingDisconnect ? 0.7 : 1
                }}
              >
                {isLoadingDisconnect ? 'Disconnecting...' : 'Disconnect & Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
