'use client'

import { useState, useTransition } from 'react'
import Link from 'next/link'
import {
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { Bars3Icon } from '@heroicons/react/20/solid'

import {
  saveServicesAction,
  saveStorefrontAction,
} from '@/app/(app)/storefront/actions'
import type {
  Storefront,
  StorefrontServiceItem,
  StorefrontUpdate,
} from '@/lib/api/types'

/** Tiny "this section is dirty" flag — used to enable Save buttons
 *  only when something has actually changed. */
function diffed<T>(a: T, b: T): boolean {
  return JSON.stringify(a) !== JSON.stringify(b)
}

/** Snapshot of the page-level fields the editor manages, derived
 *  from the full Storefront response so we can diff against the
 *  remote copy to know "is this dirty?". */
type PageFields = Pick<
  Storefront,
  | 'hero_title'
  | 'hero_subtitle'
  | 'hero_cta_text'
  | 'hero_cta_link'
  | 'hero_image_url'
  | 'about_heading'
  | 'about_body'
  | 'about_image_url'
  | 'service_area_heading'
  | 'service_area_body'
  | 'contact_email'
  | 'contact_phone'
  | 'contact_address'
  | 'contact_hours'
  | 'footer_tagline'
  | 'footer_copyright'
  | 'logo_url'
>

const PAGE_FIELD_KEYS: (keyof PageFields)[] = [
  'hero_title',
  'hero_subtitle',
  'hero_cta_text',
  'hero_cta_link',
  'hero_image_url',
  'about_heading',
  'about_body',
  'about_image_url',
  'service_area_heading',
  'service_area_body',
  'contact_email',
  'contact_phone',
  'contact_address',
  'contact_hours',
  'footer_tagline',
  'footer_copyright',
  'logo_url',
]

function pickPageFields(s: Storefront): PageFields {
  const o = {} as PageFields
  for (const k of PAGE_FIELD_KEYS) (o as Record<string, unknown>)[k] = s[k]
  return o
}

export function StorefrontEditor({ initial }: { initial: Storefront }) {
  const [serverState, setServerState] = useState<Storefront>(initial)
  const [page, setPage] = useState<PageFields>(pickPageFields(initial))
  const [services, setServices] = useState<StorefrontServiceItem[]>(
    initial.services.map((s) => ({ ...s })),
  )
  const [pending, startTransition] = useTransition()
  const [pageError, setPageError] = useState<string | null>(null)
  const [servicesError, setServicesError] = useState<string | null>(null)
  const [savedPageTick, setSavedPageTick] = useState(0)
  const [savedServicesTick, setSavedServicesTick] = useState(0)

  const remotePage = pickPageFields(serverState)
  const remoteServices = serverState.services.map((s) => ({ ...s }))
  const pageDirty = diffed(page, remotePage)
  const servicesDirty = diffed(services, remoteServices)

  function setField<K extends keyof PageFields>(key: K, value: string) {
    // Empty string = clear the field (null in DB). Trim only on
    // save, so the user can type spaces mid-edit if they want.
    setPage((prev) => ({ ...prev, [key]: value.length ? value : null }))
  }

  function savePage() {
    setPageError(null)
    // Send only the changed fields. Same shape backend expects.
    const patch: StorefrontUpdate = {}
    for (const k of PAGE_FIELD_KEYS) {
      if (page[k] !== remotePage[k]) {
        ;(patch as Record<string, unknown>)[k] = page[k]
      }
    }
    if (Object.keys(patch).length === 0) return
    startTransition(async () => {
      const result = await saveStorefrontAction(patch)
      if (result.error) {
        setPageError(result.error)
        return
      }
      // Optimistic: apply locally so dirty flag clears immediately.
      setServerState((prev) => ({
        ...prev,
        ...(patch as Partial<Storefront>),
      }))
      setSavedPageTick((n) => n + 1)
    })
  }

  function saveServices() {
    setServicesError(null)
    // Renumber sort_order monotonically before sending so reordering
    // in the UI doesn't depend on the editor being careful with
    // numbers; we always send 0, 1, 2, …
    const payload = services.map((s, i) => ({
      ...s,
      id: undefined, // server reassigns
      sort_order: i,
    }))
    startTransition(async () => {
      const result = await saveServicesAction(payload)
      if (result.error) {
        setServicesError(result.error)
        return
      }
      setServerState((prev) => ({
        ...prev,
        services: payload.map((s) => ({ ...s, id: null })),
      }))
      setSavedServicesTick((n) => n + 1)
    })
  }

  function addService() {
    setServices((prev) => [
      ...prev,
      { sort_order: prev.length, title: '', description: '', icon: '' },
    ])
  }

  function removeService(index: number) {
    setServices((prev) => prev.filter((_, i) => i !== index))
  }

  function moveService(index: number, direction: -1 | 1) {
    setServices((prev) => {
      const target = index + direction
      if (target < 0 || target >= prev.length) return prev
      const next = [...prev]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  function updateService<K extends keyof StorefrontServiceItem>(
    index: number,
    key: K,
    value: StorefrontServiceItem[K],
  ) {
    setServices((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [key]: value } : s)),
    )
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Storefront
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
            The public marketing site at{' '}
            <code className="rounded bg-gray-100 px-1 py-0.5 text-xs dark:bg-white/10">
              brenkfacilityservices.com
            </code>
            . Daryl edits the copy here; changes are live the moment you save.
          </p>
        </div>
        <a
          href="/marketing"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 dark:bg-white/5 dark:text-gray-200 dark:hover:bg-white/10"
        >
          Preview
          <ArrowTopRightOnSquareIcon className="size-4" />
        </a>
      </header>

      {/* -------- Branding + Hero -------- */}
      <EditorSection
        title="Hero & Branding"
        subtitle="The first thing visitors see — short, confident, with one clear call to action."
        dirty={pageDirty}
        onSave={savePage}
        pending={pending}
        error={pageError}
        savedTick={savedPageTick}
      >
        <Field label="Logo URL" hint="Paste a hosted image URL.">
          <TextInput
            value={page.logo_url}
            onChange={(v) => setField('logo_url', v)}
          />
        </Field>
        <Field label="Hero title">
          <TextInput
            value={page.hero_title}
            onChange={(v) => setField('hero_title', v)}
            placeholder="Brenk Facility Services"
          />
        </Field>
        <Field label="Hero subtitle">
          <TextArea
            value={page.hero_subtitle}
            onChange={(v) => setField('hero_subtitle', v)}
            rows={2}
            placeholder="Family-owned commercial facility maintenance serving Austin & San Antonio."
          />
        </Field>
        <Row>
          <Field label="CTA button text">
            <TextInput
              value={page.hero_cta_text}
              onChange={(v) => setField('hero_cta_text', v)}
              placeholder="Get a quote"
            />
          </Field>
          <Field
            label="CTA link"
            hint="Use '#contact' to jump to the contact section."
          >
            <TextInput
              value={page.hero_cta_link}
              onChange={(v) => setField('hero_cta_link', v)}
              placeholder="#contact"
            />
          </Field>
        </Row>
        <Field label="Hero image URL" hint="Optional — a background or feature image.">
          <TextInput
            value={page.hero_image_url}
            onChange={(v) => setField('hero_image_url', v)}
          />
        </Field>
      </EditorSection>

      {/* About + Service Area sections hidden 2026-05-28.
       *
       * The new hi-fi homepage (per `docs/design_handoff_brenk_homepage/`)
       * has no slots for these — they were folded into the Stats Band,
       * Why Brenk, Testimonial, and footer instead. The underlying DB
       * columns (`about_*`, `service_area_*`) are intentionally
       * preserved so we can restore the editor surface or repurpose
       * the data without a migration. Just stop rendering the editor
       * panels for now. */}

      {/* -------- Contact -------- */}
      <EditorSection
        title="Contact"
        subtitle="How customers reach Brenk. Shown in the footer and the contact section."
        dirty={pageDirty}
        onSave={savePage}
        pending={pending}
        error={null}
        savedTick={savedPageTick}
        hideSave
      >
        <Row>
          <Field label="Email">
            <TextInput
              value={page.contact_email}
              onChange={(v) => setField('contact_email', v)}
              type="email"
              placeholder="hello@brenkfacilityservices.com"
            />
          </Field>
          <Field label="Phone">
            <TextInput
              value={page.contact_phone}
              onChange={(v) => setField('contact_phone', v)}
              placeholder="(512) 555-1234"
            />
          </Field>
        </Row>
        <Field label="Address">
          <TextInput
            value={page.contact_address}
            onChange={(v) => setField('contact_address', v)}
            placeholder="Buda, TX"
          />
        </Field>
        <Field label="Hours">
          <TextInput
            value={page.contact_hours}
            onChange={(v) => setField('contact_hours', v)}
            placeholder="Mon-Fri, 8am-6pm CT"
          />
        </Field>
      </EditorSection>

      {/* -------- Footer -------- */}
      <EditorSection
        title="Footer"
        subtitle="Small print at the bottom of every page."
        dirty={pageDirty}
        onSave={savePage}
        pending={pending}
        error={null}
        savedTick={savedPageTick}
      >
        <Field label="Tagline">
          <TextInput
            value={page.footer_tagline}
            onChange={(v) => setField('footer_tagline', v)}
            placeholder="Commercial facility maintenance, done right."
          />
        </Field>
        <Field label="Copyright">
          <TextInput
            value={page.footer_copyright}
            onChange={(v) => setField('footer_copyright', v)}
            placeholder="(c) Brenk Facility Services, LLC."
          />
        </Field>
      </EditorSection>

      {/* -------- Services (separate save — different endpoint) -------- */}
      <EditorSection
        title="Services"
        subtitle="What Brenk offers. Reorder with the up/down arrows; delete with the trash icon."
        dirty={servicesDirty}
        onSave={saveServices}
        pending={pending}
        error={servicesError}
        savedTick={savedServicesTick}
        saveLabel="Save services"
      >
        <div className="space-y-3">
          {services.map((s, i) => (
            <div
              key={i}
              className="grid grid-cols-1 gap-2 rounded-md border border-gray-200 p-3 md:grid-cols-[24px_1fr_1fr_120px_64px] md:items-start dark:border-white/10"
            >
              <div className="flex flex-col items-center justify-start gap-1 text-xs text-gray-400">
                <button
                  type="button"
                  onClick={() => moveService(i, -1)}
                  disabled={i === 0 || pending}
                  className="rounded p-0.5 hover:bg-gray-100 disabled:opacity-40 dark:hover:bg-white/5"
                  title="Move up"
                >
                  <Bars3Icon className="size-3 rotate-180" />
                </button>
                <span>{i + 1}</span>
                <button
                  type="button"
                  onClick={() => moveService(i, 1)}
                  disabled={i === services.length - 1 || pending}
                  className="rounded p-0.5 hover:bg-gray-100 disabled:opacity-40 dark:hover:bg-white/5"
                  title="Move down"
                >
                  <Bars3Icon className="size-3" />
                </button>
              </div>
              <input
                type="text"
                value={s.title}
                onChange={(e) => updateService(i, 'title', e.target.value)}
                placeholder="Title (e.g. Plumbing)"
                className={inputClass}
              />
              <input
                type="text"
                value={s.description ?? ''}
                onChange={(e) =>
                  updateService(i, 'description', e.target.value || null)
                }
                placeholder="One-line description"
                className={inputClass}
              />
              <input
                type="text"
                value={s.icon ?? ''}
                onChange={(e) => updateService(i, 'icon', e.target.value || null)}
                placeholder="Icon name"
                title="Heroicon outline name (optional)"
                className={inputClass}
              />
              <button
                type="button"
                onClick={() => removeService(i)}
                disabled={pending}
                title="Remove this service"
                className="self-start justify-self-end rounded-md p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950"
              >
                <TrashIcon className="size-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addService}
            disabled={pending}
            className="inline-flex items-center gap-1 rounded-md border border-dashed border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:border-white/10 dark:text-gray-400 dark:hover:bg-white/5"
          >
            <PlusIcon className="size-4" />
            Add service
          </button>
        </div>
      </EditorSection>
    </div>
  )
}

// =============================================================================
// Section primitives
// =============================================================================

function EditorSection({
  title,
  subtitle,
  children,
  dirty,
  onSave,
  pending,
  error,
  savedTick,
  hideSave = false,
  saveLabel = 'Save section',
}: {
  title: string
  subtitle: string
  children: React.ReactNode
  dirty: boolean
  onSave: () => void
  pending: boolean
  error: string | null
  savedTick: number
  hideSave?: boolean
  saveLabel?: string
}) {
  return (
    <section className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 px-5 py-4 dark:border-white/10">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            {title}
          </h2>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            {subtitle}
          </p>
        </div>
        {!hideSave ? (
          <div className="flex items-center gap-2">
            {savedTick > 0 ? (
              <span
                key={savedTick}
                className="inline-flex items-center gap-1 text-xs text-green-600 dark:text-green-400"
              >
                <CheckCircleIcon className="size-4" />
                Saved
              </span>
            ) : null}
            <button
              type="button"
              onClick={onSave}
              disabled={!dirty || pending}
              className="rounded-md bg-indigo-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
            >
              {pending ? 'Saving…' : saveLabel}
            </button>
          </div>
        ) : null}
      </header>
      <div className="space-y-4 px-5 py-4">
        {children}
        {error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
        {label}
      </label>
      {children}
      {hint ? (
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{hint}</p>
      ) : null}
    </div>
  )
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
}

function TextInput({
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  value: string | null
  onChange: (v: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <input
      type={type}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={inputClass}
    />
  )
}

function TextArea({
  value,
  onChange,
  rows = 3,
  placeholder,
}: {
  value: string | null
  onChange: (v: string) => void
  rows?: number
  placeholder?: string
}) {
  return (
    <textarea
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      placeholder={placeholder}
      className={inputClass}
    />
  )
}

const inputClass =
  'block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 shadow-xs placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500'
