'use client'

import { useState } from 'react'
import { PencilSquareIcon } from '@heroicons/react/20/solid'

import type { LocationDetail } from '@/lib/api/types'

import { LocationFormModal } from './LocationFormModal'

/** "Edit" button + its modal. Lives on the detail page, where the full
 *  LocationDetail (all editable fields) is available. */
export function LocationEditButton({ location }: { location: LocationDetail }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-md bg-indigo-500 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-400"
      >
        <PencilSquareIcon className="size-4" />
        Edit details
      </button>
      <LocationFormModal
        open={open}
        onClose={() => setOpen(false)}
        location={location}
      />
    </>
  )
}
