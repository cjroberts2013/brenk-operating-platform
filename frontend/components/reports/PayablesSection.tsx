import Link from 'next/link'
import { ExclamationTriangleIcon } from '@heroicons/react/20/solid'

import type { PayablesResponse } from '@/lib/api/types'

function usd(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return value
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

/**
 * Outstanding sub-vendor payouts — what Brenk still owes. The "client paid,
 * vendor not" subset is the cashflow-urgent case (Brenk has the money but
 * hasn't paid the sub) and is surfaced first.
 */
export function PayablesSection({ payables }: { payables: PayablesResponse }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-gray-900 dark:text-white">
          Sub-vendor payables
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          What Brenk still owes its sub-vendors. Mark a vendor paid from the
          work order&apos;s markup helper.
        </p>
      </div>

      {payables.items.length === 0 ? (
        <p className="rounded-lg bg-gray-50 px-4 py-6 text-center text-sm text-gray-500 dark:bg-gray-800/40 dark:text-gray-400">
          Nothing outstanding — every sub-vendor with a recorded payout is paid.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:max-w-md">
            <div className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/40">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Total outstanding
              </p>
              <p className="text-xl font-semibold text-gray-900 dark:text-white">
                {usd(payables.total_outstanding)}
              </p>
            </div>
            <div className="rounded-md bg-amber-50 p-3 dark:bg-amber-950/30">
              <p className="text-xs text-amber-700 dark:text-amber-400">
                Client paid, vendor not
              </p>
              <p className="text-xl font-semibold text-amber-800 dark:text-amber-300">
                {usd(payables.total_client_paid)}
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-white/10">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  <Th>Vendor</Th>
                  <Th>Work order</Th>
                  <Th>Location</Th>
                  <Th align="right">Owed</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white dark:divide-white/10 dark:bg-gray-900">
                {payables.items.map((p) => (
                  <tr
                    key={`${p.work_order_id}-${p.vendor_id}`}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
                  >
                    <td className="px-3 py-2 align-top">
                      <Link
                        href={`/vendors/${p.vendor_id}`}
                        className="font-medium text-gray-800 hover:text-indigo-600 dark:text-gray-100 dark:hover:text-indigo-300"
                      >
                        {p.vendor_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <Link
                        href={`/work-orders/${p.work_order_id}`}
                        className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
                      >
                        #{p.sc_number}
                      </Link>
                      {p.client_paid ? (
                        <span className="ml-2 inline-flex items-center gap-0.5 rounded-sm bg-amber-100 px-1.5 py-px text-[10px] font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
                          <ExclamationTriangleIcon className="size-3" />
                          client paid
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 align-top text-gray-600 dark:text-gray-300">
                      {p.location ?? '—'}
                    </td>
                    <td className="px-3 py-2 text-right align-top font-medium text-gray-900 dark:text-white">
                      {usd(p.payout)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
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
