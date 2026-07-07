'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from '@headlessui/react'
import {
  ArrowDownTrayIcon,
  ChatBubbleLeftRightIcon,
  CheckIcon,
  ClipboardDocumentIcon,
  ExclamationTriangleIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/20/solid'

import {
  sendVendorEmailAction,
  sendVendorSmsAction,
} from '@/app/(app)/work-orders/actions'
import type { VendorEmailResult, VendorSmsResult } from '@/lib/api/work-orders'
import type { VendorMessage, WorkOrderAttachment } from '@/lib/api/types'

type SendMode = 'email' | 'sms'

type SendResult = {
  kind: 'email' | 'sms'
  to: string
  photos_attached: number
  photos_total: number
  receipt_sent: boolean
}

/**
 * "Message vendor" card. Email goes through Resend (from the business
 * address, photos attached, reply-to Daryl); text goes through Twilio
 * (photos as MMS). Both sit behind the same review-and-confirm dialog and
 * stamp the vendor notified. A manual sms: link + copy stay available as
 * fallbacks (e.g. Twilio not configured yet).
 */
export function MessageVendorCard({
  workOrderId,
  message,
  attachments,
}: {
  workOrderId: number
  message: VendorMessage
  attachments: WorkOrderAttachment[]
}) {
  const router = useRouter()
  const [copied, setCopied] = useState(false)
  const [mode, setMode] = useState<SendMode | null>(null)
  const [result, setResult] = useState<SendResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const hasEmail = !!message.to_email
  const hasPhone = !!message.to_phone
  const prefLabel = formatPreference(message.contact_preference)
  const smsHref = message.to_phone
    ? `sms:${message.to_phone}?&body=${encodeURIComponent(message.body)}`
    : null

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.body)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard unavailable (insecure context) — text is visible to select.
    }
  }

  function send(kind: SendMode) {
    setError(null)
    startTransition(async () => {
      if (kind === 'email') {
        const res = await sendVendorEmailAction(workOrderId)
        if (res.error) {
          setError(res.error)
          return
        }
        const r = res.result as VendorEmailResult
        setResult({
          kind: 'email',
          to: r.to_email,
          photos_attached: r.photos_attached,
          photos_total: r.photos_total,
          receipt_sent: r.receipt_sent,
        })
      } else {
        const res = await sendVendorSmsAction(workOrderId)
        if (res.error) {
          setError(res.error)
          return
        }
        const r = res.result as VendorSmsResult
        setResult({
          kind: 'sms',
          to: r.to_phone,
          photos_attached: r.photos_attached,
          photos_total: r.photos_total,
          receipt_sent: r.receipt_sent,
        })
      }
      setMode(null)
      router.refresh()
    })
  }

  const sent = result !== null
  const dropped = result ? result.photos_total - result.photos_attached : 0

  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="flex items-center justify-between gap-2 border-b border-gray-200 px-4 py-3 dark:border-white/10">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
          Message vendor
        </h2>
        {prefLabel ? (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Prefers {prefLabel}
          </span>
        ) : null}
      </header>

      <div className="space-y-3 px-4 py-3">
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-gray-50 p-3 font-sans text-sm text-gray-700 dark:bg-white/5 dark:text-gray-300">
          {message.body}
        </pre>

        {sent && result ? (
          <div className="rounded-md bg-green-50 px-3 py-2 dark:bg-green-950/40">
            <p className="flex items-center gap-1.5 text-sm text-green-700 dark:text-green-300">
              <CheckIcon className="size-4" />
              {result.kind === 'email' ? 'Emailed to' : 'Texted to'} {result.to}.
            </p>
            {dropped > 0 ? (
              <p className="mt-1 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                <ExclamationTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
                {dropped} of {result.photos_total} photo
                {result.photos_total === 1 ? '' : 's'} couldn&apos;t be attached.
                Download {dropped === 1 ? 'it' : 'them'} below and send separately.
              </p>
            ) : result.photos_total > 0 ? (
              <p className="mt-1 text-xs text-green-700/80 dark:text-green-300/80">
                {result.photos_attached} photo
                {result.photos_attached === 1 ? '' : 's'} attached.
              </p>
            ) : null}
            {result.receipt_sent ? (
              <p className="mt-1 text-xs text-green-700/80 dark:text-green-300/80">
                Receipt texted to Daryl.
              </p>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {hasEmail ? (
              <button
                type="button"
                onClick={() => setMode('email')}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-500"
              >
                <PaperAirplaneIcon className="size-4" />
                Send email
              </button>
            ) : null}
            {hasPhone ? (
              <button
                type="button"
                onClick={() => setMode('sms')}
                className={
                  'inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-semibold ' +
                  (hasEmail
                    ? 'text-indigo-700 ring-1 ring-inset ring-indigo-300 hover:bg-indigo-50 dark:text-indigo-300 dark:ring-indigo-500/40 dark:hover:bg-indigo-500/10'
                    : 'bg-indigo-600 text-white hover:bg-indigo-500')
                }
              >
                <ChatBubbleLeftRightIcon className="size-4" />
                Send text
              </button>
            ) : null}
            <button
              type="button"
              onClick={copy}
              className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-semibold text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-white/5"
            >
              {copied ? (
                <>
                  <CheckIcon className="size-4" />
                  Copied
                </>
              ) : (
                <>
                  <ClipboardDocumentIcon className="size-4" />
                  Copy message
                </>
              )}
            </button>
            {smsHref ? (
              <a
                href={smsHref}
                className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                Text manually
              </a>
            ) : null}
          </div>
        )}

        {error && mode === null ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </p>
        ) : null}

        {/* Photos. Email attaches them automatically; texting sends them as
            MMS where the carrier allows; copying needs a manual download. */}
        {attachments.length > 0 ? (
          <div className="border-t border-gray-200 pt-3 dark:border-white/10">
            <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400">
              Photos ({attachments.length})
            </p>
            <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
              {hasEmail || hasPhone
                ? 'These attach to a sent email or text automatically. For a manual text, download each and attach it yourself.'
                : "Copy won't attach these. Download each photo, then add them to your message."}
            </p>
            <ul className="space-y-1">
              {attachments.map((att) => (
                <li key={att.id}>
                  <a
                    href={`/work-orders/${workOrderId}/attachments/${att.id}?download=1`}
                    className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
                  >
                    <ArrowDownTrayIcon className="size-4" />
                    {att.name ?? `Attachment ${att.id}`}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <Dialog open={mode !== null} onClose={() => setMode(null)} className="relative z-50">
        <DialogBackdrop
          transition
          className="fixed inset-0 bg-gray-900/60 transition-opacity data-closed:opacity-0"
        />
        <div className="fixed inset-0 flex items-center justify-center p-4">
          <DialogPanel
            transition
            className="w-full max-w-md rounded-lg bg-white shadow-xl ring-1 ring-gray-200 transition data-closed:scale-95 data-closed:opacity-0 dark:bg-gray-900 dark:ring-white/10"
          >
            <div className="border-b border-gray-200 px-5 py-4 dark:border-white/10">
              <DialogTitle className="text-base font-semibold text-gray-900 dark:text-white">
                {mode === 'sms'
                  ? 'Text this work order to the vendor'
                  : 'Email this work order to the vendor'}
              </DialogTitle>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                {mode === 'sms'
                  ? 'Sends from the Brenk Facility Services number.'
                  : 'Sends from Brenk Facility Services; replies come back to you.'}
              </p>
            </div>

            <div className="space-y-3 px-5 py-4 text-sm">
              <Row label="To">
                {mode === 'sms' ? message.to_phone : message.to_email}
              </Row>
              {mode === 'email' ? (
                <Row label="Subject">{message.subject}</Row>
              ) : null}
              <Row label="Photos">
                {message.photo_count > 0
                  ? mode === 'sms'
                    ? `up to ${message.photo_count} as MMS`
                    : `${message.photo_count} attached`
                  : 'none'}
              </Row>
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-gray-50 p-3 font-sans text-xs text-gray-700 dark:bg-white/5 dark:text-gray-300">
                {message.body}
              </pre>
              {error ? (
                <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
                  {error}
                </p>
              ) : null}
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-gray-200 px-5 py-3 dark:border-white/10">
              <button
                type="button"
                onClick={() => setMode(null)}
                disabled={pending}
                className="rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => mode && send(mode)}
                disabled={pending}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {mode === 'sms' ? (
                  <ChatBubbleLeftRightIcon className="size-4" />
                ) : (
                  <PaperAirplaneIcon className="size-4" />
                )}
                {pending ? 'Sending…' : mode === 'sms' ? 'Send text' : 'Send email'}
              </button>
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </section>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-right text-gray-700 dark:text-gray-300">
        {children}
      </span>
    </div>
  )
}

function formatPreference(value: string | null): string | null {
  if (!value) return null
  if (value === 'sms') return 'text'
  if (value === 'call') return 'a call'
  if (value === 'email') return 'email'
  return value
}
