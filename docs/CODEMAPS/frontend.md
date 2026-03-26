<!-- Generated: 2026-03-16 | Files scanned: 384 | Token estimate: ~800 -->

# Frontend Architecture

## Stack
React 19, Vite 7, Tailwind v4, Axios, Recharts — `apps/web/src/`

## Entry
`main.jsx` → `App.jsx` → React Router v6 routes

## Page Tree
```
/                    LandingPage.jsx
/login               LoginPage.jsx         (Google + email/password)
/set-password        SetPasswordPage.jsx
/dashboard           DashboardPage.jsx     (MetricCards, AlertHistoryWidget, SystemGraph)
/incidents           IncidentList.jsx      (filterable table, SSE live updates)
/incidents/:id       IncidentDetail.jsx    (SSE-driven full detail view)
/alerts              AlertsPage.jsx        (alert feed, AlertRow)
/live                LiveFeed.jsx          (real-time SSE incident stream)
/live-monitoring     LiveMonitoringPage.jsx
/health-checks       HealthChecksPage.jsx  (dashboard + history + manual run)
/analytics           AnalyticsPage.jsx     (Recharts charts)
/runbooks            RunbooksPage.jsx      (CRUD + ingest + search)
/knowledge-base      KnowledgeBasePage.jsx
/patterns            PatternsPage.jsx
/proactive           ProactiveAlertsPage.jsx
/reports             ReportsPage.jsx
/settings            SettingsPage.jsx
/profile             ProfilePage.jsx
/users               UserManagementPage.jsx (admin)
/super-admin         SuperAdminPage.jsx     (super-admin)
/admin/login         AdminLoginPage.jsx     (platform admin auth)
/admin               PlatformAdminPage.jsx  (orgs, tenants, platform ops)
/admin/organizations OrganizationsAdminPage.jsx
/admin/workspaces    TenantWorkspaceAdminPage.jsx
/admin/integrations  IntegrationsAdminPage.jsx
/rejected            RejectedPage.jsx
*                    NotFoundPage.jsx
```

## Component Hierarchy
```
Layout.jsx (sidebar + topbar + LeadApprovalPanel)
  └─ IncidentDetail.jsx
       ├─ StatePipeline.jsx           (animated state progress bar)
       ├─ AIAnalysisPanel.jsx         (evidence + recommendation sections)
       │    ├─ EvidencePanel.jsx
       │    ├─ RecommendationCard.jsx
       │    ├─ AIRecommendationApproval.jsx
       │    ├─ ApprovalControls.jsx
       │    └─ ReasoningChain.jsx
       ├─ InvestigationTimeline.jsx
       ├─ ExecutionLogs.jsx           (Terminal.jsx)
       ├─ VerificationResult.jsx
       ├─ ResolutionOutcome.jsx
       ├─ Timeline.jsx / TimelineChart.jsx
       ├─ RelatedIncidentsPanel.jsx
       ├─ CorrelationGroup.jsx
       ├─ AutoRunbook.jsx
       ├─ FallbackHistory.jsx
       ├─ Site24x7MetricsPanel.jsx
       ├─ IncidentChat.jsx
       ├─ CommentsPanel.jsx
       ├─ AssignmentPanel.jsx
       └─ AnomalyBadge.jsx
  └─ IncidentList.jsx
       └─ IncidentCard.jsx
            └─ StateBadge.jsx / SeverityBadge.jsx
```

## State Management
```
Context providers (apps/web/src/context/):
  AuthContext.jsx    user, token, login/logout/loginWithGoogle, refreshToken
  ThemeContext.jsx   dark/light theme
  ToastContext.jsx   global toast notifications

Hooks (apps/web/src/hooks/):
  useIncidentDetail.js   SSE subscribe, incident data, approve/reject/retry actions
  useIncidents.js        incident list + polling
  useKeyboardShortcuts.js  keyboard nav
```

## API Layer
```
apps/web/src/services/api.js         ALL API calls (76 exported functions)
apps/web/src/services/auth.js        login, logout, googleLogin, refreshToken
apps/web/src/services/sse.js         SSE connection manager (auto-reconnect)
apps/web/src/services/tokenStorage.js  access/refresh token in memory/localStorage
```

## SSE Event Types
```
incident_created, state_changed, evidence_added,
execution_started, execution_log, execution_completed, verification_result
```

## UI Rules
- State checks: always `state === 'EXACT_VALUE'` — no inference
- No optimistic UI — wait for SSE state_changed event
- No inline fetch() — all calls via api.js (Axios instance)
- No dangerouslySetInnerHTML — all content as text
- No cloud SDK imports
- No hardcoded alert type checks

## Key Utilities
```
utils/formatters.js     duration, bytes, timestamps
utils/errorHandler.js   Axios error normalization
types/api.d.ts          TypeScript type definitions (18 types)
```

## Tests
- Framework: Vitest + React Testing Library
- Location: `apps/web/src/__tests__/` (18 test files, ~165 tests)
- Run: `cd apps/web && npm run test`
