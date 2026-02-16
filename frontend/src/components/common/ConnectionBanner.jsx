import { WifiOff, Loader, Wifi } from 'lucide-react'

/**
 * Displays a reconnecting/disconnected banner when SSE drops.
 * Placed at the top of the main content area.
 */
export default function ConnectionBanner({ connected, reconnecting }) {
  if (connected) return null

  return (
    <div
      style={{
        background: reconnecting
          ? 'linear-gradient(90deg, rgba(245,158,11,0.12), rgba(245,158,11,0.06))'
          : 'linear-gradient(90deg, rgba(244,63,94,0.12), rgba(244,63,94,0.06))',
        border: `1px solid ${reconnecting ? 'rgba(245,158,11,0.3)' : 'rgba(244,63,94,0.3)'}`,
        borderRadius: 8,
        padding: '10px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 16,
        fontSize: 13,
        color: reconnecting ? '#f59e0b' : '#f43f5e',
        fontWeight: 500,
      }}
    >
      {reconnecting ? (
        <Loader size={16} style={{ animation: 'spin 1s linear infinite' }} />
      ) : (
        <WifiOff size={16} />
      )}
      <span>
        {reconnecting
          ? 'Connection lost — reconnecting to live feed...'
          : 'Disconnected from live feed. Updates may be delayed.'}
      </span>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
