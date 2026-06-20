import {
  ArrowDownTrayIcon,
  DocumentIcon,
  PaperClipIcon,
} from '@heroicons/react/20/solid'

import type { WorkOrderAttachment } from '@/lib/api/types'
import { shortDate } from '@/lib/format'

/**
 * Attachments on a work order — photos, quotes, invoice copies, etc.,
 * pulled live from ServiceChannel. Image files show an inline thumbnail;
 * everything else gets a file icon. Each links to a download/open through
 * our proxy route (which carries the auth the bytes need).
 */
export function AttachmentsSection({
  workOrderId,
  attachments,
  failed,
}: {
  workOrderId: number
  attachments: WorkOrderAttachment[]
  /** SC list call failed — show a soft error rather than an empty list. */
  failed?: boolean
}) {
  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="flex items-center gap-2 border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <PaperClipIcon className="size-4 text-gray-400" />
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Attachments
        </h2>
        {attachments.length > 0 ? (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {attachments.length}
          </span>
        ) : null}
      </header>

      {failed ? (
        <p className="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">
          Couldn&apos;t load attachments from ServiceChannel just now. Reload to
          try again.
        </p>
      ) : attachments.length === 0 ? (
        <p className="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">
          No attachments on this work order.
        </p>
      ) : (
        <ul className="divide-y divide-gray-200 dark:divide-white/10">
          {attachments.map((att) => {
            const base = `/work-orders/${workOrderId}/attachments/${att.id}`
            const isImage = (att.content_type ?? '').startsWith('image/')
            const meta = [att.upload_by, shortDate(att.timestamp)]
              .filter(Boolean)
              .join(' · ')
            return (
              <li key={att.id} className="flex items-center gap-3 px-4 py-3">
                <a
                  href={base}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0"
                  title="Open"
                >
                  {isImage ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={base}
                      alt={att.name ?? 'attachment'}
                      className="size-12 rounded-md object-cover ring-1 ring-gray-200 dark:ring-white/10"
                    />
                  ) : (
                    <span className="flex size-12 items-center justify-center rounded-md bg-gray-100 ring-1 ring-gray-200 dark:bg-white/5 dark:ring-white/10">
                      <DocumentIcon className="size-6 text-gray-400" />
                    </span>
                  )}
                </a>
                <div className="min-w-0 flex-1">
                  <a
                    href={base}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block truncate text-sm font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
                  >
                    {att.name ?? `Attachment ${att.id}`}
                  </a>
                  {meta ? (
                    <p className="truncate text-xs text-gray-500 dark:text-gray-400">
                      {meta}
                    </p>
                  ) : null}
                </div>
                <a
                  href={`${base}?download=1`}
                  className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-white/5 dark:hover:text-white"
                  title="Download"
                >
                  <ArrowDownTrayIcon className="size-4" />
                  Download
                </a>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
