'use client'

import { usePathname, useRouter, useSearchParams } from 'next/navigation'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'OPEN', label: 'Open' },
  { value: 'IN PROGRESS', label: 'In Progress' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CANCELLED', label: 'Cancelled' },
]

export function StatusFilter({ current }: { current: string | undefined }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  function onChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(searchParams.toString())
    if (event.target.value) next.set('status', event.target.value)
    else next.delete('status')
    // Reset to page 1 whenever the filter changes — otherwise you can
    // land on an empty page-3 of a filter that only has 7 records.
    next.delete('page')
    router.push(`${pathname}?${next.toString()}`)
  }

  return (
    <div className="flex items-center gap-2">
      <label
        htmlFor="status"
        className="text-sm text-gray-500 dark:text-gray-400"
      >
        Status:
      </label>
      <select
        id="status"
        defaultValue={current ?? ''}
        onChange={onChange}
        className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white"
      >
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
