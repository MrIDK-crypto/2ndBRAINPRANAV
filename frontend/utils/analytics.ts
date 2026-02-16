/**
 * Lightweight analytics tracking utility for 2nd Brain.
 * Sends events to the backend /api/admin/track-event endpoint.
 */

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006') + '/api'

interface TrackEventProps {
  event: string
  properties?: Record<string, any>
}

/**
 * Track an analytics event. Fire-and-forget (does not block UI).
 */
export function trackEvent({ event, properties = {} }: TrackEventProps) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('accessToken') : null
  if (!token) return // Skip if not authenticated

  // Fire-and-forget - don't await
  fetch(`${API_BASE}/admin/track-event`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      event,
      properties: {
        ...properties,
        timestamp: new Date().toISOString(),
        url: typeof window !== 'undefined' ? window.location.pathname : '',
      },
    }),
  }).catch(() => {
    // Silently ignore tracking errors
  })
}

// Convenience methods for common events
export const analytics = {
  pageView: (page: string) => trackEvent({ event: 'page_view', properties: { page } }),
  chatQuestion: (queryLength: number) => trackEvent({ event: 'chat_question', properties: { query_length: queryLength } }),
  documentView: (docId: string) => trackEvent({ event: 'document_view', properties: { doc_id: docId } }),
  documentUpload: (fileCount: number) => trackEvent({ event: 'document_upload', properties: { file_count: fileCount } }),
  documentDelete: (docId: string) => trackEvent({ event: 'document_delete', properties: { doc_id: docId } }),
  gapAnalysis: (mode: string) => trackEvent({ event: 'gap_analysis', properties: { mode } }),
  integrationConnect: (type: string) => trackEvent({ event: 'integration_connect', properties: { integration_type: type } }),
  integrationSync: (type: string) => trackEvent({ event: 'integration_sync', properties: { integration_type: type } }),
  sidebarClick: (item: string) => trackEvent({ event: 'sidebar_click', properties: { item } }),
  feedbackGiven: (rating: string) => trackEvent({ event: 'feedback', properties: { rating } }),
  shareLink: () => trackEvent({ event: 'share_link_created' }),
  searchPerformed: (queryLength: number) => trackEvent({ event: 'search', properties: { query_length: queryLength } }),
}
