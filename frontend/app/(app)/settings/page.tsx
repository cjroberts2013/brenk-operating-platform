import { InformationCircleIcon } from '@heroicons/react/20/solid'

import { JobTypesPanel } from '@/components/settings/JobTypesPanel'
import { MarkupDefaultsTable } from '@/components/settings/MarkupDefaultsTable'
import { listJobTypes } from '@/lib/api/job-types'
import { listTrades } from '@/lib/api/trades'

export default async function SettingsPage() {
  const [trades, jobTypes] = await Promise.all([listTrades(), listJobTypes()])
  const withDefaults = trades.filter((t) => t.default_markup_percent !== null)
  const activeTypes = jobTypes.filter((t) => t.is_active).length

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Settings
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Per-account preferences and the rules the dashboard uses to suggest
          numbers.
        </p>
      </header>

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            Default markup by trade
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-gray-500 dark:text-gray-400">
            Sets the suggested markup % that shows on a work order&apos;s
            markup helper. Daryl can still override on a per-job basis — this
            is just the starting point. Leave a row blank if you&apos;d rather
            enter the number manually each time.
          </p>
        </div>

        <div className="flex items-start gap-2 rounded-md bg-gray-50 px-3 py-2.5 text-sm text-gray-600 dark:bg-gray-800/40 dark:text-gray-400">
          <InformationCircleIcon className="mt-0.5 size-4 shrink-0 text-gray-400" />
          <p>
            {withDefaults.length} of {trades.length} trades have a default set.
            Brenk&apos;s working markup range is roughly 65–200%, with most
            jobs landing somewhere in between.
          </p>
        </div>

        <MarkupDefaultsTable trades={trades} />
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            Job types
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-gray-500 dark:text-gray-400">
            The shared list the AI uses to categorize work orders and the same
            options you tag vendors with — so a job&apos;s type lines up with the
            vendors who can do it. Add a type as new trades come up; renaming one
            updates every work order already filed under it.
          </p>
        </div>

        <div className="flex items-start gap-2 rounded-md bg-gray-50 px-3 py-2.5 text-sm text-gray-600 dark:bg-gray-800/40 dark:text-gray-400">
          <InformationCircleIcon className="mt-0.5 size-4 shrink-0 text-gray-400" />
          <p>
            {activeTypes} active job types. Retiring one hides it from the
            dropdowns going forward but keeps it on any work orders already using
            it.
          </p>
        </div>

        <JobTypesPanel jobTypes={jobTypes} />
      </section>
    </div>
  )
}
