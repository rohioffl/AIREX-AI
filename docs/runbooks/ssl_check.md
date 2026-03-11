# Runbook: SSL Certificate Issue

## Alert Type
ssl_check

## Symptoms
- SSL certificate expiring within 30 days
- SSL certificate already expired
- Certificate chain incomplete or invalid
- TLS handshake failures reported by clients
- Mixed content warnings in browser

## Investigation Steps
1. Check certificate expiry: `openssl s_client -connect host:443 | openssl x509 -noout -dates`
2. Verify the full certificate chain is present
3. Check if auto-renewal (Let's Encrypt, ACM) is configured and working
4. Verify the certificate matches the domain being served
5. Check for certificate pinning issues in mobile clients
6. Review if the certificate was recently rotated and if all services picked up the new cert

## Recommended Actions

### High Risk
- **rotate_credentials**: Trigger certificate rotation or renewal. Risk: HIGH. Requires careful validation that new cert is deployed across all endpoints. For ACM-managed certs, this triggers re-issuance. For manually managed certs, this initiates the renewal workflow.

### Medium Risk
- **restart_service**: Restart services to pick up newly deployed certificates. Risk: MEDIUM. Required after certificate file replacement.

## Escalation
If the certificate is already expired and causing user-facing errors, escalate immediately. Emergency certificate issuance may be required.

## Resolution Criteria
- Certificate validity confirmed (expiry > 30 days from now)
- Full certificate chain validates successfully
- No TLS handshake errors in logs
- SSL monitoring check passes
