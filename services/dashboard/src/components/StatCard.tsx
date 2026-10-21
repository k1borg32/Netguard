export function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <section className="card stat">
      <h2 className="stat-label">{label}</h2>
      <p className="stat-value">{value}</p>
      {hint && <p className="muted small">{hint}</p>}
    </section>
  )
}
