'use client'

import React from 'react'
import Sidebar from '../shared/Sidebar'
import { useAuth } from '@/contexts/AuthContext'

// Wellspring-Inspired Warm Design System
const warmTheme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#F7F5F3',
  headerBg: '#F7F5F3',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
}

export default function TrainingGuides() {
  const { user } = useAuth()

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: warmTheme.pageBg }}>
      {/* Sidebar */}
      <Sidebar userName={user?.full_name?.split(' ')[0] || 'User'} />

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative' }}>
        {/* Header */}
        <div style={{
          padding: '24px 32px',
          borderBottom: `1px solid ${warmTheme.border}`,
          backgroundColor: warmTheme.headerBg
        }}>
          <h1 style={{
            fontSize: '26px',
            fontWeight: 700,
            color: warmTheme.textPrimary,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            Training Videos
          </h1>
          <p style={{
            fontSize: '14px',
            color: warmTheme.textSecondary,
            marginTop: '6px'
          }}>
            Learn how to get the most out of your knowledge base
          </p>
        </div>

        {/* Coming Soon Content - Centered on entire content area */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
          maxWidth: '400px',
          padding: '40px'
        }}>
          <div style={{
            textAlign: 'center'
          }}>
            {/* Icon */}
            <div style={{
              width: '80px',
              height: '80px',
              borderRadius: '20px',
              backgroundColor: warmTheme.primaryLight,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px'
            }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={warmTheme.primary} strokeWidth="1.5">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </div>

            {/* Title */}
            <h2 style={{
              fontSize: '28px',
              fontWeight: 700,
              color: warmTheme.textPrimary,
              marginBottom: '12px',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
            }}>
              Coming Soon
            </h2>

            {/* Description */}
            <p style={{
              fontSize: '16px',
              color: warmTheme.textSecondary,
              lineHeight: '1.6'
            }}>
              We're working on creating helpful video tutorials to guide your training.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
