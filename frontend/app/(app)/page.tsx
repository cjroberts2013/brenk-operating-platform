export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Needs-attention and today&apos;s schedule will live here.
        </p>
      </header>
      <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center dark:border-white/10">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Placeholder. The home view is built later — see the Dashboard Plan
          in CLAUDE.md.
        </p>
      </div>
    </div>
  )
}
