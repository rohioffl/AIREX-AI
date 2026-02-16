/**
 * Pure formatting utilities. NO business logic here.
 * Date formatting and string helpers only.
 */

export function formatTimestamp(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function truncateId(id) {
  if (!id) return ''
  return id.length > 8 ? `${id.slice(0, 8)}...` : id
}

export function formatDuration(seconds) {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = (seconds % 60).toFixed(0)
  return `${m}m ${s}s`
}
