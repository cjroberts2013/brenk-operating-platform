import LoginForm from './LoginForm'

export const metadata = {
  title: 'Sign in — Brenk',
}

// In Next.js 16, page-level searchParams is a Promise.
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>
}) {
  const { next } = await searchParams
  return <LoginForm next={next ?? '/'} />
}
