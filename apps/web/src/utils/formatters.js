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

export function formatRelativeTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatTimestamp(iso)
}

/**
 * Build a Gmail compose URL with a professional SRE incident notification.
 *
 * @param {object} incident - Full incident object (from detail or list API)
 * @param {object} opts - { escalationEmail, senderName, senderTitle, senderOrg }
 * @returns {string} Gmail compose URL
 */
export function buildAcknowledgeMailto(incident, opts = {}) {
  if (!incident) return ''

  const to = opts.escalationEmail || ''
  const severity = incident.severity || 'UNKNOWN'
  const title = incident.title || 'Untitled Incident'
  const id = incident.id || ''

  const meta = incident.meta || {}
  const cloud = (meta._cloud || '').toUpperCase() || 'N/A'
  const ip = meta._private_ip || 'N/A'
  const instanceId = meta._instance_id || 'N/A'
  const zone = meta._zone || ''
  const region = meta._region || ''
  const tenant = meta._tenant_name || 'N/A'

  const rec = incident.recommendation || meta.recommendation || {}
  const rootCause = rec.root_cause || ''
  const proposedAction = rec.proposed_action || ''
  const riskLevel = rec.risk_level || ''

  // Clean monitor name from title (remove [DOWN] prefix and reason suffix)
  const monitorName = (title.replace(/^\[.*?\]\s*/, '').split('—')[0] || '').trim()
  const incidentReason = meta.INCIDENT_REASON || title.split('—').slice(1).join('—').trim() || ''

  // Derive status description from state
  const statusText = meta.STATUS || 'DOWN'

  // Build investigation findings from evidence
  const evidenceList = incident.evidence || []
  let findings = []
  if (evidenceList.length > 0) {
    const output = (evidenceList[0]?.raw_output || '').toLowerCase()
    if (output.includes('ssh') && output.includes('timed out')) findings.push('SSH connectivity attempts timed out')
    if (output.includes('ssh') && output.includes('error')) findings.push('SSH connection could not be established')
    if (output.includes('no log entries') || output.includes('count: 0') || (output.includes('log') && output.includes('error'))) findings.push('No recent logs detected in Cloud Logging')
    if (output.includes('timed out') || output.includes('not responding')) findings.push('Instance responsiveness could not be verified')
    if (output.includes('cpu') || output.includes('load average')) findings.push('High CPU utilization detected on the instance')
    if (output.includes('memory') || output.includes('oom')) findings.push('Memory pressure or OOM conditions detected')
    if (output.includes('disk') || output.includes('no space')) findings.push('Disk space exhaustion detected')
  }
  if (findings.length === 0) findings.push('Automated investigation completed — awaiting detailed analysis')

  // Derive recommended action text
  let actionText = 'Proceed with manual investigation and remediation.'
  let riskText = ''
  if (proposedAction === 'restart_service') {
    actionText = 'Proceed with a controlled instance/service restart to restore service availability.'
    riskText = `Risk Assessment:
- Temporary downtime during restart
- No expected data loss (assuming stateless configuration or proper persistence setup)
- ${riskLevel === 'HIGH' ? 'Medium' : 'Low'} infrastructure risk`
  } else if (proposedAction === 'clear_logs') {
    actionText = 'Clear rotated log files and reclaim disk space to restore normal operations.'
    riskText = `Risk Assessment:
- Only rotated/old log files will be removed
- Active logs remain intact
- Low infrastructure risk`
  } else if (proposedAction === 'scale_instances') {
    actionText = 'Scale up the instance group to handle increased traffic/load.'
    riskText = `Risk Assessment:
- Additional cost for new instances
- No service disruption during scale-up
- ${riskLevel === 'HIGH' ? 'Medium' : 'Low'} infrastructure risk`
  }

  // Root cause summary
  let rootCauseSummary = ''
  if (rootCause) {
    rootCauseSummary = rootCause
  } else if (incidentReason) {
    rootCauseSummary = incidentReason
  } else {
    rootCauseSummary = 'Due to limited telemetry, the exact root cause could not be conclusively determined. The instance may be unresponsive due to resource exhaustion, network isolation, or system-level failure.'
  }

  const subject = `[${severity}] Incident Alert — ${monitorName || instanceId} — ${cloud} ${region || ''}`

  const body = `Dear Team,

A ${severity.toLowerCase()} incident has been detected on the ${cloud} ${region ? region + ' ' : ''}environment for workspace ${tenant}.


Incident Details

- Incident ID: ${id}
- Severity: ${severity}
- Environment: Production
- Cloud Provider: ${cloud}
- Region / Zone: ${region || 'N/A'} / ${zone || 'N/A'}
- Instance Name: ${instanceId || 'N/A'}
- Private IP: ${ip}


Issue Summary

The monitoring system reported the instance as ${statusText}. ${incidentReason ? incidentReason + '.' : 'Initial automated investigation indicates the instance is currently unreachable.'}


Investigation Findings

${findings.map(f => '- ' + f).join('\n')}

${rootCauseSummary}


Recommended Action

${actionText}

${riskText}


Kindly review and approve the recommended action at the earliest to minimize service impact.

Please let us know if you would prefer further manual investigation before proceeding.

Regards,
`

  const gmailUrl = new URL('https://mail.google.com/mail/?view=cm&fs=1')
  if (to) gmailUrl.searchParams.set('to', to)
  gmailUrl.searchParams.set('su', subject)
  gmailUrl.searchParams.set('body', body)

  return gmailUrl.toString()
}
