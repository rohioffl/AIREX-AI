import { TrendingUp, TrendingDown } from 'lucide-react'

export default function MetricCard({ title, value, trend, trendType, isCritical, icon: Icon }) {
  return (
    <div
      className="glass glass-hover p-6 flex flex-col justify-between"
      style={isCritical ? { borderColor: 'rgba(249, 115, 22, 0.4)', boxShadow: '0 10px 30px rgba(249, 115, 22, 0.15)' } : {}}
    >
      <div className="flex items-center justify-between mb-4">
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {title}
        </span>
        {isCritical && (
          <span className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: '#f97316', boxShadow: '0 0 10px #f97316' }} />
        )}
        {Icon && !isCritical && (
          <Icon size={18} style={{ color: 'var(--text-muted)' }} />
        )}
      </div>

      <div className="flex items-end justify-between">
        <span style={{ fontSize: 38, fontWeight: 800, color: 'var(--text-heading)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.03em', lineHeight: 1 }}>
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
