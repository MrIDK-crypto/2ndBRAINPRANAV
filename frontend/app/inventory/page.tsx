'use client'

import Sidebar from '@/components/shared/Sidebar'
import Inventory from '@/components/inventory/Inventory'
import { useAuth } from '@/contexts/AuthContext'

export default function InventoryPage() {
  const { user } = useAuth()

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar userName={user?.full_name || 'User'} />
      <div style={{ flex: 1, backgroundColor: '#FAF9F7' }}>
        <Inventory />
      </div>
    </div>
  )
}
