/**
 * Dependency-free horizontal bar chart for ranking categories/vendors.
 * Bars are sized relative to the largest value; a label sits on the left,
 * the formatted value on the right. Pure presentational — renders in a
 * server component.
 */

export type BarDatum = {
  label: string
  value: number
  /** Pre-formatted value shown at the bar's end (e.g. "$1,015", "67"). */
  valueLabel: string
}

export function BarChart({
  data,
  barClassName = 'bg-indigo-500',
  emptyLabel = 'No data yet.',
}: {
  data: BarDatum[]
  barClassName?: string
  emptyLabel?: string
}) {
  if (data.length === 0) {
    return (
      <p className="px-1 py-4 text-sm text-gray-500 dark:text-gray-400">
        {emptyLabel}
      </p>
    )
  }
  const max = Math.max(1, ...data.map((d) => d.value))

  return (
    <div className="space-y-1.5">
      {data.map((d) => {
        const pct = Math.max(0, (d.value / max) * 100)
        return (
          <div
            key={d.label}
            className="grid grid-cols-[7.5rem_1fr_5rem] items-center gap-3 text-sm sm:grid-cols-[10rem_1fr_6rem]"
          >
            <span
              className="truncate text-gray-700 dark:text-gray-300"
              title={d.label}
            >
              {d.label}
            </span>
            <div className="h-5 overflow-hidden rounded bg-gray-100 dark:bg-white/5">
              <div
                className={`h-5 rounded ${barClassName}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-right tabular-nums text-gray-700 dark:text-gray-300">
              {d.valueLabel}
            </span>
          </div>
        )
      })}
    </div>
  )
}
