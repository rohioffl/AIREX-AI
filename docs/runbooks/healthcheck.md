# Runbook: Health Check Failure

## Alert Type
healthcheck, heartbeat_check

## Symptoms
- Health check endpoint returning non-200 status
- Load balancer marking instances as unhealthy
- Service heartbeat missed for 3+ consecutive intervals
- Dependent services reporting connection failures

## Investigation Steps
1. Verify the health check endpoint directly: `curl -v https://service/health`
2. Check if the application process is running
3. Check application logs for crash loops, startup failures, or dependency errors
4. Verify network connectivity between the health checker and the service
5. Check if dependent services (database, Redis, external APIs) are healthy
6. Review recent deployments or configuration changes

## Recommended Actions

### Low Risk
- **restart_service**: Restart the failed service. Risk: LOW. Most common fix for transient failures. Safe if service has graceful restart.

### Medium Risk
- **restart_container**: Restart the container if running in Docker/K8s. Risk: MEDIUM. Effective for container-level issues like filesystem corruption or port binding.
- **drain_node**: Remove node from load balancer while investigating. Risk: MEDIUM. Prevents user-facing errors.
- **scale_up**: Add replacement instances if multiple nodes are unhealthy. Risk: MEDIUM.

### High Risk
- **rollback_deployment**: If health checks started failing after a deployment. Risk: HIGH. Reverts application to previous version.

## Escalation
If more than 50% of instances are unhealthy, or if restarts do not resolve the issue within 10 minutes, escalate to the on-call engineer.

## Resolution Criteria
- Health check endpoint returning 200
- Load balancer shows all instances healthy
- No error spikes in application logs
- Heartbeat signal restored for 5+ consecutive intervals
