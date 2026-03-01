'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { sessionManager } from '@/utils/sessionManager'
import { authApi } from '@/utils/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006'

interface User {
  id: string
  email: string
  full_name: string
  role: string
  tenant_id: string
  avatar_url?: string
  timezone?: string
  email_verified: boolean
  mfa_enabled: boolean
  created_at: string
  is_active: boolean
}

interface Tenant {
  id: string
  name: string
  slug: string
  plan: string
  storage_used_bytes: number
  storage_limit_bytes: number
  created_at: string
  is_active: boolean
}

interface AuthContextType {
  user: User | null
  tenant: Tenant | null
  token: string | null
  refreshToken: string | null
  isLoading: boolean
  isAuthenticated: boolean
  isEmailVerified: boolean
  login: (email: string, password: string, rememberMe?: boolean) => Promise<{ success: boolean; error?: string }>
  signup: (email: string, password: string, fullName: string, organizationName?: string, inviteCode?: string) => Promise<{ success: boolean; error?: string }>
  logout: () => Promise<void>
  resendVerificationEmail: () => Promise<{ success: boolean; error?: string }>
}

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/', '/login', '/signup', '/forgot-password', '/reset-password', '/verify-email', '/verification-pending', '/terms', '/privacy', '/landing', '/product']

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  // Handle session expiration
  const handleSessionExpired = useCallback(() => {
    console.log('[Auth] Session expired')
    setUser(null)
    setTenant(null)
    setToken(null)
    setRefreshToken(null)
    router.push('/')
  }, [router])

  // Check auth on mount
  useEffect(() => {
    // Set up session expiration handler
    sessionManager.setOnSessionExpired(handleSessionExpired)

    // Optional: Set up session warning handler
    sessionManager.setOnSessionWarning((timeRemaining) => {
      console.log(`[Auth] Session expiring in ${Math.round(timeRemaining / 1000)} seconds`)
    })

    checkAuth()
  }, [handleSessionExpired])

  // Redirect based on auth state and email verification
  useEffect(() => {
    if (!isLoading) {
      const isPublicRoute = PUBLIC_ROUTES.some(route => route === '/' ? pathname === '/' : pathname?.startsWith(route))
      const isVerificationPending = pathname === '/verification-pending'

      if (!user && !isPublicRoute) {
        // Not authenticated and not on public page -> redirect to landing
        router.push('/')
      } else if (user && !user.email_verified && !isPublicRoute && !isVerificationPending && !window.location.hostname.includes('localhost')) {
        // Authenticated but email NOT verified -> redirect to verification pending (skip on localhost)
        router.push('/verification-pending')
      } else if (user && (user.email_verified || window.location.hostname.includes('localhost')) && isVerificationPending) {
        // Email is verified (or localhost) but on verification pending page -> redirect to integrations
        router.push('/integrations')
      } else if (user && (user.email_verified || window.location.hostname.includes('localhost')) && (pathname === '/login' || pathname === '/')) {
        // Authenticated and verified (or localhost) but on login/landing page -> redirect to integrations
        router.push('/integrations')
      }
    }
  }, [user, isLoading, pathname, router])

  const checkAuth = async () => {
    // Check if we have stored auth data (JWT)
    const storedToken = sessionManager.getAccessToken()
    const storedUserId = sessionManager.getUserId()

    if (storedToken && storedUserId) {
      try {
        // Verify token with backend
        const response = await fetch(`${API_URL}/api/auth/me`, {
          headers: {
            'Authorization': `Bearer ${storedToken}`
          },
          credentials: 'include'
        })

        const data = await response.json()

        if (data.success) {
          setUser(data.user)
          setTenant(data.tenant)
          setToken(storedToken)
          setRefreshToken(sessionManager.getRefreshToken())
        } else {
          // Token invalid, clear storage
          sessionManager.clearSession()
        }
      } catch (err) {
        console.error('[Auth] Auth check failed:', err)
        // Keep stored data if server is down (offline mode)
        setToken(storedToken)
        setRefreshToken(sessionManager.getRefreshToken())
      }

      setIsLoading(false)
      return
    }

    setIsLoading(false)
  }

  const login = async (email: string, password: string, rememberMe: boolean = false): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password, remember_me: rememberMe }),
        credentials: 'include' // Include cookies
      })

      const data = await response.json()

      if (data.success) {
        // V2 API returns tokens object with access_token
        const accessToken = data.tokens?.access_token || data.token
        const refreshTok = data.tokens?.refresh_token

        setUser(data.user)
        setTenant(data.tenant)
        setToken(accessToken)
        setRefreshToken(refreshTok)
        // Initialize session manager with remember me option
        sessionManager.initializeSession(accessToken, refreshTok, {
          userId: data.user.id,
          userEmail: data.user.email,
          userName: data.user.full_name,
          userType: data.user.role,
          tenantId: data.user.tenant_id
        }, rememberMe)

        // Redirect based on email verification status (skip on localhost)
        if (data.user.email_verified || window.location.hostname.includes('localhost')) {
          router.push('/integrations')
        } else {
          router.push('/verification-pending')
        }

        return { success: true }
      } else {
        return { success: false, error: data.error || 'Login failed' }
      }
    } catch (err) {
      console.error('[Auth] Login error:', err)
      return { success: false, error: 'Unable to connect to server' }
    }
  }

  const signup = async (
    email: string,
    password: string,
    fullName: string,
    organizationName?: string,
    inviteCode?: string
  ): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_URL}/api/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          organization_name: organizationName,
          invite_code: inviteCode
        }),
        credentials: 'include'
      })

      const data = await response.json()

      if (data.success) {
        // V2 API returns tokens object with access_token
        const accessToken = data.tokens?.access_token
        const refreshTok = data.tokens?.refresh_token

        setUser(data.user)
        setTenant(data.tenant)
        setToken(accessToken)
        setRefreshToken(refreshTok)

        // Initialize session manager
        sessionManager.initializeSession(accessToken, refreshTok, {
          userId: data.user.id,
          userEmail: data.user.email,
          userName: data.user.full_name,
          userType: data.user.role,
          tenantId: data.user.tenant_id
        })

        // Redirect to integrations page
        router.push('/integrations')

        return { success: true }
      } else {
        return { success: false, error: data.error || 'Signup failed' }
      }
    } catch (err) {
      console.error('[Auth] Signup error:', err)
      return { success: false, error: 'Unable to connect to server' }
    }
  }

  const logout = async () => {
    try {
      await sessionManager.logout()
    } catch (err) {
      console.error('[Auth] Logout error:', err)
    } finally {
      setUser(null)
      setTenant(null)
      setToken(null)
      setRefreshToken(null)
      router.push('/')
    }
  }

  const resendVerificationEmail = async (): Promise<{ success: boolean; error?: string }> => {
    if (!user?.email) {
      return { success: false, error: 'No user email available' }
    }

    try {
      const response = await fetch(`${API_URL}/api/auth/resend-verification`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: user.email }),
        credentials: 'include'
      })

      const data = await response.json()

      if (data.success) {
        return { success: true }
      } else {
        return { success: false, error: data.error || 'Failed to resend verification email' }
      }
    } catch (err) {
      console.error('[Auth] Resend verification error:', err)
      return { success: false, error: 'Unable to connect to server' }
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        tenant,
        token,
        refreshToken,
        isLoading,
        isAuthenticated: !!user,
        isEmailVerified: user?.email_verified ?? false,
        login,
        signup,
        logout,
        resendVerificationEmail
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Hook to get auth headers for API calls
export function useAuthHeaders() {
  const { token } = useAuth()

  if (token) {
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  }

  return {
    'Content-Type': 'application/json'
  }
}
