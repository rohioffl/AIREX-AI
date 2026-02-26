# Runbook: High Memory Usage

## Alert Type
memory_high

## Symptoms
- Memory utilization exceeds 85% on the host
- OOM killer activity in kernel logs
- Application processes being killed unexpectedly
- Swap usage increasing significantly
- Slow garbage collection cycles

## Investigation Steps
1. Check memory usage per process with `ps aux --sort=-%mem`
2. Review application heap dumps or memory profiles if available
3. Check for memory leaks — is usage monotonically increasing over time?
4. Verify if caching layers (Redis, Memcached) are sized correctly
5. Check recent deployments for changes that may increase memory footprint
6. Review container memory limits if running in Docker/Kubernetes

## Recommended Actions

### Low Risk
- **flush_cache**: Clear application or system caches to free memory immediately. Risk: LOW. Cache will repopulate naturally. May cause temporary latency increase.
- **restart_service**: Restart the service to reclaim leaked memory. Risk: LOW if service has graceful shutdown and health checks.

### Medium Risk
- **scale_up**: Add instances to distribute memory load. Risk: MEDIUM. Effective if workload is distributable.
- **restart_container**: Restart the container to reset memory usage. Risk: MEDIUM.

### High Risk
- **kill_process**: Kill the specific memory-hogging process. Risk: HIGH. Data loss possible if process has in-flight work.

## Escalation
If memory usage exceeds 95% and OOM kills are occurring, escalate immediately. Consider emergency scaling or traffic shedding.

## Resolution Criteria
- Memory utilization below 75%
- No OOM killer activity in logs
- Application response times stable
- Swap usage minimal (< 5% of total swap)
