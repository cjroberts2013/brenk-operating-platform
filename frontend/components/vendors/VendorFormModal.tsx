'use client'

import { useActionState, useEffect, useMemo, useRef, useState } from 'react'
import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from '@headlessui/react'
import { PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'

import {
  createSkillAction,
  createVendorAction,
  updateVendorAction,
  type VendorActionState,
} from '@/app/(app)/vendors/actions'
import type { JobType, VendorSummary } from '@/lib/api/types'

const INITIAL_STATE: VendorActionState = { error: null, attempt: 0 }

const CONTACT_OPTIONS = [
  { value: '', label: '— No preference —' },
  { value: 'sms', label: 'Text (SMS)' },
  { value: 'call', label: 'Phone call' },
  { value: 'email', label: 'Email' },
  { value: 'other', label: 'Other' },
]

const MOBILE_APP_OPTIONS = [
  { value: '', label: 'Unknown' },
  { value: 'yes', label: 'Yes — uses the CubeSmart app' },
  { value: 'no', label: 'No' },
]

export type VendorFormModalProps = {
  open: boolean
  onClose: () => void
  /** When set, the modal is in "edit" mode for this vendor. Null → "create". */
  vendor: VendorSummary | null
  jobTypes: JobType[]
}

export function VendorFormModal({
  open,
  onClose,
  vendor,
  jobTypes,
}: VendorFormModalProps) {
  const isEdit = vendor !== null

  const [state, formAction, pending] = useActionState<VendorActionState, FormData>(
    isEdit ? updateVendorAction : createVendorAction,
    INITIAL_STATE,
  )

  // Close on successful submit. `attempt` is bumped by the action; the
  // ref tracks the last attempt we observed so we only close on a *new*
  // success (not on the initial mount with attempt=0).
  const lastObservedAttempt = useRef(0)
  useEffect(() => {
    if (
      state.attempt > lastObservedAttempt.current &&
      state.error === null &&
      !pending
    ) {
      lastObservedAttempt.current = state.attempt
      onClose()
    }
  }, [state.attempt, state.error, pending, onClose])

  // Skill selection lives in client state so newly-created job types can be
  // appended + auto-selected without remounting the form. Seed the available
  // list with the active job types plus any skills already on the vendor
  // (which may include a since-retired type, so it still shows as selected).
  const [skillsList, setSkillsList] = useState<JobType[]>(jobTypes)
  const [selectedSkillIds, setSelectedSkillIds] = useState<Set<number>>(
    () => new Set((vendor?.skills ?? []).map((t) => t.id)),
  )
  const [skillQuery, setSkillQuery] = useState('')
  const [creatingSkill, setCreatingSkill] = useState(false)
  const [skillCreateError, setSkillCreateError] = useState<string | null>(null)

  // When the parent swaps which vendor is being edited (modal stays
  // mounted across opens), resync the selected skills to the new vendor.
  useEffect(() => {
    setSelectedSkillIds(new Set((vendor?.skills ?? []).map((t) => t.id)))
    setSkillQuery('')
    setSkillCreateError(null)
  }, [vendor?.id])

  // Keep the available list in sync with the active job types, and fold in
  // any of this vendor's current skills that aren't active (retired types),
  // so they still render as selected chips.
  useEffect(() => {
    const base = [...jobTypes, ...(vendor?.skills ?? [])]
    const byId = new Map(base.map((t) => [t.id, t]))
    setSkillsList((prev) => {
      for (const t of prev) if (!byId.has(t.id)) byId.set(t.id, t)
      return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name))
    })
  }, [jobTypes, vendor?.id])

  const filteredSkills = useMemo(() => {
    const q = skillQuery.trim().toLowerCase()
    if (!q) return skillsList
    return skillsList.filter((t) => t.name.toLowerCase().includes(q))
  }, [skillsList, skillQuery])

  const showCreateOption =
    skillQuery.trim().length > 0 && filteredSkills.length === 0

  function toggleSkill(id: number) {
    setSelectedSkillIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleCreateSkill() {
    const name = skillQuery.trim()
    if (!name || creatingSkill) return
    setCreatingSkill(true)
    setSkillCreateError(null)
    const result = await createSkillAction(name)
    setCreatingSkill(false)
    if (result.error) {
      setSkillCreateError(result.error)
      return
    }
    if (result.skill) {
      const newSkill = result.skill
      setSkillsList((prev) =>
        [...prev, newSkill].sort((a, b) => a.name.localeCompare(b.name)),
      )
      setSelectedSkillIds((prev) => new Set([...prev, newSkill.id]))
      setSkillQuery('')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-gray-900/70 transition-opacity duration-200 data-closed:opacity-0"
      />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel
          transition
          className="relative flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-xl ring-1 ring-black/5 transition duration-200 data-closed:translate-y-2 data-closed:opacity-0 dark:bg-gray-900 dark:ring-white/10"
        >
          <div className="flex shrink-0 items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-white/10">
            <DialogTitle className="text-base font-semibold text-gray-900 dark:text-white">
              {isEdit ? `Edit vendor — ${vendor!.name}` : 'Add vendor'}
            </DialogTitle>
            <button
              type="button"
              onClick={onClose}
              className="-m-2 rounded-md p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              <span className="sr-only">Close</span>
              <XMarkIcon className="size-5" />
            </button>
          </div>

          <form action={formAction} className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
            {isEdit ? (
              <input type="hidden" name="id" value={vendor!.id} />
            ) : null}

            <Row>
              <Field label="Name" required>
                <input
                  type="text"
                  name="name"
                  required
                  defaultValue={vendor?.name ?? ''}
                  className={inputClass}
                />
              </Field>
              <Field label="Active">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="is_active"
                    defaultChecked={vendor?.is_active ?? true}
                    className="rounded border-gray-300 text-indigo-500 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Currently active
                  </span>
                </label>
              </Field>
            </Row>

            <Row>
              <Field label="Phone">
                <input
                  type="tel"
                  name="phone"
                  defaultValue={vendor?.phone ?? ''}
                  className={inputClass}
                />
              </Field>
              <Field label="Email">
                <input
                  type="email"
                  name="email"
                  defaultValue={vendor?.email ?? ''}
                  className={inputClass}
                />
              </Field>
            </Row>

            <Row>
              <Field label="Preferred contact">
                <select
                  name="contact_preference"
                  defaultValue={vendor?.contact_preference ?? ''}
                  className={inputClass}
                >
                  {CONTACT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Mobile-app capable">
                <select
                  name="mobile_app_capable"
                  defaultValue={
                    vendor?.mobile_app_capable === true
                      ? 'yes'
                      : vendor?.mobile_app_capable === false
                        ? 'no'
                        : ''
                  }
                  className={inputClass}
                >
                  {MOBILE_APP_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
            </Row>

            <Row>
              <Field label="Payment terms">
                <input
                  type="text"
                  name="payment_terms"
                  placeholder="e.g. Contract · Hourly · Flat per job"
                  defaultValue={vendor?.payment_terms ?? ''}
                  className={inputClass}
                />
              </Field>
              <Field label="Service area">
                <input
                  type="text"
                  name="service_area"
                  placeholder="e.g. Austin & San Antonio · Anywhere · Longview only"
                  defaultValue={vendor?.service_area ?? ''}
                  className={inputClass}
                />
              </Field>
            </Row>

            <Field label="Skills (job types)">
              <input
                type="search"
                value={skillQuery}
                onChange={(e) => {
                  setSkillQuery(e.target.value)
                  if (skillCreateError) setSkillCreateError(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && showCreateOption) {
                    // Prevent submitting the outer form when the user
                    // hits Enter to confirm creating a new job type.
                    e.preventDefault()
                    void handleCreateSkill()
                  }
                }}
                placeholder="Search skills… or type a new one to create"
                className={`mb-2 ${inputClass}`}
              />

              {/* Hidden inputs carry the selected job-type ids into the form
                  submission — keeps the FormData.getAll('job_type_ids')
                  contract that the server action expects. */}
              {[...selectedSkillIds].map((id) => (
                <input key={id} type="hidden" name="job_type_ids" value={id} />
              ))}

              <div className="flex flex-wrap gap-1.5">
                {filteredSkills.map((skill) => {
                  const selected = selectedSkillIds.has(skill.id)
                  return (
                    <button
                      key={skill.id}
                      type="button"
                      onClick={() => toggleSkill(skill.id)}
                      className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset transition-colors ${
                        selected
                          ? 'bg-indigo-500 text-white ring-indigo-400 dark:bg-indigo-500 dark:text-white dark:ring-indigo-400'
                          : 'bg-gray-100 text-gray-700 ring-gray-300 hover:bg-gray-200 dark:bg-white/5 dark:text-gray-300 dark:ring-white/10 dark:hover:bg-white/10'
                      }`}
                    >
                      {skill.name}
                    </button>
                  )
                })}
                {showCreateOption ? (
                  <button
                    type="button"
                    onClick={handleCreateSkill}
                    disabled={creatingSkill}
                    className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2.5 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-500/30 hover:bg-green-500/20 disabled:opacity-60 dark:text-green-300"
                  >
                    <PlusIcon className="size-3" />
                    {creatingSkill ? 'Creating…' : `Create "${skillQuery.trim()}"`}
                  </button>
                ) : null}
              </div>

              <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                These are the shared job types — the same list the AI uses to
                categorize work orders. Manage the full list in Settings.
              </p>

              {skillCreateError ? (
                <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                  {skillCreateError}
                </p>
              ) : null}
            </Field>

            <Field label="Markup notes">
              <textarea
                name="markup_notes"
                rows={2}
                placeholder="e.g. Premium work, run higher markup."
                defaultValue={vendor?.markup_notes ?? ''}
                className={inputClass}
              />
            </Field>

            <Field label="Communication notes">
              <textarea
                name="communication_notes"
                rows={2}
                placeholder="e.g. Don't text after 6pm. Responds slowly."
                defaultValue={vendor?.communication_notes ?? ''}
                className={inputClass}
              />
            </Field>

            <Field label="General notes">
              <textarea
                name="notes"
                rows={2}
                defaultValue={vendor?.notes ?? ''}
                className={inputClass}
              />
            </Field>

            {state.error ? (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
                {state.error}
              </p>
            ) : null}
            </div>

            <div className="flex shrink-0 items-center justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-white/10">
              <button
                type="button"
                onClick={onClose}
                disabled={pending}
                className="rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={pending}
                className="rounded-md bg-indigo-500 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60"
              >
                {pending
                  ? 'Saving…'
                  : isEdit
                    ? 'Save changes'
                    : 'Add vendor'}
              </button>
            </div>
          </form>
        </DialogPanel>
      </div>
    </Dialog>
  )
}

const inputClass =
  'block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 shadow-xs placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500'

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
}

function Field({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
        {label}
        {required ? <span className="ml-0.5 text-red-500">*</span> : null}
      </label>
      {children}
    </div>
  )
}
