/**
 * Status badge — colored pill for a work order's primary status.
 *
 * Adopts SC's color language (Daryl is already fluent in it) and
 * layers our internal stages on top later. Initial mapping is rough
 * and will tighten as we learn which extended_status values matter.
 *
 *   IN PROGRESS  → yellow (dispatch confirmed, work happening)
 *   COMPLETED · PENDING CONFIRMATION → orange (work done, waiting on the
 *                store to confirm — SC's "work complete" colour)
 *   COMPLETED    → green  (closed by store; ready to invoice)
 *   OPEN         → slate  (accepted, not yet dispatched)
 *   CANCELLED    → gray   (dead, struck-through)
 *   anything else → slate (unknown — let it be visible without screaming)
 */

import type { ReactNode } from 'react'

type Tone =
  | 'pink'
  | 'yellow'
  | 'orange'
  | 'green'
  | 'slate'
  | 'red'
  | 'gray'

const TONE_CLASSES: Record<Tone, string> = {
  pink: 'bg-pink-100 text-pink-800 ring-pink-600/20 dark:bg-pink-500/10 dark:text-pink-300 dark:ring-pink-400/30',
  yellow:
    'bg-yellow-100 text-yellow-800 ring-yellow-600/20 dark:bg-yellow-500/10 dark:text-yellow-300 dark:ring-yellow-400/30',
  orange:
    'bg-orange-100 text-orange-800 ring-orange-600/20 dark:bg-orange-500/10 dark:text-orange-300 dark:ring-orange-400/30',
  green:
    'bg-green-100 text-green-800 ring-green-600/20 dark:bg-green-500/10 dark:text-green-300 dark:ring-green-400/30',
  slate:
    'bg-slate-100 text-slate-800 ring-slate-600/20 dark:bg-slate-500/10 dark:text-slate-300 dark:ring-slate-400/30',
  red: 'bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-400/30',
  gray: 'bg-gray-100 text-gray-700 ring-gray-500/20 dark:bg-gray-500/10 dark:text-gray-300 dark:ring-gray-400/30',
}

function toneFor(status: string, extended?: string | null): Tone {
  const s = status.toUpperCase()
  const ext = (extended ?? '').toUpperCase()
  if (s.includes('CANCEL')) return 'gray'
  if (s.includes('PROGRESS')) return 'yellow'
  if (s.includes('COMPLETED')) {
    // SC's colour language: work is complete but the store hasn't
    // confirmed it yet → orange ("work complete"). Once the store
    // confirms (closes) it → green.
    if (ext.includes('PENDING CONFIRMATION')) return 'orange'
    return 'green'
  }
  if (s.includes('CONFIRMED')) return 'green'
  if (s === 'OPEN' || s.includes('NEW') || s.includes('PENDING')) return 'pink'
  if (s.includes('EXPIRED') || s.includes('STALE')) return 'red'
  return 'slate'
}

export function StatusBadge({
  status,
  extended,
}: {
  status: string
  extended?: string | null
}): ReactNode {
  const tone = toneFor(status, extended)
  const label = extended ? `${status} · ${extended}` : status
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASSES[tone]}`}
    >
      {label}
    </span>
  )
}
