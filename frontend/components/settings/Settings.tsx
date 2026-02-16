'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../shared/Sidebar'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

const colors = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  success: '#9CB896',
  danger: '#E57373',
}

interface ProfileData {
  full_name: string
  email: string
  job_title: string
  department: string
  location: string
  phone: string
  bio: string
  timezone: string
  language: string
}

export default function Settings() {
  const [activeItem, setActiveItem] = useState('Settings')
  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'preferences'>('profile')
  const [loggingOut, setLoggingOut] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const router = useRouter()
  const { logout, user, token } = useAuth()

  // Profile state
  const [profile, setProfile] = useState<ProfileData>({
    full_name: '',
    email: '',
    job_title: '',
    department: '',
    location: '',
    phone: '',
    bio: '',
    timezone: 'UTC',
    language: 'en',
  })

  // Password state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  const getAuthHeaders = () => ({
    'Authorization': token ? `Bearer ${token}` : '',
    'Content-Type': 'application/json'
  })

  // Load profile on mount
  useEffect(() => {
    if (token) {
      loadProfile()
    }
  }, [token])

  const loadProfile = async () => {
    try {
      const response = await axios.get(`${API_BASE}/profile`, {
        headers: getAuthHeaders()
      })
      if (response.data.success) {
        const u = response.data.user
        setProfile({
          full_name: u.full_name || '',
          email: u.email || '',
          job_title: u.job_title || '',
          department: u.department || '',
          location: u.location || '',
          phone: u.phone || '',
          bio: u.bio || '',
          timezone: u.timezone || 'UTC',
          language: u.language || 'en',
        })
      }
    } catch (error) {
      console.error('Error loading profile:', error)
    }
  }

  const handleSaveProfile = async () => {
    setSaving(true)
    setSaveMessage(null)
    try {
      const response = await axios.put(`${API_BASE}/profile`, {
        full_name: profile.full_name,
        job_title: profile.job_title,
        department: profile.department,
        location: profile.location,
        phone: profile.phone,
        bio: profile.bio,
        timezone: profile.timezone,
        language: profile.language,
      }, { headers: getAuthHeaders() })

      if (response.data.success) {
        setSaveMessage({ type: 'success', text: 'Profile updated successfully' })
        setTimeout(() => setSaveMessage(null), 3000)
      }
    } catch (error: any) {
      setSaveMessage({ type: 'error', text: error.response?.data?.error || 'Failed to update profile' })
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      setSaveMessage({ type: 'error', text: 'New passwords do not match' })
      return
    }
    if (newPassword.length < 8) {
      setSaveMessage({ type: 'error', text: 'Password must be at least 8 characters' })
      return
    }

    setChangingPassword(true)
    setSaveMessage(null)
    try {
      const response = await axios.put(`${API_BASE}/profile/password`, {
        current_password: currentPassword,
        new_password: newPassword,
      }, { headers: getAuthHeaders() })

      if (response.data.success) {
        setSaveMessage({ type: 'success', text: 'Password changed successfully' })
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
        setTimeout(() => setSaveMessage(null), 3000)
      }
    } catch (error: any) {
      setSaveMessage({ type: 'error', text: error.response?.data?.error || 'Failed to change password' })
    } finally {
      setChangingPassword(false)
    }
  }

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await logout()
      router.push('/login')
    } catch (error) {
      console.error('Logout failed:', error)
      router.push('/login')
    } finally {
      setLoggingOut(false)
    }
  }

  const InputField = ({ label, value, onChange, type = 'text', placeholder = '', disabled = false }: {
    label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string; disabled?: boolean
  }) => (
    <div style={{ marginBottom: '20px' }}>
      <label style={{
        display: 'block',
        fontSize: '13px',
        fontWeight: 600,
        color: colors.textSecondary,
        marginBottom: '6px',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '12px 16px',
          fontSize: '15px',
          border: `1px solid ${colors.border}`,
          borderRadius: '10px',
          backgroundColor: disabled ? '#F5F5F5' : colors.cardBg,
          color: disabled ? colors.textMuted : colors.textPrimary,
          outline: 'none',
          transition: 'border-color 0.15s ease',
          boxSizing: 'border-box',
        }}
        onFocus={(e) => { if (!disabled) e.currentTarget.style.borderColor = colors.primary }}
        onBlur={(e) => e.currentTarget.style.borderColor = colors.border}
      />
    </div>
  )

  const tabs = [
    { id: 'profile' as const, label: 'Profile', icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </svg>
    )},
    { id: 'password' as const, label: 'Security', icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </svg>
    )},
    { id: 'preferences' as const, label: 'Preferences', icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    )},
  ]

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: colors.pageBg }}>
      <Sidebar activeItem={activeItem} onItemClick={setActiveItem} userName={user?.full_name?.split(' ')[0] || 'User'} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ padding: '32px 40px 0', backgroundColor: colors.pageBg }}>
          <h1 style={{
            fontSize: '28px',
            fontWeight: 700,
            color: colors.textPrimary,
            margin: '0 0 24px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}>
            Account Settings
          </h1>

          {/* Tab Bar */}
          <div style={{ display: 'flex', gap: '4px', borderBottom: `1px solid ${colors.border}` }}>
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id); setSaveMessage(null) }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '12px 20px',
                  fontSize: '14px',
                  fontWeight: activeTab === tab.id ? 600 : 400,
                  color: activeTab === tab.id ? colors.primary : colors.textSecondary,
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === tab.id ? `2px solid ${colors.primary}` : '2px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  marginBottom: '-1px',
                }}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, padding: '32px 40px', overflow: 'auto' }}>
          <div style={{ maxWidth: '100%' }}>

            {/* Save/Error Message */}
            {saveMessage && (
              <div style={{
                padding: '12px 16px',
                borderRadius: '10px',
                marginBottom: '24px',
                backgroundColor: saveMessage.type === 'success' ? '#F0F7EE' : '#FDF0F0',
                border: `1px solid ${saveMessage.type === 'success' ? colors.success : colors.danger}`,
                color: saveMessage.type === 'success' ? '#5A7A52' : '#C94A4A',
                fontSize: '14px',
                fontWeight: 500,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}>
                {saveMessage.type === 'success' ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5"/></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                )}
                {saveMessage.text}
              </div>
            )}

            {/* Profile Tab */}
            {activeTab === 'profile' && (
              <div>
                {/* Avatar Section */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '20px',
                  marginBottom: '32px',
                  padding: '24px',
                  backgroundColor: colors.cardBg,
                  borderRadius: '16px',
                  border: `1px solid ${colors.border}`,
                }}>
                  <div style={{
                    width: '72px',
                    height: '72px',
                    borderRadius: '50%',
                    backgroundColor: colors.primaryLight,
                    border: `3px solid ${colors.primary}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '28px',
                    fontWeight: 700,
                    color: colors.primary,
                    flexShrink: 0,
                  }}>
                    {(profile.full_name || 'U').charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: colors.textPrimary, marginBottom: '4px' }}>
                      {profile.full_name || 'User'}
                    </div>
                    <div style={{ fontSize: '14px', color: colors.textMuted }}>
                      {profile.email}
                    </div>
                    {profile.job_title && (
                      <div style={{ fontSize: '13px', color: colors.textSecondary, marginTop: '4px' }}>
                        {profile.job_title}{profile.department ? ` - ${profile.department}` : ''}
                      </div>
                    )}
                  </div>
                </div>

                {/* Profile Form */}
                <div style={{
                  padding: '28px',
                  backgroundColor: colors.cardBg,
                  borderRadius: '16px',
                  border: `1px solid ${colors.border}`,
                }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 24px' }}>
                    Personal Information
                  </h3>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 20px' }}>
                    <InputField
                      label="Full Name"
                      value={profile.full_name}
                      onChange={(v) => setProfile(p => ({ ...p, full_name: v }))}
                      placeholder="John Doe"
                    />
                    <InputField
                      label="Email"
                      value={profile.email}
                      onChange={() => {}}
                      disabled
                    />
                    <InputField
                      label="Job Title"
                      value={profile.job_title}
                      onChange={(v) => setProfile(p => ({ ...p, job_title: v }))}
                      placeholder="Software Engineer"
                    />
                    <InputField
                      label="Department"
                      value={profile.department}
                      onChange={(v) => setProfile(p => ({ ...p, department: v }))}
                      placeholder="Engineering"
                    />
                    <InputField
                      label="Location"
                      value={profile.location}
                      onChange={(v) => setProfile(p => ({ ...p, location: v }))}
                      placeholder="San Francisco, CA"
                    />
                    <InputField
                      label="Phone"
                      value={profile.phone}
                      onChange={(v) => setProfile(p => ({ ...p, phone: v }))}
                      placeholder="+1 (555) 000-0000"
                    />
                  </div>

                  <div style={{ marginBottom: '20px' }}>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: 600,
                      color: colors.textSecondary,
                      marginBottom: '6px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}>
                      Bio
                    </label>
                    <textarea
                      value={profile.bio}
                      onChange={(e) => setProfile(p => ({ ...p, bio: e.target.value }))}
                      placeholder="Tell us a bit about yourself..."
                      rows={3}
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        fontSize: '15px',
                        border: `1px solid ${colors.border}`,
                        borderRadius: '10px',
                        backgroundColor: colors.cardBg,
                        color: colors.textPrimary,
                        outline: 'none',
                        resize: 'vertical',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                        boxSizing: 'border-box',
                      }}
                      onFocus={(e) => e.currentTarget.style.borderColor = colors.primary}
                      onBlur={(e) => e.currentTarget.style.borderColor = colors.border}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '8px' }}>
                    <button
                      onClick={handleSaveProfile}
                      disabled={saving}
                      style={{
                        padding: '12px 28px',
                        backgroundColor: saving ? colors.textMuted : colors.primary,
                        border: 'none',
                        borderRadius: '10px',
                        color: '#FFFFFF',
                        fontSize: '14px',
                        fontWeight: 600,
                        cursor: saving ? 'not-allowed' : 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => { if (!saving) e.currentTarget.style.backgroundColor = colors.primaryHover }}
                      onMouseLeave={(e) => { if (!saving) e.currentTarget.style.backgroundColor = colors.primary }}
                    >
                      {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Security Tab */}
            {activeTab === 'password' && (
              <div>
                <div style={{
                  padding: '28px',
                  backgroundColor: colors.cardBg,
                  borderRadius: '16px',
                  border: `1px solid ${colors.border}`,
                  marginBottom: '24px',
                }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 24px' }}>
                    Change Password
                  </h3>

                  <InputField
                    label="Current Password"
                    value={currentPassword}
                    onChange={setCurrentPassword}
                    type="password"
                    placeholder="Enter current password"
                  />
                  <InputField
                    label="New Password"
                    value={newPassword}
                    onChange={setNewPassword}
                    type="password"
                    placeholder="Enter new password (min 8 characters)"
                  />
                  <InputField
                    label="Confirm New Password"
                    value={confirmPassword}
                    onChange={setConfirmPassword}
                    type="password"
                    placeholder="Confirm new password"
                  />

                  {newPassword && confirmPassword && newPassword !== confirmPassword && (
                    <p style={{ color: colors.danger, fontSize: '13px', marginBottom: '16px' }}>
                      Passwords do not match
                    </p>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '8px' }}>
                    <button
                      onClick={handleChangePassword}
                      disabled={changingPassword || !currentPassword || !newPassword || newPassword !== confirmPassword}
                      style={{
                        padding: '12px 28px',
                        backgroundColor: (changingPassword || !currentPassword || !newPassword || newPassword !== confirmPassword) ? colors.textMuted : colors.primary,
                        border: 'none',
                        borderRadius: '10px',
                        color: '#FFFFFF',
                        fontSize: '14px',
                        fontWeight: 600,
                        cursor: (changingPassword || !currentPassword || !newPassword || newPassword !== confirmPassword) ? 'not-allowed' : 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {changingPassword ? 'Changing...' : 'Change Password'}
                    </button>
                  </div>
                </div>

                {/* Session Info */}
                <div style={{
                  padding: '28px',
                  backgroundColor: colors.cardBg,
                  borderRadius: '16px',
                  border: `1px solid ${colors.border}`,
                }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 16px' }}>
                    Active Session
                  </h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '16px', backgroundColor: '#F8F8F6', borderRadius: '10px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: colors.success }} />
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 500, color: colors.textPrimary }}>Current Browser</div>
                      <div style={{ fontSize: '12px', color: colors.textMuted }}>Logged in now</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Preferences Tab */}
            {activeTab === 'preferences' && (
              <div>
                <div style={{
                  padding: '28px',
                  backgroundColor: colors.cardBg,
                  borderRadius: '16px',
                  border: `1px solid ${colors.border}`,
                  marginBottom: '24px',
                }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 24px' }}>
                    Regional Settings
                  </h3>

                  <div style={{ marginBottom: '20px' }}>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: 600,
                      color: colors.textSecondary,
                      marginBottom: '6px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}>
                      Timezone
                    </label>
                    <select
                      value={profile.timezone}
                      onChange={(e) => setProfile(p => ({ ...p, timezone: e.target.value }))}
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        fontSize: '15px',
                        border: `1px solid ${colors.border}`,
                        borderRadius: '10px',
                        backgroundColor: colors.cardBg,
                        color: colors.textPrimary,
                        outline: 'none',
                        cursor: 'pointer',
                        boxSizing: 'border-box',
                      }}
                    >
                      <option value="UTC">UTC</option>
                      <option value="America/New_York">Eastern Time (ET)</option>
                      <option value="America/Chicago">Central Time (CT)</option>
                      <option value="America/Denver">Mountain Time (MT)</option>
                      <option value="America/Los_Angeles">Pacific Time (PT)</option>
                      <option value="Europe/London">London (GMT)</option>
                      <option value="Europe/Paris">Paris (CET)</option>
                      <option value="Asia/Tokyo">Tokyo (JST)</option>
                      <option value="Asia/Kolkata">India (IST)</option>
                      <option value="Australia/Sydney">Sydney (AEST)</option>
                    </select>
                  </div>

                  <div style={{ marginBottom: '20px' }}>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: 600,
                      color: colors.textSecondary,
                      marginBottom: '6px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}>
                      Language
                    </label>
                    <select
                      value={profile.language}
                      onChange={(e) => setProfile(p => ({ ...p, language: e.target.value }))}
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        fontSize: '15px',
                        border: `1px solid ${colors.border}`,
                        borderRadius: '10px',
                        backgroundColor: colors.cardBg,
                        color: colors.textPrimary,
                        outline: 'none',
                        cursor: 'pointer',
                        boxSizing: 'border-box',
                      }}
                    >
                      <option value="en">English</option>
                      <option value="es">Spanish</option>
                      <option value="fr">French</option>
                      <option value="de">German</option>
                      <option value="ja">Japanese</option>
                      <option value="zh">Chinese</option>
                    </select>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '8px' }}>
                    <button
                      onClick={handleSaveProfile}
                      disabled={saving}
                      style={{
                        padding: '12px 28px',
                        backgroundColor: saving ? colors.textMuted : colors.primary,
                        border: 'none',
                        borderRadius: '10px',
                        color: '#FFFFFF',
                        fontSize: '14px',
                        fontWeight: 600,
                        cursor: saving ? 'not-allowed' : 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => { if (!saving) e.currentTarget.style.backgroundColor = colors.primaryHover }}
                      onMouseLeave={(e) => { if (!saving) e.currentTarget.style.backgroundColor = colors.primary }}
                    >
                      {saving ? 'Saving...' : 'Save Preferences'}
                    </button>
                  </div>
                </div>

                {/* Danger Zone */}
                <div style={{
                  padding: '28px',
                  backgroundColor: colors.cardBg,
                  borderRadius: '16px',
                  border: `1px solid ${colors.danger}40`,
                }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.danger, margin: '0 0 12px' }}>
                    Danger Zone
                  </h3>
                  <p style={{ fontSize: '14px', color: colors.textSecondary, marginBottom: '20px' }}>
                    Once you log out, you will need to sign in again with your credentials.
                  </p>
                  <button
                    onClick={handleLogout}
                    disabled={loggingOut}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '12px 24px',
                      backgroundColor: 'transparent',
                      border: `1px solid ${colors.danger}`,
                      borderRadius: '10px',
                      color: colors.danger,
                      fontSize: '14px',
                      fontWeight: 600,
                      cursor: loggingOut ? 'not-allowed' : 'pointer',
                      opacity: loggingOut ? 0.6 : 1,
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#FDF0F0'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent'
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                      <polyline points="16 17 21 12 16 7"/>
                      <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                    {loggingOut ? 'Logging out...' : 'Log Out'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
