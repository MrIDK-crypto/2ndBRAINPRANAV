'use client'

import React, { useState, useEffect } from 'react'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import TopNav from '@/components/shared/TopNav'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

// Wellspring Warm Brown Design System
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
  const { user, logout, isLoading: authLoading } = useAuth()
  const authHeaders = useAuthHeaders()
  const router = useRouter()

  const [fullName, setFullName] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMessage, setProfileMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const [loggingOut, setLoggingOut] = useState(false)

  // Chatbot settings state
  const [responseMode, setResponseMode] = useState(3)
  const [loadingChatSettings, setLoadingChatSettings] = useState(true)
  const [savingChatSettings, setSavingChatSettings] = useState(false)
  const [chatSettingsMessage, setChatSettingsMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || '')
    }
  }, [user])

  // Load tenant settings on mount
  useEffect(() => {
    if (isAdmin) {
      const loadTenantSettings = async () => {
        try {
          const response = await axios.get(`${API_BASE}/auth/tenant-settings`, { headers: authHeaders })
          if (response.data.success) {
            const mode = response.data.settings?.chat_response_mode
            if (mode && mode >= 1 && mode <= 3) {
              setResponseMode(mode)
            }
          }
        } catch (error) {
          console.error('Failed to load tenant settings:', error)
        } finally {
          setLoadingChatSettings(false)
        }
      }
      loadTenantSettings()
    } else {
      setLoadingChatSettings(false)
    }
  }, [isAdmin])

  const responseModeLabels = [
    { value: 1, label: 'Sources', description: 'Only shows relevant document titles and links. Users must read the source material themselves.' },
    { value: 2, label: 'Sources & Summary', description: 'A brief summary pointing users to the right documents. No in-depth explanations.' },
    { value: 3, label: 'In-Depth', description: 'Full comprehensive AI answer with insights, citations, and thorough explanations.' },
  ]

  const handleSaveChatSettings = async () => {
    setSavingChatSettings(true)
    setChatSettingsMessage(null)
    try {
      const response = await axios.put(`${API_BASE}/auth/tenant-settings`, { chat_response_mode: responseMode }, { headers: authHeaders })
      if (response.data.success) {
        setChatSettingsMessage({ type: 'success', text: 'Chatbot settings updated!' })
      } else {
        setChatSettingsMessage({ type: 'error', text: response.data.error || 'Failed to update settings' })
      }
    } catch (error: any) {
      setChatSettingsMessage({ type: 'error', text: error.response?.data?.error || 'Failed to update settings' })
    } finally {
      setSavingChatSettings(false)
    }
  }

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
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: theme.pageBg }}>
        <TopNav userName={userName} />
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
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: theme.pageBg }}>
      <TopNav userName={userName} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{
          padding: '24px 40px',
          borderBottom: `1px solid ${theme.border}`,
          backgroundColor: theme.cardBg,
        }}>
          <div style={{ maxWidth: '900px' }}>
            <h1 style={{
              fontSize: '26px',
              fontWeight: 700,
              color: theme.textPrimary,
              margin: 0,
              fontFamily: "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif",
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
        </div>

        {/* Content */}
        <div style={{ flex: 1, padding: '32px 40px', overflowY: 'auto' }}>
          <div style={{ maxWidth: '900px', margin: '0 auto' }}>

            {/* Account Type */}
            <section style={{
              ...sectionStyle,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  backgroundColor: user?.email === 'pranav@use2ndbrain.com' ? theme.primaryLight : theme.successLight,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={user?.email === 'pranav@use2ndbrain.com' ? theme.primary : theme.success} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                </div>
                <div>
                  <p style={{ fontSize: '13px', fontWeight: 600, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 2px' }}>
                    Account Type
                  </p>
                  <p style={{ fontSize: '16px', fontWeight: 600, color: theme.textPrimary, margin: 0 }}>
                    {user?.email === 'pranav@use2ndbrain.com' ? 'Admin' : 'Member'}
                  </p>
                </div>
              </div>
              <span style={{
                padding: '6px 14px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: 600,
                backgroundColor: user?.email === 'pranav@use2ndbrain.com' ? theme.primaryLight : theme.successLight,
                color: user?.email === 'pranav@use2ndbrain.com' ? theme.primary : theme.success,
              }}>
                {user?.email === 'pranav@use2ndbrain.com' ? 'Full Access + Analytics' : 'Standard Access'}
              </span>
            </section>

            {/* Chatbot Settings Section (Admin Only) */}
            {isAdmin && (
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
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={theme.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h2 style={{ fontSize: '18px', fontWeight: 600, color: theme.textPrimary, margin: 0 }}>
                      Chatbot Settings
                    </h2>
                    <p style={{ fontSize: '13px', color: theme.textMuted, margin: '2px 0 0' }}>
                      Control how detailed the AI responses are for your organization
                    </p>
                  </div>
                </div>

                {loadingChatSettings ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '20px 0' }}>
                    <div style={{
                      width: '20px',
                      height: '20px',
                      border: `2px solid ${theme.border}`,
                      borderTopColor: theme.primary,
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite',
                    }} />
                    <span style={{ fontSize: '14px', color: theme.textMuted }}>Loading settings...</span>
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: '20px' }}>
                    {/* Slider */}
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '14px',
                        fontWeight: 500,
                        color: theme.textPrimary,
                        marginBottom: '16px',
                      }}>
                        Response Detail Level
                      </label>

                      {/* 3-stop clickable selector */}
                      <div style={{ display: 'flex', gap: '12px' }}>
                        {responseModeLabels.map((mode) => (
                          <button
                            key={mode.value}
                            onClick={() => setResponseMode(mode.value)}
                            style={{
                              flex: 1,
                              padding: '14px 12px',
                              borderRadius: '12px',
                              border: `2px solid ${responseMode === mode.value ? theme.primary : theme.border}`,
                              backgroundColor: responseMode === mode.value ? theme.primaryLight : 'transparent',
                              cursor: 'pointer',
                              transition: 'all 0.2s',
                              textAlign: 'center',
                            }}
                            onMouseEnter={(e) => {
                              if (responseMode !== mode.value) {
                                e.currentTarget.style.borderColor = theme.primaryHover
                                e.currentTarget.style.backgroundColor = theme.pageBg
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (responseMode !== mode.value) {
                                e.currentTarget.style.borderColor = theme.border
                                e.currentTarget.style.backgroundColor = 'transparent'
                              }
                            }}
                          >
                            <div style={{
                              fontSize: '14px',
                              fontWeight: 600,
                              color: responseMode === mode.value ? theme.primary : theme.textPrimary,
                              marginBottom: '4px',
                            }}>
                              {mode.label}
                            </div>
                            <div style={{
                              fontSize: '11px',
                              color: responseMode === mode.value ? theme.primary : theme.textMuted,
                              lineHeight: '1.4',
                            }}>
                              {mode.value === 1 && 'Links to docs only'}
                              {mode.value === 2 && 'Brief answer + links'}
                              {mode.value === 3 && 'Full AI response'}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Description of selected mode */}
                    <div style={{
                      padding: '16px',
                      borderRadius: '10px',
                      backgroundColor: theme.pageBg,
                      border: `1px solid ${theme.border}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span style={{
                          fontSize: '13px',
                          fontWeight: 600,
                          color: theme.primary,
                          padding: '2px 8px',
                          backgroundColor: theme.primaryLight,
                          borderRadius: '4px',
                        }}>
                          Level {responseMode}
                        </span>
                        <span style={{ fontSize: '14px', fontWeight: 600, color: theme.textPrimary }}>
                          {responseModeLabels.find(m => m.value === responseMode)?.label}
                        </span>
                      </div>
                      <p style={{ fontSize: '13px', color: theme.textSecondary, margin: 0, lineHeight: '1.5' }}>
                        {responseModeLabels.find(m => m.value === responseMode)?.description}
                      </p>
                    </div>

                    {chatSettingsMessage && (
                      <div style={{
                        padding: '14px 16px',
                        borderRadius: '10px',
                        backgroundColor: chatSettingsMessage.type === 'success' ? theme.successLight : theme.errorLight,
                        color: chatSettingsMessage.type === 'success' ? theme.success : theme.error,
                        fontSize: '14px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                      }}>
                        {chatSettingsMessage.type === 'success' ? (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M20 6L9 17l-5-5" />
                          </svg>
                        ) : (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="12" cy="12" r="10" />
                            <path d="M12 8v4m0 4h.01" />
                          </svg>
                        )}
                        {chatSettingsMessage.text}
                      </div>
                    )}

                    <button
                      onClick={handleSaveChatSettings}
                      disabled={savingChatSettings}
                      style={{
                        padding: '12px 24px',
                        borderRadius: '10px',
                        backgroundColor: theme.primary,
                        color: '#FFFFFF',
                        border: 'none',
                        fontSize: '14px',
                        fontWeight: 600,
                        cursor: savingChatSettings ? 'wait' : 'pointer',
                        opacity: savingChatSettings ? 0.7 : 1,
                        width: 'fit-content',
                        transition: 'background-color 0.2s',
                      }}
                      onMouseEnter={(e) => {
                        if (!savingChatSettings) e.currentTarget.style.backgroundColor = theme.primaryHover
                      }}
                      onMouseLeave={(e) => {
                        if (!savingChatSettings) e.currentTarget.style.backgroundColor = theme.primary
                      }}
                    >
                      {savingChatSettings ? 'Saving...' : 'Save Chatbot Settings'}
                    </button>
                  </div>
                )}
              </section>
            )}

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
                    e.currentTarget.style.backgroundColor = '#FBE8E8'
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
