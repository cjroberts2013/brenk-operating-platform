'use client'

import { useActionState } from 'react'

import { signInAction, type SignInState } from './actions'

const initialState: SignInState = { error: null }

export default function LoginForm({ next }: { next: string }) {
  const [state, formAction, pending] = useActionState(signInAction, initialState)

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center">
          <div className="mx-auto flex size-12 items-center justify-center rounded-md bg-indigo-500 text-lg font-semibold text-white">
            B
          </div>
          <h1 className="mt-6 text-2xl font-semibold tracking-tight text-gray-900 dark:text-white">
            Sign in to Brenk
          </h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Use the Supabase account your admin created for you.
          </p>
        </div>

        <form action={formAction} className="space-y-4">
          <input type="hidden" name="next" value={next} />

          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-gray-700 dark:text-gray-200"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-xs outline-none placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 sm:text-sm dark:border-white/10 dark:bg-gray-800 dark:text-white"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700 dark:text-gray-200"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-xs outline-none placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 sm:text-sm dark:border-white/10 dark:bg-gray-800 dark:text-white"
            />
          </div>

          {state.error ? (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {state.error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={pending}
            className="flex w-full justify-center rounded-md bg-indigo-500 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 disabled:opacity-60"
          >
            {pending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
