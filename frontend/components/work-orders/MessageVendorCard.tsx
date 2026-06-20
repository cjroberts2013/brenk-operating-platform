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
  EnvelopeIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/20/solid'

import { sendVendorEmailAction } from '@/app/(app)/work-orders/actions'
import type { VendorMessage, WorkOrderAttachment } from '@/lib/api/types'

/**
 * "Message vendor" card. When the vendor prefers email, Daryl can review
 * and send the message (photos attached) straight through Resend. For any
 * other preference it stays a copy-and-send-yourself helper (with a
 * prefilled text/email link and downloadable photos to attach manually).
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
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.body)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard unavailable (insecure context) — text is visible to select.
    }
  }

  const canEmail =
    message.contact_preference === 'email' && !!message.to_email
  const prefLabel = formatPreference(message.contact_preference)

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

        {canEmail ? (
          <EmailSend
            workOrderId={workOrderId}
            message={message}
            onCopy={copy}
            copied={copied}
          />
        ) : (
          <ManualSend message={message} onCopy={copy} copied={copied} />
        )}

        {/* Photos. Email auto-attaches them; the manual path needs them
            downloaded and attached by hand. */}
        {attachments.length > 0 ? (
          <div className="border-t border-gray-200 pt-3 dark:border-white/10">
            <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400">
              Photos ({attachments.length})
            </p>
            <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
              {canEmail
                ? 'These attach to the email automatically.'
                : "Text/email won't attach these automatically. Tap each photo to download it, then add them to your message after pasting."}
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
    </section>
  )
}

function EmailSend({
  workOrderId,
  message,
  onCopy,
  copied,
}: {
  workOrderId: number
  message: VendorMessage
  onCopy: () => void
  copied: boolean
}) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  function send() {
    setError(null)
    startTransition(async () => {
      const result = await sendVendorEmailAction(workOrderId)
      if (result.error) {
        setError(result.error)
      } else {
        setSent(true)
        setOpen(false)
        router.refresh()
      }
    })
  }

  if (sent) {
    return (
      <p className="flex items-center gap-1.5 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-950/40 dark:text-green-300">
        <CheckIcon className="size-4" />
        Emailed to {message.to_email}.
      </p>
    )
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          <PaperAirplaneIcon className="size-4" />
          Send email
        </button>
        <CopyButton onCopy={onCopy} copied={copied} subtle />
      </div>

      <Dialog open={open} onClose={setOpen} className="relative z-50">
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
                Email this work order to the vendor
              </DialogTitle>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                Review before sending. Replies come back to you.
              </p>
            </div>

            <div className="space-y-3 px-5 py-4 text-sm">
              <Row label="To">{message.to_email}</Row>
              <Row label="Subject">{message.subject}</Row>
              <Row label="Photos">
                {message.photo_count > 0
                  ? `${message.photo_count} attached`
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
                onClick={() => setOpen(false)}
                disabled={pending}
                className="rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={send}
                disabled={pending}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                <PaperAirplaneIcon className="size-4" />
                {pending ? 'Sending…' : 'Send email'}
              </button>
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </>
  )
}

function ManualSend({
  message,
  onCopy,
  copied,
}: {
  message: VendorMessage
  onCopy: () => void
  copied: boolean
}) {
  const smsHref = message.to_phone
    ? `sms:${message.to_phone}?&body=${encodeURIComponent(message.body)}`
    : null
  const mailHref = message.to_email
    ? `mailto:${message.to_email}?subject=${encodeURIComponent(
        message.subject,
      )}&body=${encodeURIComponent(message.body)}`
    : null

  return (
    <div className="flex flex-wrap gap-2">
      <CopyButton onCopy={onCopy} copied={copied} />
      {smsHref ? (
        <a
          href={smsHref}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-white/5"
        >
          <ChatBubbleLeftRightIcon className="size-4" />
          Text
        </a>
      ) : null}
      {mailHref ? (
        <a
          href={mailHref}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-white/5"
        >
          <EnvelopeIcon className="size-4" />
          Email
        </a>
      ) : null}
    </div>
  )
}

function CopyButton({
  onCopy,
  copied,
  subtle = false,
}: {
  onCopy: () => void
  copied: boolean
  subtle?: boolean
}) {
  const base =
    'inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-semibold'
  const cls = subtle
    ? `${base} text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:text-gray-200 dark:ring-white/10 dark:hover:bg-white/5`
    : `${base} bg-indigo-500 text-white hover:bg-indigo-400`
  return (
    <button type="button" onClick={onCopy} className={cls}>
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
