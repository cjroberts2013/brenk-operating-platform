/**
 * Month-grid calendar of work orders, scheduled-date based.
 *
 * Visual base: Tailwind UI "Month view" — adapted to our WO data shape
 * and stripped of features we don't need yet (Add event, view-mode
 * dropdown). Renders two grids — desktop (large screens, with event
 * text) and mobile (compact dots) — like the original.
 *
 * Server Component. Prev/next month nav is plain anchor links that
 * update `?month=YYYY-MM`, so server-rendering refetches with the new
 * range. WOs without a scheduled_date appear in a separate Unscheduled
 * block below the grid.
 */

import Link from 'next/link'
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/20/solid'

import type { WorkOrderSummary } from '@/lib/api/types'

type CalendarProps = {
  year: number
  /** 0-indexed month (Jan = 0, Dec = 11) */
  month: number
  workOrders: WorkOrderSummary[]
  /** Path prefix used to build prev/next links — e.g. `/vendors/5`. */
  basePath: string
}

const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]
const EVENTS_VISIBLE_PER_CELL = 2

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

/** YYYY-MM-DD in the user's local time zone (en-CA happens to format that way). */
function localDateKey(iso: string): string {
  return new Date(iso).toLocaleDateString('en-CA')
}

/** Compact "9PM" / "9:30AM" — drops minutes when on the hour. */
function timeShort(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const minutes = d.getMinutes()
  return d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: minutes === 0 ? undefined : '2-digit',
    hour12: true,
  }).replace(/\s/g, '')
}

function statusTone(
  status: string,
): 'yellow' | 'green' | 'pink' | 'red' | 'gray' | 'slate' {
  const s = status.toUpperCase()
  if (s.includes('CANCEL')) return 'gray'
  if (s.includes('PROGRESS')) return 'yellow'
  if (s.includes('COMPLETED') || s.includes('CONFIRMED')) return 'green'
  if (s === 'OPEN' || s.includes('NEW') || s.includes('PENDING')) return 'pink'
  if (s.includes('EXPIRED') || s.includes('STALE')) return 'red'
  return 'slate'
}

const TONE_DOT: Record<ReturnType<typeof statusTone>, string> = {
  yellow: 'bg-yellow-400',
  green: 'bg-green-500',
  pink: 'bg-pink-400',
  red: 'bg-red-500',
  gray: 'bg-gray-400',
  slate: 'bg-slate-400',
}

type Day = {
  date: string // YYYY-MM-DD
  dayNum: number
  isCurrentMonth: boolean
  isToday: boolean
  events: WorkOrderSummary[]
}

function buildDays(
  year: number,
  month: number,
  workOrders: WorkOrderSummary[],
): Day[] {
  const firstOfMonth = new Date(year, month, 1)
  const lastOfMonth = new Date(year, month + 1, 0)
  const daysInMonth = lastOfMonth.getDate()
  // JS Date: Sun=0..Sat=6. We want Mon=0 → shift.
  const leadingBlanks = (firstOfMonth.getDay() + 6) % 7

  // Group WOs by scheduled-date (local).
  const byDate = new Map<string, WorkOrderSummary[]>()
  for (const wo of workOrders) {
    if (!wo.scheduled_date) continue
    const key = localDateKey(wo.scheduled_date)
    const bucket = byDate.get(key)
    if (bucket) bucket.push(wo)
    else byDate.set(key, [wo])
  }

  const todayKey = new Date().toLocaleDateString('en-CA')
  const days: Day[] = []

  const push = (d: Date, isCurrent: boolean) => {
    const key = d.toLocaleDateString('en-CA')
    days.push({
      date: key,
      dayNum: d.getDate(),
      isCurrentMonth: isCurrent,
      isToday: key === todayKey,
      events: byDate.get(key) ?? [],
    })
  }

  for (let i = 0; i < leadingBlanks; i++) {
    push(new Date(year, month, -leadingBlanks + 1 + i), false)
  }
  for (let day = 1; day <= daysInMonth; day++) {
    push(new Date(year, month, day), true)
  }
  while (days.length < 42) {
    push(
      new Date(year, month + 1, days.length - daysInMonth - leadingBlanks + 1),
      false,
    )
  }
  return days
}

export function WorkOrderCalendar({
  year,
  month,
  workOrders,
  basePath,
}: CalendarProps) {
  const days = buildDays(year, month, workOrders)
  const unscheduled = workOrders.filter((wo) => !wo.scheduled_date)

  const prevYear = month === 0 ? year - 1 : year
  const prevMonth = month === 0 ? 11 : month - 1
  const nextYear = month === 11 ? year + 1 : year
  const nextMonth = month === 11 ? 0 : month + 1
  const prevHref = `${basePath}?month=${prevYear}-${pad2(prevMonth + 1)}`
  const nextHref = `${basePath}?month=${nextYear}-${pad2(nextMonth + 1)}`
  const todayHref = basePath

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
        <header className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-white/10 dark:bg-gray-800/50">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            <time dateTime={`${year}-${pad2(month + 1)}`}>
              {MONTH_NAMES[month]} {year}
            </time>
          </h2>
          <div className="flex items-center">
            <div className="relative flex items-center rounded-md bg-white shadow-xs outline -outline-offset-1 outline-gray-300 md:items-stretch dark:bg-white/10 dark:shadow-none dark:outline-white/5">
              <Link
                href={prevHref}
                className="flex h-9 w-12 items-center justify-center rounded-l-md pr-1 text-gray-400 hover:text-gray-500 focus:relative md:w-9 md:pr-0 md:hover:bg-gray-50 dark:hover:text-white dark:md:hover:bg-white/10"
              >
                <span className="sr-only">Previous month</span>
                <ChevronLeftIcon aria-hidden="true" className="size-5" />
              </Link>
              <Link
                href={todayHref}
                className="hidden px-3.5 text-sm font-semibold text-gray-900 leading-9 hover:bg-gray-50 focus:relative md:block dark:text-white dark:hover:bg-white/10"
              >
                Today
              </Link>
              <span className="relative -mx-px h-5 w-px bg-gray-300 md:hidden dark:bg-white/10" />
              <Link
                href={nextHref}
                className="flex h-9 w-12 items-center justify-center rounded-r-md pl-1 text-gray-400 hover:text-gray-500 focus:relative md:w-9 md:pl-0 md:hover:bg-gray-50 dark:hover:text-white dark:md:hover:bg-white/10"
              >
                <span className="sr-only">Next month</span>
                <ChevronRightIcon aria-hidden="true" className="size-5" />
              </Link>
            </div>
          </div>
        </header>

        <div>
          {/* Weekday header — single letters with sr-only fallback */}
          <div className="grid grid-cols-7 gap-px border-b border-gray-300 bg-gray-200 text-center text-xs font-semibold text-gray-700 dark:border-white/5 dark:bg-white/15 dark:text-gray-300">
            <Weekday short="M" rest="on" />
            <Weekday short="T" rest="ue" />
            <Weekday short="W" rest="ed" />
            <Weekday short="T" rest="hu" />
            <Weekday short="F" rest="ri" />
            <Weekday short="S" rest="at" />
            <Weekday short="S" rest="un" />
          </div>

          <div className="flex bg-gray-200 text-xs text-gray-700 dark:bg-white/10 dark:text-gray-300">
            {/* Desktop: full grid with event text */}
            <div className="hidden w-full lg:grid lg:grid-cols-7 lg:grid-rows-6 lg:gap-px">
              {days.map((day) => (
                <div
                  key={day.date}
                  data-is-today={day.isToday ? '' : undefined}
                  data-is-current-month={day.isCurrentMonth ? '' : undefined}
                  className="group relative bg-gray-50 px-3 py-2 text-gray-500 data-is-current-month:bg-white dark:bg-gray-900 dark:text-gray-400 dark:not-data-is-current-month:before:pointer-events-none dark:not-data-is-current-month:before:absolute dark:not-data-is-current-month:before:inset-0 dark:not-data-is-current-month:before:bg-gray-800/50 dark:data-is-current-month:bg-gray-900 min-h-24"
                >
                  <time
                    dateTime={day.date}
                    className="relative group-not-data-is-current-month:opacity-75 in-data-is-today:flex in-data-is-today:size-6 in-data-is-today:items-center in-data-is-today:justify-center in-data-is-today:rounded-full in-data-is-today:bg-indigo-600 in-data-is-today:font-semibold in-data-is-today:text-white dark:in-data-is-today:bg-indigo-500"
                  >
                    {day.dayNum}
                  </time>
                  {day.events.length > 0 ? (
                    <ol className="mt-2">
                      {day.events
                        .slice(0, EVENTS_VISIBLE_PER_CELL)
                        .map((wo) => {
                          const tone = statusTone(wo.primary_status)
                          return (
                            <li key={wo.id}>
                              <Link
                                href={`/work-orders/${wo.id}`}
                                className="group/event flex items-center gap-1.5"
                                title={`#${wo.sc_number} · ${wo.primary_status}${wo.extended_status ? ` / ${wo.extended_status}` : ''}`}
                              >
                                <span
                                  className={`inline-block size-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`}
                                />
                                <p className="flex-auto truncate font-medium text-gray-900 group-hover/event:text-indigo-600 dark:text-white dark:group-hover/event:text-indigo-400">
                                  #{wo.sc_number}
                                </p>
                                {wo.scheduled_date ? (
                                  <time
                                    dateTime={wo.scheduled_date}
                                    className="ml-2 hidden flex-none text-gray-500 group-hover/event:text-indigo-600 xl:block dark:text-gray-400 dark:group-hover/event:text-indigo-400"
                                  >
                                    {timeShort(wo.scheduled_date)}
                                  </time>
                                ) : null}
                              </Link>
                            </li>
                          )
                        })}
                      {day.events.length > EVENTS_VISIBLE_PER_CELL ? (
                        <li className="text-gray-500 dark:text-gray-400">
                          + {day.events.length - EVENTS_VISIBLE_PER_CELL} more
                        </li>
                      ) : null}
                    </ol>
                  ) : null}
                </div>
              ))}
            </div>

            {/* Mobile: compact grid with status-color dot indicators */}
            <div className="isolate grid w-full grid-cols-7 grid-rows-6 gap-px lg:hidden">
              {days.map((day) => (
                <div
                  key={day.date}
                  data-is-today={day.isToday ? '' : undefined}
                  data-is-current-month={day.isCurrentMonth ? '' : undefined}
                  className="group relative flex h-14 flex-col px-3 py-2 not-data-is-current-month:bg-gray-50 not-data-is-current-month:text-gray-500 data-is-current-month:bg-white data-is-current-month:text-gray-900 dark:not-data-is-current-month:bg-gray-900 dark:not-data-is-current-month:text-gray-400 dark:not-data-is-current-month:before:pointer-events-none dark:not-data-is-current-month:before:absolute dark:not-data-is-current-month:before:inset-0 dark:not-data-is-current-month:before:bg-gray-800/50 dark:data-is-current-month:bg-gray-900 dark:data-is-current-month:text-white"
                >
                  <time
                    dateTime={day.date}
                    className="ml-auto group-not-data-is-current-month:opacity-75 in-data-is-today:flex in-data-is-today:size-6 in-data-is-today:items-center in-data-is-today:justify-center in-data-is-today:rounded-full in-data-is-today:bg-indigo-600 in-data-is-today:font-semibold in-data-is-today:text-white dark:in-data-is-today:bg-indigo-500"
                  >
                    {day.dayNum}
                  </time>
                  <span className="sr-only">
                    {day.events.length} work orders
                  </span>
                  {day.events.length > 0 ? (
                    <span className="-mx-0.5 mt-auto flex flex-wrap-reverse">
                      {day.events.slice(0, 6).map((wo) => {
                        const tone = statusTone(wo.primary_status)
                        return (
                          <span
                            key={wo.id}
                            className={`mx-0.5 mb-1 size-1.5 rounded-full ${TONE_DOT[tone]}`}
                          />
                        )
                      })}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {unscheduled.length > 0 ? (
        <div className="rounded-lg ring-1 ring-gray-200 dark:ring-white/10">
          <div className="border-b border-gray-200 px-4 py-2 dark:border-white/10">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              Unscheduled ({unscheduled.length})
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              These WOs are assigned but have no scheduled date in SC.
            </p>
          </div>
          <ul className="divide-y divide-gray-200 dark:divide-white/10">
            {unscheduled.map((wo) => {
              const tone = statusTone(wo.primary_status)
              return (
                <li key={wo.id} className="px-4 py-2 text-sm">
                  <Link
                    href={`/work-orders/${wo.id}`}
                    className="flex items-center gap-2 text-gray-700 hover:text-indigo-600 dark:text-gray-300 dark:hover:text-indigo-400"
                  >
                    <span
                      className={`inline-block size-2 shrink-0 rounded-full ${TONE_DOT[tone]}`}
                    />
                    #{wo.sc_number} ·{' '}
                    <span className="text-gray-500 dark:text-gray-400">
                      {wo.primary_status}
                      {wo.extended_status ? ` / ${wo.extended_status}` : ''}
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

function Weekday({ short, rest }: { short: string; rest: string }) {
  return (
    <div className="flex justify-center bg-white py-2 dark:bg-gray-900">
      <span>{short}</span>
      <span className="sr-only sm:not-sr-only">{rest}</span>
    </div>
  )
}
