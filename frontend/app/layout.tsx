import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import AppShell from '@/components/AppShell'

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Brenk Operating Platform',
  description: 'Operations dashboard for Brenk Facility Services.',
}

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
      <body className="h-full">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
