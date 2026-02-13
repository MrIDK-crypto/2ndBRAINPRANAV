'use client'

import React, { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'

const colors = {
  warning: '#d97706',
  warningBg: '#fef3c7',
  warningBorder: '#fcd34d',
  text: '#92400e',
  success: '#059669',
  successBg: '#d1fae5',
}

export function EmailVerificationBanner() {
  const { user, isEmailVerified, resendVerificationEmail } = useAuth()
  const [isResending, setIsResending] = useState(false)
  const [resendStatus, setResendStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  // Don't show if no user or already verified
  if (!user || isEmailVerified) {
    return null
  }

  const handleResend = async () => {
    setIsResending(true)
    setResendStatus('idle')
    setErrorMessage('')

    try {
      const result = await resendVerificationEmail()
      if (result.success) {
        setResendStatus('success')
        // Reset after 5 seconds
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

  if (resendStatus === 'success') {
    return (
      <div
        style={{
          width: '100%',
          padding: '12px 20px',
          backgroundColor: colors.successBg,
          borderBottom: `1px solid ${colors.success}`,
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
          Verification email sent! Check your inbox (or console for testing).
        </span>
      </div>
    )
  }

  return (
    <div
      style={{
        width: '100%',
        padding: '12px 20px',
        backgroundColor: colors.warningBg,
        borderBottom: `1px solid ${colors.warningBorder}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke={colors.warning}
          strokeWidth="2"
        >
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        <span style={{ color: colors.text, fontSize: '14px' }}>
          Please verify your email address to access all features.
        </span>
      </div>

      <button
        onClick={handleResend}
        disabled={isResending}
        style={{
          padding: '6px 12px',
          fontSize: '13px',
          fontWeight: 500,
          color: colors.warning,
          backgroundColor: 'white',
          border: `1px solid ${colors.warningBorder}`,
          borderRadius: '6px',
          cursor: isResending ? 'not-allowed' : 'pointer',
          opacity: isResending ? 0.7 : 1,
          transition: 'all 0.2s',
        }}
      >
        {isResending ? 'Sending...' : 'Resend verification email'}
      </button>

      {resendStatus === 'error' && (
        <span style={{ color: '#dc2626', fontSize: '13px' }}>
          {errorMessage}
        </span>
      )}
    </div>
  )
}

export default EmailVerificationBanner
