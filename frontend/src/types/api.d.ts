/**
 * AIREX API Types — auto-generated from OpenAPI spec.
 *
 * Regenerate with: bash scripts/generate-types.sh
 * Manual types below serve as a development fallback.
 */

export interface Incident {
  id: string
  tenant_id: string
  alert_type: string
  state: IncidentState
  severity: SeverityLevel
  title: string
  investigation_retry_count: number
  execution_retry_count: number
  verification_retry_count: number
  created_at: string
  updated_at: string
}

export interface RelatedIncidentItem {
  id: string
  alert_type: string
  state: IncidentState
  severity: SeverityLevel
  title: string
  created_at: string
}

export interface IncidentDetail extends Incident {
  evidence: Evidence[]
  state_transitions: StateTransition[]
  executions: Execution[]
  recommendation: Recommendation | null
  meta: Record<string, unknown> | null
  related_incidents?: RelatedIncidentItem[]
}

export interface Evidence {
  id: string
  tool_name: string
  raw_output: string
  timestamp: string
}

export interface StateTransition {
  id: string
  from_state: IncidentState
  to_state: IncidentState
  reason: string | null
  actor: string
  created_at: string
}

export interface Execution {
  id: string
  action_type: string
  attempt: number
  status: ExecutionStatus
  logs: string | null
  started_at: string
  completed_at: string | null
  duration_seconds: number | null
}

export interface Recommendation {
  root_cause: string
  proposed_action: string
  risk_level: RiskLevel
  confidence: number
}

export interface PaginatedIncidents {
  items: Incident[]
  next_cursor: string | null
  has_more: boolean
  total: number | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string | null
  token_type: string
  expires_in: number
}

export interface UserResponse {
  id: string
  tenant_id: string
  email: string
  display_name: string
  role: string
}

export type IncidentState =
  | 'RECEIVED'
  | 'INVESTIGATING'
  | 'RECOMMENDATION_READY'
  | 'AWAITING_APPROVAL'
  | 'EXECUTING'
  | 'VERIFYING'
  | 'RESOLVED'
  | 'FAILED_ANALYSIS'
  | 'FAILED_EXECUTION'
  | 'FAILED_VERIFICATION'
  | 'ESCALATED'

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

export type ExecutionStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
