import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Brenk Operating Platform',
  description: 'Operations dashboard for Brenk Facility Services.',
}

/**
 * Root layout — html + body only.
 *
 * The signed-in app shell (sidebar, header) lives in
 * `app/(app)/layout.tsx`. Public pages like `/login` get just this
 * root, so they render without the dashboard chrome around them.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} h-full bg-white antialiased dark:bg-gray-900`}
    >
      <body className="h-full">{children}</body>
    </html>
  )
}
