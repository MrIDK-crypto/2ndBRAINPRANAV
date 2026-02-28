'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

interface TopNavProps {
  userName?: string
  onNewChat?: () => void
}

const navItems = [
  { id: 'Integrations', label: 'integrations', href: '/integrations', adminOnly: true },
  { id: 'Documents', label: 'documents', href: '/documents' },
  { id: 'Knowledge Gaps', label: 'knowledge gaps', href: '/knowledge-gaps' },
  { id: 'ChatBot', label: 'chatbot', href: '/', icon: 'chatbot' },
  { id: 'Training Videos', label: 'training videos', href: '/training-guides' },
  { id: 'Co-Researcher', label: 'co-researcher', href: '/co-researcher' },
  { id: 'Inventory', label: 'inventory', href: '/inventory' },
  { id: 'Analytics', label: 'analytics', href: '/analytics', adminOnly: true },
]

export default function TopNav({ userName = 'User', onNewChat }: TopNavProps) {
  const pathname = usePathname()
  const { user: authUser, logout } = useAuth()
  const isAdmin = authUser?.role === 'admin'
  const [showUserMenu, setShowUserMenu] = useState(false)

  const visibleItems = isAdmin
    ? navItems
    : navItems.filter(item => !item.adminOnly)

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/' || pathname === '/chat'
    return pathname?.startsWith(href)
  }

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
      backgroundColor: '#FFFFFF',
      borderBottom: '1px solid #F0EEEC',
      fontFamily: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
    }}>
      {/* Left: Logo */}
      <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
        <Image src="/owl.png" alt="2nd Brain" width={28} height={28} style={{ objectFit: 'contain' }} />
        <span style={{
          fontWeight: 700,
          fontSize: '17px',
          color: '#2D2D2D',
          letterSpacing: '-0.3px',
        }}>
          2nd Brain
        </span>
      </Link>

      {/* Center: Nav links */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {visibleItems.map((item) => {
          const active = isActive(item.href)
          return (
            <Link
              key={item.id}
              href={item.href}
              onClick={() => {
                if (item.id === 'ChatBot' && onNewChat) onNewChat()
              }}
              style={{
                padding: '7px 16px',
                borderRadius: '8px',
                fontSize: '14.5px',
                fontWeight: active ? 600 : 400,
                color: active ? '#C9A598' : '#6B6B6B',
                backgroundColor: active ? '#FBF4F1' : 'transparent',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
                textTransform: 'lowercase' as const,
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = '#F7F5F3'
                  e.currentTarget.style.color = '#2D2D2D'
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = '#6B6B6B'
                }
              }}
            >
              {item.label}
            </Link>
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
            fontFamily: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
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
                  fontFamily: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
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
    </nav>
  )
}
