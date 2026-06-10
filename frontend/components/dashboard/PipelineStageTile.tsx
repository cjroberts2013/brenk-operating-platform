import Link from 'next/link'
import {
  CheckCircleIcon,
  CurrencyDollarIcon,
  UserIcon,
} from '@heroicons/react/24/outline'

import type { PipelineStage, PipelineStageColor } from '@/lib/api/types'

// Each stage links into the work-orders list pre-filtered to the
// same rows the tile counted. The backend honors `?stage=…` with
// the exact composite filter from `app/services/pipeline.py`, so
// the tile count and the resulting list page row count are
// guaranteed to match.

// Tailwind classes per SC color name. The accent bar uses the
// saturated tone; the count uses the same hue, slightly darker so
// it still reads on white. Dark-mode variants kept simple — same
// hue, the rest of the card carries the contrast.
const COLOR_CLASSES: Record<
  PipelineStageColor,
  { bar: string; count: string; dot: string }
> = {
  pink: {
    bar: 'bg-pink-500',
    count: 'text-pink-700 dark:text-pink-400',
    dot: 'bg-pink-500',
  },
  yellow: {
    bar: 'bg-yellow-400',
    count: 'text-yellow-700 dark:text-yellow-400',
    dot: 'bg-yellow-400',
  },
  orange: {
    bar: 'bg-orange-500',
    count: 'text-orange-700 dark:text-orange-400',
    dot: 'bg-orange-500',
  },
  green: {
    bar: 'bg-green-500',
    count: 'text-green-700 dark:text-green-400',
    dot: 'bg-green-500',
  },
  emerald: {
    bar: 'bg-emerald-500',
    count: 'text-emerald-700 dark:text-emerald-400',
    dot: 'bg-emerald-500',
  },
  gray: {
    bar: 'bg-gray-400',
    count: 'text-gray-700 dark:text-gray-400',
    dot: 'bg-gray-400',
  },
}

function StageIcon({ name }: { name: PipelineStage['icon'] }) {
  if (name === null) return null
  const Icon =
    name === 'user'
      ? UserIcon
      : name === 'money'
        ? CurrencyDollarIcon
        : name === 'check'
          ? CheckCircleIcon
          : null
  if (!Icon) return null
  return <Icon className="size-3.5 text-gray-500 dark:text-gray-400" />
}

function formatAge(days: number | null): string {
  if (days === null) return '—'
  if (days < 1) return '<1d avg'
  return `${Math.round(days)}d avg`
}

// The two billing-tail stages route to the purpose-built Invoices
// worklist (money columns + markup/paid sub-states) instead of the
// generic Work Orders table. They land on the most actionable tab; the
// Invoices tab nav then shows the full per-tab breakdown of the tile's
// count. Every earlier stage routes to the WO list filtered to it.
const STAGE_HREFS: Record<string, string> = {
  ready_to_invoice: '/invoices?tab=ready_to_markup',
  invoiced: '/invoices?tab=sent',
}

export function PipelineStageTile({ stage }: { stage: PipelineStage }) {
  const colors = COLOR_CLASSES[stage.color]
  const href =
    STAGE_HREFS[stage.key] ??
    `/work-orders?stage=${encodeURIComponent(stage.key)}`

  return (
    <Link
      href={href}
      className="group relative block overflow-hidden rounded-lg bg-white p-4 ring-1 ring-gray-200 transition hover:ring-gray-300 dark:bg-gray-900 dark:ring-white/10 dark:hover:ring-white/20"
    >
      {/* Top accent bar — same color language as SC status badges */}
      <div className={`absolute inset-x-0 top-0 h-1 ${colors.bar}`} />

      <div className="flex items-center gap-1.5">
        <span className={`size-2 rounded-full ${colors.dot}`} />
        <StageIcon name={stage.icon} />
        <p className="text-xs font-medium tracking-wide text-gray-600 uppercase dark:text-gray-400">
          {stage.label}
        </p>
      </div>

      <p className={`mt-3 text-3xl font-semibold ${colors.count}`}>
        {stage.count}
      </p>

      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="text-gray-500 dark:text-gray-400">
          {formatAge(stage.avg_age_days)}
        </span>
        {stage.stuck_count > 0 ? (
          <span className="rounded-sm bg-red-50 px-1.5 py-px font-medium text-red-700 dark:bg-red-950/50 dark:text-red-400">
            {stage.stuck_count} stuck
          </span>
        ) : (
          <span className="text-gray-400 dark:text-gray-500">on track</span>
        )}
      </div>
    </Link>
  )
}
