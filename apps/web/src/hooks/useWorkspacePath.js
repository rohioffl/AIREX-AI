import { useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/**
 * Returns helpers for building workspace-scoped paths.
 *
 * Org users (no tenantSlug in URL) use `/:orgSlug/<page>` paths.
 * Tenant users use `/:orgSlug/:tenantSlug/<page>` paths.
 *
 * `isOrgScoped` is true when there is no `:tenantSlug` in the current route,
 * meaning the user is viewing the org-wide / "all workspaces" view.
 */
export function useWorkspacePath() {
  const params = useParams()
  const { activeTenant, activeOrganization } = useAuth()

  const orgSlug = params.orgSlug || activeOrganization?.slug || String(activeOrganization?.id || '')
  const tenantSlug = params.tenantSlug || activeTenant?.name || String(activeTenant?.id || '')
  const isOrgScoped = !params.tenantSlug

  function buildPath(page) {
    if (!params.tenantSlug && orgSlug) return `/${orgSlug}/${page}`
    if (!orgSlug || !tenantSlug) return `/${page}`
    return `/${orgSlug}/${tenantSlug}/${page}`
  }

  const basePath = !params.tenantSlug
    ? (orgSlug ? `/${orgSlug}` : '')
    : (orgSlug && tenantSlug ? `/${orgSlug}/${tenantSlug}` : '')

  return { orgSlug, tenantSlug, buildPath, basePath, isOrgScoped }
}
