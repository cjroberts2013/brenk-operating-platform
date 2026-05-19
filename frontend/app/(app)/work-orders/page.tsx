export default function WorkOrdersPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Work Orders
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Filterable list of work orders, color-coded by status.
        </p>
      </header>
      <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center dark:border-white/10">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Placeholder. Wires up to <code>GET /api/v1/work-orders/</code> in
          the next step.
        </p>
      </div>
    </div>
  )
}
