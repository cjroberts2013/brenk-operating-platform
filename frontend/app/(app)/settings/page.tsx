export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Settings
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          User and account settings.
        </p>
      </header>
      <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center dark:border-white/10">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Placeholder. Wires up after Supabase Auth lands.
        </p>
      </div>
    </div>
  )
}
