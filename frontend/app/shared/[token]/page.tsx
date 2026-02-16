'use client'

import { useParams } from 'next/navigation'
import SharedPortal from '@/components/shared/SharedPortal'

export default function SharedPortalPage() {
  const params = useParams()
  const token = params.token as string

  return <SharedPortal token={token} />
}
