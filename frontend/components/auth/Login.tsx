'use client'

import React, { useState, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { validateLogin, getPasswordStrength } from '@/utils/validation'

// Wellspring-inspired warm color palette
const colors = {
  primary: '#C9A598', // Warm coral
  primaryHover: '#B8948A',
  secondary: '#C9A598', // Coral accent
  background: '#FAF9F7', // Warm cream background
  card: '#FFFFFE',
  text: '#2D2D2D',
  textMuted: '#6B6B6B',
  border: '#F0EEEC',
  error: '#dc2626',
  errorBg: '#fef2f2',
}

export default function Login() {
  const router = useRouter()
  const { login, isAuthenticated, isLoading: authLoading } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(true)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(false)

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.push('/integrations')
    }
  }, [isAuthenticated, router])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()

    // Validate form
    const validation = validateLogin({ email, password })
    if (!validation.isValid) {
      setFieldErrors(validation.errors)
      return
    }

    setFieldErrors({})
    setError('')
    setIsLoading(true)

    try {
      const result = await login(email, password, rememberMe)

      if (!result.success) {
        // Handle specific error codes
        if (result.error?.includes('locked')) {
          setError('Account is temporarily locked. Please try again later.')
        } else if (result.error?.includes('Invalid')) {
          setError('Invalid email or password. Please try again.')
        } else {
          setError(result.error || 'Login failed. Please try again.')
        }
      }
      // Success handled by AuthContext redirect
    } catch (err) {
      setError('Connection error. Please check your internet connection.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit()
    }
  }

  // Show loading spinner while checking auth
  if (authLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: colors.background,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: '40px',
            height: '40px',
            border: `3px solid ${colors.border}`,
            borderTopColor: colors.primary,
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }}
        />
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

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: colors.background,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header with logo */}
      <header
        style={{
          padding: '24px 32px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
        <span
          style={{
            fontSize: '20px',
            fontWeight: 600,
            color: colors.text,
          }}
        >
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
          }}
        >
          {/* Title */}
          <h1
            style={{
              fontSize: '28px',
              fontWeight: 700,
              color: colors.text,
              marginBottom: '8px',
              textAlign: 'center',
            }}
          >
            Welcome back
          </h1>
          <p
            style={{
              fontSize: '15px',
              color: colors.textMuted,
              marginBottom: '32px',
              textAlign: 'center',
            }}
          >
            Sign in to access your knowledge base
          </p>

          {/* Error message */}
          {error && (
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: colors.errorBg,
                borderRadius: '8px',
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM10 6v4m0 4h.01"
                  stroke={colors.error}
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
              <span style={{ fontSize: '14px', color: colors.error }}>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {/* Email field */}
            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: colors.text,
                  marginBottom: '8px',
                }}
              >
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setFieldErrors((prev) => ({ ...prev, email: '' }))
                }}
                onKeyPress={handleKeyPress}
                placeholder="you@company.com"
                style={{
                  width: '100%',
                  height: '48px',
                  padding: '0 16px',
                  fontSize: '15px',
                  borderRadius: '8px',
                  border: `1px solid ${fieldErrors.email ? colors.error : colors.border}`,
                  backgroundColor: colors.card,
                  outline: 'none',
                  transition: 'border-color 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                onBlur={(e) =>
                  (e.target.style.borderColor = fieldErrors.email ? colors.error : colors.border)
                }
              />
              {fieldErrors.email && (
                <p style={{ fontSize: '13px', color: colors.error, marginTop: '6px' }}>
                  {fieldErrors.email}
                </p>
              )}
            </div>

            {/* Password field */}
            <div style={{ marginBottom: '20px' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '8px',
                }}
              >
                <label
                  style={{
                    fontSize: '14px',
                    fontWeight: 500,
                    color: colors.text,
                  }}
                >
                  Password
                </label>
                <Link
                  href="/forgot-password"
                  style={{
                    fontSize: '13px',
                    color: colors.secondary,
                    textDecoration: 'none',
                  }}
                >
                  Forgot password?
                </Link>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    setFieldErrors((prev) => ({ ...prev, password: '' }))
                  }}
                  onKeyPress={handleKeyPress}
                  placeholder="Enter your password"
                  style={{
                    width: '100%',
                    height: '48px',
                    padding: '0 48px 0 16px',
                    fontSize: '15px',
                    borderRadius: '8px',
                    border: `1px solid ${fieldErrors.password ? colors.error : colors.border}`,
                    backgroundColor: colors.card,
                    outline: 'none',
                    transition: 'border-color 0.2s',
                    boxSizing: 'border-box',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                  onBlur={(e) =>
                    (e.target.style.borderColor = fieldErrors.password
                      ? colors.error
                      : colors.border)
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke={colors.textMuted}
                      strokeWidth="2"
                    >
                      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke={colors.textMuted}
                      strokeWidth="2"
                    >
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
              {fieldErrors.password && (
                <p style={{ fontSize: '13px', color: colors.error, marginTop: '6px' }}>
                  {fieldErrors.password}
                </p>
              )}
            </div>

            {/* Remember me checkbox */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                marginBottom: '24px',
              }}
            >
              <div
                onClick={() => setRememberMe(!rememberMe)}
                style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '4px',
                  border: `2px solid ${rememberMe ? colors.primary : colors.border}`,
                  backgroundColor: rememberMe ? colors.primary : 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s ease',
                }}
              >
                {rememberMe && (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
              <label
                onClick={() => setRememberMe(!rememberMe)}
                style={{
                  fontSize: '14px',
                  color: colors.text,
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                Remember me
              </label>
            </div>

            {/* Submit button */}
            <button
              type="submit"
              disabled={isLoading}
              style={{
                width: '100%',
                height: '48px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: isLoading ? colors.textMuted : colors.primary,
                color: '#ffffff',
                fontSize: '15px',
                fontWeight: 600,
                cursor: isLoading ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
              onMouseEnter={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.backgroundColor = colors.primaryHover
                }
              }}
              onMouseLeave={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.backgroundColor = colors.primary
                }
              }}
            >
              {isLoading ? (
                <>
                  <div
                    style={{
                      width: '18px',
                      height: '18px',
                      border: '2px solid rgba(255,255,255,0.3)',
                      borderTopColor: '#fff',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite',
                    }}
                  />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          {/* Sign up link */}
          <p
            style={{
              textAlign: 'center',
              marginTop: '24px',
              fontSize: '14px',
              color: colors.textMuted,
            }}
          >
            Don't have an account?{' '}
            <Link
              href="/signup"
              style={{
                color: colors.secondary,
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              Sign up
            </Link>
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          padding: '24px 32px',
          textAlign: 'center',
          color: colors.textMuted,
          fontSize: '13px',
        }}
      >
        <p>&copy; 2026 2nd Brain. All rights reserved.</p>
      </footer>

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
