'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006';

// Get auth token from localStorage
const getAuthToken = () => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('accessToken');
};

interface EmailForwardingStatus {
  success: boolean;
  forwarding_address: string;
  configured: boolean;
  instructions: string;
}

export default function EmailForwardingCard() {
  const [status, setStatus] = useState<EmailForwardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const token = getAuthToken();
      // Use authenticated endpoint for proper tenant isolation
      const response = await axios.get(`${API_BASE_URL}/api/email-forwarding/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch status:', error);
      // Fallback to public endpoint if auth fails
      try {
        const response = await axios.get(`${API_BASE_URL}/api/email-forwarding/status-public`);
        setStatus(response.data);
      } catch (e) {
        console.error('Public fallback also failed:', e);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFetchEmails = async () => {
    setFetching(true);
    setResult(null);

    try {
      const token = getAuthToken();
      // Use authenticated endpoint for proper tenant isolation
      // Longer timeout since email fetching can take time
      const response = await axios.post(
        `${API_BASE_URL}/api/email-forwarding/fetch`,
        {},
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          timeout: 60000 // 60 second timeout for email operations
        }
      );

      setResult(response.data);
    } catch (error: any) {
      console.error('Email fetch error:', error);

      // If auth fails, try public endpoint as fallback
      if (error.response?.status === 401) {
        try {
          const response = await axios.post(
            `${API_BASE_URL}/api/email-forwarding/fetch-public`,
            {},
            { timeout: 60000 }
          );
          setResult(response.data);
          return;
        } catch (e: any) {
          console.error('Public endpoint error:', e);
          setResult({
            success: false,
            error: e.response?.data?.error || e.message
          });
          return;
        }
      }

      // Better error messages for common issues
      let errorMessage = error.response?.data?.error || error.message;
      if (error.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. The email server may be slow.';
      } else if (error.message === 'Network Error') {
        errorMessage = 'Could not connect to server. Please check your connection.';
      }

      setResult({
        success: false,
        error: errorMessage
      });
    } finally {
      setFetching(false);
    }
  };

  // Clean black and white design to match site aesthetic
  return (
    <div className="bg-white p-6">
      {/* Instructions */}
      <div className="mb-6">
        <p className="text-sm text-gray-600 mb-3" style={{ fontFamily: 'Inter, sans-serif' }}>
          Forward emails to this address to add them to your knowledge base:
        </p>
        <div className="border border-gray-300 rounded-lg px-4 py-3 bg-gray-50">
          <code className="text-base font-mono text-gray-900">
            {loading ? 'Loading...' : (status?.forwarding_address || 'beatatucla@gmail.com')}
          </code>
        </div>
      </div>

      {/* Fetch Button */}
      <button
        onClick={handleFetchEmails}
        disabled={fetching}
        className={`w-full py-3 px-4 rounded-lg font-medium text-sm transition-all ${
          fetching
            ? 'bg-gray-100 text-gray-400 cursor-wait border border-gray-300'
            : 'bg-black text-white hover:bg-gray-800 border border-black'
        }`}
        style={{ fontFamily: 'Inter, sans-serif' }}
      >
        {fetching ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Fetching emails...
          </span>
        ) : 'Fetch Emails'}
      </button>

      {/* Progress indicator while fetching */}
      {fetching && (
        <div className="mt-4 p-4 rounded-lg border border-blue-200 bg-blue-50">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <svg className="animate-spin h-5 w-5 text-blue-600" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-blue-900" style={{ fontFamily: 'Inter, sans-serif' }}>
                Syncing emails...
              </p>
              <p className="text-xs text-blue-700 mt-1" style={{ fontFamily: 'Inter, sans-serif' }}>
                This may take a minute. Processing new emails and adding them to your knowledge base.
              </p>
            </div>
          </div>
          <div className="mt-3 w-full bg-blue-200 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-blue-600 h-1.5 rounded-full"
              style={{
                width: '30%',
                animation: 'progressSlide 1.5s ease-in-out infinite'
              }}
            />
          </div>
          <style jsx>{`
            @keyframes progressSlide {
              0% { transform: translateX(-100%); }
              50% { transform: translateX(250%); }
              100% { transform: translateX(-100%); }
            }
          `}</style>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className={`mt-4 p-4 rounded-lg border ${
          result.success
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          {result.success ? (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <svg className="h-5 w-5 text-green-600" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <p className="text-sm font-medium text-green-900" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Sync Complete!
                </p>
              </div>
              <p className="text-sm text-green-700 mb-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                {result.processed > 0
                  ? `${result.processed} new email${result.processed !== 1 ? 's' : ''} added to your knowledge base.`
                  : 'No new emails to process. Your knowledge base is up to date!'}
              </p>
              {result.emails && result.emails.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-medium text-green-800" style={{ fontFamily: 'Inter, sans-serif' }}>Recently added:</p>
                  {result.emails.slice(0, 3).map((email: any, idx: number) => (
                    <div key={idx} className="text-xs text-gray-600 border-l-2 border-green-300 pl-3 py-1">
                      <p className="font-medium text-gray-900" style={{ fontFamily: 'Inter, sans-serif' }}>
                        {email.subject || 'No subject'}
                      </p>
                      <p className="text-gray-500" style={{ fontFamily: 'Inter, sans-serif' }}>
                        {email.from}
                      </p>
                    </div>
                  ))}
                  {result.emails.length > 3 && (
                    <p className="text-xs text-green-600" style={{ fontFamily: 'Inter, sans-serif' }}>
                      +{result.emails.length - 3} more
                    </p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-red-900 mb-1" style={{ fontFamily: 'Inter, sans-serif' }}>
                ✗ Error
              </p>
              <p className="text-sm text-red-700" style={{ fontFamily: 'Inter, sans-serif' }}>
                {result.error || 'Failed to fetch emails'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
