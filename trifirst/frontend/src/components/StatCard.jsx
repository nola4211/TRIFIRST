export default function StatCard({ title, value, subtitle, loading }) {
  return (
    <div className="rounded-xl bg-dark-800 p-4 shadow-md">
      <p className="text-sm text-gray-300">{title}</p>
      <p className="mt-2 text-3xl font-bold text-primary">{loading ? '...' : value}</p>
      {subtitle ? <p className="mt-1 text-xs text-gray-400">{subtitle}</p> : null}
    </div>
  )
}
