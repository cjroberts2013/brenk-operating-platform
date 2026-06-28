import { CheckIcon, SparklesIcon } from '@heroicons/react/20/solid'

/**
 * Compact category display for the work-orders list. Mirrors the
 * detail-page CategoryControl's color language so the two read the same:
 *
 *   - source 'ai'        → amber ✨ chip — AI-suggested, NOT yet reviewed.
 *                          This is the "needs your eyes" state; it pops so
 *                          you can scan the list and spot what to confirm.
 *   - source 'confirmed' → quiet green check — you accepted the AI guess.
 *   - source 'manual'    → quiet plain text — you set/changed it yourself.
 *   - no category        → muted dash — uncategorized (AI hasn't run / no
 *                          description to classify).
 *
 * Intentionally distinct from the SC `trade` column next to it: trade is
 * the raw ServiceChannel value (free-form, not our taxonomy); category is
 * Brenk's curated taxonomy used for markup suggestions + profit reports.
 */
export function CategoryCell({
  category,
  source,
  confidence,
}: {
  category: string | null
  source: string | null
  confidence: string | null
}) {
  if (!category) {
    return <span className="text-xs text-gray-400 dark:text-gray-500">—</span>
  }

  if (source === 'ai') {
    const pct =
      confidence != null && confidence !== ''
        ? Math.round(Number(confidence) * 100)
        : null
    return (
      <span
        title={
          pct != null
            ? `AI-suggested · ${pct}% confidence — open the WO to confirm or change`
            : 'AI-suggested — open the WO to confirm or change'
        }
        className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"
      >
        <SparklesIcon className="size-3 shrink-0" />
        {category}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 text-sm text-gray-900 dark:text-white">
      {category}
      {source === 'confirmed' ? (
        <CheckIcon
          className="size-3.5 shrink-0 text-green-600 dark:text-green-400"
          title="Confirmed"
        />
      ) : null}
    </span>
  )
}
