/** Placeholder for screens that come in later weeks (see Docs/ArchitectureDocument/dashboard). */
export function PlannedPage({ title, week, children }: { title: string; week: number; children: string }) {
  return (
    <>
      <div className="page-head">
        <h1>{title}</h1>
      </div>
      <section className="card">
        <p>{children}</p>
        <p className="muted small">Planned for week {week}.</p>
      </section>
    </>
  )
}
