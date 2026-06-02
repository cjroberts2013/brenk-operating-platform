import { Archivo, IBM_Plex_Mono, IBM_Plex_Sans } from 'next/font/google'

/**
 * Storefront layout — used for the public marketing site at the
 * bare domain (rewritten from `/` to `/marketing/` by `proxy.ts`).
 *
 * Loads the three brand families via `next/font/google` and exposes
 * them as CSS variables on a `.marketing` wrapper. Scoping the font
 * className to this layout (not the root) means dashboard pages
 * keep their Inter setup and don't ship the marketing typefaces.
 *
 * Token rationale lives in the 2026-05-28 hi-fi design handoff —
 * Archivo for display, IBM Plex Sans for body/UI, IBM Plex Mono
 * for eyebrows + captions + stat labels.
 */

// Variable-weight Archivo covers all the display weights we need
// (700/800) in a single subset, so no need to enumerate weights.
const archivo = Archivo({
  variable: '--font-archivo',
  subsets: ['latin'],
  display: 'swap',
})

// IBM Plex Sans isn't a variable font on Google Fonts; we need an
// explicit weight list. 400 = body, 500 = nav links + minor UI,
// 600 = buttons + emphasis.
const plexSans = IBM_Plex_Sans({
  variable: '--font-plex-sans',
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'swap',
})

// Plex Mono — used only for small uppercased labels (eyebrows,
// stat captions, button kickers). 400 / 500 cover both weights
// the design uses.
const plexMono = IBM_Plex_Mono({
  variable: '--font-plex-mono',
  subsets: ['latin'],
  weight: ['400', '500'],
  display: 'swap',
})

export const metadata = {
  title: 'Brenk Facility Services | Commercial Facility Maintenance',
  description:
    'One partner for every system in your building. HVAC, electrical, plumbing, doors, grounds, and full build-outs, serving commercial facilities across the I-35 corridor since 1989.',
}

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div
      className={`${archivo.variable} ${plexSans.variable} ${plexMono.variable} marketing min-h-screen bg-white text-ink antialiased`}
      style={{ scrollBehavior: 'smooth' }}
    >
      {children}
    </div>
  )
}
