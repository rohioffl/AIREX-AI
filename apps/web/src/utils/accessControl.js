export function normalizeRole(role) {
  const normalized = (role || 'operator').toLowerCase()
  if (normalized.startsWith('org_')) return normalized.replace(/^org_/, '')
  if (normalized.startsWith('tenant_')) return normalized.replace(/^tenant_/, '')
  return normalized
}

function uniqueById(items) {
  const seen = new Set()
  return items.filter((item) => {
    if (!item?.id || seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}

export function deriveOrganizations(sessionContext) {
  const memberships = Array.isArray(sessionContext?.organization_memberships)
    ? sessionContext.organization_memberships
    : []
  const activeOrganization = sessionContext?.active_organization
    ? [sessionContext.active_organization]
    : []
  const tenantOrganizations = Array.isArray(sessionContext?.tenants)
    ? sessionContext.tenants
        .filter((tenant) => tenant.organization_id)
        .map((tenant) => ({
          id: tenant.organization_id,
          name: tenant.organization_name || tenant.organization_slug || 'Organization',
          slug: tenant.organization_slug || '',
          role: 'tenant_member',
        }))
    : []

  return uniqueById([...memberships, ...activeOrganization, ...tenantOrganizations])
}

function hasRoleInMemberships(memberships, role) {
  return Array.isArray(memberships)
    && memberships.some((membership) => normalizeRole(membership?.role) === role)
}

function getActiveTenantMembership(auth) {
  const activeTenantId = auth?.activeTenantId
  if (!activeTenantId || !Array.isArray(auth?.tenantMemberships)) return null
  return auth.tenantMemberships.find((membership) => membership.id === activeTenantId) || null
}

export function isPlatformAdmin(auth) {
  return normalizeRole(auth?.user?.role) === 'platform_admin'
}

export function hasGlobalAdminAccess(auth) {
  const role = normalizeRole(auth?.user?.role)
  return role === 'admin' || role === 'platform_admin'
}

export function canAccessOrganizationsAdmin(auth) {
  if (hasGlobalAdminAccess(auth)) return true
  return hasRoleInMemberships(auth?.organizationMemberships, 'admin')
}

export function canAccessTenantAdmin(auth) {
  if (hasGlobalAdminAccess(auth)) return true
  if (normalizeRole(auth?.activeOrganization?.role) === 'admin') return true
  return normalizeRole(getActiveTenantMembership(auth)?.role) === 'admin'
}

export function canAccessRoute(auth, access) {
  switch (access) {
    case 'platform_admin':
      return isPlatformAdmin(auth)
    case 'organizations_admin':
      return canAccessOrganizationsAdmin(auth)
    case 'tenant_admin':
      return canAccessTenantAdmin(auth)
    default:
      return true
  }
}
