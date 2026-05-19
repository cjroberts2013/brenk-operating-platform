'use server'

import { redirect } from 'next/navigation'

import { createSupabaseServerClient } from '@/lib/supabase/server'

export type SignInState = { error: string | null }

export async function signInAction(
  _prev: SignInState,
  formData: FormData,
): Promise<SignInState> {
  const email = String(formData.get('email') ?? '').trim()
  const password = String(formData.get('password') ?? '')
  const next = String(formData.get('next') ?? '/') || '/'

  if (!email || !password) {
    return { error: 'Email and password are required.' }
  }

  const supabase = await createSupabaseServerClient()
  const { error } = await supabase.auth.signInWithPassword({ email, password })

  if (error) {
    return { error: error.message }
  }

  // Avoid open-redirect: only follow `next` if it's a same-origin path.
  const safeNext = next.startsWith('/') && !next.startsWith('//') ? next : '/'
  redirect(safeNext)
}
