const ACTIVE_ORGANIZATION_KEY = 'airex-active-organization-id'

export function getActiveOrganizationIdOverride() {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(ACTIVE_ORGANIZATION_KEY)
}

export function setActiveOrganizationIdOverride(organizationId) {
  if (typeof window === 'undefined') return
  if (organizationId) {
    window.localStorage.setItem(ACTIVE_ORGANIZATION_KEY, organizationId)
  } else {
    window.localStorage.removeItem(ACTIVE_ORGANIZATION_KEY)
  }
}
