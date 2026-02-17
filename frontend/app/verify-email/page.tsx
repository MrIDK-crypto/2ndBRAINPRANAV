'use client'

import React, { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useSearchParams, useRouter } from 'next/navigation'

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
  warningBg: '#fef3c7',
  warning: '#d97706',
}

type VerificationStatus = 'loading' | 'success' | 'error' | 'no-token' | 'already-verified'

export default function VerifyEmailPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token = searchParams.get('token')

  const [status, setStatus] = useState<VerificationStatus>('loading')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // Prevent duplicate requests (React StrictMode runs useEffect twice)
  const hasVerified = useRef(false)

  useEffect(() => {
    if (!token) {
      setStatus('no-token')
      return
    }

    // Prevent duplicate verification attempts
    if (hasVerified.current) return
    hasVerified.current = true

    verifyEmail(token)
  }, [token])

  const verifyEmail = async (verificationToken: string) => {
    try {
      const response = await fetch(`${API_URL}/api/auth/verify-email?token=${verificationToken}`)
      const data = await response.json()

      if (data.success) {
        setStatus('success')
        setMessage(data.message || 'Email verified successfully!')
        // Redirect to login after 3 seconds
        setTimeout(() => {
          router.push('/login')
        }, 3000)
      } else {
        // Check if email is already verified - treat as success
        if (data.error?.toLowerCase().includes('already verified')) {
          setStatus('already-verified')
          setMessage('Your email has already been verified.')
          setTimeout(() => {
            router.push('/login')
          }, 3000)
        } else {
          setStatus('error')
          setError(data.error || 'Verification failed')
        }
      }
    } catch (err) {
      setStatus('error')
      setError('Unable to connect to server')
    }
  }

  // Loading state
  if (status === 'loading') {
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
            gap: '12px',
          }}
        >
          <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
          <span style={{ fontSize: '20px', fontWeight: 600, color: colors.primary }}>
            2nd Brain
          </span>
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
              maxWidth: '420px',
              backgroundColor: colors.card,
              borderRadius: '16px',
              boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
              padding: '40px',
              textAlign: 'center',
            }}
          >
            {/* Loading spinner */}
            <div
              style={{
                width: '48px',
                height: '48px',
                border: `3px solid ${colors.border}`,
                borderTopColor: colors.primary,
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                margin: '0 auto 24px',
              }}
            />

            <h1
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: colors.text,
                marginBottom: '12px',
              }}
            >
              Verifying your email...
            </h1>
            <p
              style={{
                fontSize: '15px',
                color: colors.textMuted,
                lineHeight: '1.5',
              }}
            >
              Please wait while we verify your email address.
            </p>
          </div>
        </main>

        <style jsx>{`
          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
      </div>
    )
  }

  // No token state
  if (status === 'no-token') {
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
            gap: '12px',
          }}
        >
          <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
          <span style={{ fontSize: '20px', fontWeight: 600, color: colors.primary }}>
            2nd Brain
          </span>
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
              maxWidth: '420px',
              backgroundColor: colors.card,
              borderRadius: '16px',
              boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
              padding: '40px',
              textAlign: 'center',
            }}
          >
            {/* Warning icon */}
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: colors.warningBg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 24px',
              }}
            >
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke={colors.warning}
                strokeWidth="2"
              >
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>

            <h1
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: colors.text,
                marginBottom: '12px',
              }}
            >
              No verification token
            </h1>
            <p
              style={{
                fontSize: '15px',
                color: colors.textMuted,
                marginBottom: '24px',
                lineHeight: '1.5',
              }}
            >
              The verification link appears to be invalid or incomplete. Please check your email
              for the correct link or request a new verification email.
            </p>

            <Link
              href="/login"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                color: colors.secondary,
                fontSize: '15px',
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              Back to sign in
            </Link>
          </div>
        </main>
      </div>
    )
  }

  // Success state (also used for already-verified)
  if (status === 'success' || status === 'already-verified') {
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
            gap: '12px',
          }}
        >
          <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
          <span style={{ fontSize: '20px', fontWeight: 600, color: colors.primary }}>
            2nd Brain
          </span>
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
              maxWidth: '420px',
              backgroundColor: colors.card,
              borderRadius: '16px',
              boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
              padding: '40px',
              textAlign: 'center',
            }}
          >
            {/* Success icon */}
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: colors.successBg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 24px',
              }}
            >
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke={colors.success}
                strokeWidth="2"
              >
                <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>

            <h1
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: colors.text,
                marginBottom: '12px',
              }}
            >
              {status === 'already-verified' ? 'Already verified!' : 'Email verified!'}
            </h1>
            <p
              style={{
                fontSize: '15px',
                color: colors.textMuted,
                marginBottom: '24px',
                lineHeight: '1.5',
              }}
            >
              {message}
              <br />
              <span style={{ fontSize: '13px' }}>Redirecting to login...</span>
            </p>

            <Link
              href="/login"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                height: '48px',
                borderRadius: '8px',
                backgroundColor: colors.primary,
                color: '#ffffff',
                fontSize: '15px',
                fontWeight: 600,
                textDecoration: 'none',
                transition: 'background-color 0.2s',
              }}
            >
              Continue to sign in
            </Link>
          </div>
        </main>
      </div>
    )
  }

  // Error state
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
          gap: '12px',
        }}
      >
        <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
        <span style={{ fontSize: '20px', fontWeight: 600, color: colors.primary }}>
          2nd Brain
        </span>
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
            maxWidth: '420px',
            backgroundColor: colors.card,
            borderRadius: '16px',
            boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
            padding: '40px',
            textAlign: 'center',
          }}
        >
          {/* Error icon */}
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: colors.errorBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
            }}
          >
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke={colors.error}
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>

          <h1
            style={{
              fontSize: '24px',
              fontWeight: 700,
              color: colors.text,
              marginBottom: '12px',
            }}
          >
            Verification failed
          </h1>
          <p
            style={{
              fontSize: '15px',
              color: colors.textMuted,
              marginBottom: '24px',
              lineHeight: '1.5',
            }}
          >
            {error}
          </p>

          <Link
            href="/login"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              color: colors.secondary,
              fontSize: '15px',
              fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to sign in
          </Link>
        </div>
      </main>
    </div>
  )
}
