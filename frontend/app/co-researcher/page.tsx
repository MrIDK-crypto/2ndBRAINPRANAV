'use client'

import React, { useState, useCallback } from 'react'
import UploadPanel from '@/components/co-researcher/UploadPanel'

const API_BASE = 'http://localhost:5010/api/co-researcher'

type Phase = 'upload' | 'generating' | 'tournament' | 'results'

export interface Hypothesis {
  hypothesis_id: string
  title: string
  integration_type: string
  evidence: string
  risk_level: string
  protocol_sections_affected: string[]
  implementation_steps: string[]
  confidence: number
  agent_id: string
  agent_name: string
  agent_domain: string
  agent_personality: string
  agent_color: string
  elo?: number
  wins?: number
  losses?: number
  draws?: number
}

export interface Agent {
  agent_id: string
  name: string
  domain: string
  methodology: string
  personality: string
  color: string
  description: string
  hypotheses: Hypothesis[]
  complete: boolean
  error?: string
}

export interface MatchupResult {
  round: number
  total_rounds: number
  hypothesis_a: { id: string; title: string; agent_name: string; agent_color: string }
  hypothesis_b: { id: string; title: string; agent_name: string; agent_color: string }
  winner: string
  score: string
  reasoning: string
  criteria_scores: any
}

export interface RankingEntry {
  id: string
  title: string
  agent_name: string
  agent_color: string
  elo: number
  wins: number
  losses: number
  draws: number
  pinned: boolean
}

export default function CoResearcherPage() {
  const [phase, setPhase] = useState<Phase>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [agents, setAgents] = useState<Record<string, Agent>>({})
  const [currentMatchup, setCurrentMatchup] = useState<MatchupResult | null>(null)
  const [rankings, setRankings] = useState<RankingEntry[]>([])
  const [pinned, setPinned] = useState<Set<string>>(new Set())
  const [rejected, setRejected] = useState<Set<string>>(new Set())
  const [parseProgress, setParseProgress] = useState({ progress: 0, message: '' })
  const [tournamentInfo, setTournamentInfo] = useState({ total: 0, current: 0 })
  const [finalRankings, setFinalRankings] = useState<any[]>([])
  const [report, setReport] = useState<any>(null)
  const [revisedProtocol, setRevisedProtocol] = useState<string>('')
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startStream = (sid: string) => {
    const eventSource = new EventSource(`${API_BASE}/stream/${sid}`)

    eventSource.addEventListener('parsing_status', (e) => {
      const data = JSON.parse(e.data)
      setParseProgress({ progress: data.progress, message: data.message })
    })

    eventSource.addEventListener('agent_started', (e) => {
      const data = JSON.parse(e.data)
      setAgents(prev => ({
        ...prev,
        [data.agent_id]: {
          ...data,
          hypotheses: [],
          complete: false,
        }
      }))
    })

    eventSource.addEventListener('hypothesis_generated', (e) => {
      const data = JSON.parse(e.data)
      setAgents(prev => ({
        ...prev,
        [data.agent_id]: {
          ...prev[data.agent_id],
          hypotheses: [...(prev[data.agent_id]?.hypotheses || []), data.hypothesis],
        }
      }))
    })

    eventSource.addEventListener('agent_complete', (e) => {
      const data = JSON.parse(e.data)
      setAgents(prev => ({
        ...prev,
        [data.agent_id]: {
          ...prev[data.agent_id],
          complete: true,
          error: data.error,
        }
      }))
    })

    eventSource.addEventListener('tournament_started', (e) => {
      const data = JSON.parse(e.data)
      setTournamentInfo({ total: data.total_matchups, current: 0 })
      setPhase('tournament')
    })

    eventSource.addEventListener('matchup_result', (e) => {
      const data = JSON.parse(e.data)
      setCurrentMatchup(data)
      setTournamentInfo(prev => ({ ...prev, current: data.round }))
    })

    eventSource.addEventListener('leaderboard_update', (e) => {
      const data = JSON.parse(e.data)
      setRankings(data.rankings)
    })

    eventSource.addEventListener('tournament_complete', (e) => {
      const data = JSON.parse(e.data)
      setFinalRankings(data.final_rankings)
      setPhase('results')
    })

    eventSource.addEventListener('error', (e) => {
      if (eventSource.readyState === EventSource.CLOSED) return
      try {
        const data = JSON.parse((e as any).data)
        setError(data.message)
      } catch {}
    })

    eventSource.addEventListener('pipeline_complete', () => {
      eventSource.close()
    })
  }

  const handleUpload = useCallback(async (protocolFile: File, paperFile: File) => {
    setError(null)
    const formData = new FormData()
    formData.append('protocol', protocolFile)
    formData.append('paper', paperFile)

    try {
      const resp = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: formData,
      })
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.error || 'Upload failed')
      }
      const { session_id } = await resp.json()
      setSessionId(session_id)
      setPhase('generating')
      startStream(session_id)
    } catch (e: any) {
      setError(e.message)
    }
  }, [])

  const handlePin = async (hypothesisId: string) => {
    if (!sessionId) return
    setPinned(prev => new Set([...prev, hypothesisId]))
    setRejected(prev => { const next = new Set(prev); next.delete(hypothesisId); return next })
    await fetch(`${API_BASE}/pin/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hypothesis_id: hypothesisId }),
    })
  }

  const handleReject = async (hypothesisId: string) => {
    if (!sessionId) return
    setRejected(prev => new Set([...prev, hypothesisId]))
    setPinned(prev => { const next = new Set(prev); next.delete(hypothesisId); return next })
    await fetch(`${API_BASE}/reject/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hypothesis_id: hypothesisId }),
    })
  }

  const handleGenerateReport = async () => {
    if (!sessionId) return
    setIsGeneratingReport(true)
    try {
      const resp = await fetch(`${API_BASE}/report/${sessionId}`, { method: 'POST' })
      const data = await resp.json()
      setReport(data.report)
      setRevisedProtocol(data.revised_protocol)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setIsGeneratingReport(false)
    }
  }

  const handleReset = () => {
    setPhase('upload')
    setSessionId(null)
    setAgents({})
    setCurrentMatchup(null)
    setRankings([])
    setPinned(new Set())
    setRejected(new Set())
    setParseProgress({ progress: 0, message: '' })
    setTournamentInfo({ total: 0, current: 0 })
    setFinalRankings([])
    setReport(null)
    setRevisedProtocol('')
    setError(null)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0F0F12', fontFamily: "'Inter', sans-serif" }}>
      {/* Header */}
      <div style={{
        padding: '20px 40px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, color: '#fff', fontWeight: 700,
          }}>
            C
          </div>
          <div>
            <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, letterSpacing: '-0.02em' }}>
              Co-Researcher
            </div>
            <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>
              AI-Powered Protocol Integration Engine
            </div>
          </div>
        </div>
        {phase !== 'upload' && (
          <button
            onClick={handleReset}
            style={{
              padding: '8px 16px', borderRadius: 8,
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              color: 'rgba(255,255,255,0.6)', fontSize: 13, cursor: 'pointer',
            }}
          >
            New Analysis
          </button>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div style={{
          margin: '16px 40px', padding: '12px 16px', borderRadius: 8,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#EF4444', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* Phase content */}
      <div style={{ padding: '40px' }}>
        {phase === 'upload' && (
          <UploadPanel onUpload={handleUpload} />
        )}

        {phase === 'generating' && (
          <div>
            {parseProgress.progress < 100 && (
              <div style={{ marginBottom: 32 }}>
                <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: 14, marginBottom: 8 }}>
                  {parseProgress.message}
                </div>
                <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                  <div style={{
                    height: '100%', borderRadius: 2, transition: 'width 0.5s',
                    background: 'linear-gradient(90deg, #6366F1, #8B5CF6)',
                    width: `${parseProgress.progress}%`,
                  }} />
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: 16 }}>
              {Object.values(agents).map(agent => (
                <div key={agent.agent_id} style={{
                  padding: 20, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)',
                  border: `1px solid ${agent.complete ? agent.color + '40' : 'rgba(255,255,255,0.06)'}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: '50%',
                      background: agent.complete ? agent.color : 'rgba(255,255,255,0.2)',
                      boxShadow: agent.complete ? `0 0 8px ${agent.color}60` : 'none',
                    }} />
                    <div style={{ color: '#fff', fontWeight: 600, fontSize: 15 }}>
                      Agent {agent.name}
                    </div>
                    <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12, marginLeft: 'auto' }}>
                      {agent.personality} / {agent.domain}
                    </div>
                  </div>
                  {!agent.complete && agent.hypotheses.length === 0 && (
                    <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>
                      Generating hypotheses...
                    </div>
                  )}
                  {agent.error && (
                    <div style={{ color: '#EF4444', fontSize: 13 }}>Error: {agent.error}</div>
                  )}
                  {agent.hypotheses.map((h, i) => (
                    <div key={i} style={{
                      padding: '8px 12px', marginBottom: 6, borderRadius: 8,
                      background: 'rgba(255,255,255,0.04)', fontSize: 13,
                      color: 'rgba(255,255,255,0.7)',
                    }}>
                      {h.title}
                    </div>
                  ))}
                  {agent.complete && (
                    <div style={{ color: agent.color, fontSize: 12, marginTop: 8 }}>
                      {agent.hypotheses.length} hypotheses generated
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {phase === 'tournament' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
              <div style={{ color: '#fff', fontSize: 20, fontWeight: 600 }}>Tournament</div>
              <div style={{
                padding: '4px 12px', borderRadius: 20,
                background: 'rgba(99,102,241,0.15)', color: '#818CF8', fontSize: 13,
              }}>
                Round {tournamentInfo.current} / {tournamentInfo.total}
              </div>
            </div>

            {/* Progress bar */}
            <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, marginBottom: 24 }}>
              <div style={{
                height: '100%', borderRadius: 2, transition: 'width 0.3s',
                background: 'linear-gradient(90deg, #6366F1, #8B5CF6)',
                width: `${(tournamentInfo.current / Math.max(tournamentInfo.total, 1)) * 100}%`,
              }} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>
              <div>
                {currentMatchup && (
                  <div style={{
                    padding: 24, borderRadius: 16,
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    marginBottom: 16,
                  }}>
                    <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      Current Matchup
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, alignItems: 'start' }}>
                      <div style={{
                        padding: 16, borderRadius: 12,
                        background: currentMatchup.winner === 'a' ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${currentMatchup.winner === 'a' ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.06)'}`,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: currentMatchup.hypothesis_a.agent_color }} />
                          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>{currentMatchup.hypothesis_a.agent_name}</span>
                          {currentMatchup.winner === 'a' && <span style={{ color: '#10B981', fontSize: 11, marginLeft: 'auto' }}>WINNER</span>}
                        </div>
                        <div style={{ color: '#fff', fontSize: 14 }}>{currentMatchup.hypothesis_a.title}</div>
                      </div>

                      <div style={{ color: 'rgba(255,255,255,0.2)', fontSize: 14, fontWeight: 700, alignSelf: 'center', padding: '0 8px' }}>VS</div>

                      <div style={{
                        padding: 16, borderRadius: 12,
                        background: currentMatchup.winner === 'b' ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${currentMatchup.winner === 'b' ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.06)'}`,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: currentMatchup.hypothesis_b.agent_color }} />
                          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>{currentMatchup.hypothesis_b.agent_name}</span>
                          {currentMatchup.winner === 'b' && <span style={{ color: '#10B981', fontSize: 11, marginLeft: 'auto' }}>WINNER</span>}
                        </div>
                        <div style={{ color: '#fff', fontSize: 14 }}>{currentMatchup.hypothesis_b.title}</div>
                      </div>
                    </div>

                    {currentMatchup.reasoning && (
                      <div style={{
                        marginTop: 16, padding: 12, borderRadius: 8,
                        background: 'rgba(99,102,241,0.06)',
                        border: '1px solid rgba(99,102,241,0.15)',
                      }}>
                        <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, marginBottom: 4, textTransform: 'uppercase' }}>
                          Evaluator Reasoning
                        </div>
                        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13, lineHeight: 1.5 }}>
                          {currentMatchup.reasoning}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Pin/Reject controls */}
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {rankings.slice(0, 8).map(r => (
                    <div key={r.id} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '6px 12px', borderRadius: 8,
                      background: pinned.has(r.id) ? 'rgba(16,185,129,0.1)' : rejected.has(r.id) ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.03)',
                      border: `1px solid ${pinned.has(r.id) ? 'rgba(16,185,129,0.3)' : rejected.has(r.id) ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.06)'}`,
                      fontSize: 12, color: 'rgba(255,255,255,0.6)',
                    }}>
                      <span style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.title}
                      </span>
                      <button onClick={() => handlePin(r.id)} style={{
                        background: 'none', border: 'none', cursor: 'pointer', fontSize: 14,
                        color: pinned.has(r.id) ? '#10B981' : 'rgba(255,255,255,0.3)', padding: '0 2px',
                      }} title="Pin">P</button>
                      <button onClick={() => handleReject(r.id)} style={{
                        background: 'none', border: 'none', cursor: 'pointer', fontSize: 14,
                        color: rejected.has(r.id) ? '#EF4444' : 'rgba(255,255,255,0.3)', padding: '0 2px',
                      }} title="Reject">X</button>
                    </div>
                  ))}
                </div>
              </div>

              {/* ELO Leaderboard */}
              <div style={{
                padding: 20, borderRadius: 12,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                height: 'fit-content',
              }}>
                <div style={{ color: '#fff', fontWeight: 600, fontSize: 14, marginBottom: 16 }}>
                  ELO Leaderboard
                </div>
                {rankings.map((r, i) => (
                  <div key={r.id} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 0',
                    borderBottom: i < rankings.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                  }}>
                    <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12, width: 20 }}>{i + 1}</span>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: r.agent_color }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        color: 'rgba(255,255,255,0.8)', fontSize: 12,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {r.title}
                      </div>
                      <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 11 }}>
                        {r.agent_name} | {r.wins}W-{r.losses}L
                      </div>
                    </div>
                    <span style={{
                      color: r.elo > 1200 ? '#10B981' : r.elo < 1200 ? '#EF4444' : 'rgba(255,255,255,0.4)',
                      fontSize: 13, fontWeight: 600, fontFamily: 'monospace',
                    }}>
                      {r.elo}
                    </span>
                    {r.pinned && <span style={{ color: '#10B981', fontSize: 10 }}>PIN</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {phase === 'results' && (
          <div>
            <div style={{ color: '#fff', fontSize: 24, fontWeight: 600, marginBottom: 8 }}>Results</div>
            <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, marginBottom: 32 }}>
              Top integration recommendations ranked by ELO tournament
            </div>

            <div style={{ display: 'grid', gap: 16, marginBottom: 32 }}>
              {finalRankings.map((r: any, i: number) => (
                <div key={r.id} style={{
                  padding: 24, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)',
                  border: `1px solid ${i === 0 ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)'}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: i === 0 ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.06)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: i === 0 ? '#818CF8' : 'rgba(255,255,255,0.4)', fontSize: 13, fontWeight: 700,
                    }}>
                      {i + 1}
                    </div>
                    <div style={{ color: '#fff', fontSize: 16, fontWeight: 500, flex: 1 }}>{r.title}</div>
                    <div style={{
                      padding: '4px 10px', borderRadius: 6,
                      background: 'rgba(255,255,255,0.06)',
                      color: 'rgba(255,255,255,0.5)', fontSize: 13, fontFamily: 'monospace',
                    }}>
                      ELO {r.elo}
                    </div>
                  </div>
                  <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>
                    Agent {r.agent_name} | {r.wins}W-{r.losses}L
                  </div>
                </div>
              ))}
            </div>

            {!report && (
              <button
                onClick={handleGenerateReport}
                disabled={isGeneratingReport}
                style={{
                  padding: '12px 24px', borderRadius: 10,
                  background: isGeneratingReport ? 'rgba(99,102,241,0.3)' : 'linear-gradient(135deg, #6366F1, #8B5CF6)',
                  border: 'none', color: '#fff', fontSize: 14, fontWeight: 500,
                  cursor: isGeneratingReport ? 'not-allowed' : 'pointer',
                }}
              >
                {isGeneratingReport ? 'Generating Report...' : 'Generate Integration Report & Revised Protocol'}
              </button>
            )}

            {report && (
              <div style={{ marginTop: 32 }}>
                <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Integration Report</div>
                <div style={{
                  padding: 24, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
                  color: 'rgba(255,255,255,0.7)', fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap',
                }}>
                  {report.report_markdown}
                </div>
              </div>
            )}

            {revisedProtocol && (
              <div style={{ marginTop: 32 }}>
                <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Revised Protocol</div>
                <div style={{
                  padding: 24, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
                  color: 'rgba(255,255,255,0.7)', fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap',
                }}>
                  {revisedProtocol}
                </div>
              </div>
            )}

            <button onClick={handleReset} style={{
              marginTop: 24, padding: '10px 20px', borderRadius: 8,
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              color: 'rgba(255,255,255,0.6)', fontSize: 13, cursor: 'pointer',
            }}>
              Start New Analysis
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
