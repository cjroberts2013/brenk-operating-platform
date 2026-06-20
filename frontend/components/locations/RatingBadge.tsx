/**
 * Color-coded 3-tier location health badge. null/unknown → neutral
 * "Unrated" so a never-reviewed site doesn't read as healthy.
 */

const STYLES: Record<string, { label: string; className: string }> = {
  good: {
    label: 'Good',
    className:
      'bg-green-100 text-green-800 ring-green-600/20 dark:bg-green-500/10 dark:text-green-300 dark:ring-green-500/30',
  },
  watch: {
    label: 'Watch',
    className:
      'bg-amber-100 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30',
  },
  problem: {
    label: 'Problem',
    className:
      'bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30',
  },
}

const UNRATED = {
  label: 'Unrated',
  className:
    'bg-gray-100 text-gray-500 ring-gray-500/20 dark:bg-white/5 dark:text-gray-400 dark:ring-white/10',
}

export function RatingBadge({ rating }: { rating: string | null }) {
  const style = (rating && STYLES[rating]) || UNRATED
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style.className}`}
    >
      {style.label}
    </span>
  )
}
