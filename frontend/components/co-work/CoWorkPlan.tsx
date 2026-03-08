'use client'

import React from 'react'

// ── Design tokens ──
const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
  amber: '#D4A853',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

// ── Types ──
export interface PlanStep {
  section: string
  text: string
  status: 'complete' | 'in_progress' | 'pending'
}

interface CoWorkPlanProps {
  steps: PlanStep[]
}

export default function CoWorkPlan({ steps }: CoWorkPlanProps) {
  // Group steps by section
  const sections: { name: string; steps: PlanStep[] }[] = []
  const sectionMap = new Map<string, PlanStep[]>()

  for (const step of steps) {
    const key = step.section
    if (!sectionMap.has(key)) {
      sectionMap.set(key, [])
      sections.push({ name: key, steps: sectionMap.get(key)! })
    }
    sectionMap.get(key)!.push(step)
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: COLORS.cardBg,
      borderLeft: `1px solid ${COLORS.border}`,
      fontFamily: FONT,
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: `1px solid ${COLORS.border}`,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexShrink: 0,
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span style={{ fontSize: '15px', fontWeight: 600, color: COLORS.textPrimary }}>Plan</span>
      </div>

      {/* Content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
      }}>
        {steps.length === 0 ? (
          // Empty state
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            textAlign: 'center',
            gap: '12px',
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              backgroundColor: COLORS.primaryLight,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={COLORS.textMuted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                <rect x="9" y="3" width="6" height="4" rx="2" />
                <path d="M9 14l2 2 4-4" />
              </svg>
            </div>
            <p style={{
              fontSize: '13px',
              color: COLORS.textMuted,
              lineHeight: '1.5',
              maxWidth: '200px',
            }}>
              Start a conversation to generate a research plan
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {sections.map((section, sIdx) => (
              <div key={sIdx}>
                {/* Section header */}
                <div style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: COLORS.textPrimary,
                  marginBottom: '10px',
                  textTransform: 'capitalize' as const,
                }}>
                  {section.name}
                </div>

                {/* Steps */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {section.steps.map((step, stepIdx) => {
                    // Determine dot color and style
                    const isComplete = step.status === 'complete'
                    const isActive = step.status === 'in_progress'

                    return (
                      <div
                        key={stepIdx}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '10px',
                          padding: '6px 0',
                        }}
                      >
                        {/* Status dot */}
                        <div style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          flexShrink: 0,
                          marginTop: '3px',
                          ...(isComplete
                            ? { backgroundColor: COLORS.success }
                            : isActive
                              ? { backgroundColor: COLORS.amber, boxShadow: `0 0 0 3px ${COLORS.amber}20` }
                              : { backgroundColor: 'transparent', border: `2px solid ${COLORS.border}` }
                          ),
                        }} />

                        {/* Step text */}
                        <span style={{
                          fontSize: '13px',
                          lineHeight: '1.5',
                          color: isActive ? COLORS.textPrimary : COLORS.textSecondary,
                          fontWeight: isActive ? 500 : 400,
                        }}>
                          {step.text}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
