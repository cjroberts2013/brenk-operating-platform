import AppShell, { type ShellUser } from '@/components/AppShell'
import { createSupabaseServerClient } from '@/lib/supabase/server'

/**
 * Authenticated app layout — wraps every signed-in route in the
 * dashboard chrome (sidebar + header). The auth middleware
 * (`middleware.ts`) guarantees that anyone reaching a path under this
 * route group is signed in, so `user` should never be null here in
 * practice — but we render gracefully if it is.
 */
async function getShellUser(): Promise<ShellUser | null> {
  const supabase = await createSupabaseServerClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()
  if (!user?.email) return null
  return { email: user.email }
}

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getShellUser()
  return <AppShell user={user}>{children}</AppShell>
}
