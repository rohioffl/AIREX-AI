# Runbook: HTTP Check Failure

## Alert Type
http_check, api_check

## Symptoms
- HTTP endpoint returning 5xx errors
- Response time exceeding SLA threshold
- API availability dropping below 99.9%
- Connection refused or timeout errors from monitoring
- Elevated error rates in load balancer metrics

## Investigation Steps
1. Test the endpoint directly: `curl -v -o /dev/null -w "%{http_code} %{time_total}" URL`
2. Check application logs for errors, exceptions, or panic traces
3. Verify backend dependencies (database, cache, external APIs) are healthy
4. Check if the issue is isolated to one instance or fleet-wide
5. Review recent deployments — did a bad release go out?
6. Check rate limiting or WAF rules that might be blocking legitimate traffic

## Recommended Actions

### Low Risk
- **restart_service**: Restart the web server / application. Risk: LOW. Resolves most transient failures like stuck threads or connection pool exhaustion.

### Medium Risk
- **scale_up**: Add capacity if the failure is due to overload. Risk: MEDIUM.
- **drain_node**: Remove failing instance from load balancer. Risk: MEDIUM.
- **restart_container**: Restart the container if running in Docker/K8s. Risk: MEDIUM.

### High Risk
- **rollback_deployment**: Revert to the previous version if failure correlates with a deployment. Risk: HIGH. Reverts all code changes.

## Escalation
If error rate exceeds 50% or all instances are returning 5xx, escalate immediately. Consider enabling maintenance mode.

## Resolution Criteria
- Endpoint returning 200 OK consistently
- Error rate below 0.1%
- Response time within SLA (p99 < 1000ms)
- All instances marked healthy in load balancer
