'use client'

import React, { useState, useEffect } from 'react'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/shared/Sidebar'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

// Wellspring-Inspired Warm Design System
const theme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#F7F5F3',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  success: '#9CB896',
  successLight: '#F0F7EE',
  error: '#D97B7B',
  errorLight: '#FDF2F2',
}

export default function SettingsPage() {
  const { user, logout, isLoading: authLoading, isSharedAccess } = useAuth()
  const authHeaders = useAuthHeaders()
  const router = useRouter()

  // Redirect shared users away from settings page
  useEffect(() => {
    if (isSharedAccess) {
      router.replace('/documents')
    }
  }, [isSharedAccess, router])

  const [fullName, setFullName] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMessage, setProfileMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const [loggingOut, setLoggingOut] = useState(false)

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || '')
    }
  }, [user])

  const handleSaveProfile = async () => {
    setSavingProfile(true)
    setProfileMessage(null)
    try {
      const response = await axios.put(`${API_BASE}/auth/profile`, { full_name: fullName }, { headers: authHeaders })
      if (response.data.success) {
        setProfileMessage({ type: 'success', text: 'Profile updated successfully!' })
      } else {
        setProfileMessage({ type: 'error', text: response.data.error || 'Failed to update profile' })
      }
    } catch (error: any) {
      setProfileMessage({ type: 'error', text: error.response?.data?.error || 'Failed to update profile' })
    } finally {
      setSavingProfile(false)
    }
  }

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      setPasswordMessage({ type: 'error', text: 'New passwords do not match' })
      return
    }
    if (newPassword.length < 8) {
      setPasswordMessage({ type: 'error', text: 'Password must be at least 8 characters' })
      return
    }
    setSavingPassword(true)
    setPasswordMessage(null)
    try {
      const response = await axios.put(`${API_BASE}/auth/password`, { current_password: currentPassword, new_password: newPassword }, { headers: authHeaders })
      if (response.data.success) {
        setPasswordMessage({ type: 'success', text: 'Password changed successfully!' })
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
      } else {
        setPasswordMessage({ type: 'error', text: response.data.error || 'Failed to change password' })
      }
    } catch (error: any) {
      setPasswordMessage({ type: 'error', text: error.response?.data?.error || 'Failed to change password' })
    } finally {
      setSavingPassword(false)
    }
  }

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await logout()
      router.push('/login')
    } catch (error) {
      console.error('Logout failed:', error)
      setLoggingOut(false)
    }
  }

  const userName = user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'User'

  if (authLoading) {
    return (
      <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: theme.pageBg }}>
        <Sidebar userName={userName} />
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{
            width: '40px',
            height: '40px',
            border: `3px solid ${theme.border}`,
            borderTopColor: theme.primary,
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }} />
        </div>
        <style jsx>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    )
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '12px 16px',
    borderRadius: '10px',
    border: `1px solid ${theme.border}`,
    fontSize: '15px',
    outline: 'none',
    backgroundColor: theme.pageBg,
    color: theme.textPrimary,
    transition: 'border-color 0.2s, box-shadow 0.2s',
    boxSizing: 'border-box',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '14px',
    fontWeight: 500,
    color: theme.textPrimary,
    marginBottom: '8px',
  }

  const sectionStyle: React.CSSProperties = {
    backgroundColor: theme.cardBg,
    borderRadius: '16px',
    padding: '28px',
    marginBottom: '24px',
    border: `1px solid ${theme.border}`,
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: theme.pageBg }}>
      <Sidebar userName={userName} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{
          padding: '24px 40px',
          borderBottom: `1px solid ${theme.border}`,
          backgroundColor: theme.cardBg,
        }}>
          <h1 style={{
            fontSize: '26px',
            fontWeight: 700,
            color: theme.textPrimary,
            margin: 0,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}>
            Account Settings
          </h1>
          <p style={{
            color: theme.textSecondary,
            fontSize: '14px',
            marginTop: '6px',
            marginBottom: 0,
          }}>
            Manage your profile and security preferences
          </p>
        </div>

        {/* Content */}
        <div style={{ flex: 1, padding: '32px 40px', overflowY: 'auto' }}>
          <div style={{ maxWidth: '640px' }}>

            {/* Profile Section */}
            <section style={sectionStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  backgroundColor: theme.primaryLight,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                </div>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, color: theme.textPrimary, margin: 0 }}>
                    Profile Information
                  </h2>
                  <p style={{ fontSize: '13px', color: theme.textMuted, margin: '2px 0 0' }}>
                    Update your personal details
                  </p>
                </div>
              </div>

              <div style={{ display: 'grid', gap: '20px' }}>
                <div>
                  <label style={labelStyle}>Full Name</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    style={inputStyle}
                    placeholder="Enter your full name"
                    onFocus={(e) => {
                      e.target.style.borderColor = theme.primary
                      e.target.style.boxShadow = `0 0 0 3px ${theme.primaryLight}`
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = theme.border
                      e.target.style.boxShadow = 'none'
                    }}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Email Address</label>
                  <input
                    type="email"
                    value={user?.email || ''}
                    disabled
                    style={{
                      ...inputStyle,
                      backgroundColor: theme.border,
                      color: theme.textMuted,
                      cursor: 'not-allowed',
                    }}
                  />
                  <p style={{ fontSize: '12px', color: theme.textMuted, marginTop: '6px' }}>
                    Email cannot be changed
                  </p>
                </div>

                {profileMessage && (
                  <div style={{
                    padding: '14px 16px',
                    borderRadius: '10px',
                    backgroundColor: profileMessage.type === 'success' ? theme.successLight : theme.errorLight,
                    color: profileMessage.type === 'success' ? theme.success : theme.error,
                    fontSize: '14px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                  }}>
                    {profileMessage.type === 'success' ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 8v4m0 4h.01" />
                      </svg>
                    )}
                    {profileMessage.text}
                  </div>
                )}

                <button
                  onClick={handleSaveProfile}
                  disabled={savingProfile}
                  style={{
                    padding: '12px 24px',
                    borderRadius: '10px',
                    backgroundColor: theme.primary,
                    color: '#FFFFFF',
                    border: 'none',
                    fontSize: '14px',
                    fontWeight: 600,
                    cursor: savingProfile ? 'wait' : 'pointer',
                    opacity: savingProfile ? 0.7 : 1,
                    width: 'fit-content',
                    transition: 'background-color 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    if (!savingProfile) e.currentTarget.style.backgroundColor = theme.primaryHover
                  }}
                  onMouseLeave={(e) => {
                    if (!savingProfile) e.currentTarget.style.backgroundColor = theme.primary
                  }}
                >
                  {savingProfile ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </section>

            {/* Security Section */}
            <section style={sectionStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  backgroundColor: theme.primaryLight,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </div>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, color: theme.textPrimary, margin: 0 }}>
                    Security
                  </h2>
                  <p style={{ fontSize: '13px', color: theme.textMuted, margin: '2px 0 0' }}>
                    Change your password
                  </p>
                </div>
              </div>

              <div style={{ display: 'grid', gap: '20px' }}>
                <div>
                  <label style={labelStyle}>Current Password</label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    style={inputStyle}
                    placeholder="Enter current password"
                    onFocus={(e) => {
                      e.target.style.borderColor = theme.primary
                      e.target.style.boxShadow = `0 0 0 3px ${theme.primaryLight}`
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = theme.border
                      e.target.style.boxShadow = 'none'
                    }}
                  />
                </div>
                <div>
                  <label style={labelStyle}>New Password</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    style={inputStyle}
                    placeholder="Enter new password"
                    onFocus={(e) => {
                      e.target.style.borderColor = theme.primary
                      e.target.style.boxShadow = `0 0 0 3px ${theme.primaryLight}`
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = theme.border
                      e.target.style.boxShadow = 'none'
                    }}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Confirm New Password</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    style={inputStyle}
                    placeholder="Confirm new password"
                    onFocus={(e) => {
                      e.target.style.borderColor = theme.primary
                      e.target.style.boxShadow = `0 0 0 3px ${theme.primaryLight}`
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = theme.border
                      e.target.style.boxShadow = 'none'
                    }}
                  />
                </div>

                {passwordMessage && (
                  <div style={{
                    padding: '14px 16px',
                    borderRadius: '10px',
                    backgroundColor: passwordMessage.type === 'success' ? theme.successLight : theme.errorLight,
                    color: passwordMessage.type === 'success' ? theme.success : theme.error,
                    fontSize: '14px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                  }}>
                    {passwordMessage.type === 'success' ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 8v4m0 4h.01" />
                      </svg>
                    )}
                    {passwordMessage.text}
                  </div>
                )}

                <button
                  onClick={handleChangePassword}
                  disabled={savingPassword || !currentPassword || !newPassword || !confirmPassword}
                  style={{
                    padding: '12px 24px',
                    borderRadius: '10px',
                    backgroundColor: (savingPassword || !currentPassword || !newPassword || !confirmPassword) ? theme.border : theme.primary,
                    color: (savingPassword || !currentPassword || !newPassword || !confirmPassword) ? theme.textMuted : '#FFFFFF',
                    border: 'none',
                    fontSize: '14px',
                    fontWeight: 600,
                    cursor: (savingPassword || !currentPassword || !newPassword || !confirmPassword) ? 'not-allowed' : 'pointer',
                    width: 'fit-content',
                    transition: 'background-color 0.2s',
                  }}
                >
                  {savingPassword ? 'Changing...' : 'Change Password'}
                </button>
              </div>
            </section>

            {/* Sign Out Section */}
            <section style={sectionStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  backgroundColor: theme.errorLight,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={theme.error} strokeWidth="2">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                </div>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, color: theme.textPrimary, margin: 0 }}>
                    Sign Out
                  </h2>
                  <p style={{ fontSize: '13px', color: theme.textMuted, margin: '2px 0 0' }}>
                    End your current session
                  </p>
                </div>
              </div>

              <button
                onClick={handleLogout}
                disabled={loggingOut}
                style={{
                  padding: '12px 24px',
                  borderRadius: '10px',
                  backgroundColor: theme.errorLight,
                  color: theme.error,
                  border: `1px solid ${theme.error}`,
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: loggingOut ? 'wait' : 'pointer',
                  opacity: loggingOut ? 0.7 : 1,
                  transition: 'background-color 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (!loggingOut) {
                    e.currentTarget.style.backgroundColor = '#FDEAEA'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!loggingOut) {
                    e.currentTarget.style.backgroundColor = theme.errorLight
                  }
                }}
              >
                {loggingOut ? 'Signing out...' : 'Sign Out'}
              </button>
            </section>

          </div>
        </div>
      </main>

      <style jsx>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
