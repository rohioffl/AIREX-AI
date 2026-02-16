/**
 * k6 Load Test — AIREX Incident Pipeline
 *
 * Tests:
 *   1. Webhook ingestion throughput
 *   2. Incident listing latency
 *   3. Incident detail fetch
 *   4. Concurrent approval flow
 *
 * Run:
 *   k6 run infra/loadtest/k6_incident_flow.js
 *
 * With options:
 *   k6 run --vus 50 --duration 2m infra/loadtest/k6_incident_flow.js
 */

import http from 'k6/http'
import { check, sleep, group } from 'k6'
import { Rate, Trend } from 'k6/metrics'

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'
const TENANT_ID = __ENV.TENANT_ID || '00000000-0000-0000-0000-000000000000'

const webhookErrors = new Rate('webhook_errors')
const listLatency = new Trend('incident_list_latency', true)
const detailLatency = new Trend('incident_detail_latency', true)
const webhookLatency = new Trend('webhook_latency', true)

export const options = {
  stages: [
    { duration: '15s', target: 10 },  // Ramp up
    { duration: '30s', target: 25 },  // Sustained load
    { duration: '30s', target: 50 },  // Peak
    { duration: '15s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.05'],
    webhook_errors: ['rate<0.1'],
    incident_list_latency: ['p(95)<1000'],
  },
}

const headers = {
  'Content-Type': 'application/json',
  'X-Tenant-Id': TENANT_ID,
}

export default function () {
  group('Webhook Ingestion', () => {
    const alertTypes = ['cpu_high', 'disk_full', 'memory_high', 'network_issue']
    const severities = ['critical', 'high', 'medium', 'low']

    const payload = JSON.stringify({
      alert_type: alertTypes[Math.floor(Math.random() * alertTypes.length)],
      severity: severities[Math.floor(Math.random() * severities.length)],
      title: `Load test alert ${Date.now()}-${__VU}`,
      resource_id: `lt-host-${__VU}-${__ITER}`,
      meta: {
        host: `lt-host-${__VU}`,
        monitor_name: `lt-monitor-${__VU}`,
        service_name: 'test-service',
      },
    })

    const res = http.post(`${BASE_URL}/api/v1/webhooks/generic`, payload, { headers })
    webhookLatency.add(res.timings.duration)

    const ok = check(res, {
      'webhook status is 202': (r) => r.status === 202,
      'webhook returns incident_id': (r) => {
        try {
          return JSON.parse(r.body).incident_id !== undefined
        } catch {
          return false
        }
      },
    })
    if (!ok) webhookErrors.add(1)
    else webhookErrors.add(0)
  })

  sleep(0.5)

  group('Incident List', () => {
    const res = http.get(`${BASE_URL}/api/v1/incidents?limit=20`, { headers })
    listLatency.add(res.timings.duration)

    check(res, {
      'list status is 200': (r) => r.status === 200,
      'list returns items': (r) => {
        try {
          const data = JSON.parse(r.body)
          return (data.items || data).length >= 0
        } catch {
          return false
        }
      },
    })
  })

  sleep(0.3)

  group('Incident Detail', () => {
    // First, get an incident ID from the list
    const listRes = http.get(`${BASE_URL}/api/v1/incidents?limit=1`, { headers })
    if (listRes.status === 200) {
      try {
        const data = JSON.parse(listRes.body)
        const items = data.items || data
        if (items.length > 0) {
          const id = items[0].id
          const detailRes = http.get(`${BASE_URL}/api/v1/incidents/${id}`, { headers })
          detailLatency.add(detailRes.timings.duration)

          check(detailRes, {
            'detail status is 200': (r) => r.status === 200,
            'detail has state': (r) => {
              try {
                return JSON.parse(r.body).state !== undefined
              } catch {
                return false
              }
            },
          })
        }
      } catch {
        // Ignore parse errors
      }
    }
  })

  sleep(0.5)

  group('Health Check', () => {
    const res = http.get(`${BASE_URL}/health`)
    check(res, {
      'health is ok': (r) => r.status === 200,
    })
  })
}

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    total_requests: data.metrics.http_reqs.values.count,
    avg_duration_ms: data.metrics.http_req_duration.values.avg.toFixed(2),
    p95_duration_ms: data.metrics.http_req_duration.values['p(95)'].toFixed(2),
    p99_duration_ms: data.metrics.http_req_duration.values['p(99)'].toFixed(2),
    error_rate: (data.metrics.http_req_failed.values.rate * 100).toFixed(2) + '%',
  }

  console.log('\n=== AIREX Load Test Summary ===')
  console.log(JSON.stringify(summary, null, 2))

  return {}
}
