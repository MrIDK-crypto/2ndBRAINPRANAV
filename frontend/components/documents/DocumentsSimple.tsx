'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../shared/Sidebar'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006')

interface FetchedEmail {
  id: number
  subject: string
  from: string
  date: string
  body: string
  fetched_at: string
}

export default function DocumentsSimple() {
  const [emails, setEmails] = useState<FetchedEmail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadEmails()
    // Auto-refresh every 10 seconds
    const interval = setInterval(loadEmails, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadEmails = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/email-forwarding/documents`)
      if (response.data.success) {
        setEmails(response.data.emails || [])
        setError(null)
      } else {
        setError(response.data.error || 'Failed to load emails')
      }
    } catch (err: any) {
      setError(err.message || 'Connection error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-primary overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 bg-primary border-b border-gray-200">
          <div>
            <h1 style={{
              color: '#081028',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '28px',
              fontWeight: 600,
              lineHeight: '32px'
            }}>
              Documents
            </h1>
            <p style={{
              color: '#71717A',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '16px',
              fontWeight: 400,
              lineHeight: '24px',
              marginTop: '6px'
            }}>
              Fetched emails from beatatucla@gmail.com · {emails.length} total · Auto-refreshes every 10s
            </p>
          </div>
          <button
            onClick={loadEmails}
            className="px-4 py-2 bg-black text-white hover:bg-gray-800 transition-colors"
            style={{ borderRadius: '6px', fontSize: '14px', fontWeight: 500 }}
          >
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-8 py-6 bg-primary">
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-800 font-medium">Error: {error}</p>
              <p className="text-red-600 text-sm mt-1">
                Make sure the backend server is running on {API_BASE}
              </p>
            </div>
          )}

          {loading && emails.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <div className="w-8 h-8 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
                <p className="text-gray-600">Loading emails...</p>
              </div>
            </div>
          ) : emails.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center max-w-md">
                <h3 className="text-xl font-semibold text-gray-900 mb-2">No emails yet</h3>
                <p className="text-gray-600 mb-4">
                  Forward emails to <code className="bg-gray-100 px-2 py-1 rounded">beatatucla@gmail.com</code> and
                  click "Fetch Emails" in the <a href="/integrations" className="text-blue-600 hover:underline">Integrations page</a>
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4 max-w-5xl">
              {emails.slice().reverse().map((email) => (
                <div
                  key={email.id}
                  className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
                >
                  {/* Email Header */}
                  <div className="border-b border-gray-100 pb-4 mb-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      {email.subject}
                    </h3>
                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-600">
                      <span>
                        <strong className="font-medium text-gray-700">From:</strong> {email.from}
                      </span>
                      <span>
                        <strong className="font-medium text-gray-700">Date:</strong> {email.date || 'Unknown'}
                      </span>
                    </div>
                  </div>

                  {/* Email Body */}
                  <div
                    className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap font-light"
                    style={{ maxHeight: '200px', overflow: 'hidden' }}
                  >
                    {email.body}
                  </div>

                  {/* Email Footer */}
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-xs text-gray-500">
                      Fetched: {new Date(email.fetched_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
