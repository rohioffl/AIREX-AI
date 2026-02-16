import { TrendingUp, TrendingDown } from 'lucide-react'

export default function MetricCard({ title, value, trend, trendType, isCritical, icon: Icon }) {
  return (
    <div
      className="glass glass-hover p-5 flex flex-col justify-between"
      style={isCritical ? { borderColor: 'rgba(244, 63, 94, 0.3)', boxShadow: '0 0 20px rgba(244, 63, 94, 0.08)' } : {}}
    >
      <div className="flex items-center justify-between mb-3">
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {title}
        </span>
        {isCritical && (
          <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#f43f5e', boxShadow: '0 0 8px #f43f5e' }} />
        )}
        {Icon && !isCritical && (
          <Icon size={16} style={{ color: 'var(--text-muted)' }} />
        )}
      </div>

      <div className="flex items-end justify-between">
        <span style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', letterSpacing: '-0.02em' }}>
          {value}
        </span>
        <div
          className="flex items-center gap-1 px-2 py-1 rounded-md"
          style={{
            fontSize: 11,
            fontWeight: 600,
            background: 'var(--bg-input)',
            border: '1px solid var(--border)',
            color: trendType === 'positive' ? '#10b981' : trendType === 'negative' ? '#f43f5e' : 'var(--text-secondary)',
          }}
        >
          {trendType === 'positive' && <TrendingUp size={12} />}
          {trendType === 'negative' && <TrendingDown size={12} />}
          <span>{trend}</span>
        </div>
      </div>
    </div>
  )
}
