---
name: frontend-sre-dashboard
description: Build a production-grade, state-driven SRE dashboard for the Agentic AI Incident Response Platform. Focus on operational clarity, real-time updates (SSE), and strict backend state adherence.
license: Private
---

# Frontend Skill — AIREX

> **Single-tenant note:** The product currently operates in a single-tenant configuration. UI controls or headers referencing tenant IDs are ignored until multi-tenancy returns.

This skill defines the frontend implementation rules for the operational SRE dashboard.

This is NOT a marketing site.
This is NOT a generic admin panel.
This is an operational control surface for incident management.

The UI must be:

- **State-driven**: Render strictly based on backend state.
- **Dark-themed**: Default to dark mode for operational use.
- **Deterministic**: Same state = Same UI, always.
- **Safe**: Prevent accidental execution.
- **Scalable**: Support 30+ alert types **without code changes**.

---

## 1. Tech Stack (Mandatory)

| Component | Choice | Restriction |
| :--- | :--- | :--- |
| **Framework** | React (Vite) | Functional Components + Hooks ONLY. No Class Components. |
| **Styling** | Tailwind CSS | Utility-first. No custom CSS files unless unavoidable. |
| **HTTP** | Fetch / Axios | Centralized API client. No inline `fetch()` calls. |
| **Real-time** | SSE (Server-Sent Events) | Must handle auto-reconnect. |
| **State** | React Context / Hooks | **NO Redux**. **NO MobX**. Keep it simple. |

---

## 2. Core Architectural Rule: "State is King"

The UI MUST be 100% state-driven.

**Backend State Machine (Immutable Source of Truth):**
`RECEIVED` → `INVESTIGATING` → `RECOMMENDATION_READY` → `AWAITING_APPROVAL` → `EXECUTING` → `VERIFYING` → `RESOLVED` | `FAILED_ANALYSIS` | `FAILED_EXECUTION` | `FAILED_VERIFICATION` | `REJECTED`
> `REJECTED` only occurs when an operator uses the Reject action. Automation failures remain in their corresponding `FAILED_*` states with `_manual_review_required` metadata.

**Strict Rules for AI:**
1.  **NEVER** infer state (e.g., `if (logs.length > 0) return 'EXECUTING'`).
2.  **NEVER** simulate transitions locally (e.g., `setState('EXECUTING')` on button click).
3.  **ALWAYS** wait for the backend to broadcast the new state via SSE.
4.  **ONLY** render components authorized for the current state using **EXPLICIT CHECKS** (e.g., `state === 'EXECUTING'`). **NEVER** use string comparison operators (`>=`).

---

## 3. Pages

### 3.1 Incident List Page (`/incidents`)

- **Data Source**: Fetch initial list -> Update via SSE `incident_created` / `state_changed`.
- **Sorting**: Default `created_at` DESC.
- **Filtering**: By State, Severity, Alert Type.

#### Incident Card Spec:
| Field | UI Component | Logic |
| :--- | :--- | :--- |
| `incident_id` | Text (Truncated) | Copy on click. |
| `alert_type` | Badge (Gray) | No color coding. |
| `cloud` | Icon/Badge | AWS / GCP. |
| `severity` | Badge (Color) | Critical (Red), High (Orange), Medium (Yellow), Low (Blue). |
| `state` | Badge (Outline) | Map directly from backend string. |
| `retry_count` | Text `(x/3)` | Show if > 0. |

---

### 3.2 Incident Detail Page (`/incidents/:id`)

**Render Order (Immutable):**
1.  **Header**: Core metadata.
2.  **Timeline**: Chronological events.
3.  **Evidence**: Raw data (logs/JSON).
4.  **Recommendation**: AI analysis (If `state >= RECOMMENDATION_READY`).
5.  **Approval Controls**: Actions (If `state == AWAITING_APPROVAL`).
6.  **Execution Logs**: Live output (If `state >= EXECUTING`).
7.  **Verification Result**: Final status (If `state >= VERIFYING`).

---

## 4. Component Specifications

### 4.3 Evidence Panel
- **Font**: `font-mono` (Menlo/Consolas).
- **Behavior**: Collapsed by default.
- **Safety**: Render `raw_output` as text, **NEVER** as HTML (`dangerouslySetInnerHTML` is BANNED).
- **UX**: "Copy to Clipboard" button required.

### 4.4 Recommendation Section
- **Condition**: Render strictly when `recommendation` object exists AND:
    ```javascript
    state === 'RECOMMENDATION_READY' ||
    state === 'AWAITING_APPROVAL' ||
    state === 'EXECUTING' ||
    state === 'VERIFYING' ||
    state === 'RESOLVED' ||
    state.startsWith('FAILED') ||
    state === 'REJECTED'
    ```
- **Risk Display**:
    - **Low**: Green border/text.
    - **Medium**: Yellow border/text.
    - **High**: Red border/text + Warning Icon.
- **NO** risk calculation in frontend. Use backend `risk_level` field.

### 4.5 Approval Controls
- **Condition**: Render strictly when `state == AWAITING_APPROVAL`.
- **Interaction**:
    1.  User clicks "Approve".
    2.  **Modal** appears: "Are you sure you want to execute [action_type]?"
    3.  User confirms.
    4.  UI calls `POST /approve` with **Idempotency Key** (`incident_id` + `action_type`).
    5.  Buttons become **DISABLED**. Loading spinner appears.
    6.  **WAIT** for SSE `state_changed` event. **DO NOT** manually change UI state.
    7.  **NO** automatic retry on failure.

### 4.6 Execution Logs
- **Updates**: Append-only via SSE `execution_log` events.
- **Scroll**: Auto-scroll to bottom if active.

---

## 5. Real-Time Updates (SSE)

**Required Event Handlers:**
- `incident_created`: Add to list.
- `state_changed`: Update badge / unlock sections.
- `evidence_added`: Append to Evidence Panel.
- `execution_started`: Switch to Execution view.
- `execution_log`: Append line to logs.
- `execution_completed`: Update status.
- `verification_result`: Show final banner.

**Robustness**:
- Auto-reconnect on disconnect (Exponential backoff).
- Toast notification on connection loss.

---

## 6. Design System

- **Theme**: `dark` (Slate-900 bg, Slate-50 text).
- **Accent**: Indigo-500 (Primary).
- **Status Colors**:
    - **Success**: Emerald-500
    - **Warning**: Amber-500
    - **Error**: Rose-500
    - **Info**: Blue-400
- **Typography**: Inter (UI), JetBrains Mono (Code).

## UI Edge Cases (Mandatory)
- **Loading**: Show skeleton loader fetching incident detail.
- **Empty Evidence**: Show "No Evidence Collected" if array is empty.
- **No Recommendation**: Show "Analysis in Progress..." if state < RECOMMENDATION_READY.
- **Verifying**: Show "Verifying Fix..." spinner during VERIFYING state.

---

## 7. STRICT PROHIBITIONS (The "Instant Reject" List)

1.  **NO Cloud SDKs**: `aws-sdk`, `google-cloud-node` are BANNED in frontend.
2.  **NO Business Logic**: Formatting dates is okay; calculating "Risk Score" is NOT.
3.  **NO Optimistic UI**: Do not predict success. Wait for the server.
4.  **NO Hardcoded Alerts**: `if (alert.type === 'DiskFull')` is BANNED. UI must be generic.
5.  **NO HTML Injection**: All user content must be escaped. **Never** interpolate raw backend content into HTML attributes.
- Treat all string content as untrusted input.

---

## 8. Expected API Shape

```typescript
type IncidentState =
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
  | 'REJECTED';

interface Incident {
  incident_id: string;
  tenant_id: string;
  alert_type: string;
  state: IncidentState; // Enum matching backend
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  retry_count: number;
  evidence: EvidenceItem[];
  recommendation: Recommendation | null;
  executions: ExecutionLog[];
  timeline: TimelineEvent[];
  created_at: string;
}
```

## 9. Folder Structure
```
src/
  pages/
    IncidentList.jsx
    IncidentDetail.jsx
  components/
    common/
      StateBadge.jsx
      SeverityBadge.jsx
      ConfirmationModal.jsx
    incident/
      IncidentCard.jsx
      Timeline.jsx
      EvidencePanel.jsx
      RecommendationCard.jsx
      ExecutionLogs.jsx
  services/
    api.js       // Axios instance
    sse.js       // SSE connection manager
  hooks/
    useIncidents.js
    useIncidentDetail.js
  utils/
    formatters.js
```

## 10. Acceptance Criteria

- [ ] **Generic**: Renders a "Disk Full" alert and a "DB High CPU" alert identically without code changes.
- [ ] **State-Driven**: Manually changing backend state in DB immediately reflects in UI via SSE.
- [ ] **Safe**: Reviewer cannot execute an action without explicit confirmation.
- [ ] **Resilient**: SSE disconnects do not crash the app; it attempts to reconnect.

This skill defines the **ONLY** acceptable way to build the frontend.
