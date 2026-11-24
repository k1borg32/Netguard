import { describeError } from '../lib/errors'
import { formatTime } from '../lib/format'

/** Shown until the first answer arrives; role="status" lets screen readers announce it. */
export function Loading({ what }: { what: string }) {
  return (
    <p className="muted" role="status">
      Loading {what}...
    </p>
  )
}

interface LoadErrorProps {
  /** What failed to load, e.g. "alerts". */
  what: string
  error: Error
  /** When the data still on screen was fetched (dataUpdatedAt); 0 or missing if there is none. */
  updatedAt?: number
}

/**
 * A failed request. If older data is still on screen (a live page whose refresh failed), it says how old that data
 * is instead of hiding it.
 */
export function LoadError({ what, error, updatedAt }: LoadErrorProps) {
  if (updatedAt) {
    return (
      <p className="notice notice-warn small" role="status">
        Showing {what} from {formatTime(updatedAt)}: the last refresh failed. {describeError(error)}
      </p>
    )
  }
  return (
    <p className="error" role="alert">
      Could not load {what}. {describeError(error)}
    </p>
  )
}
