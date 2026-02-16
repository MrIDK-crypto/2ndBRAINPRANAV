'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../shared/Sidebar'
import Image from 'next/image'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

// Wellspring-Inspired Warm Design System
const warmTheme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F6',
  cardBg: '#FFFFFF',
  headerBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
}

interface Video {
  id: string
  title: string
  description: string | null
  status: string
  progress_percent: number
  file_path: string | null
  thumbnail_path: string | null
  duration_seconds: number | null
  created_at: string
  source_type: string
  slides_count: number | null
  views?: number
  author?: string
}

interface VideoPlayerModalProps {
  video: Video
  onClose: () => void
}

const VideoPlayerModal = ({ video, onClose }: VideoPlayerModalProps) => {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'Unknown'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '20px'
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          maxWidth: '900px',
          width: '100%',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Video Player Area */}
        <div
          style={{
            backgroundColor: '#0F172A',
            aspectRatio: '16/9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative'
          }}
        >
          {video.file_path ? (
            <video
              controls
              autoPlay
              style={{ width: '100%', height: '100%' }}
            >
              <source src={video.file_path} type="video/mp4" />
            </video>
          ) : (
            <div style={{ textAlign: 'center', color: '#94A3B8' }}>
              <svg width="80" height="80" viewBox="0 0 24 24" fill="none" style={{ margin: '0 auto 16px' }}>
                <circle cx="12" cy="12" r="10" stroke={warmTheme.primary} strokeWidth="2" />
                <path d="M10 8L16 12L10 16V8Z" fill={warmTheme.primary} />
              </svg>
              <p style={{ fontSize: '16px', fontWeight: 500 }}>Demo Video Preview</p>
              <p style={{ fontSize: '14px', marginTop: '8px' }}>Duration: {formatDuration(video.duration_seconds)}</p>
            </div>
          )}

          {/* Close button */}
          <button
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '16px',
              right: '16px',
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              backgroundColor: 'rgba(0,0,0,0.6)',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF'
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Video Info */}
        <div style={{ padding: '24px' }}>
          <h2 style={{
            fontSize: '20px',
            fontWeight: 600,
            color: warmTheme.textPrimary,
            marginBottom: '8px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            {video.title}
          </h2>
          <p style={{
            fontSize: '14px',
            color: warmTheme.textSecondary,
            marginBottom: '16px',
            lineHeight: '1.5'
          }}>
            {video.description}
          </p>
          <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '13px', color: warmTheme.textMuted }}>
              {video.views?.toLocaleString() || 0} views
            </span>
            <span style={{ fontSize: '13px', color: warmTheme.textMuted }}>
              {video.slides_count} slides
            </span>
            <span style={{ fontSize: '13px', color: warmTheme.textMuted }}>
              {formatDuration(video.duration_seconds)}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

// YouTube-style video item component
const VideoListItem = ({ video, onClick, index }: { video: Video, onClick: () => void, index: number }) => {
  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatViews = (views: number | undefined) => {
    if (!views) return '0 views'
    if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M views`
    if (views >= 1000) return `${(views / 1000).toFixed(1)}K views`
    return `${views} views`
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
    return `${Math.floor(diffDays / 365)} years ago`
  }

  // Warm gradient colors for thumbnails
  const gradients = [
    'linear-gradient(135deg, #C9A598 0%, #B8948A 100%)',
    'linear-gradient(135deg, #D4B8B0 0%, #C9A598 100%)',
    'linear-gradient(135deg, #9CB896 0%, #8AAA84 100%)',
    'linear-gradient(135deg, #B8C4D4 0%, #A0AEBE 100%)',
    'linear-gradient(135deg, #D4C4B8 0%, #C9B8A8 100%)',
  ]

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        gap: '20px',
        padding: '16px',
        borderRadius: '16px',
        cursor: 'pointer',
        transition: 'all 0.15s ease'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = warmTheme.primaryLight
        e.currentTarget.style.transform = 'translateX(4px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent'
        e.currentTarget.style.transform = 'translateX(0)'
      }}
    >
      {/* Thumbnail - Bigger */}
      <div style={{
        width: '280px',
        height: '157px',
        borderRadius: '12px',
        overflow: 'hidden',
        flexShrink: 0,
        position: 'relative',
        background: video.thumbnail_path ? undefined : gradients[index % gradients.length]
      }}>
        {video.thumbnail_path ? (
          <img
            src={video.thumbnail_path}
            alt={video.title}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none">
              <path d="M8 5V19L19 12L8 5Z" fill="rgba(255,255,255,0.9)" />
            </svg>
          </div>
        )}

        {/* Duration badge */}
        <div style={{
          position: 'absolute',
          bottom: '8px',
          right: '8px',
          backgroundColor: 'rgba(0,0,0,0.85)',
          color: '#FFFFFF',
          fontSize: '13px',
          fontWeight: 600,
          padding: '4px 8px',
          borderRadius: '4px'
        }}>
          {formatDuration(video.duration_seconds)}
        </div>
      </div>

      {/* Info - Larger text */}
      <div style={{ flex: 1, minWidth: 0, paddingTop: '4px' }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: warmTheme.textPrimary,
          marginBottom: '8px',
          lineHeight: '1.4',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }}>
          {video.title}
        </h3>
        <p style={{
          fontSize: '14px',
          color: warmTheme.textSecondary,
          marginBottom: '6px'
        }}>
          {video.author || '2nd Brain'}
        </p>
        <p style={{
          fontSize: '14px',
          color: warmTheme.textMuted
        }}>
          {formatViews(video.views)} • {formatDate(video.created_at)}
        </p>
      </div>

      {/* More options */}
      <button
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: warmTheme.textSecondary,
          flexShrink: 0
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="5" r="2" />
          <circle cx="12" cy="12" r="2" />
          <circle cx="12" cy="19" r="2" />
        </svg>
      </button>
    </div>
  )
}

export default function TrainingGuides() {
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const authHeaders = useAuthHeaders()
  const { user } = useAuth()

  useEffect(() => {
    loadVideos()
  }, [])

  const loadVideos = async () => {
    try {
      const response = await axios.get(`${API_BASE}/videos?status=completed`, {
        headers: authHeaders
      })

      if (response.data.success && response.data.videos) {
        setVideos(response.data.videos)
      } else {
        setVideos([])
      }
    } catch (error) {
      console.error('Error loading videos:', error)
      setVideos([])
    } finally {
      setLoading(false)
    }
  }

  const displayVideos = videos.filter(v =>
    v.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    v.description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const totalDuration = displayVideos.reduce((sum, v) => sum + (v.duration_seconds || 0), 0)
  const totalMins = Math.floor(totalDuration / 60)
  const totalViews = displayVideos.reduce((sum, v) => sum + (v.views || 0), 0)

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: warmTheme.pageBg }}>
      {/* Sidebar */}
      <Sidebar userName={user?.full_name?.split(' ')[0] || 'User'} />

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{
          padding: '24px 32px',
          borderBottom: `1px solid ${warmTheme.border}`,
          backgroundColor: warmTheme.headerBg
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h1 style={{
              fontSize: '24px',
              fontWeight: 700,
              color: warmTheme.textPrimary,
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
            }}>
              Training Videos
            </h1>

            {/* Search */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '10px 16px',
              backgroundColor: warmTheme.primaryLight,
              borderRadius: '24px',
              border: `1px solid ${warmTheme.border}`,
              width: '320px'
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={warmTheme.textMuted} strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <path d="M21 21l-4.35-4.35" />
              </svg>
              <input
                type="text"
                placeholder="Search videos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  flex: 1,
                  border: 'none',
                  outline: 'none',
                  backgroundColor: 'transparent',
                  fontSize: '14px',
                  color: warmTheme.textPrimary
                }}
              />
            </div>
          </div>
        </div>

        {/* Content Area - Full Width Video List */}
        <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
          {loading ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '300px'
            }}>
              <div style={{
                width: '32px',
                height: '32px',
                border: `3px solid ${warmTheme.border}`,
                borderTopColor: warmTheme.primary,
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }} />
            </div>
          ) : (
            <>
              {/* Stats Bar */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '24px'
              }}>
                <p style={{ fontSize: '14px', color: warmTheme.textSecondary }}>
                  {displayVideos.length} videos • {totalMins} min total
                </p>
              </div>

              {/* Video List - Full Width */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {displayVideos.map((video, index) => (
                  <VideoListItem
                    key={video.id}
                    video={video}
                    index={index}
                    onClick={() => setSelectedVideo(video)}
                  />
                ))}
              </div>

              {displayVideos.length === 0 && (
                <div style={{
                  textAlign: 'center',
                  padding: '48px',
                  backgroundColor: warmTheme.cardBg,
                  borderRadius: '16px',
                  border: `1px solid ${warmTheme.border}`
                }}>
                  <p style={{ fontSize: '16px', marginBottom: '8px', color: warmTheme.textSecondary }}>No videos found</p>
                  <p style={{ fontSize: '14px', color: warmTheme.textMuted }}>Try a different search term</p>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Video Player Modal */}
      {selectedVideo && (
        <VideoPlayerModal
          video={selectedVideo}
          onClose={() => setSelectedVideo(null)}
        />
      )}

      {/* CSS for spinner animation */}
      <style jsx global>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
