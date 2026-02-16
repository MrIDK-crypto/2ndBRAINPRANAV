'use client'

import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { sessionManager } from '@/utils/sessionManager'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006'

export default function SharedLandingPage() {
  const params = useParams()
  const router = useRouter()
  const token = params.token as string
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const validateAndRedirect = async () => {
      try {
        // Clear any existing session first (JWT or previous share)
        sessionManager.clearSession()

        const response = await fetch(
          `${API_BASE}/api/shared/validate?token=${encodeURIComponent(token)}`
        )
        const data = await response.json()

        if (data.success) {
          // Store share token and tenant info
          sessionManager.initializeSharedSession(token, {
            id: data.tenant.id,
            name: data.tenant.name,
            slug: data.tenant.slug || '',
          })

          // Redirect to the main Documents page
          router.replace('/documents')
        } else {
          setError(data.error || 'Invalid or expired share link')
        }
      } catch {
        setError('Failed to validate share link. Please try again.')
      }
    }
    validateAndRedirect()
  }, [token, router])

  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: '#FAF9F7' }}>
        <div style={{ textAlign: 'center', maxWidth: 400, padding: 32 }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, backgroundColor: '#FBF4F1', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#C9A598" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
          </div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: '#2D2D2D', marginBottom: 8 }}>Link Unavailable</h1>
          <p style={{ color: '#6B6B6B', fontSize: 14, lineHeight: 1.6 }}>{error}</p>
        </div>
      </div>
    )
  }

  // Loading state
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: '#FAF9F7' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 40, height: 40, border: '3px solid #F0EEEC', borderTopColor: '#C9A598', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }} />
        <p style={{ color: '#6B6B6B', fontSize: 14 }}>Validating share link...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}
