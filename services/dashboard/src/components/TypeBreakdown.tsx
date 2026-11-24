import { DETECTION_TYPES, formatNumber, formatType } from '../lib/format'

/** Horizontal bars, one per detection class. All classes stay listed, so the layout doesn't jump. */
export function TypeBreakdown({ types }: { types: string[] }) {
  const counts = new Map(Object.keys(DETECTION_TYPES).map((t) => [t, 0]))
  for (const t of types) counts.set(t, (counts.get(t) ?? 0) + 1)
  const max = Math.max(1, ...counts.values())
  return (
    <ul className="type-bars">
      {[...counts].map(([type, count]) => (
        <li key={type}>
          <span className="type-name">{formatType(type)}</span>
          <span className="type-track">
            {count > 0 && <span className="type-bar" style={{ width: `${(count / max) * 100}%` }} />}
          </span>
          <span className="type-count">{formatNumber(count)}</span>
        </li>
      ))}
    </ul>
  )
}
