import { useSearchParams } from 'react-router'

/** Filters and page number live in the URL, so a view can be reloaded and shared. */
export function useUrlFilters() {
  const [params, setParams] = useSearchParams()

  /** Every filter change goes back to page 1. */
  function setFilter(name: string, value: string) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('page')
      if (value) next.set(name, value)
      else next.delete(name)
      return next
    })
  }

  function setPage(value: number) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set('page', String(value))
      return next
    })
  }

  return {
    get: (name: string) => params.get(name) ?? undefined,
    page: Math.max(1, Number(params.get('page')) || 1),
    setFilter,
    setPage,
    reset: () => setParams(new URLSearchParams()),
  }
}
