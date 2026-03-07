import { TrendingUp, TrendingDown } from 'lucide-react'

export default function MetricCard({ title, value, trend, trendType, isCritical, icon: Icon, colorVariant }) {
  const accentColorMap = {
    'card-cyan': '#22d3ee',
    'card-green': '#10b981',
    'card-rose': '#f43f5e',
    'card-amber': '#f59e0b'
  }
  const accentColor = colorVariant ? accentColorMap[colorVariant] : '#818cf8'

  return (
    <div
      className={`glass glass-hover p-6 flex flex-col justify-between metric-card ${colorVariant || ''}`}
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
          <div
            className="p-2 rounded-lg flex items-center justify-center"
            style={{ background: `linear-gradient(135deg, ${accentColor}15, transparent)` }}
          >
            <Icon size={18} style={{ color: accentColor }} />
          </div>
        )}
      </div>

      <div className="flex items-end justify-between">
        <span className="count-up metric-value">
          {value}
        </span>
        <div
          className="flex items-center gap-1 px-2 py-1 rounded-md hover-lift"
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
