'use client'

import { useState, useTransition } from 'react'
import { CheckIcon, PlusIcon } from '@heroicons/react/20/solid'

import {
  createJobTypeAction,
  setJobTypeActiveAction,
  updateJobTypeAction,
} from '@/app/(app)/settings/job-type-actions'
import type { JobType } from '@/lib/api/types'

export function JobTypesPanel({ jobTypes }: { jobTypes: JobType[] }) {
  return (
    <div className="space-y-3">
      <AddJobTypeRow />
      <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
          <thead className="bg-gray-50 dark:bg-gray-800/50">
            <tr>
              <Th className="w-48">Name</Th>
              <Th>Description (guides the AI)</Th>
              <Th className="w-24 text-right">Status</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
            {jobTypes.map((jt) => (
              <JobTypeRow key={jt.id} jobType={jt} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Th({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <th
      scope="col"
      className={`px-3 py-2 text-left text-xs font-medium tracking-wide text-gray-500 uppercase dark:text-gray-400 ${className}`}
    >
      {children}
    </th>
  )
}

function JobTypeRow({ jobType }: { jobType: JobType }) {
  const [name, setName] = useState(jobType.name)
  const [description, setDescription] = useState(jobType.description ?? '')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [savedTick, setSavedTick] = useState(0)

  const dirty =
    name.trim() !== jobType.name || description.trim() !== (jobType.description ?? '')

  function save() {
    setError(null)
    startTransition(async () => {
      const res = await updateJobTypeAction(jobType.id, {
        name: name.trim(),
        description: description.trim() || null,
      })
      if (res.error) setError(res.error)
      else setSavedTick((n) => n + 1)
    })
  }

  function toggleActive() {
    setError(null)
    startTransition(async () => {
      const res = await setJobTypeActiveAction(jobType.id, !jobType.is_active)
      if (res.error) setError(res.error)
    })
  }

  const muted = !jobType.is_active

  return (
    <tr className={muted ? 'bg-gray-50/60 dark:bg-gray-800/30' : ''}>
      <td className="px-3 py-2 align-top">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={pending}
          className={inputClass}
        />
        {jobType.is_catchall ? (
          <span className="mt-1 inline-block text-[10px] font-medium tracking-wide text-gray-400 uppercase">
            catch-all
          </span>
        ) : null}
      </td>
      <td className="px-3 py-2 align-top">
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What kind of work falls here?"
          disabled={pending}
          className={inputClass}
        />
        {error ? (
          <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>
        ) : null}
      </td>
      <td className="px-3 py-2 text-right align-top">
        <div className="flex items-center justify-end gap-2">
          {dirty ? (
            <button
              type="button"
              onClick={save}
              disabled={pending}
              className="rounded-md bg-indigo-500 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-60"
            >
              {pending ? '…' : 'Save'}
            </button>
          ) : savedTick > 0 ? (
            <span className="text-green-600 dark:text-green-400" title="Saved">
              <CheckIcon className="size-4" />
            </span>
          ) : null}
          {jobType.is_catchall ? null : (
            <button
              type="button"
              onClick={toggleActive}
              disabled={pending}
              className="rounded-md px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-60 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-200"
            >
              {jobType.is_active ? 'Retire' : 'Restore'}
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

function AddJobTypeRow() {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  function add() {
    if (!name.trim()) return
    setError(null)
    startTransition(async () => {
      const res = await createJobTypeAction(name, description)
      if (res.error) {
        setError(res.error)
      } else {
        setName('')
        setDescription('')
      }
    })
  }

  return (
    <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-800/40">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              add()
            }
          }}
          placeholder="New job type (e.g. Solar, Awnings)"
          disabled={pending}
          className={`sm:w-48 ${inputClass}`}
        />
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description to help the AI classify it"
          disabled={pending}
          className={`flex-1 ${inputClass}`}
        />
        <button
          type="button"
          onClick={add}
          disabled={pending || !name.trim()}
          className="inline-flex items-center justify-center gap-1 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
        >
          <PlusIcon className="size-4" />
          Add
        </button>
      </div>
      {error ? (
        <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{error}</p>
      ) : null}
    </div>
  )
}

const inputClass =
  'block w-full rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 shadow-xs placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-white/10 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500'
