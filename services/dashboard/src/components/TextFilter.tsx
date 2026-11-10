interface TextFilterProps {
  label: string
  value: string | undefined
  onApply: (value: string) => void
  placeholder?: string
  type?: 'text' | 'datetime-local'
}

/** Applied on Enter or when leaving the field, not on every key, so half an address is never sent. */
export function TextFilter({ label, value, onApply, placeholder, type = 'text' }: TextFilterProps) {
  return (
    <label>
      {label}
      <input
        key={value ?? ''}
        type={type}
        defaultValue={value ?? ''}
        placeholder={placeholder}
        onBlur={(e) => onApply(e.target.value.trim())}
        onKeyDown={(e) => e.key === 'Enter' && onApply(e.currentTarget.value.trim())}
      />
    </label>
  )
}
