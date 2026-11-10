import { formatNumber } from '../lib/format'

interface PagerProps {
  noun: string
  total: number
  page: number
  pageSize: number
  onPage: (page: number) => void
}

export function Pager({ noun, total, page, pageSize, onPage }: PagerProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="pager">
      <span className="muted small">
        {formatNumber(total)} {noun} · page {page} of {pages}
      </span>
      <span className="pager-buttons">
        <button type="button" className="btn btn-small" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <button type="button" className="btn btn-small" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </span>
    </div>
  )
}
