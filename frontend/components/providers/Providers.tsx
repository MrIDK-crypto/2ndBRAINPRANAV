'use client'

import { AuthProvider } from '@/contexts/AuthContext'
import { SyncProgressProvider } from '@/contexts/SyncProgressContext'
import GlobalSyncIndicator from '@/components/sync/GlobalSyncIndicator'
import { ReactNode } from 'react'

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <SyncProgressProvider>
        {children}
        <GlobalSyncIndicator />
      </SyncProgressProvider>
    </AuthProvider>
  )
}
