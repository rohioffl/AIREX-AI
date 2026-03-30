const WORKSPACE_SCOPE_KEY = 'airex-workspace-scope'

export function getWorkspaceScope() {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(WORKSPACE_SCOPE_KEY)
}

export function setWorkspaceScope(scope) {
  if (typeof window === 'undefined') return
  if (scope) {
    window.localStorage.setItem(WORKSPACE_SCOPE_KEY, scope)
  } else {
    window.localStorage.removeItem(WORKSPACE_SCOPE_KEY)
  }
}

export function getAllTenantsScopeValue(organizationId) {
  return organizationId ? `all:${organizationId}` : null
}

export function isAllTenantsScopeForOrganization(organizationId) {
  const expectedScope = getAllTenantsScopeValue(organizationId)
  return Boolean(expectedScope && getWorkspaceScope() === expectedScope)
}

export function getTenantScopeValue(tenantId) {
  return tenantId ? `tenant:${tenantId}` : null
}
