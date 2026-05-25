/**
 * Storefront layout — used for the public marketing site at the
 * bare domain (rewritten from `/` to `/marketing/` by `proxy.ts`).
 *
 * Deliberately minimal. No AppShell, no auth check, no Supabase
 * client. Just renders children inside a body class that picks up
 * the marketing palette (light by default, blue accents driven by
 * Tailwind classes on individual components).
 *
 * The root layout (`app/layout.tsx`) still wraps everything in
 * `<html>` + `<body>` — this just nests inside that.
 */

export const metadata = {
  title: 'Brenk Facility Services',
  description:
    'Family-owned commercial facility maintenance serving Austin, San Antonio, and the I-35 corridor.',
}

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-white text-gray-900 antialiased">
      {children}
    </div>
  )
}
