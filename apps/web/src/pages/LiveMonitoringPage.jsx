import { useNavigate } from 'react-router-dom'
import {
  HeartPulse, ChevronRight, Clock,
  BarChart2, Bell, Activity, Layers,
} from 'lucide-react'

const PLUGINS = [
  {
    id: 'site24x7',
    name: 'Site24x7',
    description: 'Monitor service health, uptime, and proactive alerts via Site24x7 synthetic & infrastructure monitors.',
    icon: HeartPulse,
    iconColor: 'var(--neon-indigo)',
    iconBg: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(34,211,238,0.1))',
    iconBorder: 'rgba(99,102,241,0.25)',
    status: 'connected',
    href: '/health-checks/site24x7',
    tags: ['Uptime', 'Synthetic', 'Infrastructure'],
  },
  {
    id: 'prometheus',
    name: 'Prometheus & Grafana',
    description: 'Pull metrics from Prometheus and surface Grafana dashboard alerts and anomaly annotations.',
    icon: BarChart2,
    iconColor: 'var(--brand-orange)',
    iconBg: 'linear-gradient(135deg, rgba(249,115,22,0.2), rgba(251,191,36,0.1))',
    iconBorder: 'rgba(249,115,22,0.25)',
    status: 'coming_soon',
    href: null,
    tags: ['Metrics', 'Dashboards', 'Alerting'],
  },
  {
    id: 'datadog',
    name: 'Datadog',
    description: 'Ingest Datadog monitor events, APM traces, and log-based alerts into the AIREX incident pipeline.',
    icon: Activity,
    iconColor: 'var(--neon-purple)',
    iconBg: 'linear-gradient(135deg, rgba(168,85,247,0.2), rgba(236,72,153,0.1))',
    iconBorder: 'rgba(168,85,247,0.25)',
    status: 'coming_soon',
    href: null,
    tags: ['APM', 'Logs', 'Infrastructure'],
  },
  {
    id: 'pagerduty',
    name: 'PagerDuty',
    description: 'Sync PagerDuty incidents and on-call schedules, enabling bi-directional alert acknowledgment.',
    icon: Bell,
    iconColor: 'var(--neon-cyan)',
    iconBg: 'linear-gradient(135deg, rgba(34,211,238,0.2), rgba(99,102,241,0.1))',
    iconBorder: 'rgba(34,211,238,0.25)',
    status: 'coming_soon',
    href: null,
    tags: ['On-Call', 'Escalation', 'Notifications'],
  },
  {
    id: 'newrelic',
    name: 'New Relic',
    description: 'Stream New Relic alert conditions and golden signal violations into AIREX for AI-driven triage.',
    icon: Layers,
    iconColor: 'var(--color-accent-green)',
    iconBg: 'linear-gradient(135deg, rgba(16,185,129,0.2), rgba(34,211,238,0.1))',
    iconBorder: 'rgba(16,185,129,0.25)',
    status: 'coming_soon',
    href: null,
    tags: ['APM', 'Golden Signals', 'Alerting'],
  },
  {
    id: 'cloudwatch',
    name: 'AWS CloudWatch',
    description: 'Route CloudWatch alarms and Composite Alarms directly into the AIREX incident state machine.',
    icon: Clock,
    iconColor: 'var(--color-accent-amber)',
    iconBg: 'linear-gradient(135deg, rgba(245,158,11,0.2), rgba(249,115,22,0.1))',
    iconBorder: 'rgba(245,158,11,0.25)',
    status: 'coming_soon',
    href: null,
    tags: ['AWS', 'Alarms', 'Logs Insights'],
  },
]

const STATUS_BADGE = {
  connected: { label: 'Connected', color: 'var(--color-accent-green)', bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.3)' },
  coming_soon: { label: 'Coming Soon', color: 'var(--text-muted)', bg: 'rgba(107,114,128,0.1)', border: 'rgba(107,114,128,0.2)' },
}

export default function LiveMonitoringPage() {
  const navigate = useNavigate()

  const connected = PLUGINS.filter(p => p.status === 'connected')
  const upcoming = PLUGINS.filter(p => p.status === 'coming_soon')

  return (
    <div className="space-y-8 p-4 md:p-6 max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div
            className="p-2.5 rounded-xl"
            style={{
              background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(34,211,238,0.1))',
              border: '1px solid rgba(99,102,241,0.25)',
            }}
          >
            <HeartPulse size={22} style={{ color: 'var(--neon-indigo)' }} />
          </div>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
              Live Monitoring
            </h1>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
              Select a monitoring integration to view service health, alerts, and insights.
            </p>
          </div>
        </div>
      </div>

      {/* Stats strip */}
      <div
        className="rounded-xl px-5 py-3 flex flex-wrap gap-6"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
      >
        <div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>Active Integrations</p>
          <p style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-accent-green)' }}>{connected.length}</p>
        </div>
        <div style={{ borderLeft: '1px solid var(--border)', paddingLeft: 24 }}>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>Coming Soon</p>
          <p style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-secondary)' }}>{upcoming.length}</p>
        </div>
        <div style={{ borderLeft: '1px solid var(--border)', paddingLeft: 24 }}>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>Total Plugins</p>
          <p style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-heading)' }}>{PLUGINS.length}</p>
        </div>
      </div>

      {/* Active integrations */}
      <section>
        <h2 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
          Active Integrations
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {connected.map(plugin => (
            <PluginCard key={plugin.id} plugin={plugin} navigate={navigate} />
          ))}
        </div>
      </section>

      {/* Upcoming integrations */}
      <section>
        <h2 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
          Upcoming Integrations
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {upcoming.map(plugin => (
            <PluginCard key={plugin.id} plugin={plugin} navigate={navigate} />
          ))}
        </div>
      </section>
    </div>
  )
}

function PluginCard({ plugin, navigate }) {
  const badge = STATUS_BADGE[plugin.status]
  const Icon = plugin.icon
  const isActive = plugin.status === 'connected'

  const handleClick = () => {
    if (isActive && plugin.href) navigate(plugin.href)
  }

  return (
    <div
      onClick={handleClick}
      className={`glass rounded-2xl p-5 flex flex-col gap-4 transition-all relative overflow-hidden ${
        isActive ? 'hover-lift cursor-pointer hover:border-indigo-500/30 hover:shadow-[0_0_20px_rgba(99,102,241,0.12)]' : 'opacity-70'
      }`}
      style={{ border: isActive ? '1px solid rgba(99,102,241,0.15)' : '1px solid var(--border)' }}
    >
      {/* Subtle glow for active */}
      {isActive && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse at top left, rgba(99,102,241,0.05) 0%, transparent 60%)' }}
        />
      )}

      {/* Top row: icon + status badge */}
      <div className="flex items-start justify-between gap-3">
        <div
          className="p-2.5 rounded-xl flex-shrink-0"
          style={{ background: plugin.iconBg, border: `1px solid ${plugin.iconBorder}` }}
        >
          <Icon size={20} style={{ color: plugin.iconColor }} />
        </div>
        <span
          className="text-xs font-semibold px-2.5 py-1 rounded-full"
          style={{ color: badge.color, background: badge.bg, border: `1px solid ${badge.border}` }}
        >
          {badge.label}
        </span>
      </div>

      {/* Name + description */}
      <div className="flex-1">
        <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 6 }}>
          {plugin.name}
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
          {plugin.description}
        </p>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {plugin.tags.map(tag => (
          <span
            key={tag}
            className="text-xs px-2 py-0.5 rounded-md"
            style={{ color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
          >
            {tag}
          </span>
        ))}
      </div>

      {/* CTA */}
      <div className="flex items-center justify-between pt-1" style={{ borderTop: '1px solid var(--border)' }}>
        {isActive ? (
          <span style={{ fontSize: 12, fontWeight: 600, color: plugin.iconColor }}>
            Open Dashboard
          </span>
        ) : (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Not yet available
          </span>
        )}
        <ChevronRight
          size={16}
          style={{ color: isActive ? plugin.iconColor : 'var(--text-muted)', opacity: isActive ? 1 : 0.4 }}
        />
      </div>
    </div>
  )
}
