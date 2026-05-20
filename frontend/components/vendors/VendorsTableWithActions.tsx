'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  PencilSquareIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/20/solid'

import { deleteVendorAction } from '@/app/(app)/vendors/actions'
import type { TradeRef, VendorSummary } from '@/lib/api/types'

import { SyncFromScButton } from './SyncFromScButton'
import { VendorFormModal } from './VendorFormModal'

export function VendorsTableWithActions({
  vendors,
  trades,
}: {
  vendors: VendorSummary[]
  trades: TradeRef[]
}) {
  const [modal, setModal] = useState<{ open: boolean; vendor: VendorSummary | null }>(
    { open: false, vendor: null },
  )

  function openCreate() {
    setModal({ open: true, vendor: null })
  }

  function openEdit(vendor: VendorSummary) {
    setModal({ open: true, vendor })
  }

  function close() {
    setModal((m) => ({ open: false, vendor: m.vendor }))
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SyncFromScButton />
        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center gap-1 rounded-md bg-indigo-500 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-400"
        >
          <PlusIcon className="size-4" />
          Add vendor
        </button>
      </div>

      <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        {vendors.length === 0 ? (
          <div className="px-4 py-16 text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No vendors yet. Click <strong>Add vendor</strong> to create one,
              or import a list once you have it.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  <Th>Name</Th>
                  <Th>Phone</Th>
                  <Th>Contact</Th>
                  <Th>Payment terms</Th>
                  <Th>Service area</Th>
                  <Th>Trades</Th>
                  <Th align="right">Active WOs</Th>
                  <Th align="right">Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
                {vendors.map((vendor) => (
                  <tr
                    key={vendor.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
                  >
                    <Td>
                      <Link
                        href={`/vendors/${vendor.id}`}
                        className="font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
                      >
                        {vendor.name}
                      </Link>
                      {!vendor.is_active ? (
                        <span className="ml-2 rounded-sm bg-gray-100 px-1.5 py-px text-[10px] font-medium text-gray-500 uppercase dark:bg-white/5 dark:text-gray-400">
                          Inactive
                        </span>
                      ) : null}
                      {vendor.email ? (
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {vendor.email}
                        </div>
                      ) : null}
                    </Td>
                    <Td>{vendor.phone ?? '—'}</Td>
                    <Td>{formatContact(vendor.contact_preference)}</Td>
                    <Td>{vendor.payment_terms ?? '—'}</Td>
                    <Td>{vendor.service_area ?? '—'}</Td>
                    <Td>
                      {vendor.trade_specializations.length === 0 ? (
                        <span className="text-gray-400">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {vendor.trade_specializations.map((t) => (
                            <span
                              key={t.id}
                              className="rounded-md bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700 dark:bg-white/5 dark:text-gray-300"
                            >
                              {t.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </Td>
                    <Td align="right">{vendor.active_work_orders}</Td>
                    <Td align="right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(vendor)}
                          title="Edit vendor"
                          className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-white"
                        >
                          <span className="sr-only">Edit</span>
                          <PencilSquareIcon className="size-4" />
                        </button>
                        <DeleteForm vendor={vendor} />
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <VendorFormModal
        open={modal.open}
        onClose={close}
        vendor={modal.vendor}
        trades={trades}
      />
    </>
  )
}

function DeleteForm({ vendor }: { vendor: VendorSummary }) {
  function confirmDelete(event: React.FormEvent<HTMLFormElement>) {
    if (
      !window.confirm(
        `Mark "${vendor.name}" as inactive? Their work-order history stays intact.`,
      )
    ) {
      event.preventDefault()
    }
  }
  return (
    <form action={deleteVendorAction} onSubmit={confirmDelete}>
      <input type="hidden" name="id" value={vendor.id} />
      <button
        type="submit"
        title="Deactivate vendor"
        className="rounded-md p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600 dark:text-gray-400 dark:hover:bg-red-950 dark:hover:text-red-400"
      >
        <span className="sr-only">Deactivate</span>
        <TrashIcon className="size-4" />
      </button>
    </form>
  )
}

function formatContact(value: string | null): string {
  if (!value) return '—'
  if (value === 'sms') return 'Text'
  if (value === 'call') return 'Call'
  if (value === 'email') return 'Email'
  return value
}

function Th({
  children,
  align = 'left',
}: {
  children: React.ReactNode
  align?: 'left' | 'right'
}) {
  return (
    <th
      scope="col"
      className={`px-3 py-2 ${
        align === 'right' ? 'text-right' : 'text-left'
      } text-xs font-medium tracking-wide text-gray-500 uppercase dark:text-gray-400`}
    >
      {children}
    </th>
  )
}

function Td({
  children,
  align = 'left',
}: {
  children: React.ReactNode
  align?: 'left' | 'right'
}) {
  return (
    <td
      className={`px-3 py-2 ${
        align === 'right' ? 'text-right' : 'text-left'
      } align-top text-sm text-gray-700 dark:text-gray-300`}
    >
      {children}
    </td>
  )
}
