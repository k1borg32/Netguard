// Turns the free-form JSON parameters of a detection configuration into form fields and back.
// Numbers get number fields, true/false a checkbox, text a text field, and lists or objects a JSON field.

import type { ParameterValue, Parameters } from '../api/detectionConfigs'

export type FieldKind = 'integer' | 'number' | 'boolean' | 'text' | 'json'

export interface ParameterField {
  name: string
  kind: FieldKind
  /** What the input shows: the number or text as typed, or 'true'/'false' for a checkbox. */
  value: string
}

// The engine only has 1, 10 and 60 s windows (F05, config/detection.yaml windows_s).
export const WINDOW_SIZES = [1, 10, 60] as const

// The database (JSONB) does not keep the key order, so window_s is put first, where people look for it.
export function toFields(parameters: Parameters): ParameterField[] {
  const entries = Object.entries(parameters).sort(([a], [b]) => Number(b === 'window_s') - Number(a === 'window_s'))
  return entries.map(([name, value]): ParameterField => {
    if (typeof value === 'number') return { name, kind: Number.isInteger(value) ? 'integer' : 'number', value: String(value) }
    if (typeof value === 'boolean') return { name, kind: 'boolean', value: String(value) }
    if (typeof value === 'string') return { name, kind: 'text', value }
    return { name, kind: 'json', value: JSON.stringify(value) }
  })
}

/** The kind of a parameter added in the form: the value typed decides it, so "100" becomes a number. */
export function guessKind(value: string): FieldKind {
  const v = value.trim()
  if (v === 'true' || v === 'false') return 'boolean'
  if (v !== '' && Number.isFinite(Number(v))) return Number.isInteger(Number(v)) ? 'integer' : 'number'
  if (v.startsWith('[') || v.startsWith('{')) return 'json'
  return 'text'
}

/** Errors are keyed by the field's position in the list. */
export type ParseResult = { ok: true; parameters: Parameters } | { ok: false; errors: Record<number, string> }

export function fromFields(fields: ParameterField[]): ParseResult {
  const parameters: Parameters = {}
  const errors: Record<number, string> = {}
  const seen = new Set<string>()
  fields.forEach((field, i) => {
    const name = field.name.trim()
    if (!name) {
      errors[i] = 'A parameter needs a name.'
      return
    }
    if (seen.has(name)) {
      errors[i] = 'This name is used twice.'
      return
    }
    seen.add(name)
    const result = parseValue(field)
    if (typeof result === 'string') errors[i] = result
    else parameters[name] = result.value
  })
  return Object.keys(errors).length ? { ok: false, errors } : { ok: true, parameters }
}

/** True when the form holds exactly the stored parameters, whatever the key order. */
export function sameParameters(fields: ParameterField[], stored: Parameters): boolean {
  const result = fromFields(fields)
  return result.ok && canonical(result.parameters) === canonical(stored)
}

function canonical(value: ParameterValue): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value && typeof value === 'object') {
    const keys = Object.keys(value).sort()
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function parseValue(field: ParameterField): { value: ParameterValue } | string {
  const raw = field.value.trim()
  switch (field.kind) {
    case 'integer':
    case 'number': {
      const n = Number(raw)
      if (raw === '' || !Number.isFinite(n)) return 'Enter a number.'
      if (field.kind === 'integer' && !Number.isInteger(n)) return 'Enter a whole number.'
      return { value: n }
    }
    case 'boolean':
      return { value: raw === 'true' }
    case 'text':
      return { value: field.value }
    case 'json':
      try {
        return { value: JSON.parse(raw) as ParameterValue }
      } catch {
        return 'Enter valid JSON, for example [22, 3389].'
      }
  }
}

interface ValidationIssue {
  loc?: (string | number)[]
  msg?: string
}

/** The API's 422 detail is a list of {loc, msg}; this makes each one a readable line. */
export function validationMessages(detail: unknown): string[] {
  if (typeof detail === 'string') return [detail]
  if (!Array.isArray(detail)) return []
  return (detail as ValidationIssue[]).map((issue) => {
    const where = (issue.loc ?? []).filter((part) => part !== 'body').join('.')
    return where ? `${where}: ${issue.msg ?? 'invalid value'}` : (issue.msg ?? 'Invalid value')
  })
}
