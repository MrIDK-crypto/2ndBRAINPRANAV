'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '@/components/shared/Sidebar'
import { useAuth } from '@/contexts/AuthContext'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

const colors = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
  accent: '#7B9EBD',
}

interface Metrics {
  overview: {
    total_users: number
    total_documents: number
    embedded_documents: number
    total_conversations: number
    total_messages: number
    total_gaps: number
    answered_gaps: number
    embedding_coverage: number
    gap_resolution_rate: number
  }
  chat: {
    conversations_last_period: number
    messages_last_period: number
    questions_asked: number
    avg_messages_per_conversation: number
  }
  documents: {
    added_last_period: number
    by_source: Record<string, number>
    by_classification: Record<string, number>
  }
  knowledge_gaps: {
    detected_last_period: number
    by_category: Record<string, number>
  }
  integrations: Array<{
    type: string
    status: string
    last_synced: string | null
    documents_synced: number
  }>
  activity_timeline: Array<{
    date: string
    questions_asked: number
    documents_added: number
  }>
  period_days: number
}

export default function AnalyticsPage() {
  const { user, token } = useAuth()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState(30)

  useEffect(() => {
    if (token) {
      fetchMetrics()
    }
  }, [token, period])

  const fetchMetrics = async () => {
    setLoading(true)
    try {
      const response = await axios.get(`${API_BASE}/admin/analytics?days=${period}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.data.success) {
        setMetrics(response.data.metrics)
      }
    } catch (error) {
      console.error('Error fetching analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  const StatCard = ({ title, value, subtitle, icon }: { title: string; value: string | number; subtitle?: string; icon: React.ReactNode }) => (
    <div style={{
      padding: '24px',
      backgroundColor: colors.cardBg,
      borderRadius: '16px',
      border: `1px solid ${colors.border}`,
      display: 'flex',
      alignItems: 'flex-start',
      gap: '16px',
    }}>
      <div style={{
        width: '48px',
        height: '48px',
        borderRadius: '12px',
        backgroundColor: colors.primaryLight,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        color: colors.primary,
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: '28px', fontWeight: 700, color: colors.textPrimary, lineHeight: 1.2 }}>
          {value}
        </div>
        <div style={{ fontSize: '14px', fontWeight: 500, color: colors.textSecondary, marginTop: '4px' }}>
          {title}
        </div>
        {subtitle && (
          <div style={{ fontSize: '12px', color: colors.textMuted, marginTop: '2px' }}>
            {subtitle}
          </div>
        )}
      </div>
    </div>
  )

  const BarChart = ({ data, maxHeight = 120 }: { data: Array<{ label: string; value: number }>; maxHeight?: number }) => {
    const maxVal = Math.max(...data.map(d => d.value), 1)
    return (
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: `${maxHeight}px` }}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
            <div style={{
              width: '100%',
              maxWidth: '24px',
              height: `${Math.max((d.value / maxVal) * maxHeight, 2)}px`,
              backgroundColor: colors.primary,
              borderRadius: '4px 4px 0 0',
              transition: 'height 0.3s ease',
            }} />
            <span style={{ fontSize: '9px', color: colors.textMuted, whiteSpace: 'nowrap' }}>
              {d.label}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: colors.pageBg }}>
      <Sidebar userName={user?.full_name?.split(' ')[0] || 'User'} />

      <div style={{ flex: 1, padding: '32px', overflow: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 700, color: colors.textPrimary, margin: 0 }}>
            Analytics & Metrics
          </h1>
          <div style={{ display: 'flex', gap: '8px' }}>
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setPeriod(d)}
                style={{
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: period === d ? 600 : 400,
                  backgroundColor: period === d ? colors.primaryLight : 'transparent',
                  border: `1px solid ${period === d ? colors.primary : colors.border}`,
                  borderRadius: '8px',
                  color: period === d ? colors.primary : colors.textSecondary,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '80px' }}>
            <div style={{
              width: '40px', height: '40px',
              border: `3px solid ${colors.border}`,
              borderTop: `3px solid ${colors.primary}`,
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
            }} />
            <style jsx>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
          </div>
        ) : metrics ? (
          <>
            {/* Overview Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '32px' }}>
              <StatCard
                title="Questions Asked"
                value={metrics.chat.questions_asked}
                subtitle={`Last ${period} days`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>}
              />
              <StatCard
                title="Documents"
                value={metrics.overview.total_documents}
                subtitle={`${metrics.overview.embedding_coverage}% indexed`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>}
              />
              <StatCard
                title="Knowledge Gaps"
                value={metrics.overview.total_gaps}
                subtitle={`${metrics.overview.gap_resolution_rate}% resolved`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>}
              />
              <StatCard
                title="Conversations"
                value={metrics.overview.total_conversations}
                subtitle={`Avg ${metrics.chat.avg_messages_per_conversation} msgs each`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>}
              />
            </div>

            {/* Activity Timeline */}
            <div style={{
              padding: '28px',
              backgroundColor: colors.cardBg,
              borderRadius: '16px',
              border: `1px solid ${colors.border}`,
              marginBottom: '24px',
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 20px' }}>
                Activity Timeline (Last {period} Days)
              </h3>
              <BarChart
                data={metrics.activity_timeline.map(d => ({
                  label: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                  value: d.questions_asked + d.documents_added,
                }))}
              />
              <div style={{ display: 'flex', gap: '16px', marginTop: '12px', justifyContent: 'center' }}>
                <span style={{ fontSize: '12px', color: colors.textMuted, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '2px', backgroundColor: colors.primary }} />
                  Questions + Documents per day
                </span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
              {/* Document Sources */}
              <div style={{
                padding: '28px',
                backgroundColor: colors.cardBg,
                borderRadius: '16px',
                border: `1px solid ${colors.border}`,
              }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 20px' }}>
                  Documents by Source
                </h3>
                {Object.entries(metrics.documents.by_source).length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {Object.entries(metrics.documents.by_source)
                      .sort((a, b) => b[1] - a[1])
                      .map(([source, count]) => {
                        const pct = Math.round((count / metrics!.overview.total_documents) * 100)
                        return (
                          <div key={source}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                              <span style={{ fontSize: '13px', fontWeight: 500, color: colors.textPrimary, textTransform: 'capitalize' }}>{source}</span>
                              <span style={{ fontSize: '13px', color: colors.textMuted }}>{count} ({pct}%)</span>
                            </div>
                            <div style={{ height: '6px', backgroundColor: '#F0EEEC', borderRadius: '3px', overflow: 'hidden' }}>
                              <div style={{ width: `${pct}%`, height: '100%', backgroundColor: colors.primary, borderRadius: '3px', transition: 'width 0.3s' }} />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                ) : (
                  <p style={{ fontSize: '14px', color: colors.textMuted }}>No documents yet</p>
                )}
              </div>

              {/* Integrations Status */}
              <div style={{
                padding: '28px',
                backgroundColor: colors.cardBg,
                borderRadius: '16px',
                border: `1px solid ${colors.border}`,
              }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 20px' }}>
                  Connected Integrations
                </h3>
                {metrics.integrations.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {metrics.integrations.map((integration, idx) => (
                      <div key={idx} style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px',
                        backgroundColor: '#F8F8F6',
                        borderRadius: '10px',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            backgroundColor: integration.status === 'connected' ? colors.success : colors.textMuted,
                          }} />
                          <span style={{ fontSize: '14px', fontWeight: 500, color: colors.textPrimary, textTransform: 'capitalize' }}>
                            {integration.type}
                          </span>
                        </div>
                        <span style={{ fontSize: '12px', color: colors.textMuted }}>
                          {integration.documents_synced} docs
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: '14px', color: colors.textMuted }}>No integrations connected</p>
                )}
              </div>
            </div>

            {/* Gap Categories */}
            {Object.keys(metrics.knowledge_gaps.by_category).length > 0 && (
              <div style={{
                padding: '28px',
                backgroundColor: colors.cardBg,
                borderRadius: '16px',
                border: `1px solid ${colors.border}`,
              }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 20px' }}>
                  Knowledge Gaps by Category
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                  {Object.entries(metrics.knowledge_gaps.by_category)
                    .sort((a, b) => b[1] - a[1])
                    .map(([category, count]) => (
                      <div key={category} style={{
                        padding: '8px 16px',
                        backgroundColor: colors.primaryLight,
                        borderRadius: '20px',
                        fontSize: '13px',
                        fontWeight: 500,
                        color: colors.primary,
                      }}>
                        {category}: {count}
                      </div>
                    ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '80px', color: colors.textMuted }}>
            No analytics data available
          </div>
        )}
      </div>
    </div>
  )
}
