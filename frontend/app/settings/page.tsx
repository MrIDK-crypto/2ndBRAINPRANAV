'use client'

import React, { useState, useEffect } from 'react'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/shared/Sidebar'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

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
      <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#F8FAFC' }}>
        <Sidebar userName={userName} />
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ color: '#6B7280' }}>Loading...</div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#F8FAFC' }}>
      <Sidebar userName={userName} />
      <main style={{ flex: 1, padding: '32px', overflowY: 'auto' }}>
        <div style={{ maxWidth: '600px', margin: '0 auto' }}>
          <div style={{ marginBottom: '32px' }}>
            <h1 style={{ fontSize: '28px', fontWeight: 600, color: '#111827', marginBottom: '8px', fontFamily: '"Work Sans", sans-serif' }}>Account Settings</h1>
            <p style={{ color: '#6B7280', fontSize: '14px' }}>Manage your profile and security</p>
          </div>

          {/* Profile Section */}
          <section style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', padding: '24px', marginBottom: '24px', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', marginBottom: '20px' }}>
              Profile
            </h2>
            <div style={{ display: 'grid', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>Full Name</label>
                <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #E5E7EB', fontSize: '14px', outline: 'none' }} placeholder="Enter your full name" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>Email</label>
                <input type="email" value={user?.email || ''} disabled style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #E5E7EB', fontSize: '14px', backgroundColor: '#F9FAFB', color: '#6B7280' }} />
              </div>
              {profileMessage && <div style={{ padding: '12px', borderRadius: '8px', backgroundColor: profileMessage.type === 'success' ? '#ECFDF5' : '#FEF2F2', color: profileMessage.type === 'success' ? '#059669' : '#DC2626', fontSize: '14px' }}>{profileMessage.text}</div>}
              <button onClick={handleSaveProfile} disabled={savingProfile} style={{ padding: '10px 20px', borderRadius: '8px', backgroundColor: '#2563EB', color: '#FFFFFF', border: 'none', fontSize: '14px', fontWeight: 500, cursor: savingProfile ? 'wait' : 'pointer', opacity: savingProfile ? 0.7 : 1, width: 'fit-content' }}>{savingProfile ? 'Saving...' : 'Save Changes'}</button>
            </div>
          </section>

          {/* Security Section */}
          <section style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', padding: '24px', marginBottom: '24px', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', marginBottom: '20px' }}>
              Change Password
            </h2>
            <div style={{ display: 'grid', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>Current Password</label>
                <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #E5E7EB', fontSize: '14px', outline: 'none' }} placeholder="Enter current password" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>New Password</label>
                <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #E5E7EB', fontSize: '14px', outline: 'none' }} placeholder="Enter new password" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>Confirm New Password</label>
                <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #E5E7EB', fontSize: '14px', outline: 'none' }} placeholder="Confirm new password" />
              </div>
              {passwordMessage && <div style={{ padding: '12px', borderRadius: '8px', backgroundColor: passwordMessage.type === 'success' ? '#ECFDF5' : '#FEF2F2', color: passwordMessage.type === 'success' ? '#059669' : '#DC2626', fontSize: '14px' }}>{passwordMessage.text}</div>}
              <button onClick={handleChangePassword} disabled={savingPassword || !currentPassword || !newPassword || !confirmPassword} style={{ padding: '10px 20px', borderRadius: '8px', backgroundColor: '#2563EB', color: '#FFFFFF', border: 'none', fontSize: '14px', fontWeight: 500, cursor: 'pointer', opacity: (savingPassword || !currentPassword || !newPassword || !confirmPassword) ? 0.7 : 1, width: 'fit-content' }}>{savingPassword ? 'Changing...' : 'Change Password'}</button>
            </div>
          </section>

          {/* Sign Out Section */}
          <section style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', marginBottom: '16px' }}>
              Sign Out
            </h2>
            <button onClick={handleLogout} disabled={loggingOut} style={{ padding: '10px 20px', borderRadius: '8px', backgroundColor: '#FEE2E2', color: '#DC2626', border: '1px solid #FECACA', fontSize: '14px', fontWeight: 500, cursor: loggingOut ? 'wait' : 'pointer', opacity: loggingOut ? 0.7 : 1 }}>{loggingOut ? 'Signing out...' : 'Sign Out'}</button>
          </section>
        </div>
      </main>
    </div>
  )
}
