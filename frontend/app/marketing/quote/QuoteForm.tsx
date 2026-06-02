'use client'

import { useActionState } from 'react'

import { submitQuoteAction, type QuoteState } from './actions'

// Defined here, not in actions.ts: a 'use server' file may only export
// async functions, so the initial-state object lives client-side.
const INITIAL_QUOTE_STATE: QuoteState = { ok: false, error: null }

const fieldClass =
  'block w-full rounded-md border border-line-brand bg-white px-3.5 py-3 text-[15.5px] text-ink shadow-xs outline-none focus:border-signal focus:ring-1 focus:ring-signal disabled:opacity-60'
const labelClass = 'mb-1.5 block text-[13px] font-semibold text-ink'

export function QuoteForm() {
  const [state, formAction, pending] = useActionState<QuoteState, FormData>(
    submitQuoteAction,
    INITIAL_QUOTE_STATE,
  )

  if (state.ok) {
    return (
      <div className="rounded-xl border border-line-brand bg-white p-8 text-center">
        <h2 className="font-display text-[26px] font-extrabold tracking-[-0.01em] text-ink">
          Thanks, we’ll be in touch.
        </h2>
        <p className="mt-3 text-[15.5px] text-slate-600">
          Your request reached Daryl directly. For anything urgent, call the
          24/7 line at{' '}
          <a href="tel:5123692719" className="font-semibold text-signal">
            (512) 369-2719
          </a>
          .
        </p>
      </div>
    )
  }

  return (
    <form
      action={formAction}
      className="rounded-xl border border-line-brand bg-white p-6 sm:p-8"
    >
      {/* Honeypot — visually hidden, off the tab order. Bots fill it; we drop those. */}
      <div aria-hidden className="hidden">
        <label>
          Website
          <input type="text" name="website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="name" className={labelClass}>
            Name
          </label>
          <input
            id="name"
            name="name"
            type="text"
            required
            maxLength={120}
            disabled={pending}
            className={fieldClass}
          />
        </div>
        <div>
          <label htmlFor="email" className={labelClass}>
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            maxLength={254}
            disabled={pending}
            className={fieldClass}
          />
        </div>
      </div>

      <div className="mt-5">
        <label htmlFor="phone" className={labelClass}>
          Phone <span className="font-normal text-slate-400">(optional)</span>
        </label>
        <input
          id="phone"
          name="phone"
          type="tel"
          maxLength={40}
          disabled={pending}
          className={fieldClass}
        />
      </div>

      <div className="mt-5">
        <label htmlFor="message" className={labelClass}>
          How can we help?
        </label>
        <textarea
          id="message"
          name="message"
          required
          rows={5}
          maxLength={5000}
          disabled={pending}
          placeholder="Tell us about the property, the work needed, and your timeline."
          className={`${fieldClass} resize-y`}
        />
      </div>

      {state.error ? (
        <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {state.error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={pending}
        className="mt-6 inline-flex w-full items-center justify-center rounded-md bg-signal px-7 py-4 font-sans text-[16px] font-semibold text-white transition-colors hover:bg-signal-ink active:translate-y-px disabled:opacity-60 sm:w-auto"
      >
        {pending ? 'Sending…' : 'Send request'}
      </button>
    </form>
  )
}
