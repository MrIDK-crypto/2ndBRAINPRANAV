'use client'

import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'

// Types
interface InventoryCategory {
  id: string
  name: string
  description?: string
  color: string
  item_count: number
}

interface InventoryLocation {
  id: string
  name: string
  description?: string
  building?: string
  room?: string
  item_count: number
}

interface InventoryVendor {
  id: string
  name: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  website?: string
  item_count: number
}

interface InventoryTransaction {
  id: string
  item_id: string
  user_name: string
  transaction_type: string
  field_changed?: string
  old_value?: string
  new_value?: string
  quantity_change?: number
  quantity_before?: number
  quantity_after?: number
  notes?: string
  reference?: string
  created_at: string
}

interface InventoryItem {
  id: string
  name: string
  description?: string
  sku?: string
  barcode?: string
  quantity: number
  min_quantity: number
  unit: string
  unit_price?: number
  currency: string
  category_id?: string
  location_id?: string
  vendor_id?: string
  category?: InventoryCategory
  location?: InventoryLocation
  vendor?: InventoryVendor
  purchase_date?: string
  warranty_expiry?: string
  manufacturer?: string
  model_number?: string
  serial_number?: string
  notes?: string
  // Lab-specific fields
  hazard_class?: string
  sds_url?: string
  storage_temp?: string
  storage_conditions?: string
  requires_calibration?: boolean
  calibration_interval_days?: number
  last_calibration?: string
  next_calibration?: string
  requires_maintenance?: boolean
  maintenance_interval_days?: number
  last_maintenance?: string
  next_maintenance?: string
  last_used?: string
  use_count?: number
  is_checked_out?: boolean
  checked_out_by?: string
  // Computed
  is_low_stock: boolean
  is_warranty_expiring_soon: boolean
  is_calibration_due?: boolean
  is_maintenance_due?: boolean
  total_value: number
  created_at: string
}

interface Stats {
  total_items: number
  total_value: number
  low_stock_count: number
  categories_count: number
  locations_count: number
  vendors_count: number
}

interface Alerts {
  low_stock: InventoryItem[]
  expiring_warranty: InventoryItem[]
  expired_warranty: InventoryItem[]
  counts: {
    total_alerts: number
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5003/api'

export default function Inventory() {
  const { token } = useAuth()
  const [activeTab, setActiveTab] = useState<'items' | 'categories' | 'locations' | 'vendors' | 'history'>('items')
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')

  // Data states
  const [items, setItems] = useState<InventoryItem[]>([])
  const [categories, setCategories] = useState<InventoryCategory[]>([])
  const [locations, setLocations] = useState<InventoryLocation[]>([])
  const [vendors, setVendors] = useState<InventoryVendor[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [alerts, setAlerts] = useState<Alerts | null>(null)
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([])

  // UI states
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCategory, setFilterCategory] = useState<string>('')
  const [filterLocation, setFilterLocation] = useState<string>('')
  const [showLowStockOnly, setShowLowStockOnly] = useState(false)

  // Barcode scanner state
  const [showBarcodeScanner, setShowBarcodeScanner] = useState(false)
  const [barcodeInput, setBarcodeInput] = useState('')
  const [scannedItem, setScannedItem] = useState<InventoryItem | null>(null)

  
  // Modal states
  const [showAddItemModal, setShowAddItemModal] = useState(false)
  const [showAddCategoryModal, setShowAddCategoryModal] = useState(false)
  const [showAddLocationModal, setShowAddLocationModal] = useState(false)
  const [showAddVendorModal, setShowAddVendorModal] = useState(false)
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null)

  // Form states
  const [itemForm, setItemForm] = useState({
    name: '',
    description: '',
    sku: '',
    quantity: 0,
    min_quantity: 0,
    unit: 'units',
    unit_price: '',
    category_id: '',
    location_id: '',
    vendor_id: '',
    manufacturer: '',
    model_number: '',
    serial_number: '',
    warranty_expiry: '',
    notes: ''
  })

  const [categoryForm, setCategoryForm] = useState({ name: '', description: '', color: '#C9A598' })
  const [locationForm, setLocationForm] = useState({ name: '', description: '', building: '', room: '' })
  const [vendorForm, setVendorForm] = useState({ name: '', contact_name: '', contact_email: '', contact_phone: '', website: '' })

  // API helper
  const api = axios.create({
    baseURL: API_BASE,
    headers: { Authorization: `Bearer ${token}` }
  })

  // Fetch data
  const fetchData = async () => {
    setIsLoading(true)
    try {
      const [itemsRes, categoriesRes, locationsRes, vendorsRes, statsRes, alertsRes] = await Promise.all([
        api.get('/inventory/items'),
        api.get('/inventory/categories'),
        api.get('/inventory/locations'),
        api.get('/inventory/vendors'),
        api.get('/inventory/stats'),
        api.get('/inventory/alerts')
      ])
      setItems(itemsRes.data)
      setCategories(categoriesRes.data)
      setLocations(locationsRes.data)
      setVendors(vendorsRes.data)
      setStats(statsRes.data)
      setAlerts(alertsRes.data)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load inventory')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (token) {
      fetchData()
    }
  }, [token])

  // Fetch additional data based on active tab
  useEffect(() => {
    if (!token) return
    if (activeTab === 'history') {
      fetchTransactions()
    }
  }, [activeTab, token])

  const fetchTransactions = async () => {
    try {
      const res = await api.get('/inventory/transactions?limit=100')
      setTransactions(res.data.transactions || [])
    } catch (err) {
      console.error('Failed to fetch transactions', err)
    }
  }

  // Barcode lookup
  const handleBarcodeLookup = async () => {
    if (!barcodeInput.trim()) return
    try {
      const res = await api.get(`/inventory/barcode/${encodeURIComponent(barcodeInput.trim())}`)
      setScannedItem(res.data)
      setBarcodeInput('')
    } catch (err: any) {
      alert(err.response?.data?.error || 'Item not found')
      setScannedItem(null)
    }
  }

  // Send email alerts
  const handleSendAlerts = async () => {
    try {
      const res = await api.post('/inventory/alerts/send')
      alert(res.data.message)
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to send alerts')
    }
  }

  // Filter items
  const filteredItems = items.filter(item => {
    if (searchQuery && !item.name.toLowerCase().includes(searchQuery.toLowerCase())) return false
    if (filterCategory && item.category_id !== filterCategory) return false
    if (filterLocation && item.location_id !== filterLocation) return false
    if (showLowStockOnly && !item.is_low_stock) return false
    return true
  })

  // Handlers
  const handleAddItem = async () => {
    try {
      const payload = {
        ...itemForm,
        quantity: Number(itemForm.quantity),
        min_quantity: Number(itemForm.min_quantity),
        unit_price: itemForm.unit_price ? Number(itemForm.unit_price) : undefined,
        category_id: itemForm.category_id || undefined,
        location_id: itemForm.location_id || undefined,
        vendor_id: itemForm.vendor_id || undefined,
        warranty_expiry: itemForm.warranty_expiry || undefined
      }
      if (editingItem) {
        await api.put(`/inventory/items/${editingItem.id}`, payload)
      } else {
        await api.post('/inventory/items', payload)
      }
      setShowAddItemModal(false)
      setEditingItem(null)
      resetItemForm()
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to save item')
    }
  }

  const handleDeleteItem = async (id: string) => {
    if (!confirm('Are you sure you want to delete this item?')) return
    try {
      await api.delete(`/inventory/items/${id}`)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete item')
    }
  }

  const handleAdjustQuantity = async (id: string, adjustment: number) => {
    try {
      await api.post(`/inventory/items/${id}/adjust-quantity`, { adjustment })
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to adjust quantity')
    }
  }

  const handleAddCategory = async () => {
    try {
      await api.post('/inventory/categories', categoryForm)
      setShowAddCategoryModal(false)
      setCategoryForm({ name: '', description: '', color: '#C9A598' })
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to add category')
    }
  }

  const handleDeleteCategory = async (id: string) => {
    if (!confirm('Are you sure? Category must have no items to delete.')) return
    try {
      await api.delete(`/inventory/categories/${id}`)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete category')
    }
  }

  const handleAddLocation = async () => {
    try {
      await api.post('/inventory/locations', locationForm)
      setShowAddLocationModal(false)
      setLocationForm({ name: '', description: '', building: '', room: '' })
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to add location')
    }
  }

  const handleDeleteLocation = async (id: string) => {
    if (!confirm('Are you sure? Location must have no items to delete.')) return
    try {
      await api.delete(`/inventory/locations/${id}`)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete location')
    }
  }

  const handleAddVendor = async () => {
    try {
      await api.post('/inventory/vendors', vendorForm)
      setShowAddVendorModal(false)
      setVendorForm({ name: '', contact_name: '', contact_email: '', contact_phone: '', website: '' })
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to add vendor')
    }
  }

  const handleDeleteVendor = async (id: string) => {
    if (!confirm('Are you sure? Vendor must have no items to delete.')) return
    try {
      await api.delete(`/inventory/vendors/${id}`)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete vendor')
    }
  }

  const handleExport = async () => {
    try {
      const response = await api.get('/inventory/export', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'inventory_export.csv')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Failed to export inventory')
    }
  }

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    try {
      setIsLoading(true)
      const response = await api.post('/inventory/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      alert(`${response.data.message}${response.data.errors?.length ? `\n\nWarnings:\n${response.data.errors.join('\n')}` : ''}`)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to import file')
    } finally {
      setIsLoading(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const handleClearAll = async () => {
    if (!confirm('WARNING: This will permanently delete ALL inventory data (items, categories, locations, vendors). This cannot be undone. Continue?')) return
    if (!confirm('Are you absolutely sure? Type "DELETE" in the next prompt to confirm.')) return
    const confirmation = prompt('Type DELETE to confirm:')
    if (confirmation !== 'DELETE') {
      alert('Deletion cancelled.')
      return
    }
    try {
      setIsLoading(true)
      await api.delete('/inventory/clear-all')
      alert('All inventory data has been cleared.')
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to clear inventory')
    } finally {
      setIsLoading(false)
    }
  }

  const resetItemForm = () => {
    setItemForm({
      name: '', description: '', sku: '', quantity: 0, min_quantity: 0,
      unit: 'units', unit_price: '', category_id: '', location_id: '',
      vendor_id: '', manufacturer: '', model_number: '', serial_number: '',
      warranty_expiry: '', notes: ''
    })
  }

  const openEditItem = (item: InventoryItem) => {
    setEditingItem(item)
    setItemForm({
      name: item.name,
      description: item.description || '',
      sku: item.sku || '',
      quantity: item.quantity,
      min_quantity: item.min_quantity,
      unit: item.unit,
      unit_price: item.unit_price?.toString() || '',
      category_id: item.category_id || '',
      location_id: item.location_id || '',
      vendor_id: item.vendor_id || '',
      manufacturer: item.manufacturer || '',
      model_number: item.model_number || '',
      serial_number: item.serial_number || '',
      warranty_expiry: item.warranty_expiry ? item.warranty_expiry.split('T')[0] : '',
      notes: item.notes || ''
    })
    setShowAddItemModal(true)
  }

  // Styles
  const styles = {
    container: { padding: '32px', maxWidth: '1400px', margin: '0 auto' },
    header: { marginBottom: '32px' },
    title: { fontSize: '28px', fontWeight: 700, color: '#2D2D2D', marginBottom: '8px' },
    subtitle: { fontSize: '14px', color: '#6B6B6B' },
    statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' },
    statCard: {
      backgroundColor: '#FFFFFF', borderRadius: '12px', padding: '20px',
      border: '1px solid #F0EEEC', boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
    },
    statValue: { fontSize: '24px', fontWeight: 700, color: '#2D2D2D' },
    statLabel: { fontSize: '13px', color: '#6B6B6B', marginTop: '4px' },
    alertBanner: {
      backgroundColor: '#F9F1ED', border: '1px solid #E5CFC5', borderRadius: '12px',
      padding: '16px 20px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px'
    },
    tabs: { display: 'flex', gap: '8px', marginBottom: '24px' },
    tab: (active: boolean) => ({
      padding: '10px 20px', borderRadius: '8px', border: 'none', cursor: 'pointer',
      backgroundColor: active ? '#C9A598' : '#F7F5F3', color: active ? '#FFFFFF' : '#6B6B6B',
      fontWeight: 500, fontSize: '14px', transition: 'all 0.15s'
    }),
    toolbar: {
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: '20px', gap: '16px', flexWrap: 'wrap' as const
    },
    searchInput: {
      padding: '10px 14px', borderRadius: '8px', border: '1px solid #F0EEEC',
      fontSize: '14px', width: '280px', outline: 'none'
    },
    select: {
      padding: '10px 14px', borderRadius: '8px', border: '1px solid #F0EEEC',
      fontSize: '14px', backgroundColor: '#FFFFFF', outline: 'none', cursor: 'pointer'
    },
    button: (primary = false) => ({
      padding: '10px 20px', borderRadius: '8px', border: 'none', cursor: 'pointer',
      backgroundColor: primary ? '#C9A598' : '#F7F5F3', color: primary ? '#FFFFFF' : '#6B6B6B',
      fontWeight: 500, fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px'
    }),
    table: { width: '100%', borderCollapse: 'collapse' as const },
    th: {
      textAlign: 'left' as const, padding: '12px 16px', backgroundColor: '#F7F5F3',
      fontSize: '12px', fontWeight: 600, color: '#6B6B6B', textTransform: 'uppercase' as const,
      borderBottom: '1px solid #F0EEEC'
    },
    td: {
      padding: '16px', borderBottom: '1px solid #F0EEEC', fontSize: '14px', color: '#2D2D2D'
    },
    badge: (type: 'warning' | 'danger' | 'success' | 'default') => {
      // Warm taupe color scheme badges
      const colors = {
        warning: { bg: '#F5E6D3', text: '#8B6914' },      // Warm amber
        danger: { bg: '#FEE2E2', text: '#D97B7B' },       // Warm terracotta
        success: { bg: '#F0FDF4', text: '#6B6B6B' },      // Muted taupe (OK status)
        default: { bg: '#F7F5F3', text: '#6B6B6B' }       // Light cream
      }
      return {
        padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 500,
        backgroundColor: colors[type].bg, color: colors[type].text, display: 'inline-block'
      }
    },
    modal: {
      position: 'fixed' as const, top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', zIndex: 1000
    },
    modalContent: {
      backgroundColor: '#FFFFFF', borderRadius: '16px', padding: '32px',
      width: '90%', maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto' as const
    },
    modalTitle: { fontSize: '20px', fontWeight: 600, color: '#2D2D2D', marginBottom: '24px' },
    formGroup: { marginBottom: '20px' },
    formLabel: { display: 'block', fontSize: '13px', fontWeight: 500, color: '#4B5563', marginBottom: '6px' },
    formInput: {
      width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #F0EEEC',
      fontSize: '14px', outline: 'none', boxSizing: 'border-box' as const
    },
    formRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' },
    card: {
      backgroundColor: '#FFFFFF', borderRadius: '12px', padding: '20px',
      border: '1px solid #F0EEEC', marginBottom: '12px'
    }
  }

  if (isLoading) {
    return (
      <div style={{ ...styles.container, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '40px', height: '40px', border: '3px solid #F0EEEC',
            borderTopColor: '#C9A598', borderRadius: '50%', animation: 'spin 1s linear infinite',
            margin: '0 auto 16px'
          }} />
          <p style={{ color: '#6B6B6B' }}>Loading inventory...</p>
        </div>
        <style jsx>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>Inventory</h1>
        <p style={styles.subtitle}>Manage your lab equipment, supplies, and assets</p>
      </div>

      {/* Stats */}
      {stats && (
        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <div style={styles.statValue}>{stats.total_items}</div>
            <div style={styles.statLabel}>Total Items</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statValue}>${stats.total_value.toLocaleString()}</div>
            <div style={styles.statLabel}>Total Value</div>
          </div>
          <div style={styles.statCard}>
            <div style={{ ...styles.statValue, color: stats.low_stock_count > 0 ? '#D97B7B' : '#2D2D2D' }}>
              {stats.low_stock_count}
            </div>
            <div style={styles.statLabel}>Low Stock Items</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statValue}>{stats.categories_count}</div>
            <div style={styles.statLabel}>Categories</div>
          </div>
        </div>
      )}

      {/* Alerts */}
      {alerts && alerts.counts.total_alerts > 0 && (
        <div style={styles.alertBanner}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D97B7B" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span style={{ color: '#D97B7B', fontWeight: 500 }}>
            {alerts.counts.total_alerts} alert{alerts.counts.total_alerts > 1 ? 's' : ''}: {' '}
            {alerts.low_stock.length > 0 && `${alerts.low_stock.length} low stock`}
            {alerts.low_stock.length > 0 && alerts.expiring_warranty.length > 0 && ', '}
            {alerts.expiring_warranty.length > 0 && `${alerts.expiring_warranty.length} warranty expiring`}
          </span>
        </div>
      )}

      {/* Tabs */}
      <div style={styles.tabs}>
        <button style={styles.tab(activeTab === 'items')} onClick={() => setActiveTab('items')}>Items</button>
        <button style={styles.tab(activeTab === 'categories')} onClick={() => setActiveTab('categories')}>Categories</button>
        <button style={styles.tab(activeTab === 'locations')} onClick={() => setActiveTab('locations')}>Locations</button>
        <button style={styles.tab(activeTab === 'vendors')} onClick={() => setActiveTab('vendors')}>Vendors</button>
        <button style={styles.tab(activeTab === 'history')} onClick={() => setActiveTab('history')}>History</button>
      </div>

      {/* Items Tab */}
      {activeTab === 'items' && (
        <>
          <div style={styles.toolbar}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Search items..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={styles.searchInput}
              />
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                style={styles.select}
              >
                <option value="">All Categories</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select
                value={filterLocation}
                onChange={(e) => setFilterLocation(e.target.value)}
                style={styles.select}
              >
                <option value="">All Locations</option>
                {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: '#6B6B6B', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={showLowStockOnly}
                  onChange={(e) => setShowLowStockOnly(e.target.checked)}
                />
                Low stock only
              </label>
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              {/* Import Button */}
              <label style={{ ...styles.button(false), cursor: 'pointer' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="17,8 12,3 7,8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                Import
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleImport}
                  style={{ display: 'none' }}
                />
              </label>
              {/* Export Button */}
              <button style={styles.button(false)} onClick={handleExport}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="7,10 12,15 17,10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Export
              </button>
              {/* Clear All Button */}
              {items.length > 0 && (
                <button style={{ ...styles.button(false), color: '#D97B7B' }} onClick={handleClearAll}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3,6 5,6 21,6" />
                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                  </svg>
                  Clear All
                </button>
              )}
              {/* Add Item Button */}
              <button style={styles.button(true)} onClick={() => { resetItemForm(); setEditingItem(null); setShowAddItemModal(true); }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Add Item
              </button>
            </div>
          </div>

          {/* Items Table */}
          <div style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', border: '1px solid #F0EEEC', overflow: 'hidden' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Name</th>
                  <th style={styles.th}>Category</th>
                  <th style={styles.th}>Location</th>
                  <th style={styles.th}>Quantity</th>
                  <th style={styles.th}>Value</th>
                  <th style={styles.th}>Status</th>
                  <th style={styles.th}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ ...styles.td, textAlign: 'center', color: '#A89B91', padding: '40px' }}>
                      <div style={{ marginBottom: '12px' }}>No items found.</div>
                      <div style={{ fontSize: '13px' }}>
                        Click <strong>"Add Item"</strong> to create one manually or{' '}
                        <strong>"Import"</strong> to upload a CSV/Excel file.
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredItems.map(item => (
                    <tr key={item.id}>
                      <td style={styles.td}>
                        <div style={{ fontWeight: 500 }}>{item.name}</div>
                        {item.sku && <div style={{ fontSize: '12px', color: '#A89B91' }}>SKU: {item.sku}</div>}
                      </td>
                      <td style={styles.td}>
                        {item.category ? (
                          <span style={{ ...styles.badge('default'), backgroundColor: '#FBF4F1', color: '#6B6B6B', border: '1px solid #F0EEEC' }}>
                            {item.category.name}
                          </span>
                        ) : '-'}
                      </td>
                      <td style={styles.td}>{item.location?.name || '-'}</td>
                      <td style={styles.td}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <button
                            onClick={() => handleAdjustQuantity(item.id, -1)}
                            style={{ padding: '4px 8px', border: '1px solid #F0EEEC', borderRadius: '4px', backgroundColor: '#FAF9F7', cursor: 'pointer', color: '#6B6B6B' }}
                          >-</button>
                          <span style={{ fontWeight: 500 }}>{item.quantity} {item.unit}</span>
                          <button
                            onClick={() => handleAdjustQuantity(item.id, 1)}
                            style={{ padding: '4px 8px', border: '1px solid #F0EEEC', borderRadius: '4px', backgroundColor: '#FAF9F7', cursor: 'pointer', color: '#6B6B6B' }}
                          >+</button>
                        </div>
                      </td>
                      <td style={styles.td}>
                        {item.unit_price ? `$${item.total_value.toLocaleString()}` : '-'}
                      </td>
                      <td style={styles.td}>
                        {item.is_low_stock && <span style={styles.badge('danger')}>Low Stock</span>}
                        {item.is_warranty_expiring_soon && <span style={{ ...styles.badge('warning'), marginLeft: item.is_low_stock ? '6px' : 0 }}>Warranty Expiring</span>}
                        {!item.is_low_stock && !item.is_warranty_expiring_soon && <span style={styles.badge('success')}>OK</span>}
                      </td>
                      <td style={styles.td}>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => openEditItem(item)}
                            style={{ padding: '6px', background: 'none', border: 'none', cursor: 'pointer', color: '#6B6B6B' }}
                            title="Edit"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                              <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleDeleteItem(item.id)}
                            style={{ padding: '6px', background: 'none', border: 'none', cursor: 'pointer', color: '#D97B7B' }}
                            title="Delete"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3,6 5,6 21,6" />
                              <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Categories Tab */}
      {activeTab === 'categories' && (
        <>
          <div style={{ ...styles.toolbar, marginBottom: '20px' }}>
            <div />
            <button style={styles.button(true)} onClick={() => setShowAddCategoryModal(true)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Category
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
            {categories.map((cat, index) => {
              // Taupe color variations for categories
              const taupeColors = ['#C9A598', '#B8948A', '#A68379', '#D4B5AA', '#E2CCC4'];
              const dotColor = taupeColors[index % taupeColors.length];
              return (
              <div key={cat.id} style={styles.card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                      <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: dotColor }} />
                      <span style={{ fontWeight: 600, fontSize: '16px', color: '#2D2D2D' }}>{cat.name}</span>
                    </div>
                    <p style={{ fontSize: '13px', color: '#6B6B6B', margin: '0 0 8px 0' }}>{cat.description || 'No description'}</p>
                    <span style={styles.badge('default')}>{cat.item_count} items</span>
                  </div>
                  <button
                    onClick={() => handleDeleteCategory(cat.id)}
                    style={{ padding: '6px', background: 'none', border: 'none', cursor: 'pointer', color: '#D97B7B' }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3,6 5,6 21,6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                  </button>
                </div>
              </div>
            );})}
            {categories.length === 0 && (
              <p style={{ color: '#A89B91', gridColumn: '1 / -1', textAlign: 'center', padding: '40px' }}>
                No categories yet. Create one to organize your inventory.
              </p>
            )}
          </div>
        </>
      )}

      {/* Locations Tab */}
      {activeTab === 'locations' && (
        <>
          <div style={{ ...styles.toolbar, marginBottom: '20px' }}>
            <div />
            <button style={styles.button(true)} onClick={() => setShowAddLocationModal(true)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Location
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
            {locations.map(loc => (
              <div key={loc.id} style={styles.card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '16px', color: '#2D2D2D', marginBottom: '8px' }}>{loc.name}</div>
                    {(loc.building || loc.room) && (
                      <p style={{ fontSize: '13px', color: '#6B6B6B', margin: '0 0 8px 0' }}>
                        {[loc.building, loc.room].filter(Boolean).join(' - ')}
                      </p>
                    )}
                    <span style={styles.badge('default')}>{loc.item_count} items</span>
                  </div>
                  <button
                    onClick={() => handleDeleteLocation(loc.id)}
                    style={{ padding: '6px', background: 'none', border: 'none', cursor: 'pointer', color: '#D97B7B' }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3,6 5,6 21,6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
            {locations.length === 0 && (
              <p style={{ color: '#A89B91', gridColumn: '1 / -1', textAlign: 'center', padding: '40px' }}>
                No locations yet. Add physical locations for your inventory.
              </p>
            )}
          </div>
        </>
      )}

      {/* Vendors Tab */}
      {activeTab === 'vendors' && (
        <>
          <div style={{ ...styles.toolbar, marginBottom: '20px' }}>
            <div />
            <button style={styles.button(true)} onClick={() => setShowAddVendorModal(true)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Vendor
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {vendors.map(v => (
              <div key={v.id} style={styles.card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '16px', color: '#2D2D2D', marginBottom: '8px' }}>{v.name}</div>
                    {v.contact_name && <p style={{ fontSize: '13px', color: '#6B6B6B', margin: '0 0 4px 0' }}>{v.contact_name}</p>}
                    {v.contact_email && <p style={{ fontSize: '13px', color: '#C9A598', margin: '0 0 4px 0' }}>{v.contact_email}</p>}
                    {v.contact_phone && <p style={{ fontSize: '13px', color: '#6B6B6B', margin: '0 0 8px 0' }}>{v.contact_phone}</p>}
                    <span style={styles.badge('default')}>{v.item_count} items</span>
                  </div>
                  <button
                    onClick={() => handleDeleteVendor(v.id)}
                    style={{ padding: '6px', background: 'none', border: 'none', cursor: 'pointer', color: '#D97B7B' }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3,6 5,6 21,6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
            {vendors.length === 0 && (
              <p style={{ color: '#A89B91', gridColumn: '1 / -1', textAlign: 'center', padding: '40px' }}>
                No vendors yet. Add your suppliers and manufacturers.
              </p>
            )}
          </div>
        </>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <>
          <div style={{ ...styles.toolbar, marginBottom: '20px' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <button style={{ ...styles.button(false), backgroundColor: '#FBF4F1', color: '#6B6B6B' }} onClick={() => setShowBarcodeScanner(true)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 5h2v14H3V5zm4 0h1v14H7V5zm3 0h2v14h-2V5zm4 0h3v14h-3V5zm5 0h2v14h-2V5z" />
                </svg>
                Barcode Lookup
              </button>
            </div>
            <button style={styles.button(true)} onClick={handleSendAlerts}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
              Send Email Alerts
            </button>
          </div>
          <div style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', border: '1px solid #F0EEEC', overflow: 'hidden' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Date</th>
                  <th style={styles.th}>User</th>
                  <th style={styles.th}>Type</th>
                  <th style={styles.th}>Details</th>
                  <th style={styles.th}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ ...styles.td, textAlign: 'center', color: '#A89B91', padding: '40px' }}>
                      No transaction history yet. Actions like adding items, adjusting quantities, and checkouts will appear here.
                    </td>
                  </tr>
                ) : (
                  transactions.map(t => (
                    <tr key={t.id}>
                      <td style={styles.td}>
                        <div style={{ fontSize: '13px', color: '#6B6B6B' }}>
                          {new Date(t.created_at).toLocaleDateString()}{' '}
                          {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>
                      <td style={styles.td}>{t.user_name}</td>
                      <td style={styles.td}>
                        <span style={{
                          ...styles.badge(
                            t.transaction_type === 'CREATE' ? 'success' :
                            t.transaction_type === 'DELETE' ? 'danger' :
                            t.transaction_type === 'CHECKOUT' ? 'warning' : 'default'
                          )
                        }}>
                          {t.transaction_type}
                        </span>
                      </td>
                      <td style={styles.td}>
                        {t.quantity_change !== undefined && t.quantity_change !== null ? (
                          <span>
                            Qty: {t.quantity_before} → {t.quantity_after}{' '}
                            <span style={{ color: t.quantity_change > 0 ? '#9CB896' : '#D97B7B' }}>
                              ({t.quantity_change > 0 ? '+' : ''}{t.quantity_change})
                            </span>
                          </span>
                        ) : t.field_changed ? (
                          <span>{t.field_changed}: {t.old_value || '(empty)'} → {t.new_value}</span>
                        ) : '-'}
                      </td>
                      <td style={styles.td}>
                        <span style={{ fontSize: '13px', color: '#6B6B6B' }}>{t.notes || '-'}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Barcode Scanner Modal */}
      {showBarcodeScanner && (
        <div style={styles.modal} onClick={() => { setShowBarcodeScanner(false); setScannedItem(null); setBarcodeInput(''); }}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Barcode Lookup</h2>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Scan or Enter Barcode/SKU</label>
              <div style={{ display: 'flex', gap: '12px' }}>
                <input
                  type="text"
                  value={barcodeInput}
                  onChange={(e) => setBarcodeInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleBarcodeLookup()}
                  style={{ ...styles.formInput, flex: 1 }}
                  placeholder="Enter barcode or SKU..."
                  autoFocus
                />
                <button onClick={handleBarcodeLookup} style={styles.button(true)}>Search</button>
              </div>
            </div>
            {scannedItem && (
              <div style={{ ...styles.card, marginTop: '20px', backgroundColor: '#FAF9F7' }}>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#2D2D2D', marginBottom: '12px' }}>{scannedItem.name}</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '14px' }}>
                  <div><span style={{ color: '#6B6B6B' }}>SKU:</span> {scannedItem.sku || '-'}</div>
                  <div><span style={{ color: '#6B6B6B' }}>Barcode:</span> {scannedItem.barcode || '-'}</div>
                  <div><span style={{ color: '#6B6B6B' }}>Quantity:</span> {scannedItem.quantity} {scannedItem.unit}</div>
                  <div><span style={{ color: '#6B6B6B' }}>Location:</span> {scannedItem.location?.name || '-'}</div>
                  <div><span style={{ color: '#6B6B6B' }}>Category:</span> {scannedItem.category?.name || '-'}</div>
                  <div>
                    <span style={{ color: '#6B6B6B' }}>Status:</span>{' '}
                    {scannedItem.is_low_stock ? <span style={styles.badge('danger')}>Low Stock</span> : <span style={styles.badge('success')}>OK</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                  <button onClick={() => { openEditItem(scannedItem); setShowBarcodeScanner(false); }} style={styles.button(true)}>Edit Item</button>
                </div>
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
              <button onClick={() => { setShowBarcodeScanner(false); setScannedItem(null); setBarcodeInput(''); }} style={styles.button(false)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Add/Edit Item Modal */}
      {showAddItemModal && (
        <div style={styles.modal} onClick={() => { setShowAddItemModal(false); setEditingItem(null); }}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>{editingItem ? 'Edit Item' : 'Add New Item'}</h2>

            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Name *</label>
              <input
                type="text"
                value={itemForm.name}
                onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })}
                style={styles.formInput}
                placeholder="Item name"
              />
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>SKU / Part Number</label>
                <input
                  type="text"
                  value={itemForm.sku}
                  onChange={(e) => setItemForm({ ...itemForm, sku: e.target.value })}
                  style={styles.formInput}
                  placeholder="SKU"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Manufacturer</label>
                <input
                  type="text"
                  value={itemForm.manufacturer}
                  onChange={(e) => setItemForm({ ...itemForm, manufacturer: e.target.value })}
                  style={styles.formInput}
                  placeholder="Manufacturer"
                />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Quantity</label>
                <input
                  type="number"
                  value={itemForm.quantity}
                  onChange={(e) => setItemForm({ ...itemForm, quantity: parseInt(e.target.value) || 0 })}
                  style={styles.formInput}
                  min="0"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Min Quantity (Alert Threshold)</label>
                <input
                  type="number"
                  value={itemForm.min_quantity}
                  onChange={(e) => setItemForm({ ...itemForm, min_quantity: parseInt(e.target.value) || 0 })}
                  style={styles.formInput}
                  min="0"
                />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Unit</label>
                <select
                  value={itemForm.unit}
                  onChange={(e) => setItemForm({ ...itemForm, unit: e.target.value })}
                  style={styles.formInput}
                >
                  <option value="units">Units</option>
                  <option value="boxes">Boxes</option>
                  <option value="pieces">Pieces</option>
                  <option value="liters">Liters</option>
                  <option value="ml">mL</option>
                  <option value="kg">kg</option>
                  <option value="grams">Grams</option>
                </select>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Unit Price ($)</label>
                <input
                  type="number"
                  value={itemForm.unit_price}
                  onChange={(e) => setItemForm({ ...itemForm, unit_price: e.target.value })}
                  style={styles.formInput}
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Category</label>
                <select
                  value={itemForm.category_id}
                  onChange={(e) => setItemForm({ ...itemForm, category_id: e.target.value })}
                  style={styles.formInput}
                >
                  <option value="">Select category</option>
                  {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Location</label>
                <select
                  value={itemForm.location_id}
                  onChange={(e) => setItemForm({ ...itemForm, location_id: e.target.value })}
                  style={styles.formInput}
                >
                  <option value="">Select location</option>
                  {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Vendor</label>
              <select
                value={itemForm.vendor_id}
                onChange={(e) => setItemForm({ ...itemForm, vendor_id: e.target.value })}
                style={styles.formInput}
              >
                <option value="">Select vendor</option>
                {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Model Number</label>
                <input
                  type="text"
                  value={itemForm.model_number}
                  onChange={(e) => setItemForm({ ...itemForm, model_number: e.target.value })}
                  style={styles.formInput}
                  placeholder="Model #"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Serial Number</label>
                <input
                  type="text"
                  value={itemForm.serial_number}
                  onChange={(e) => setItemForm({ ...itemForm, serial_number: e.target.value })}
                  style={styles.formInput}
                  placeholder="Serial #"
                />
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Warranty Expiry Date</label>
              <input
                type="date"
                value={itemForm.warranty_expiry}
                onChange={(e) => setItemForm({ ...itemForm, warranty_expiry: e.target.value })}
                style={styles.formInput}
              />
            </div>

            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Notes</label>
              <textarea
                value={itemForm.notes}
                onChange={(e) => setItemForm({ ...itemForm, notes: e.target.value })}
                style={{ ...styles.formInput, minHeight: '80px', resize: 'vertical' }}
                placeholder="Additional notes..."
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button
                onClick={() => { setShowAddItemModal(false); setEditingItem(null); }}
                style={styles.button(false)}
              >
                Cancel
              </button>
              <button
                onClick={handleAddItem}
                style={styles.button(true)}
                disabled={!itemForm.name}
              >
                {editingItem ? 'Save Changes' : 'Add Item'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Category Modal */}
      {showAddCategoryModal && (
        <div style={styles.modal} onClick={() => setShowAddCategoryModal(false)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Add Category</h2>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Name *</label>
              <input
                type="text"
                value={categoryForm.name}
                onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                style={styles.formInput}
                placeholder="Category name"
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Description</label>
              <textarea
                value={categoryForm.description}
                onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
                style={{ ...styles.formInput, minHeight: '80px', resize: 'vertical' }}
                placeholder="Optional description"
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Color</label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="color"
                  value={categoryForm.color}
                  onChange={(e) => setCategoryForm({ ...categoryForm, color: e.target.value })}
                  style={{ width: '40px', height: '40px', border: 'none', cursor: 'pointer' }}
                />
                <span style={{ fontSize: '14px', color: '#6B6B6B' }}>{categoryForm.color}</span>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button onClick={() => setShowAddCategoryModal(false)} style={styles.button(false)}>Cancel</button>
              <button onClick={handleAddCategory} style={styles.button(true)} disabled={!categoryForm.name}>Add Category</button>
            </div>
          </div>
        </div>
      )}

      {/* Add Location Modal */}
      {showAddLocationModal && (
        <div style={styles.modal} onClick={() => setShowAddLocationModal(false)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Add Location</h2>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Name *</label>
              <input
                type="text"
                value={locationForm.name}
                onChange={(e) => setLocationForm({ ...locationForm, name: e.target.value })}
                style={styles.formInput}
                placeholder="Location name (e.g., Lab Room 101)"
              />
            </div>
            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Building</label>
                <input
                  type="text"
                  value={locationForm.building}
                  onChange={(e) => setLocationForm({ ...locationForm, building: e.target.value })}
                  style={styles.formInput}
                  placeholder="Building name"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Room</label>
                <input
                  type="text"
                  value={locationForm.room}
                  onChange={(e) => setLocationForm({ ...locationForm, room: e.target.value })}
                  style={styles.formInput}
                  placeholder="Room number"
                />
              </div>
            </div>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Description</label>
              <textarea
                value={locationForm.description}
                onChange={(e) => setLocationForm({ ...locationForm, description: e.target.value })}
                style={{ ...styles.formInput, minHeight: '80px', resize: 'vertical' }}
                placeholder="Optional description"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button onClick={() => setShowAddLocationModal(false)} style={styles.button(false)}>Cancel</button>
              <button onClick={handleAddLocation} style={styles.button(true)} disabled={!locationForm.name}>Add Location</button>
            </div>
          </div>
        </div>
      )}

      {/* Add Vendor Modal */}
      {showAddVendorModal && (
        <div style={styles.modal} onClick={() => setShowAddVendorModal(false)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Add Vendor</h2>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Company Name *</label>
              <input
                type="text"
                value={vendorForm.name}
                onChange={(e) => setVendorForm({ ...vendorForm, name: e.target.value })}
                style={styles.formInput}
                placeholder="Vendor company name"
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Contact Name</label>
              <input
                type="text"
                value={vendorForm.contact_name}
                onChange={(e) => setVendorForm({ ...vendorForm, contact_name: e.target.value })}
                style={styles.formInput}
                placeholder="Primary contact"
              />
            </div>
            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Email</label>
                <input
                  type="email"
                  value={vendorForm.contact_email}
                  onChange={(e) => setVendorForm({ ...vendorForm, contact_email: e.target.value })}
                  style={styles.formInput}
                  placeholder="contact@vendor.com"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Phone</label>
                <input
                  type="tel"
                  value={vendorForm.contact_phone}
                  onChange={(e) => setVendorForm({ ...vendorForm, contact_phone: e.target.value })}
                  style={styles.formInput}
                  placeholder="(555) 123-4567"
                />
              </div>
            </div>
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>Website</label>
              <input
                type="url"
                value={vendorForm.website}
                onChange={(e) => setVendorForm({ ...vendorForm, website: e.target.value })}
                style={styles.formInput}
                placeholder="https://vendor.com"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button onClick={() => setShowAddVendorModal(false)} style={styles.button(false)}>Cancel</button>
              <button onClick={handleAddVendor} style={styles.button(true)} disabled={!vendorForm.name}>Add Vendor</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
