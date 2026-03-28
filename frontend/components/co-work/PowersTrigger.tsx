'use client'

import React, { useState, useRef, useEffect } from 'react'

const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  border: '#F0EEEC',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface Power {
  id: string
  label: string
  icon: string
  needsFile: boolean
  description: string
}

const POWERS: Power[] = [
  { id: 'hij', label: 'Score Manuscript', icon: '📄', needsFile: true, description: 'Evaluate your paper and match to journals' },
  { id: 'competitor_finder', label: 'Find Competitors', icon: '🔍', needsFile: false, description: 'Search for competing labs and grants' },
  { id: 'idea_reality', label: 'Validate Idea', icon: '💡', needsFile: false, description: 'Check if your idea is novel' },
  { id: 'co_researcher', label: 'Co-Researcher', icon: '🧪', needsFile: false, description: 'Brainstorm research hypotheses' },
]

interface PowersTriggerProps {
  onSelectPower: (powerId: string, file?: File) => void
  disabled?: boolean
}

export default function PowersTrigger({ onSelectPower, disabled }: PowersTriggerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [pendingPower, setPendingPower] = useState<string | null>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  const handlePowerClick = (power: Power) => {
    if (power.needsFile) {
      setPendingPower(power.id)
      fileInputRef.current?.click()
    } else {
      onSelectPower(power.id)
      setIsOpen(false)
    }
  }

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && pendingPower) {
      onSelectPower(pendingPower, file)
      setPendingPower(null)
      setIsOpen(false)
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        title="Research Powers"
        style={{
          width: '36px', height: '36px', borderRadius: '8px',
          border: `1px solid ${COLORS.border}`,
          backgroundColor: isOpen ? COLORS.primaryLight : 'transparent',
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          opacity: disabled ? 0.5 : 1, transition: 'all 0.15s ease', flexShrink: 0,
        }}
        onMouseEnter={(e) => { if (!disabled) (e.target as HTMLElement).style.backgroundColor = COLORS.primaryLight }}
        onMouseLeave={(e) => { if (!disabled && !isOpen) (e.target as HTMLElement).style.backgroundColor = 'transparent' }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
      </button>

      <input ref={fileInputRef} type="file" accept=".pdf,.doc,.docx,.txt" onChange={handleFileSelected} style={{ display: 'none' }} />

      {isOpen && (
        <div style={{
          position: 'absolute', bottom: '44px', right: '0', width: '260px',
          backgroundColor: COLORS.cardBg, borderRadius: '12px',
          border: `1px solid ${COLORS.border}`, boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
          padding: '6px', zIndex: 100, fontFamily: FONT,
        }}>
          <div style={{ padding: '8px 12px 4px', fontSize: '11px', fontWeight: 600, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Research Powers
          </div>
          {POWERS.map((power) => (
            <button
              key={power.id}
              onClick={() => handlePowerClick(power)}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px', width: '100%',
                padding: '10px 12px', border: 'none', backgroundColor: 'transparent',
                borderRadius: '8px', cursor: 'pointer', textAlign: 'left',
                transition: 'background-color 0.1s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = COLORS.primaryLight)}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <span style={{ fontSize: '18px', flexShrink: 0 }}>{power.icon}</span>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: COLORS.textPrimary, fontFamily: FONT }}>{power.label}</div>
                <div style={{ fontSize: '11px', color: COLORS.textSecondary, fontFamily: FONT, marginTop: '1px' }}>{power.description}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
