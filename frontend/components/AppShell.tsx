'use client'

/**
 * App shell — sidebar + header + main content slot.
 *
 * Adapted from the Tailwind UI "Dark sidebar with header" reference
 * (see docs/design/dashboard-shell.tsx for the original).
 *
 * The shell itself is a Client Component (uses state + Headless UI
 * interactivity). The signed-in user is fetched server-side in
 * app/layout.tsx and passed in as a prop, so the shell stays purely
 * presentational re: auth.
 */

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  Menu,
  MenuButton,
  MenuItem,
  MenuItems,
  TransitionChild,
} from '@headlessui/react'
import {
  Bars3Icon,
  BellIcon,
  BanknotesIcon,
  ChartPieIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  Cog6ToothIcon,
  GlobeAltIcon,
  HomeIcon,
  ClipboardDocumentListIcon,
  UsersIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { ChevronDownIcon } from '@heroicons/react/20/solid'

import { ContextualSearch } from './ContextualSearch'

type NavItem = {
  name: string
  href: string
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  /** Hidden from the sidebar in production builds. Used for surfaces
   * that aren't ready for Daryl yet (Storefront has no real content;
   * Reports is empty until markup data exists). The routes still
   * resolve directly by URL in any environment — this only controls
   * sidebar visibility. */
  devOnly?: boolean
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Work Orders', href: '/work-orders', icon: ClipboardDocumentListIcon },
  { name: 'Invoices', href: '/invoices', icon: BanknotesIcon },
  { name: 'Vendors', href: '/vendors', icon: UsersIcon },
  { name: 'Storefront', href: '/storefront', icon: GlobeAltIcon, devOnly: true },
  { name: 'Reports', href: '/reports', icon: ChartPieIcon, devOnly: true },
]

// process.env.NODE_ENV is inlined by Next at build time. On Vercel
// (production) devOnly items drop out; on `next dev` they stay.
const visibleNavigation: NavItem[] = navigation.filter(
  (item) => process.env.NODE_ENV !== 'production' || !item.devOnly,
)

export type ShellUser = {
  email: string
}

function classNames(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(' ')
}

function avatarInitial(email: string): string {
  return email.charAt(0).toUpperCase() || '?'
}

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(`${href}/`)
}

function SidebarContents({
  pathname,
  onNavigate,
  collapsed = false,
}: {
  pathname: string
  /** Called when a nav item is tapped. Used on mobile to close the drawer. */
  onNavigate?: () => void
  /** Icon-only rail mode (desktop). Labels hide; titles take over. */
  collapsed?: boolean
}) {
  return (
    <nav className="flex flex-1 flex-col">
      <ul role="list" className="flex flex-1 flex-col gap-y-7">
        <li>
          <ul role="list" className={classNames(!collapsed && '-mx-2', 'space-y-1')}>
            {visibleNavigation.map((item) => {
              const active = isActive(pathname, item.href)
              return (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    title={collapsed ? item.name : undefined}
                    aria-current={active ? 'page' : undefined}
                    className={classNames(
                      active
                        ? 'bg-white/5 text-white'
                        : 'text-gray-400 hover:bg-white/5 hover:text-white',
                      collapsed && 'justify-center',
                      'group flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold',
                    )}
                  >
                    <item.icon aria-hidden="true" className="size-6 shrink-0" />
                    {!collapsed && item.name}
                  </Link>
                </li>
              )
            })}
          </ul>
        </li>
        <li className="mt-auto">
          <Link
            href="/settings"
            onClick={onNavigate}
            title={collapsed ? 'Settings' : undefined}
            aria-current={isActive(pathname, '/settings') ? 'page' : undefined}
            className={classNames(
              isActive(pathname, '/settings')
                ? 'bg-white/5 text-white'
                : 'text-gray-400 hover:bg-white/5 hover:text-white',
              collapsed ? 'justify-center' : '-mx-2',
              'group flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold',
            )}
          >
            <Cog6ToothIcon aria-hidden="true" className="size-6 shrink-0" />
            {!collapsed && 'Settings'}
          </Link>
        </li>
      </ul>
    </nav>
  )
}

function LogoMark({ compact = false }: { compact?: boolean }) {
  // Placeholder until we have a real logo asset.
  return (
    <div className="flex items-center gap-x-2">
      <div className="flex size-8 items-center justify-center rounded-md bg-indigo-500 text-sm font-semibold text-white">
        B
      </div>
      {!compact && <span className="text-sm font-semibold text-white">Brenk</span>}
    </div>
  )
}

export default function AppShell({
  children,
  user,
  initialNavCollapsed = false,
}: {
  children: React.ReactNode
  user: ShellUser | null
  /** Server-read cookie value so the collapsed state renders correctly
   * on first paint (no flash / hydration mismatch). */
  initialNavCollapsed?: boolean
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [navCollapsed, setNavCollapsed] = useState(initialNavCollapsed)
  const pathname = usePathname()

  function toggleNavCollapsed() {
    const next = !navCollapsed
    setNavCollapsed(next)
    // Persisted as a cookie (not localStorage) so the server layout can
    // render the right width on the next request.
    document.cookie = `nav_collapsed=${next ? '1' : '0'}; path=/; max-age=31536000; samesite=lax`
  }

  return (
    <div>
      {/* Mobile sidebar (slide-over) */}
      <Dialog
        open={sidebarOpen}
        onClose={setSidebarOpen}
        className="relative z-50 lg:hidden"
      >
        <DialogBackdrop
          transition
          className="fixed inset-0 bg-gray-900/80 transition-opacity duration-300 ease-linear data-closed:opacity-0"
        />

        <div className="fixed inset-0 flex">
          <DialogPanel
            transition
            className="relative mr-16 flex w-full max-w-xs flex-1 transform transition duration-300 ease-in-out data-closed:-translate-x-full"
          >
            <TransitionChild>
              <div className="absolute top-0 left-full flex w-16 justify-center pt-5 duration-300 ease-in-out data-closed:opacity-0">
                <button
                  type="button"
                  onClick={() => setSidebarOpen(false)}
                  className="-m-2.5 p-2.5"
                >
                  <span className="sr-only">Close sidebar</span>
                  <XMarkIcon aria-hidden="true" className="size-6 text-white" />
                </button>
              </div>
            </TransitionChild>

            <div className="relative flex grow flex-col gap-y-5 overflow-y-auto bg-gray-900 px-6 pb-4 ring-1 ring-white/10 dark:before:pointer-events-none dark:before:absolute dark:before:inset-0 dark:before:bg-black/10">
              <div className="relative flex h-16 shrink-0 items-center">
                <LogoMark />
              </div>
              <div className="relative flex flex-1 flex-col">
                <SidebarContents
                  pathname={pathname}
                  onNavigate={() => setSidebarOpen(false)}
                />
              </div>
            </div>
          </DialogPanel>
        </div>
      </Dialog>

      {/* Static sidebar for desktop — collapsible to an icon rail. */}
      <div
        className={classNames(
          'hidden bg-gray-900 ring-1 ring-white/10 transition-[width] duration-200 lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:flex-col',
          navCollapsed ? 'lg:w-16' : 'lg:w-72',
        )}
      >
        <div
          className={classNames(
            'flex grow flex-col gap-y-5 overflow-y-auto bg-black/10 pb-4',
            navCollapsed ? 'px-2' : 'px-6',
          )}
        >
          <div
            className={classNames(
              'flex h-16 shrink-0 items-center',
              navCollapsed && 'justify-center',
            )}
          >
            <LogoMark compact={navCollapsed} />
          </div>
          <SidebarContents pathname={pathname} collapsed={navCollapsed} />
          <button
            type="button"
            onClick={toggleNavCollapsed}
            title={navCollapsed ? 'Expand navigation' : 'Collapse navigation'}
            className={classNames(
              'flex items-center gap-x-2 rounded-md p-2 text-xs font-medium text-gray-500 hover:bg-white/5 hover:text-white',
              navCollapsed ? 'justify-center' : '-mx-2',
            )}
          >
            {navCollapsed ? (
              <ChevronDoubleRightIcon aria-hidden="true" className="size-5 shrink-0" />
            ) : (
              <>
                <ChevronDoubleLeftIcon aria-hidden="true" className="size-5 shrink-0" />
                Collapse
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main column */}
      <div
        className={classNames(
          'transition-[padding] duration-200',
          navCollapsed ? 'lg:pl-16' : 'lg:pl-72',
        )}
      >
        <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 bg-white px-4 shadow-xs sm:gap-x-6 sm:px-6 lg:px-8 dark:border-white/10 dark:bg-gray-900">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="-m-2.5 p-2.5 text-gray-700 hover:text-gray-900 lg:hidden dark:text-gray-400 dark:hover:text-white"
          >
            <span className="sr-only">Open sidebar</span>
            <Bars3Icon aria-hidden="true" className="size-6" />
          </button>

          <div
            aria-hidden="true"
            className="h-6 w-px bg-gray-900/10 lg:hidden dark:bg-white/10"
          />

          <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
            <ContextualSearch />

            <div className="flex items-center gap-x-4 lg:gap-x-6">
              <button
                type="button"
                className="-m-2.5 p-2.5 text-gray-400 hover:text-gray-500 dark:text-gray-400 dark:hover:text-gray-300"
              >
                <span className="sr-only">View notifications</span>
                <BellIcon aria-hidden="true" className="size-6" />
              </button>

              <div
                aria-hidden="true"
                className="hidden lg:block lg:h-6 lg:w-px lg:bg-gray-900/10 dark:lg:bg-gray-100/10"
              />

              {/* User menu */}
              <Menu as="div" className="relative">
                <MenuButton className="relative flex items-center">
                  <span className="absolute -inset-1.5" />
                  <span className="sr-only">Open user menu</span>
                  <div className="flex size-8 items-center justify-center rounded-full bg-indigo-500 text-xs font-semibold text-white">
                    {user ? avatarInitial(user.email) : '?'}
                  </div>
                  <span className="hidden lg:flex lg:items-center">
                    <span
                      aria-hidden="true"
                      className="ml-4 text-sm/6 font-semibold text-gray-900 dark:text-white"
                    >
                      {user?.email ?? 'Not signed in'}
                    </span>
                    <ChevronDownIcon
                      aria-hidden="true"
                      className="ml-2 size-5 text-gray-400 dark:text-gray-500"
                    />
                  </span>
                </MenuButton>
                <MenuItems
                  transition
                  className="absolute right-0 z-10 mt-2.5 w-40 origin-top-right rounded-md bg-white py-2 shadow-lg outline outline-gray-900/5 transition data-closed:scale-95 data-closed:transform data-closed:opacity-0 data-enter:duration-100 data-enter:ease-out data-leave:duration-75 data-leave:ease-in dark:bg-gray-800 dark:shadow-none dark:-outline-offset-1 dark:outline-white/10"
                >
                  {user ? (
                    <>
                      <MenuItem>
                        <Link
                          href="/settings"
                          className="block px-3 py-1 text-sm/6 text-gray-900 data-focus:bg-gray-50 data-focus:outline-hidden dark:text-white dark:data-focus:bg-white/5"
                        >
                          Settings
                        </Link>
                      </MenuItem>
                      <MenuItem>
                        {/* Plain form posts to a Route Handler. Avoids
                            needing a separate client-side click handler
                            for sign-out. */}
                        <form action="/auth/sign-out" method="POST">
                          <button
                            type="submit"
                            className="block w-full px-3 py-1 text-left text-sm/6 text-gray-900 data-focus:bg-gray-50 data-focus:outline-hidden dark:text-white dark:data-focus:bg-white/5"
                          >
                            Sign out
                          </button>
                        </form>
                      </MenuItem>
                    </>
                  ) : (
                    <MenuItem>
                      <Link
                        href="/login"
                        className="block px-3 py-1 text-sm/6 text-gray-900 data-focus:bg-gray-50 data-focus:outline-hidden dark:text-white dark:data-focus:bg-white/5"
                      >
                        Sign in
                      </Link>
                    </MenuItem>
                  )}
                </MenuItems>
              </Menu>
            </div>
          </div>
        </div>

        <main className="py-10">
          <div className="px-4 sm:px-6 lg:px-8">{children}</div>
        </main>
      </div>
    </div>
  )
}
