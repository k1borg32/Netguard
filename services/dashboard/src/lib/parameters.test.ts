import { describe, expect, it } from 'vitest'
import { fromFields, guessKind, sameParameters, toFields, validationMessages } from './parameters'

describe('toFields / fromFields', () => {
  const parameters = { window_s: 60, zscore_threshold: 3.5, services: [22, 3389], enabled: true, note: 'x' }

  it('gives every JSON type its own kind of field', () => {
    expect(toFields(parameters).map((f) => [f.name, f.kind, f.value])).toEqual([
      ['window_s', 'integer', '60'],
      ['zscore_threshold', 'number', '3.5'],
      ['services', 'json', '[22,3389]'],
      ['enabled', 'boolean', 'true'],
      ['note', 'text', 'x'],
    ])
  })

  it('turns unchanged fields back into the same parameters', () => {
    expect(fromFields(toFields(parameters))).toEqual({ ok: true, parameters })
  })

  it('rejects empty, non-numeric and fractional values where a whole number is needed', () => {
    const fields = toFields({ a: 1, b: 2, c: 3, d: 0.5 })
    fields[0].value = ''
    fields[1].value = 'ten'
    fields[2].value = '2.5'
    fields[3].value = '0.75'
    expect(fromFields(fields)).toEqual({
      ok: false,
      errors: { 0: 'Enter a number.', 1: 'Enter a number.', 2: 'Enter a whole number.' },
    })
  })

  it('rejects broken JSON and names used twice', () => {
    const fields = [
      { name: 'services', kind: 'json' as const, value: '[22, ' },
      { name: 'a', kind: 'integer' as const, value: '1' },
      { name: 'a', kind: 'integer' as const, value: '2' },
    ]
    const result = fromFields(fields)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors[0]).toMatch(/valid JSON/)
      expect(result.errors[2]).toBe('This name is used twice.')
    }
  })
})

describe('sameParameters', () => {
  it('ignores the key order, because the database does not keep it', () => {
    const fields = toFields({ window_s: 60, attempts: 50, services: [22, 21] })
    expect(sameParameters(fields, { services: [22, 21], attempts: 50, window_s: 60 })).toBe(true)
    expect(fields[0].name).toBe('window_s')
  })

  it('sees a changed, added or removed value', () => {
    const fields = toFields({ window_s: 60, attempts: 50 })
    expect(sameParameters(fields, { window_s: 60, attempts: 40 })).toBe(false)
    expect(sameParameters(fields, { window_s: 60 })).toBe(false)
    expect(sameParameters(fields.slice(1), { window_s: 60, attempts: 50 })).toBe(false)
    expect(sameParameters(toFields({ services: [22, 21] }), { services: [21, 22] })).toBe(false)
  })
})

describe('guessKind', () => {
  it('reads the kind of an added parameter from its value', () => {
    expect(guessKind('100')).toBe('integer')
    expect(guessKind('2.5')).toBe('number')
    expect(guessKind('false')).toBe('boolean')
    expect(guessKind('[22, 80]')).toBe('json')
    expect(guessKind('zscore')).toBe('text')
    expect(guessKind('')).toBe('text')
  })
})

describe('validationMessages', () => {
  it('makes one line per FastAPI validation error, without the "body" prefix', () => {
    const detail = [{ loc: ['body', 'parameters', 'x'], msg: 'Text must not contain null characters' }]
    expect(validationMessages(detail)).toEqual(['parameters.x: Text must not contain null characters'])
    expect(validationMessages('Detection configuration not found')).toEqual(['Detection configuration not found'])
    expect(validationMessages(null)).toEqual([])
  })
})
