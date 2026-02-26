# Runbook: Database Issue

## Alert Type
database_check

## Symptoms
- Database connection pool exhaustion
- Slow query execution (queries exceeding 5s)
- Replication lag exceeding threshold
- Database CPU or memory at capacity
- Lock contention / deadlocks detected
- Storage approaching capacity

## Investigation Steps
1. Check active connections: `SELECT count(*) FROM pg_stat_activity`
2. Find slow queries: `SELECT * FROM pg_stat_activity WHERE state = 'active' AND duration > interval '5s'`
3. Check replication lag on replicas
4. Review database CPU, memory, IOPS metrics in monitoring
5. Check for long-running transactions or lock waits
6. Verify connection pool settings in application configuration
7. Check if recent schema migrations or index changes caused issues

## Recommended Actions

### Low Risk
- **flush_cache**: Clear database query cache if stale plans are suspected. Risk: LOW.
- **restart_service**: Restart the application to reset connection pools. Risk: LOW.

### Medium Risk
- **restart_container**: Restart the database container (dev/staging only). Risk: MEDIUM. Causes brief downtime.
- **resize_disk**: Expand database storage volume if running low. Risk: MEDIUM.

### High Risk
- **kill_process**: Terminate specific long-running queries causing lock contention. Risk: HIGH. May cause data inconsistency if transaction is interrupted.

## Escalation
If the database is unresponsive or replication lag exceeds 5 minutes, escalate to the DBA team. Consider read-only mode if write performance is degraded.

## Resolution Criteria
- Connection pool utilization below 80%
- Query execution times within normal range (p99 < 1s)
- Replication lag under 1 second
- No lock contention or deadlocks
- Database CPU below 75%
