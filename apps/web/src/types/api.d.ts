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
  meta: Record<string, unknown> | null
  resolution_type?: string | null
  resolution_duration_seconds?: number | null
  feedback_score?: number | null
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
  // Resolution tracking (Phase 2 ARE)
  resolution_type?: string | null
  resolution_summary?: string | null
  resolution_duration_seconds?: number | null
  feedback_score?: number | null
  feedback_note?: string | null
  resolved_at?: string | null
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

export interface AlternativeRecommendation {
  action: string
  rationale: string
  confidence: number
  risk_level?: RiskLevel
}

export interface ConfidenceBreakdown {
  model_confidence: number
  evidence_strength_score: number
  tool_grounding_score: number
  kg_match_score: number
  hallucination_penalty: number
  composite_confidence: number
  warning?: string
}

export interface Recommendation {
  root_cause: string
  proposed_action: string
  risk_level: RiskLevel
  confidence: number
  summary?: string
  rationale?: string
  blast_radius?: string
  root_cause_category?: string
  contributing_factors?: string[]
  alternatives?: AlternativeRecommendation[]
  verification_criteria?: string[]
  reasoning_chain?: ReasoningStep[]
  evidence_annotations?: Record<string, string>
  confidence_breakdown?: ConfidenceBreakdown | null
  grounding_summary?: string
  impact_estimate?: ImpactEstimate | null
  execution_guard?: ExecutionGuard | null
}

export interface ReasoningStep {
  step: string
  detail: string
}

/** Approval decision metadata stored in incident.meta by the backend. */
export type ApprovalLevel = 'operator' | 'senior'

export interface ApprovalMeta {
  _approval_level?: ApprovalLevel
  _approval_reason?: string
  _confidence_met?: boolean
  _senior_required?: boolean
  _approval_confidence?: number
  _approval_confidence_source?: 'model' | 'composite'
}

export interface ImpactEstimate {
  cost_delta: 'low' | 'medium' | 'high'
  dependency_pressure: 'low' | 'medium' | 'high'
  resource_limit_risk: 'low' | 'medium' | 'high'
  blast_radius_summary: string
  scale_delta?: number | null
  notes?: string[]
}

export interface ExecutionGuard {
  valid: boolean
  reason: string
  enforcement_mode: 'legacy' | 'strict'
  credential_scope_valid: boolean
  cluster_ownership_valid: boolean
  namespace_scope_valid: boolean
  cross_tenant_denied: boolean
  binding_id?: string
  target_scope: Record<string, string>
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
  is_active?: boolean | null
  created_at?: string | null
  updated_at?: string | null
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
  | 'REJECTED'

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

export type ExecutionStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
