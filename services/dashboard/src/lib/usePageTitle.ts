import { useEffect } from 'react'

/** Every screen gets its own browser tab title, which screen readers also announce after navigation. */
export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · NetGuard`
  }, [title])
}
