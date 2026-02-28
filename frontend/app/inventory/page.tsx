'use client'

import TopNav from '@/components/shared/TopNav'
import Inventory from '@/components/inventory/Inventory'
import { useAuth } from '@/contexts/AuthContext'

export default function InventoryPage() {
  const { user } = useAuth()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <TopNav userName={user?.full_name || 'User'} />
      <div style={{ flex: 1, backgroundColor: '#F8FAFC' }}>
        <Inventory />
      </div>
    </div>
  )
}
