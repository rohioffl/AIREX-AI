import { WifiOff, Loader } from 'lucide-react'

/**
 * Displays connection status: connecting (initial), reconnecting, or disconnected.
 * Only shows "Disconnected" after we had a connection and then closed (e.g. left page).
 * Avoids flashing "Disconnected" on initial load.
 */
export default function ConnectionBanner({ connected, reconnecting, initial }) {
  if (connected) return null
  if (initial) {
    return (
      <div
        style={{
          background: 'rgba(99,102,241,0.08)',
          border: '1px solid rgba(99,102,241,0.2)',
          borderRadius: 8,
          padding: '8px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 16,
          fontSize: 12,
          color: '#818cf8',
          fontWeight: 500,
        }}
      >
        <Loader size={14} style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />
        <span>Connecting to live feed...</span>
        <style>{`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    )
  }

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
          ? 'Connection lost — reconnecting...'
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
