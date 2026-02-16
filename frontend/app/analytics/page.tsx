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
  slack_bot: {
    questions_asked: number
    answered: number
    no_results: number
    answer_rate: number
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

function generateEmptyTimeline(days: number): Array<{ date: string; questions_asked: number; documents_added: number }> {
  const timeline = []
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    timeline.push({
      date: d.toISOString().split('T')[0],
      questions_asked: 0,
      documents_added: 0,
    })
  }
  return timeline
}

const emptyMetrics = (days: number): Metrics => ({
  overview: {
    total_users: 0,
    total_documents: 0,
    embedded_documents: 0,
    total_conversations: 0,
    total_messages: 0,
    total_gaps: 0,
    answered_gaps: 0,
    embedding_coverage: 0,
    gap_resolution_rate: 0,
  },
  chat: {
    conversations_last_period: 0,
    messages_last_period: 0,
    questions_asked: 0,
    avg_messages_per_conversation: 0,
  },
  documents: {
    added_last_period: 0,
    by_source: {},
    by_classification: {},
  },
  knowledge_gaps: {
    detected_last_period: 0,
    by_category: {},
  },
  slack_bot: {
    questions_asked: 0,
    answered: 0,
    no_results: 0,
    answer_rate: 0,
  },
  integrations: [],
  activity_timeline: generateEmptyTimeline(days),
  period_days: days,
})

const ALLOWED_EMAIL = 'pranav@use2ndbrain.com'

interface TenantOption {
  id: string
  name: string
  slug: string
  user_count: number
}

export default function AnalyticsPage() {
  const { user, token } = useAuth()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState(30)
  const [tenants, setTenants] = useState<TenantOption[]>([])
  const [selectedTenant, setSelectedTenant] = useState<string>('')
  const [apiError, setApiError] = useState<string | null>(null)

  const isSuperAdmin = user?.email === ALLOWED_EMAIL

  useEffect(() => {
    if (token && isSuperAdmin) {
      fetchTenants()
    }
  }, [token, isSuperAdmin])

  useEffect(() => {
    if (token) {
      fetchMetrics()
    } else {
      setLoading(false)
    }
  }, [token, period, selectedTenant])

  const fetchTenants = async () => {
    try {
      const response = await axios.get(`${API_BASE}/admin/tenants`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.data.success) {
        setTenants(response.data.tenants)
      }
    } catch (error) {
      console.error('Error fetching tenants:', error)
    }
  }

  const fetchMetrics = async () => {
    setLoading(true)
    setApiError(null)
    try {
      let url = `${API_BASE}/admin/analytics?days=${period}`
      if (selectedTenant) {
        url += `&tenant_id=${selectedTenant}`
      }
      const response = await axios.get(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.data.success) {
        setMetrics(response.data.metrics)
      } else {
        setApiError(response.data.error || 'API returned unsuccessful response')
        setMetrics(null)
      }
    } catch (error: any) {
      const errMsg = error.response?.data?.error || error.response?.data?.debug?.traceback || error.message || 'Unknown error'
      const status = error.response?.status || 'no status'
      setApiError(`${status}: ${errMsg}`)
      console.error('Analytics API error:', status, error.response?.data || error.message)
      setMetrics(null)
    } finally {
      setLoading(false)
    }
  }

  // Always use real metrics if available, otherwise show zeroed-out layout
  const m = metrics || emptyMetrics(period)

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
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {/* Tenant Selector - Super admin only */}
            {isSuperAdmin && tenants.length > 0 && (
              <select
                value={selectedTenant}
                onChange={(e) => setSelectedTenant(e.target.value)}
                style={{
                  padding: '8px 12px',
                  fontSize: '13px',
                  fontWeight: 500,
                  backgroundColor: colors.cardBg,
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  color: colors.textPrimary,
                  cursor: 'pointer',
                  outline: 'none',
                  minWidth: '160px',
                }}
              >
                <option value="">My Tenant</option>
                {tenants.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.user_count} users)
                  </option>
                ))}
              </select>
            )}

            {/* Period Selector */}
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
        ) : (
          <>
            {/* API Error Banner */}
            {apiError && (
              <div style={{
                padding: '12px 16px',
                backgroundColor: '#FEF2F2',
                border: '1px solid #FECACA',
                borderRadius: '10px',
                marginBottom: '20px',
                fontSize: '13px',
                color: '#991B1B',
              }}>
                Unable to load analytics: {apiError}
              </div>
            )}
            {/* Overview Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '32px' }}>
              <StatCard
                title="Questions Asked"
                value={m.chat.questions_asked}
                subtitle={`Last ${period} days`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>}
              />
              <StatCard
                title="Documents"
                value={m.overview.total_documents}
                subtitle={`${m.overview.embedding_coverage}% indexed`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>}
              />
              <StatCard
                title="Knowledge Gaps"
                value={m.overview.total_gaps}
                subtitle={`${m.overview.gap_resolution_rate}% resolved`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>}
              />
              <StatCard
                title="Conversations"
                value={m.overview.total_conversations}
                subtitle={`Avg ${m.chat.avg_messages_per_conversation} msgs each`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>}
              />
            </div>

            {/* Second row of stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '32px' }}>
              <StatCard
                title="Total Users"
                value={m.overview.total_users}
                subtitle="Active accounts"
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>}
              />
              <StatCard
                title="Total Messages"
                value={m.overview.total_messages}
                subtitle={`${m.chat.messages_last_period} in last ${period}d`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>}
              />
              <StatCard
                title="Docs Added"
                value={m.documents.added_last_period}
                subtitle={`Last ${period} days`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14"/><path d="M5 12h14"/></svg>}
              />
              <StatCard
                title="Gaps Detected"
                value={m.knowledge_gaps.detected_last_period}
                subtitle={`Last ${period} days`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>}
              />
            </div>

            {/* Slack Bot Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '32px' }}>
              <StatCard
                title="Slack Bot Questions"
                value={m.slack_bot.questions_asked}
                subtitle={`Last ${period} days`}
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.5 10c-.83 0-1.5-.67-1.5-1.5v-5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5z"/><path d="M20.5 10H19V8.5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/><path d="M9.5 14c.83 0 1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5S8 21.33 8 20.5v-5c0-.83.67-1.5 1.5-1.5z"/><path d="M3.5 14H5v1.5c0 .83-.67 1.5-1.5 1.5S2 16.33 2 15.5 2.67 14 3.5 14z"/><path d="M14 14.5c0-.83.67-1.5 1.5-1.5h5c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5h-5c-.83 0-1.5-.67-1.5-1.5z"/><path d="M15.5 19H14v1.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5-.67-1.5-1.5-1.5z"/><path d="M10 9.5C10 10.33 9.33 11 8.5 11h-5C2.67 11 2 10.33 2 9.5S2.67 8 3.5 8h5c.83 0 1.5.67 1.5 1.5z"/><path d="M8.5 5H10V3.5C10 2.67 9.33 2 8.5 2S7 2.67 7 3.5 7.67 5 8.5 5z"/></svg>}
              />
              <StatCard
                title="Bot Answered"
                value={m.slack_bot.answered}
                subtitle="Had the info"
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>}
              />
              <StatCard
                title="Bot No Results"
                value={m.slack_bot.no_results}
                subtitle="Did not have info"
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>}
              />
              <StatCard
                title="Bot Answer Rate"
                value={`${m.slack_bot.answer_rate}%`}
                subtitle="Success rate"
                icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>}
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
              {m.activity_timeline.length > 0 ? (
                <BarChart
                  data={m.activity_timeline.map(d => ({
                    label: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                    value: d.questions_asked + d.documents_added,
                  }))}
                />
              ) : (
                <div style={{ height: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textMuted, fontSize: '14px' }}>
                  No activity yet
                </div>
              )}
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
                {Object.entries(m.documents.by_source).length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {Object.entries(m.documents.by_source)
                      .sort((a, b) => b[1] - a[1])
                      .map(([source, count]) => {
                        const total = m.overview.total_documents || 1
                        const pct = Math.round((count / total) * 100)
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
                  <div style={{ padding: '24px 0', textAlign: 'center' }}>
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={colors.border} strokeWidth="1.5" style={{ margin: '0 auto 12px' }}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>
                    </svg>
                    <p style={{ fontSize: '14px', color: colors.textMuted, margin: 0 }}>No documents yet</p>
                    <p style={{ fontSize: '12px', color: colors.textMuted, margin: '4px 0 0' }}>Connect an integration to start syncing</p>
                  </div>
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
                {m.integrations.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {m.integrations.map((integration, idx) => (
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
                  <div style={{ padding: '24px 0', textAlign: 'center' }}>
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={colors.border} strokeWidth="1.5" style={{ margin: '0 auto 12px' }}>
                      <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
                    </svg>
                    <p style={{ fontSize: '14px', color: colors.textMuted, margin: 0 }}>No integrations connected</p>
                    <p style={{ fontSize: '12px', color: colors.textMuted, margin: '4px 0 0' }}>Go to Integrations to connect Gmail, Slack, etc.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Knowledge Gaps by Category */}
            <div style={{
              padding: '28px',
              backgroundColor: colors.cardBg,
              borderRadius: '16px',
              border: `1px solid ${colors.border}`,
              marginBottom: '24px',
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 20px' }}>
                Knowledge Gaps by Category
              </h3>
              {Object.entries(m.knowledge_gaps.by_category).length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                  {Object.entries(m.knowledge_gaps.by_category)
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
              ) : (
                <div style={{ padding: '16px 0', textAlign: 'center' }}>
                  <p style={{ fontSize: '14px', color: colors.textMuted, margin: 0 }}>No knowledge gaps detected yet</p>
                  <p style={{ fontSize: '12px', color: colors.textMuted, margin: '4px 0 0' }}>Run a gap analysis from the Knowledge Gaps page</p>
                </div>
              )}
            </div>

            {/* Embedding Coverage */}
            <div style={{
              padding: '28px',
              backgroundColor: colors.cardBg,
              borderRadius: '16px',
              border: `1px solid ${colors.border}`,
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 20px' }}>
                Embedding Coverage
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                      {m.overview.embedded_documents} of {m.overview.total_documents} documents indexed
                    </span>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: colors.primary }}>
                      {m.overview.embedding_coverage}%
                    </span>
                  </div>
                  <div style={{ height: '8px', backgroundColor: '#F0EEEC', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${m.overview.embedding_coverage}%`,
                      height: '100%',
                      backgroundColor: colors.primary,
                      borderRadius: '4px',
                      transition: 'width 0.5s ease',
                    }} />
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '24px', marginTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: colors.success }} />
                  <span style={{ fontSize: '12px', color: colors.textMuted }}>Indexed: {m.overview.embedded_documents}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: colors.border }} />
                  <span style={{ fontSize: '12px', color: colors.textMuted }}>Pending: {m.overview.total_documents - m.overview.embedded_documents}</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
