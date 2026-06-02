/**
 * Marketing-site icon set.
 *
 * The design handoff README is explicit that the prototype's
 * geometric SVG marks are stand-ins for "a real icon library
 * (e.g. Lucide, Phosphor, Heroicons)". We use Heroicons since
 * the rest of the codebase already does. For the few groups
 * Heroicons doesn't cover cleanly (Doors & Openings, Plumbing
 * pipes), we keep small inline SVGs.
 *
 * Sizes per the README:
 *   - service group chips → ~17px
 *   - value-prop tiles    → ~24px
 *   - certification badges→ ~24px
 *   - nav / button arrows → ~18px
 */

import {
  ArrowRightIcon,
  BoltIcon,
  CalendarDaysIcon,
  CheckBadgeIcon,
  ClockIcon,
  Cog6ToothIcon,
  DocumentCheckIcon,
  GlobeAltIcon,
  RectangleGroupIcon,
  ShieldCheckIcon,
  SunIcon,
  WrenchIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'

import type { ServiceGroup } from './data'

export { ArrowRightIcon }

// -------------- Service group icons --------------

/** Inline SVG for plumbing — a stylized pipe T-joint that reads
 * better than any Heroicons match. Stroke matches Heroicons 24px
 * outline so it pairs cleanly when both render side-by-side. */
function PlumbingIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M5 8.5h6v-3h2v9h7" />
      <rect x="3" y="6.5" width="2.5" height="4" rx="0.6" />
      <rect x="18.5" y="13" width="2.5" height="4" rx="0.6" />
    </svg>
  )
}

/** Inline SVG for doors — a vertical panel with a tiny knob. */
function DoorsIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <rect x="6" y="3.5" width="12" height="17" rx="1" />
      <circle cx="14.5" cy="12" r="1" fill="currentColor" stroke="none" />
      <line x1="4" y1="20.5" x2="20" y2="20.5" />
    </svg>
  )
}

export function ServiceGroupIcon({
  slug,
  className,
}: {
  slug: ServiceGroup['slug']
  className?: string
}) {
  const cls = className ?? 'size-[17px]'
  switch (slug) {
    case 'hvac':
      return <Cog6ToothIcon className={cls} />
    case 'electrical':
      return <BoltIcon className={cls} />
    case 'plumbing':
      return <PlumbingIcon className={cls} />
    case 'doors':
      return <DoorsIcon className={cls} />
    case 'exterior':
      return <SunIcon className={cls} />
    case 'construction':
      return <WrenchScrewdriverIcon className={cls} />
    case 'general':
      return <WrenchIcon className={cls} />
  }
}

// -------------- Value-prop icons --------------

export function ValuePropIcon({
  iconKey,
  className,
}: {
  iconKey: 'cluster' | 'clock' | 'shield' | 'calendar'
  className?: string
}) {
  const cls = className ?? 'size-6 text-white'
  switch (iconKey) {
    case 'cluster':
      return <RectangleGroupIcon className={cls} />
    case 'clock':
      return <ClockIcon className={cls} />
    case 'shield':
      return <ShieldCheckIcon className={cls} />
    case 'calendar':
      return <CalendarDaysIcon className={cls} />
  }
}

// -------------- Certification icons --------------

export function CertificationIcon({
  iconKey,
  className,
}: {
  iconKey: 'badge' | 'globe' | 'doc' | 'shield'
  className?: string
}) {
  const cls = className ?? 'size-6 text-white'
  switch (iconKey) {
    case 'badge':
      return <CheckBadgeIcon className={cls} />
    case 'globe':
      return <GlobeAltIcon className={cls} />
    case 'doc':
      return <DocumentCheckIcon className={cls} />
    case 'shield':
      return <ShieldCheckIcon className={cls} />
  }
}
