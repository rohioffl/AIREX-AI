/**
 * AIREX Landing Page — Hero, features, how it works, stats, CTA, footer.
 */

import { Link } from 'react-router-dom'
import {
  Zap,
  Search,
  FileCheck,
  ShieldCheck,
  Cloud,
  Activity,
  Bell,
  ArrowRight,
  Server,
  Lock,
  BarChart3,
  CheckCircle2,
} from 'lucide-react'
import landFinalBg from '../assets/land_final.jpg'
import './LandingPage.css'

const FEATURES = [
  {
    icon: Bell,
    title: 'Alert ingestion',
    description: 'Webhooks from Site24x7, PagerDuty, or any source. Deduplication and idempotency so the same alert doesn’t create duplicate incidents.',
  },
  {
    icon: Search,
    title: 'AI investigation',
    description: 'Automatic root-cause analysis using cloud metadata, SSM, and EC2 Instance Connect. Evidence gathered in under 60 seconds.',
  },
  {
    icon: Zap,
    title: 'AI recommendations',
    description: 'LiteLLM-backed suggestions with registered runbook actions. Circuit breaker and fallbacks keep the system reliable.',
  },
  {
    icon: ShieldCheck,
    title: 'Human approval',
    description: 'No action runs without explicit approval. Policy gating and audit trails for every execution.',
  },
  {
    icon: FileCheck,
    title: 'Deterministic runbooks',
    description: 'Execute only approved, registered actions. Redis locks prevent double-runs; verification retries don’t replay executions.',
  },
  {
    icon: Cloud,
    title: 'Multi-cloud ready',
    description: 'AWS, GCP, and more. Tenant-scoped config, RLS, and correlation IDs across the stack.',
  },
  {
    icon: Activity,
    title: 'Live feed',
    description: 'Real-time incident stream via SSE. State changes and new incidents as they happen.',
  },
  {
    icon: BarChart3,
    title: 'Observability',
    description: 'Prometheus metrics, hash-chained state transitions, and DLQ visibility for failed work.',
  },
]

const STEPS = [
  { step: 1, title: 'Alert received', body: 'Webhook hits the unification layer; idempotency ensures one incident per unique event.' },
  { step: 2, title: 'Investigate', body: 'Plugins run read-only diagnostics (SSM, SSH, logs). Evidence is attached to the incident.' },
  { step: 3, title: 'Recommend', body: 'AI suggests actions from the registry. You see reasoning and risk before approving.' },
  { step: 4, title: 'Approve & execute', body: 'One-click approval runs the runbook. Verification confirms remediation.' },
]

const STATS = [
  { value: '99.9%', label: 'Uptime SLA' },
  { value: '< 60s', label: 'Investigation target' },
  { value: 'Zero', label: 'Unapproved actions' },
]

const INTEGRATIONS = [
  { name: 'Site24x7', type: 'Monitoring' },
  { name: 'AWS', type: 'Cloud' },
  { name: 'GCP', type: 'Cloud' },
  { name: 'PagerDuty', type: 'Alerting' },
]

export default function LandingPage() {
  return (
    <div className="airex-landing">
      {/* Image as bg for everything until Secure by design; then it scrolls up ── */}
      <div className="airex-image-zone" style={{ backgroundImage: `url(${landFinalBg})` }}>
      {/* Fixed header: all sections scroll under it ── */}
      <header className="airex-landing-header">
        <div className="airex-logo-block">
          <span className="airex-logo">AIREX</span>
          <span className="airex-logo-abbr">Autonomous Incident Resolution Engine</span>
        </div>
        <nav className="airex-landing-nav">
          <Link to="/login" className="airex-nav-link">Sign in</Link>
          <Link to="/incidents" className="airex-nav-link airex-nav-cta">Open app</Link>
        </nav>
      </header>
      {/* ── Hero (text left, cube clear) ── */}
      <section className="airex-scroll-section" aria-label="Hero">
        <div className="airex-content-overlay">
          <div className="airex-hero-content">
            <span className="airex-hero-badge">AI-powered SRE</span>
            <h1 className="airex-hero-title">Autonomous Incident Resolution</h1>
            <p className="airex-hero-abbr">Autonomous Incident Resolution Engine</p>
            <p className="airex-hero-subtitle">
              From alert to resolution with AI in the loop and humans in control. Detect. Investigate. Resolve.
            </p>
            <div className="airex-hero-cta">
              <Link to="/incidents" className="airex-hero-btn airex-hero-btn-primary">Open AIREX</Link>
              <Link to="/login" className="airex-hero-btn airex-hero-btn-secondary">Sign in</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Bg section: lifecycle content ── */}
      <section className="airex-bg-section" aria-label="Platform">
        <div className="airex-bg-section-overlay" />
        <div className="airex-bg-section-content">
          <p className="airex-bg-section-lead">One platform for the full incident lifecycle</p>
          <ul className="airex-bg-section-list">
            <li>Ingest alerts from any source</li>
            <li>AI investigates and recommends</li>
            <li>You approve — we execute</li>
            <li>Verify and close</li>
          </ul>
        </div>
      </section>

      {/* ── Integrations: content left, cube clear on right ── */}
      <section className="airex-integrations-bg" aria-label="Integrations">
        <div className="airex-integrations-bg-overlay" />
        <div className="airex-integrations-bg-content">
          <h2 className="airex-integrations-bg-title">Integrations</h2>
          <p className="airex-integrations-bg-lead">Connect your monitoring and cloud providers.</p>
          <div className="airex-integrations-bg-list">
            {INTEGRATIONS.map(({ name, type }) => (
              <div key={name} className="airex-integration-item">
                <Server size={20} className="airex-integration-icon" />
                <span className="airex-integration-name">{name}</span>
                <span className="airex-integration-type">{type}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why AIREX (highlights) ── */}
      <section className="airex-section airex-why" aria-label="Why AIREX">
        <div className="airex-container">
          <h2 className="airex-section-title">Why AIREX?</h2>
          <p className="airex-section-lead">Built for teams that need speed without sacrificing control.</p>
          <div className="airex-why-grid">
            <div className="airex-why-card">
              <Zap className="airex-why-icon" size={28} />
              <h3>Faster MTTR</h3>
              <p>AI investigates in under 60s and suggests runbooks so you resolve incidents faster.</p>
            </div>
            <div className="airex-why-card">
              <ShieldCheck className="airex-why-icon" size={28} />
              <h3>Human in the loop</h3>
              <p>No action runs without approval. Full audit trail and policy gating.</p>
            </div>
            <div className="airex-why-card">
              <Cloud className="airex-why-icon" size={28} />
              <h3>Multi-cloud native</h3>
              <p>AWS, GCP, and more. Tenant-scoped, RLS, and correlation IDs end to end.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="airex-section airex-features" aria-label="Features">
        <div className="airex-container">
          <h2 className="airex-section-title">Built for autonomous SRE</h2>
          <p className="airex-section-lead">From alert to resolution with AI in the loop and humans in control.</p>
          <div className="airex-features-grid">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <article key={title} className="airex-feature-card">
                <div className="airex-feature-icon">
                  <Icon size={24} strokeWidth={1.8} />
                </div>
                <h3 className="airex-feature-title">{title}</h3>
                <p className="airex-feature-desc">{description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="airex-section airex-how" aria-label="How it works">
        <div className="airex-container">
          <h2 className="airex-section-title">How it works</h2>
          <p className="airex-section-lead">Predictable pipeline from ingestion to verification.</p>
          <div className="airex-steps">
            {STEPS.map(({ step, title, body }) => (
              <div key={step} className="airex-step">
                <div className="airex-step-num">{step}</div>
                <div className="airex-step-content">
                  <h3 className="airex-step-title">{title}</h3>
                  <p className="airex-step-body">{body}</p>
                </div>
                {step < STEPS.length && <div className="airex-step-connector" aria-hidden />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="airex-section airex-stats" aria-label="Stats">
        <div className="airex-container">
          <div className="airex-stats-grid">
            {STATS.map(({ value, label }) => (
              <div key={label} className="airex-stat">
                <span className="airex-stat-value">{value}</span>
                <span className="airex-stat-label">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Security & compliance ── */}
      <section className="airex-section airex-security" aria-label="Security">
        <div className="airex-container airex-security-inner">
          <div className="airex-security-icon">
            <Lock size={36} strokeWidth={2.25} className="airex-security-lock" />
          </div>
          <h2 className="airex-section-title">Secure by design</h2>
          <ul className="airex-security-list">
            <li><CheckCircle2 size={18} /> No raw shell; only registered actions</li>
            <li><CheckCircle2 size={18} /> Tenant isolation and RLS</li>
            <li><CheckCircle2 size={18} /> Immutable state transitions with hash chaining</li>
            <li><CheckCircle2 size={18} /> Secrets in env; no business logic on the client</li>
          </ul>
        </div>
      </section>

      {/* ── Testimonial / social proof ── */}
      <section className="airex-section airex-testimonial" aria-label="Testimonial">
        <div className="airex-container">
          <blockquote className="airex-quote">
            <p>“AIREX gives us one place to see, investigate, and resolve incidents—with AI doing the heavy lifting and our team keeping final say.”</p>
            <footer className="airex-quote-footer">— Platform reliability team</footer>
          </blockquote>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="airex-section airex-cta-section" aria-label="Get started">
        <div className="airex-container">
          <h2 className="airex-cta-title">Ready to run autonomous SRE?</h2>
          <p className="airex-cta-lead">Open the app and see incidents, recommendations, and the live feed.</p>
          <div className="airex-cta-buttons">
            <Link to="/incidents" className="airex-hero-btn airex-hero-btn-primary">
              Open AIREX <ArrowRight size={18} />
            </Link>
            <Link to="/login" className="airex-hero-btn airex-hero-btn-secondary">Sign in</Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="airex-footer">
        <div className="airex-container airex-footer-inner">
          <div className="airex-footer-brand">
            <span className="airex-logo">AIREX</span>
            <p className="airex-footer-tagline">Autonomous Incident Resolution Engine — Xecution</p>
          </div>
          <p className="airex-footer-copy">© AIREX. All rights reserved.</p>
        </div>
      </footer>

      </div>
    </div>
  )
}
