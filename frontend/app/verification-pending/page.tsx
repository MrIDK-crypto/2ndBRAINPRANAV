'use client'

import React, { useState, useEffect } from 'react'
import Image from 'next/image'
import { useAuth } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006'

// Wellspring-inspired warm color palette
const colors = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  secondary: '#C9A598',
  background: '#FAF9F7',
  card: '#FFFFFE',
  text: '#2D2D2D',
  textMuted: '#6B6B6B',
  border: '#F0EEEC',
  error: '#dc2626',
  errorBg: '#fef2f2',
  success: '#9CB896',
  successBg: '#F0F7EE',
  warning: '#d97706',
  warningBg: '#fef3c7',
}

export default function VerificationPendingPage() {
  const { user, logout, resendVerificationEmail, isEmailVerified } = useAuth()
  const router = useRouter()
  const [isResending, setIsResending] = useState(false)
  const [resendStatus, setResendStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [checkingStatus, setCheckingStatus] = useState(false)

  // If email is verified, redirect to integrations
  useEffect(() => {
    if (isEmailVerified) {
      router.push('/integrations')
    }
  }, [isEmailVerified, router])

  // Periodically check if email has been verified
  useEffect(() => {
    const checkVerification = async () => {
      if (!user) return

      setCheckingStatus(true)
      try {
        const response = await fetch(`${API_URL}/api/auth/me`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
          }
        })
        const data = await response.json()
        if (data.success && data.user?.email_verified) {
          router.push('/integrations')
        }
      } catch {
        // Ignore errors
      } finally {
        setCheckingStatus(false)
      }
    }

    // Check every 5 seconds
    const interval = setInterval(checkVerification, 5000)
    return () => clearInterval(interval)
  }, [user, router])

  const handleResend = async () => {
    setIsResending(true)
    setResendStatus('idle')
    setErrorMessage('')

    try {
      const result = await resendVerificationEmail()
      if (result.success) {
        setResendStatus('success')
        setTimeout(() => setResendStatus('idle'), 5000)
      } else {
        setResendStatus('error')
        setErrorMessage(result.error || 'Failed to resend')
      }
    } catch {
      setResendStatus('error')
      setErrorMessage('Failed to resend verification email')
    } finally {
      setIsResending(false)
    }
  }

  const handleLogout = async () => {
    await logout()
  }

  if (!user) {
    return null
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: colors.background,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <header
        style={{
          padding: '24px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
          <span style={{ fontSize: '20px', fontWeight: 600, color: colors.primary }}>
            2nd Brain
          </span>
        </div>
        <button
          onClick={handleLogout}
          style={{
            padding: '8px 16px',
            fontSize: '14px',
            color: colors.textMuted,
            backgroundColor: 'transparent',
            border: `1px solid ${colors.border}`,
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          Sign out
        </button>
      </header>

      {/* Main content */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 20px',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '480px',
            backgroundColor: colors.card,
            borderRadius: '16px',
            boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
            padding: '48px 40px',
            textAlign: 'center',
          }}
        >
          {/* Email icon */}
          <div
            style={{
              width: '80px',
              height: '80px',
              borderRadius: '50%',
              backgroundColor: colors.warningBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
            }}
          >
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke={colors.warning}
              strokeWidth="2"
            >
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
          </div>

          <h1
            style={{
              fontSize: '28px',
              fontWeight: 700,
              color: colors.text,
              marginBottom: '12px',
            }}
          >
            Verify your email
          </h1>

          <p
            style={{
              fontSize: '15px',
              color: colors.textMuted,
              marginBottom: '8px',
              lineHeight: '1.6',
            }}
          >
            We sent a verification email to:
          </p>

          <p
            style={{
              fontSize: '16px',
              fontWeight: 600,
              color: colors.text,
              marginBottom: '24px',
            }}
          >
            {user.email}
          </p>

          <p
            style={{
              fontSize: '14px',
              color: colors.textMuted,
              marginBottom: '32px',
              lineHeight: '1.6',
            }}
          >
            Click the link in that email to verify your account and access 2nd Brain.
          </p>

          {/* Resend button */}
          {resendStatus === 'success' ? (
            <div
              style={{
                padding: '12px 20px',
                backgroundColor: colors.successBg,
                borderRadius: '8px',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke={colors.success}
                strokeWidth="2"
              >
                <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              <span style={{ color: colors.success, fontSize: '14px', fontWeight: 500 }}>
                Verification email sent!
              </span>
            </div>
          ) : (
            <button
              onClick={handleResend}
              disabled={isResending}
              style={{
                width: '100%',
                padding: '14px 24px',
                fontSize: '15px',
                fontWeight: 600,
                color: '#ffffff',
                backgroundColor: isResending ? colors.textMuted : colors.primary,
                border: 'none',
                borderRadius: '8px',
                cursor: isResending ? 'not-allowed' : 'pointer',
                marginBottom: '16px',
                transition: 'background-color 0.2s',
              }}
            >
              {isResending ? 'Sending...' : 'Resend verification email'}
            </button>
          )}

          {resendStatus === 'error' && (
            <p style={{ color: colors.error, fontSize: '14px', marginBottom: '16px' }}>
              {errorMessage}
            </p>
          )}

          {/* Auto-check status indicator */}
          {checkingStatus && (
            <p style={{ fontSize: '12px', color: colors.textMuted }}>
              Checking verification status...
            </p>
          )}

          <div
            style={{
              borderTop: `1px solid ${colors.border}`,
              paddingTop: '24px',
              marginTop: '24px',
            }}
          >
            <p style={{ fontSize: '13px', color: colors.textMuted }}>
              Wrong email?{' '}
              <button
                onClick={handleLogout}
                style={{
                  color: colors.secondary,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: 500,
                  fontSize: '13px',
                }}
              >
                Sign out and try again
              </button>
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
