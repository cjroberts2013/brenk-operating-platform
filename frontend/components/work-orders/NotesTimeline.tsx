/**
 * Notes timeline — chronological feed of SC + (later) Brenk-internal
 * notes on a work order. Reads each note's pre-rendered HTML safely
 * (SC system notes contain <b> tags etc. — we render them as text,
 * not as HTML, to avoid any XSS risk).
 *
 * SystemNote vs UserNote is hinted with a small badge so Daryl can
 * eyeball which entries are auto-generated and which were typed by a
 * real human.
 */

import type { WorkOrderNoteRef } from '@/lib/api/types'
import { relativeTime } from '@/lib/format'

function initial(value: string | null | undefined): string {
  return (value ?? '').charAt(0).toUpperCase() || '·'
}

/** Strip HTML tags from SC note bodies — they sometimes include `<b>` etc. */
function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, '')
}

function isSystemNote(note: WorkOrderNoteRef): boolean {
  return (note.note_type ?? '').toLowerCase() === 'systemnote'
}

export function NotesTimeline({ notes }: { notes: WorkOrderNoteRef[] }) {
  if (notes.length === 0) {
    return (
      <div className="rounded-lg ring-1 ring-gray-200 px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400 dark:ring-white/10">
        No notes yet.
      </div>
    )
  }

  return (
    <div className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Notes
        </h2>
        <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
          {notes.length} total, oldest first.
        </p>
      </header>
      <ul role="list" className="divide-y divide-gray-200 dark:divide-white/10">
        {notes.map((note) => (
          <li key={note.id} className="flex gap-3 px-4 py-3 text-sm">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-500 text-xs font-semibold text-white">
              {initial(note.created_by)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium text-gray-900 dark:text-white">
                  {note.created_by || 'Unknown'}
                </span>
                {note.company_name ? (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    · {note.company_name}
                  </span>
                ) : null}
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  · {relativeTime(note.created_at_sc)}
                </span>
                {isSystemNote(note) ? (
                  <span className="rounded-sm bg-gray-100 px-1.5 py-px text-[10px] font-medium text-gray-500 uppercase dark:bg-white/5 dark:text-gray-400">
                    System
                  </span>
                ) : null}
              </div>
              <p className="mt-1 whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                {stripHtml(note.note_data)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
