import { useQuery } from '@tanstack/react-query'
import { getDetectionFlows, type DetectionDetails } from '../api/detections'
import { endpoint, formatConfidence, formatDateTime, formatNumber, formatTime } from '../lib/format'

function featureValue(value: unknown): string {
  if (typeof value === 'number') return formatNumber(value)
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

interface DetectionEvidenceProps {
  detection: Omit<DetectionDetails, 'last_ingested_at'>
  /** Shown right after "Detected at", for example the state of the alert. */
  extraRows?: [string, string][]
}

/** Why a detection was made (F09, F15): summary, explanation, feature values and the flows behind it. */
export function DetectionEvidence({ detection: d, extraRows = [] }: DetectionEvidenceProps) {
  const flows = useQuery({
    queryKey: ['detection-flows', d.detection_id],
    queryFn: () => getDetectionFlows(d.detection_id),
  })
  const summary: [string, string][] = [
    ['Detected at', formatDateTime(d.created_at)],
    ...extraRows,
    ['Method', d.method],
    ['Confidence', formatConfidence(d.confidence)],
    ['Source', d.src_ip ?? '-'],
    ['Destination', d.dst_ip ?? '-'],
    [
      'Time window',
      d.window_start && d.window_end
        ? `${d.window_size_s} s (${formatTime(d.window_start)} - ${formatTime(d.window_end)})`
        : '-',
    ],
  ]
  const features = Object.entries(d.features ?? {})

  return (
    <>
      <div className="grid-2">
        <section className="card">
          <h2>Summary</h2>
          <dl className="kv">
            {summary.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <div className="stack">
          <section className="card">
            <h2>Explanation</h2>
            <p className="explanation">{d.explanation ?? 'No explanation stored.'}</p>
          </section>
          <section className="card">
            <h2>Feature values</h2>
            {features.length === 0 && <p className="muted">No feature values stored.</p>}
            {features.length > 0 && (
              <table className="table">
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {features.map(([key, value]) => (
                    <tr key={key}>
                      <td className="mono">{key}</td>
                      <td>{featureValue(value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      </div>

      <section className="card section-gap">
        <h2>Contributing flows</h2>
        {flows.isError && <p className="error">Could not load the flows: {flows.error.message}</p>}
        {flows.data?.items.length === 0 && <p className="muted">No stored flows for this detection.</p>}
        {!!flows.data?.items.length && (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Start</th>
                    <th>Source</th>
                    <th>Destination</th>
                    <th>Protocol</th>
                    <th>Packets</th>
                    <th>Bytes</th>
                    <th>Flags</th>
                    <th>Trace ID</th>
                  </tr>
                </thead>
                <tbody>
                  {flows.data.items.map((f) => (
                    <tr key={`${f.flow_id}-${f.ts_start}`}>
                      <td>{formatDateTime(f.ts_start)}</td>
                      <td>{endpoint(f.src_ip, f.src_port)}</td>
                      <td>{endpoint(f.dst_ip, f.dst_port)}</td>
                      <td>{f.protocol ?? '-'}</td>
                      <td>{f.packets === null ? '-' : formatNumber(f.packets)}</td>
                      <td>{f.bytes === null ? '-' : formatNumber(f.bytes)}</td>
                      <td>{f.tcp_flags ?? '-'}</td>
                      <td className="mono">{f.trace_id ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small">
              A sample of the flows behind this detection. Follow one through the pipeline logs with: make trace
              ID=&lt;trace id&gt;
            </p>
          </>
        )}
      </section>
    </>
  )
}
