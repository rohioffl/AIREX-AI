# Runbook: Log Anomaly Detected

## Alert Type
log_anomaly

## Symptoms
- Sudden spike in error log volume
- New error patterns appearing in logs
- Stack traces or panic messages
- Authentication failure bursts
- Unusual access patterns detected

## Investigation Steps
1. Identify the error pattern: grep for ERROR, FATAL, PANIC in recent logs
2. Check if the errors correlate with a specific service or endpoint
3. Review timestamps — did errors start after a deployment or config change?
4. Check if the pattern indicates a security issue (brute force, injection attempts)
5. Correlate with metrics — is there a corresponding spike in latency or error rates?
6. Check if log volume itself is causing disk pressure

## Recommended Actions

### Low Risk
- **restart_service**: Restart the service if errors indicate a corrupted state. Risk: LOW.
- **flush_cache**: Clear caches if errors suggest stale data. Risk: LOW.

### Medium Risk
- **block_ip**: Block suspicious IP addresses if log anomaly indicates an attack. Risk: MEDIUM.
- **toggle_feature_flag**: Disable a feature flag if errors correlate with a specific feature. Risk: MEDIUM.
- **rollback_deployment**: Revert if errors started after a deployment. Risk: MEDIUM-HIGH.

## Escalation
If the log anomaly indicates a security breach (credential stuffing, SQL injection, unauthorized access), escalate to the security team immediately. Preserve logs for forensic analysis.

## Resolution Criteria
- Error rate returns to baseline
- No new anomalous patterns detected
- Root cause identified and documented
- Corrective action taken (patch, config fix, or block)
