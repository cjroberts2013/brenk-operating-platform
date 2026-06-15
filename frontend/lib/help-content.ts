/**
 * Contextual help shown in the "?" side panel, keyed by the page you're on.
 * Mirrors the printed user guide (docs/daryl-user-guide*.md) — keep the two
 * in sync when either changes. Plain, non-technical language for Daryl.
 */

export type HelpSection = { heading?: string; items: string[] }
export type HelpEntry = { title: string; intro: string; sections: HelpSection[] }

type Rule = { test: (pathname: string) => boolean; entry: HelpEntry }

const RULES: Rule[] = [
  {
    test: (p) => p === '/',
    entry: {
      title: 'Dashboard',
      intro: 'Your morning overview of where the money and the work stand.',
      sections: [
        {
          items: [
            'Money tiles: unbilled work, awaiting payment, and paid this month.',
            'The pipeline shows every job by stage, plus what’s stuck.',
            'Click any tile or stage to jump to those work orders.',
          ],
        },
      ],
    },
  },
  {
    test: (p) => p.startsWith('/work-orders'),
    entry: {
      title: 'Work Orders',
      intro: 'Every job from ServiceChannel, with your own tracking on top.',
      sections: [
        {
          heading: 'In the list',
          items: ['Filter and search the list. “Unassigned” shows in red.'],
        },
        {
          heading: 'Inside a work order',
          items: [
            'Assign a sub-vendor, then Mark notified once you’ve reached out.',
            'Markup helper: enter the vendor’s cost and your markup, or just type the total bill. It warns if you go over the NTE.',
            'When the price is set, invoice in ServiceChannel, then Mark paid once the client pays.',
          ],
        },
      ],
    },
  },
  {
    test: (p) => p.startsWith('/invoices'),
    entry: {
      title: 'Invoices',
      intro: 'Real invoices in ServiceChannel, plus jobs still waiting to be priced.',
      sections: [
        {
          heading: 'Invoices',
          items: [
            'Tabs: Awaiting payment (the default), Paid, Rejected, All.',
            'Search by invoice #, work order #, or location.',
            'Statuses update themselves: Sent → Approved → Paid.',
          ],
        },
        {
          heading: 'Work orders to invoice',
          items: ['Completed jobs that still need pricing, then invoicing in ServiceChannel.'],
        },
      ],
    },
  },
  {
    test: (p) => p.startsWith('/vendors'),
    entry: {
      title: 'Vendors',
      intro: 'Your sub-vendor roster and everything you track about them.',
      sections: [
        {
          items: [
            'Add or edit a vendor: contact info, preferred contact method, payment terms, trades, and notes.',
            'Open a vendor to see their current jobs and a schedule calendar.',
            'Sync from ServiceChannel pulls vendor info in from SC.',
          ],
        },
      ],
    },
  },
  {
    test: (p) => p.startsWith('/settings'),
    entry: {
      title: 'Settings',
      intro: 'Your default markup % per trade.',
      sections: [
        {
          items: [
            'Set a default markup % for each trade (e.g., doors 85%, plumbing 70%).',
            'It appears as a suggestion in the Markup helper — never applied automatically. You always decide.',
          ],
        },
      ],
    },
  },
]

const FALLBACK: HelpEntry = {
  title: 'Getting around',
  intro: 'Use the left menu to move between areas.',
  sections: [
    {
      items: [
        'Dashboard — your overview of money and work.',
        'Work Orders — every job, plus vendor and pricing tracking.',
        'Invoices — real SC invoices and jobs still to be priced.',
        'Vendors — your sub-vendor roster and schedules.',
        'Settings — your default markup % per trade.',
      ],
    },
  ],
}

export function helpForPath(pathname: string): HelpEntry {
  return RULES.find((r) => r.test(pathname))?.entry ?? FALLBACK
}
