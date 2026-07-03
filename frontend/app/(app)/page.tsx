import { DeadlineWatchPanel } from '@/components/dashboard/DeadlineWatchPanel'
import { MoneyStatsBand } from '@/components/dashboard/MoneyStatsBand'
import { PipelineStageTile } from '@/components/dashboard/PipelineStageTile'
import { StuckPanel } from '@/components/dashboard/StuckPanel'
import { getDashboardPipeline } from '@/lib/api/dashboard'

export default async function DashboardPage() {
  const data = await getDashboardPipeline()

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {data.total_open} work order{data.total_open === 1 ? '' : 's'} in the
          pipeline · {data.total_invoiced} invoiced to date
        </p>
      </header>

      {/* Money first: unbilled / awaiting payment / paid this month.
          Counts say what's moving; these say what it's worth. */}
      <section>
        <MoneyStatsBand stats={data.money} />
      </section>

      {/* Pipeline funnel: SC's color language left to right.
          Mobile: 2-up, md: 3-up, xl: full row of 6. */}
      <section>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {data.stages.map((stage) => (
            <PipelineStageTile key={stage.key} stage={stage} />
          ))}
        </div>
      </section>

      {/* Deadline watch — CubeSmart's 3-5 day turnaround promise. */}
      <section>
        <DeadlineWatchPanel watch={data.deadline_watch} />
      </section>

      {/* Stuck right now — the operational reason this page exists. */}
      <section>
        <StuckPanel items={data.stuck} />
      </section>
    </div>
  )
}
