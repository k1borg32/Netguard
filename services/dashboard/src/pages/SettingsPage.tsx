import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { ApiError } from '../api/client'
import { getDetectionConfig, getDetectionConfigs, type Parameters } from '../api/detectionConfigs'
import { useAuth } from '../auth/context'
import { ConfigForm } from '../components/ConfigForm'
import { formatType } from '../lib/format'
import { toFields } from '../lib/parameters'

/** One line per configuration, in the same order as the form. */
function summary(parameters: Parameters): string {
  const parts = toFields(parameters).map((f) => `${f.name} ${f.value}`)
  return parts.length ? parts.join(' · ') : '-'
}

export function SettingsPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [params, setParams] = useSearchParams()
  const selected = params.get('config')
  const editingId = selected && selected !== 'new' ? selected : null

  // Settings change rarely: they load on open and with the Refresh button, no polling.
  const list = useQuery({ queryKey: ['detection-configs', 'list'], queryFn: () => getDetectionConfigs() })
  const detail = useQuery({
    queryKey: ['detection-configs', editingId],
    queryFn: () => getDetectionConfig(editingId ?? ''),
    enabled: !!editingId,
  })

  const close = () => setParams({})
  const notFound = detail.error instanceof ApiError && (detail.error.status === 404 || detail.error.status === 422)
  const items = list.data?.items ?? []

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="muted small">
            Detection configurations: thresholds and windows per detection type.
            {!isAdmin && ' Read-only: changes need the admin role.'}
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn" onClick={() => void list.refetch()}>
            Refresh
          </button>
          {isAdmin && (
            <button type="button" className="btn btn-primary" onClick={() => setParams({ config: 'new' })}>
              New configuration
            </button>
          )}
        </div>
      </div>

      <p className="notice small">
        The running detection engine reads its thresholds from <span className="mono">config/detection.yaml</span>{' '}
        when it starts. Configurations saved and activated here are stored in the database; the engine does not load
        them yet.
      </p>

      <section className="card section-gap">
        <h2>Detection configurations</h2>
        {list.isError && <p className="error">Could not load the configurations: {list.error.message}</p>}
        {list.isPending && <p className="muted">Loading...</p>}
        {list.data && items.length === 0 && <p className="muted">No configurations stored yet.</p>}
        {items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Method</th>
                  <th>Parameters</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.configuration_id} aria-current={c.configuration_id === selected ? 'true' : undefined}>
                    <td>{formatType(c.detection_type)}</td>
                    <td>{c.method}</td>
                    <td className="mono params-summary">{summary(c.parameters)}</td>
                    <td>
                      <span className={`status ${c.active ? 'status-active' : 'status-inactive'}`}>
                        {c.active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <Link
                        to={`?config=${c.configuration_id}`}
                        aria-label={`${isAdmin ? 'Edit' : 'View'} ${formatType(c.detection_type)}`}
                      >
                        {isAdmin ? 'Edit' : 'View'}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {list.data && list.data.total > items.length && (
          <p className="muted small">
            Showing the first {items.length} of {list.data.total} configurations.
          </p>
        )}
      </section>

      {selected === 'new' && isAdmin && (
        <ConfigForm key="new" canEdit onCreated={(id) => setParams({ config: id })} onClose={close} />
      )}
      {editingId && detail.isError && (
        <section className="card section-gap">
          <p className="error">
            {notFound ? 'Configuration not found.' : `Could not load the configuration: ${detail.error.message}`}
          </p>
          <button type="button" className="btn" onClick={close}>
            Close
          </button>
        </section>
      )}
      {editingId && detail.data && (
        <ConfigForm
          key={editingId}
          config={detail.data}
          canEdit={isAdmin}
          onCreated={(id) => setParams({ config: id })}
          onClose={close}
        />
      )}
    </>
  )
}
