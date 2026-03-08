'use client'

import React, { useState, useRef, useCallback, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

interface TopNavProps {
  userName?: string
  onNewChat?: () => void
}

// ---------- types ----------
interface DropdownItem {
  label: string
  description: string
  href: string
  adminOnly?: boolean
  comingSoon?: boolean
}

type NavEntry = {
  kind: 'dropdown'
  id: string
  label: string
  items: DropdownItem[]
} | {
  kind: 'link'
  id: string
  label: string
  href: string
}

// ---------- nav structure ----------
const navStructure: NavEntry[] = [
  {
    kind: 'dropdown',
    id: 'uploads',
    label: 'uploads',
    items: [
      { label: 'drag & drop', description: 'Upload files by dragging them in', href: '/uploads/drag-drop' },
      { label: 'integrations', description: 'Connect external data sources', href: '/integrations', adminOnly: true },
    ],
  },
  {
    kind: 'link',
    id: 'documents',
    label: 'documents',
    href: '/documents',
  },
  {
    kind: 'link',
    id: 'co-work',
    label: 'co-work',
    href: '/co-work',
  },
  {
    kind: 'dropdown',
    id: 'more',
    label: 'more',
    items: [
      { label: 'training videos', description: 'Guided walkthroughs and tutorials', href: '/training-guides', comingSoon: true },
      { label: 'knowledge gaps', description: 'Identify missing organizational knowledge', href: '/knowledge-gaps' },
      { label: 'analytics', description: 'Usage metrics and insights', href: '/analytics', adminOnly: true },
      { label: 'inventory', description: 'Browse your indexed knowledge base', href: '/inventory' },
    ],
  },
]

// ---------- design tokens ----------
const COLORS = {
  accent: '#C9A598',
  activeBg: '#FBF4F1',
  hoverBg: '#F7F5F3',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  white: '#FFFFFF',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

// ---------- chevron icon ----------
function ChevronDown({ color = COLORS.textMuted, size = 11 }: { color?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: '2px', flexShrink: 0 }}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

// ---------- component ----------
export default function TopNav({ userName = 'User', onNewChat }: TopNavProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { user: authUser, logout } = useAuth()
  const isAdmin = authUser?.role === 'admin'
  const [showUserMenu, setShowUserMenu] = useState(false)

  // dropdown hover state
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // clean up timer on unmount
  useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    }
  }, [])

  const handleMouseEnter = useCallback((id: string) => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
    setOpenDropdown(id)
  }, [])

  const handleMouseLeave = useCallback(() => {
    closeTimerRef.current = setTimeout(() => {
      setOpenDropdown(null)
    }, 150)
  }, [])

  // helpers
  const isPathActive = (href: string) => {
    if (href === '/chat') return pathname === '/chat'
    return pathname?.startsWith(href)
  }

  const isDropdownActive = (items: DropdownItem[]) => {
    return items.some(item => {
      if (item.adminOnly && !isAdmin) return false
      return isPathActive(item.href)
    })
  }

  const filterItems = (items: DropdownItem[]) =>
    isAdmin ? items : items.filter(item => !item.adminOnly)

  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 32px',
      height: '60px',
      backgroundColor: COLORS.white,
      borderBottom: `1px solid ${COLORS.border}`,
      fontFamily: FONT,
    }}>
      {/* Left: Logo */}
      <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
        <Image src="/owl.png" alt="2nd Brain" width={42} height={42} style={{ objectFit: 'contain' }} />
        <span style={{
          fontWeight: 700,
          fontSize: '17px',
          color: COLORS.textPrimary,
          letterSpacing: '-0.3px',
        }}>
          2nd Brain
        </span>
      </Link>

      {/* Center: Nav items */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {navStructure.map((entry) => {
          if (entry.kind === 'link') {
            const active = isPathActive(entry.href)
            return (
              <Link
                key={entry.id}
                href={entry.href}
                style={{
                  padding: '7px 16px',
                  borderRadius: '8px',
                  fontSize: '14.5px',
                  fontWeight: active ? 600 : 400,
                  color: active ? COLORS.accent : COLORS.textSecondary,
                  backgroundColor: active ? COLORS.activeBg : 'transparent',
                  textDecoration: 'none',
                  transition: 'all 0.15s ease',
                  textTransform: 'lowercase' as const,
                }}
                onMouseEnter={(e) => {
                  if (!active) {
                    e.currentTarget.style.backgroundColor = COLORS.hoverBg
                    e.currentTarget.style.color = COLORS.textPrimary
                  }
                }}
                onMouseLeave={(e) => {
                  if (!active) {
                    e.currentTarget.style.backgroundColor = 'transparent'
                    e.currentTarget.style.color = COLORS.textSecondary
                  }
                }}
              >
                {entry.label}
              </Link>
            )
          }

          // dropdown entry
          const visibleItems = filterItems(entry.items)
          if (visibleItems.length === 0) return null

          const active = isDropdownActive(entry.items)
          const isOpen = openDropdown === entry.id

          return (
            <div
              key={entry.id}
              style={{ position: 'relative' }}
              onMouseEnter={() => handleMouseEnter(entry.id)}
              onMouseLeave={handleMouseLeave}
            >
              {/* trigger button — clicking navigates to the first dropdown item */}
              <button
                onClick={() => {
                  const defaultHref = visibleItems[0]?.href
                  if (defaultHref) router.push(defaultHref)
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '2px',
                  padding: '7px 14px',
                  borderRadius: '8px',
                  fontSize: '14.5px',
                  fontWeight: active ? 600 : 400,
                  color: active ? COLORS.accent : isOpen ? COLORS.textPrimary : COLORS.textSecondary,
                  backgroundColor: active ? COLORS.activeBg : isOpen ? COLORS.hoverBg : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  textTransform: 'lowercase' as const,
                  fontFamily: FONT,
                  lineHeight: '1',
                }}
              >
                {entry.label}
                <ChevronDown color={active ? COLORS.accent : COLORS.textMuted} />
              </button>

              {/* dropdown panel */}
              {isOpen && (
                <div style={{
                  position: 'absolute',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  top: '100%',
                  paddingTop: '6px', // gap between button and panel (mouse bridge)
                }}>
                  <div style={{
                    minWidth: '240px',
                    backgroundColor: COLORS.white,
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: '12px',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04)',
                    padding: '6px',
                    animation: 'topnav-dropdown-fade-in 0.12s ease-out',
                  }}>
                    {visibleItems.map((item, idx) => {
                      const itemActive = isPathActive(item.href)

                      if (item.comingSoon) {
                        return (
                          <div
                            key={idx}
                            style={{
                              display: 'flex',
                              alignItems: 'flex-start',
                              justifyContent: 'space-between',
                              gap: '10px',
                              padding: '10px 14px',
                              borderRadius: '8px',
                              cursor: 'default',
                              opacity: 0.55,
                            }}
                          >
                            <div>
                              <div style={{
                                fontSize: '13.5px',
                                fontWeight: 500,
                                color: COLORS.textMuted,
                                textTransform: 'lowercase' as const,
                              }}>
                                {item.label}
                              </div>
                              <div style={{
                                fontSize: '12px',
                                color: COLORS.textMuted,
                                marginTop: '2px',
                                lineHeight: '1.35',
                              }}>
                                {item.description}
                              </div>
                            </div>
                            <span style={{
                              flexShrink: 0,
                              marginTop: '1px',
                              padding: '2px 7px',
                              fontSize: '10px',
                              fontWeight: 600,
                              color: COLORS.accent,
                              backgroundColor: COLORS.activeBg,
                              borderRadius: '4px',
                              textTransform: 'uppercase' as const,
                              letterSpacing: '0.5px',
                              whiteSpace: 'nowrap',
                            }}>
                              soon
                            </span>
                          </div>
                        )
                      }

                      return (
                        <Link
                          key={idx}
                          href={item.href}
                          style={{
                            display: 'block',
                            padding: '10px 14px',
                            borderRadius: '8px',
                            textDecoration: 'none',
                            backgroundColor: itemActive ? COLORS.activeBg : 'transparent',
                            transition: 'background 0.12s ease',
                          }}
                          onMouseEnter={(e) => {
                            if (!itemActive) {
                              e.currentTarget.style.backgroundColor = COLORS.hoverBg
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!itemActive) {
                              e.currentTarget.style.backgroundColor = 'transparent'
                            }
                          }}
                        >
                          <div style={{
                            fontSize: '13.5px',
                            fontWeight: itemActive ? 600 : 500,
                            color: itemActive ? COLORS.accent : COLORS.textPrimary,
                            textTransform: 'lowercase' as const,
                          }}>
                            {item.label}
                          </div>
                          <div style={{
                            fontSize: '12px',
                            color: COLORS.textMuted,
                            marginTop: '2px',
                            lineHeight: '1.35',
                          }}>
                            {item.description}
                          </div>
                        </Link>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Right: User menu */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            border: '1px solid #F0EEEC',
            borderRadius: '8px',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            transition: 'all 0.15s',
            fontFamily: FONT,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#FAF9F7' }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
        >
          <div style={{
            width: '28px',
            height: '28px',
            borderRadius: '50%',
            overflow: 'hidden',
            border: '1.5px solid #F0EEEC',
          }}>
            <Image src="/Maya.png" alt="User" width={28} height={28} />
          </div>
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#2D2D2D' }}>
            {userName}
          </span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#9A9A9A" strokeWidth="2" strokeLinecap="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {/* Dropdown */}
        {showUserMenu && (
          <>
            <div
              style={{ position: 'fixed', inset: 0, zIndex: 99 }}
              onClick={() => setShowUserMenu(false)}
            />
            <div style={{
              position: 'absolute',
              right: 0,
              top: '100%',
              marginTop: '6px',
              width: '180px',
              backgroundColor: '#FFFFFF',
              border: '1px solid #F0EEEC',
              borderRadius: '10px',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
              padding: '4px',
              zIndex: 100,
            }}>
              <Link
                href="/settings"
                onClick={() => setShowUserMenu(false)}
                style={{
                  display: 'block',
                  padding: '10px 12px',
                  fontSize: '13px',
                  color: '#2D2D2D',
                  textDecoration: 'none',
                  borderRadius: '8px',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F7F5F3' }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
              >
                settings
              </Link>
              <div style={{ height: '1px', backgroundColor: '#F0EEEC', margin: '4px 0' }} />
              <button
                onClick={() => { setShowUserMenu(false); logout() }}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px 12px',
                  fontSize: '13px',
                  color: '#D97B7B',
                  textAlign: 'left',
                  border: 'none',
                  backgroundColor: 'transparent',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                  fontFamily: FONT,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#FDF2F2' }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
              >
                log out
              </button>
            </div>
          </>
        )}
      </div>

      {/* Inline keyframes for dropdown animation */}
      <style>{`
        @keyframes topnav-dropdown-fade-in {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </nav>
  )
}
