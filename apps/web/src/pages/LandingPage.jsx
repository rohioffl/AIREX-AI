/**
 * AIREX Landing Page — Hero, features, how it works, stats, CTA, footer.
 */

import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
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
  Mail,
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
    description: 'LiteLLM-backed suggestions with registered runbook actions, model routing, and reliable fallbacks for production incident workflows.',
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
    description: 'Prometheus metrics, Langfuse traces for LLM calls, hash-chained state transitions, and DLQ visibility for failed work.',
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
  { name: 'LiteLLM', type: 'LLM Gateway' },
  { name: 'Langfuse', type: 'Tracing' },
]

/* Hook for scroll reveal animation */
function useScrollReveal() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('active')
            // Optional: unobserve after reveal so it doesn't re-trigger
            // observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.15, rootMargin: '0px 0px -50px 0px' }
    )

    const hiddenElements = document.querySelectorAll('.airex-reveal')
    hiddenElements.forEach((el) => observer.observe(el))

    return () => hiddenElements.forEach((el) => observer.unobserve(el))
  }, [])
}

export default function LandingPage() {
  useScrollReveal()
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '' })
  const [submitted, setSubmitted] = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    setSubmitted(true)
  }

  return (
    <div className="airex-landing">
      {/* Image as bg for everything until Secure by design; then it scrolls up ── */}
      <div className="airex-image-zone">
        <div className="airex-cinematic-bg" style={{ backgroundImage: `url(${landFinalBg})` }} />
      
      {/* Fixed header: all sections scroll under it ── */}
      <header className="airex-landing-header">
        <div className="airex-logo-block">
          <span className="airex-logo">AIREX</span>
          <span className="airex-logo-abbr">Autonomous Incident Resolution Engine</span>
        </div>
        <nav className="airex-landing-nav">
          <Link to="/admin/login" className="airex-nav-link airex-nav-admin">Platform Admin</Link>
          <Link to="/login" className="airex-nav-link">Sign in</Link>
        </nav>
      </header>
      {/* ── Hero (text left, cube clear) ── */}
      <section className="airex-scroll-section" aria-label="Hero">
        <div className="airex-content-overlay">
          <div className="airex-hero-content airex-reveal">
            <span className="airex-hero-badge">AI-powered SRE</span>
            <h1 className="airex-hero-title">Autonomous Incident Resolution</h1>
            <p className="airex-hero-abbr">Autonomous Incident Resolution Engine</p>
            <p className="airex-hero-subtitle">
              From alert to resolution with AI in the loop and humans in control. Detect. Investigate. Resolve.
            </p>
            <div className="airex-hero-cta">
              <a href="#demo" className="airex-hero-btn airex-hero-btn-primary">Get Demo</a>
              <Link to="/login" className="airex-hero-btn airex-hero-btn-secondary">Sign in</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Parallel Block: Lifecycle & Integrations ── */}
      <section className="airex-parallel-section airex-container" aria-label="Platform and Integrations">
        <div className="airex-parallel-grid">
          {/* Lifecycle (Left) */}
          <div className="airex-bg-section-content airex-reveal">
            <p className="airex-bg-section-lead">One platform for the full incident lifecycle</p>
            <ul className="airex-bg-section-list">
              <li>Ingest alerts from any source</li>
              <li>AI investigates and recommends</li>
              <li>You approve — we execute</li>
              <li>Verify and close</li>
            </ul>
          </div>

          {/* Integrations (Right) */}
          <div className="airex-integrations-bg-content airex-reveal airex-reveal-stagger-1">
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
        </div>
      </section>

      {/* ── Why AIREX (highlights) ── */}
      <section className="airex-section airex-why" aria-label="Why AIREX">
        <div className="airex-container">
          <h2 className="airex-section-title airex-reveal">Why AIREX?</h2>
          <p className="airex-section-lead airex-reveal">Built for teams that need speed without sacrificing control.</p>
          <div className="airex-why-grid">
            <div className="airex-why-card airex-reveal airex-reveal-stagger-1">
              <Zap className="airex-why-icon" size={28} />
              <h3>Faster MTTR</h3>
              <p>AI investigates in under 60s and suggests runbooks so you resolve incidents faster.</p>
            </div>
            <div className="airex-why-card airex-reveal airex-reveal-stagger-2">
              <ShieldCheck className="airex-why-icon" size={28} />
              <h3>Human in the loop</h3>
              <p>No action runs without approval. Full audit trail and policy gating.</p>
            </div>
            <div className="airex-why-card airex-reveal airex-reveal-stagger-3">
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
          <h2 className="airex-section-title airex-reveal">Built for autonomous SRE</h2>
          <p className="airex-section-lead airex-reveal">From alert to resolution with AI in the loop and humans in control.</p>
          <div className="airex-features-grid">
            { }
            {FEATURES.map(({ icon: FeatureIcon, title, description }, idx) => (
              <article key={title} className={`airex-feature-card airex-reveal airex-reveal-stagger-${(idx % 3) + 1}`}>
                <div className="airex-feature-icon">
                  <FeatureIcon size={24} strokeWidth={1.8} />
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
          <h2 className="airex-section-title airex-reveal">How it works</h2>
          <p className="airex-section-lead airex-reveal">Predictable pipeline from ingestion to verification.</p>
          <div className="airex-steps">
            {STEPS.map(({ step, title, body }, idx) => (
              <div key={step} className={`airex-step airex-reveal airex-reveal-stagger-${idx + 1}`}>
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
            {STATS.map(({ value, label }, idx) => (
              <div key={label} className={`airex-stat airex-reveal airex-reveal-stagger-${idx + 1}`}>
                <span className="airex-stat-value">{value}</span>
                <span className="airex-stat-label">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Security & compliance ── */}
      <section className="airex-section airex-security" aria-label="Security">
        <div className="airex-container airex-security-inner airex-reveal">
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
          <blockquote className="airex-quote airex-reveal">
            <p>“AIREX gives us one place to see, investigate, and resolve incidents—with AI doing the heavy lifting and our team keeping final say.”</p>
            <footer className="airex-quote-footer">— Platform reliability team</footer>
          </blockquote>
        </div>
      </section>

      {/* ── Demo & Contact ── */}
      <section id="demo" className="airex-section airex-demo" aria-label="Demo and Contact">
        <div className="airex-container">
          <h2 className="airex-section-title airex-reveal">See AIREX in action</h2>
          <p className="airex-section-lead airex-reveal">
            AI-driven incident response from alert to resolution — with humans always in control.
          </p>
          <div className="airex-demo-grid">
            {/* Product Showcase */}
            <div className="airex-demo-showcase airex-reveal">
              <div className="airex-mock-header">
                <span className="airex-mock-dot red" />
                <span className="airex-mock-dot yellow" />
                <span className="airex-mock-dot green" />
                <span className="airex-mock-title">AIREX — Incident Dashboard</span>
              </div>
              <div className="airex-mock-body">
                <div className="airex-mock-incident active">
                  <div className="airex-mock-incident-header">
                    <span className="airex-mock-badge critical">CRITICAL</span>
                    <span className="airex-mock-time">just now</span>
                  </div>
                  <div className="airex-mock-incident-title">High CPU on prod-api-01</div>
                  <div className="airex-mock-state investigating">
                    <Activity size={12} /> Investigating...
                  </div>
                </div>
                <div className="airex-mock-incident">
                  <div className="airex-mock-incident-header">
                    <span className="airex-mock-badge warning">HIGH</span>
                    <span className="airex-mock-time">2m ago</span>
                  </div>
                  <div className="airex-mock-incident-title">Disk usage 94% on db-replica-2</div>
                  <div className="airex-mock-state awaiting">
                    <ShieldCheck size={12} /> Awaiting approval
                  </div>
                </div>
                <div className="airex-mock-incident">
                  <div className="airex-mock-incident-header">
                    <span className="airex-mock-badge info">MED</span>
                    <span className="airex-mock-time">14m ago</span>
                  </div>
                  <div className="airex-mock-incident-title">Memory pressure on worker-3</div>
                  <div className="airex-mock-state resolved">
                    <CheckCircle2 size={12} /> Resolved
                  </div>
                </div>
                <div className="airex-mock-rec">
                  <div className="airex-mock-rec-label">AI Recommendation</div>
                  <div className="airex-mock-rec-action">
                    restart_service <span className="airex-mock-risk">risk: LOW</span>
                  </div>
                  <div className="airex-mock-rec-reason">
                    CPU spike linked to memory leak in v2.4.1. Restarting will clear the leak. Confidence: 91%
                  </div>
                  <div className="airex-mock-rec-actions">
                    <button className="airex-mock-btn approve">Approve</button>
                    <button className="airex-mock-btn reject">Reject</button>
                  </div>
                </div>
              </div>
            </div>

            {/* Contact Form */}
            <div className="airex-contact-panel airex-reveal airex-reveal-stagger-1">
              <h3 className="airex-contact-title">Request a demo</h3>
              <p className="airex-contact-lead">
                Tell us about your infrastructure and we&apos;ll show you AIREX in your environment.
              </p>
              {submitted ? (
                <div className="airex-form-success">
                  <CheckCircle2 size={36} className="airex-success-icon" />
                  <p>Thanks! We&apos;ll be in touch shortly.</p>
                </div>
              ) : (
                <form className="airex-contact-form" onSubmit={handleSubmit}>
                  <div className="airex-form-row">
                    <div className="airex-form-group">
                      <label className="airex-form-label">Name</label>
                      <input
                        className="airex-form-input"
                        type="text"
                        placeholder="Your name"
                        value={form.name}
                        onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                        required
                      />
                    </div>
                    <div className="airex-form-group">
                      <label className="airex-form-label">Email</label>
                      <input
                        className="airex-form-input"
                        type="email"
                        placeholder="Work email"
                        value={form.email}
                        onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                        required
                      />
                    </div>
                  </div>
                  <div className="airex-form-group">
                    <label className="airex-form-label">Company</label>
                    <input
                      className="airex-form-input"
                      type="text"
                      placeholder="Your company"
                      value={form.company}
                      onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                    />
                  </div>
                  <div className="airex-form-group">
                    <label className="airex-form-label">Message</label>
                    <textarea
                      className="airex-form-textarea"
                      rows={4}
                      placeholder="What incident pain points are you solving?"
                      value={form.message}
                      onChange={e => setForm(f => ({ ...f, message: e.target.value }))}
                    />
                  </div>
                  <button type="submit" className="airex-form-submit">
                    <Mail size={16} /> Request Demo
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="airex-section airex-cta-section" aria-label="Get started">
        <div className="airex-container airex-reveal">
          <h2 className="airex-cta-title">Ready to run autonomous SRE?</h2>
          <p className="airex-cta-lead">AI-backed incident response — detection, investigation, and resolution.</p>
          <div className="airex-cta-buttons">
            <a href="#demo" className="airex-hero-btn airex-hero-btn-primary">
              Request Demo <ArrowRight size={18} />
            </a>
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
