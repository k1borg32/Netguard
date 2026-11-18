import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import {
  activateDetectionConfig,
  createDetectionConfig,
  METHODS,
  updateDetectionConfig,
  type DetectionConfig,
} from '../api/detectionConfigs'
import { DETECTION_TYPES, formatType } from '../lib/format'
import {
  fromFields,
  guessKind,
  sameParameters,
  toFields,
  validationMessages,
  WINDOW_SIZES,
  type ParameterField,
} from '../lib/parameters'

interface ConfigFormProps {
  /** The stored configuration, or undefined for a new one. */
  config?: DetectionConfig
  canEdit: boolean
  onCreated: (id: string) => void
  onClose: () => void
}

function errorLines(error: Error): string[] {
  if (error instanceof ApiError) {
    if (error.status === 403) return ['Only administrators can change detection settings.']
    if (error.status === 422) return validationMessages(error.detail)
  }
  return [error.message]
}

export function ConfigForm({ config, canEdit, onCreated, onClose }: ConfigFormProps) {
  const queryClient = useQueryClient()
  const isNew = !config
  const [type, setType] = useState('port_scan')
  const [method, setMethod] = useState<string>('rule')
  const [fields, setFields] = useState<ParameterField[]>(() => (config ? toFields(config.parameters) : []))
  const [fieldErrors, setFieldErrors] = useState<Record<number, string>>({})
  const [newName, setNewName] = useState('')
  const [newValue, setNewValue] = useState('')
  const [addError, setAddError] = useState('')
  const [saved, setSaved] = useState(false)

  const stored = (result: DetectionConfig) => {
    queryClient.setQueryData(['detection-configs', result.configuration_id], result)
    return queryClient.invalidateQueries({ queryKey: ['detection-configs', 'list'] })
  }
  const save = useMutation({
    mutationFn: (parameters: DetectionConfig['parameters']) =>
      config
        ? updateDetectionConfig(config.configuration_id, parameters)
        : createDetectionConfig({ detection_type: type, method, parameters }),
    onSuccess: async (result) => {
      await stored(result)
      setSaved(true)
      if (isNew) onCreated(result.configuration_id)
    },
  })
  const activate = useMutation({
    mutationFn: () => activateDetectionConfig(config?.configuration_id ?? ''),
    onSuccess: stored,
  })

  const dirty = config ? !sameParameters(fields, config.parameters) : true
  const busy = save.isPending || activate.isPending

  const change = (i: number, value: string) => {
    setFields((all) => all.map((f, j) => (j === i ? { ...f, value } : f)))
    setSaved(false)
  }
  const remove = (i: number) => {
    setFields((all) => all.filter((_, j) => j !== i))
    setFieldErrors({})
    setSaved(false)
  }
  const add = () => {
    const name = newName.trim()
    if (!name) return setAddError('Enter a name.')
    if (fields.some((f) => f.name === name)) return setAddError(`${name} is already in the list.`)
    setFields((all) => [...all, { name, kind: guessKind(newValue), value: newValue.trim() }])
    setNewName('')
    setNewValue('')
    setAddError('')
    setSaved(false)
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const result = fromFields(fields)
    if (!result.ok) {
      setFieldErrors(result.errors)
      return
    }
    setFieldErrors({})
    save.mutate(result.parameters)
  }

  const title = config ? `${formatType(config.detection_type)} (${config.method})` : 'New configuration'

  return (
    <form className="card section-gap" onSubmit={submit} aria-label={title} noValidate>
      <div className="page-head">
        <h2>{title}</h2>
        {config && (
          <span className={`status ${config.active ? 'status-active' : 'status-inactive'}`}>
            {config.active ? 'Active' : 'Inactive'}
          </span>
        )}
      </div>

      {isNew && (
        <div className="filters">
          <label>
            Type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {Object.entries(DETECTION_TYPES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Method
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      <h3 className="form-subhead">Parameters</h3>
      {fields.length === 0 && <p className="muted">No parameters yet.</p>}
      <div className="params">
        {fields.map((field, i) => (
          <div className="param" key={field.name}>
            <ParameterInput field={field} disabled={!canEdit || busy} onChange={(v) => change(i, v)} />
            {canEdit && (
              <button
                type="button"
                className="btn btn-small"
                aria-label={`Remove ${field.name}`}
                disabled={busy}
                onClick={() => remove(i)}
              >
                Remove
              </button>
            )}
            {fieldErrors[i] && (
              <p className="error small param-error" role="alert">
                {fieldErrors[i]}
              </p>
            )}
          </div>
        ))}
      </div>

      {canEdit && (
        <div className="filters add-param">
          <label>
            New parameter
            <input value={newName} placeholder="name" onChange={(e) => setNewName(e.target.value)} />
          </label>
          <label>
            Value
            <input value={newValue} placeholder="e.g. 100" onChange={(e) => setNewValue(e.target.value)} />
          </label>
          <button type="button" className="btn" onClick={add}>
            Add
          </button>
          {addError && (
            <span className="error small" role="alert">
              {addError}
            </span>
          )}
        </div>
      )}

      {save.isError && (
        <div className="error small" role="alert">
          <p>Could not save:</p>
          <ul>
            {errorLines(save.error).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      {activate.isError && (
        <p className="error small" role="alert">
          Could not activate: {errorLines(activate.error).join(' ')}
        </p>
      )}
      {saved && !dirty && <p className="notice small">Saved.</p>}

      {canEdit ? (
        <div className="page-actions">
          <button type="submit" className="btn btn-primary" disabled={busy || (!isNew && !dirty)}>
            {save.isPending ? 'Saving...' : isNew ? 'Create' : 'Save'}
          </button>
          {config && !config.active && (
            <button
              type="button"
              className="btn"
              disabled={busy || dirty}
              title={dirty ? 'Save the changes first' : undefined}
              onClick={() => activate.mutate()}
            >
              {activate.isPending ? 'Activating...' : 'Activate'}
            </button>
          )}
          <button type="button" className="btn" onClick={onClose}>
            {isNew || dirty ? 'Cancel' : 'Close'}
          </button>
        </div>
      ) : (
        <>
          <p className="muted small">Only administrators can change detection settings.</p>
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </>
      )}
    </form>
  )
}

function ParameterInput({
  field,
  disabled,
  onChange,
}: {
  field: ParameterField
  disabled: boolean
  onChange: (value: string) => void
}) {
  const id = useId()
  if (field.kind === 'boolean') {
    return (
      <label className="param-check">
        <input
          type="checkbox"
          checked={field.value === 'true'}
          disabled={disabled}
          onChange={(e) => onChange(String(e.target.checked))}
        />
        <span className="mono">{field.name}</span>
      </label>
    )
  }
  return (
    <div className="param-field">
      <label htmlFor={id} className="mono">
        {field.name}
      </label>
      {field.name === 'window_s' && field.kind === 'integer' ? (
        <select id={id} value={field.value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          {windowSizes(field.value).map((s) => (
            <option key={s} value={String(s)}>
              {s} s
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          type={field.kind === 'integer' || field.kind === 'number' ? 'number' : 'text'}
          step={field.kind === 'integer' ? 1 : 'any'}
          className={field.kind === 'json' ? 'mono' : undefined}
          value={field.value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  )
}

/** The engine's window sizes, plus the stored value if it is something else, so it is not silently changed. */
function windowSizes(current: string): number[] {
  const sizes: number[] = [...WINDOW_SIZES]
  return sizes.includes(Number(current)) ? sizes : [...sizes, Number(current)]
}
