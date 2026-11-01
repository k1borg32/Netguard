import { useMutation, useQueryClient } from '@tanstack/react-query'
import { acknowledgeAlert } from '../api/alerts'

/** Every alert query starts with 'alerts', so the list, the details and the open count all update at once. */
export function AcknowledgeButton({ alertId, primary = false }: { alertId: string; primary?: boolean }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => acknowledgeAlert(alertId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  })
  return (
    <>
      <button
        type="button"
        className={primary ? 'btn btn-primary' : 'btn btn-small'}
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? 'Saving...' : 'Acknowledge'}
      </button>
      {mutation.isError && (
        <span className="error small" role="alert">
          {' '}
          Could not acknowledge
        </span>
      )}
    </>
  )
}
