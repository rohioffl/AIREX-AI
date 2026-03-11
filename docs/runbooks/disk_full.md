# Runbook: Disk Full

## Alert Type
disk_full

## Symptoms
- Disk usage exceeds 90% on one or more partitions
- Application write failures or errors
- Log rotation failures
- Database transaction log growth
- Container image layer accumulation

## Investigation Steps
1. Identify which partition is full using `df -h`
2. Find large files with `du -sh /* | sort -rh | head -20`
3. Check log file sizes — are logs being rotated properly?
4. Check for core dumps, temp files, or orphaned uploads
5. Verify if old deployment artifacts or Docker images are accumulating
6. Check database WAL/binlog size

## Recommended Actions

### Low Risk
- **flush_cache**: Clear temporary files, old logs, and cached artifacts. Risk: LOW. Only removes expendable data.

### Medium Risk
- **resize_disk**: Expand the disk volume. Risk: MEDIUM. Requires filesystem extension after volume resize. Works with EBS, Persistent Disks, and managed disks.
- **restart_service**: Restart services that may be holding deleted file handles open. Risk: MEDIUM.

### High Risk
- **rollback_deployment**: If disk filled due to a bad deployment with excessive logging. Risk: HIGH. Reverts to previous version.

## Escalation
If disk is at 99%+ and critical writes are failing, escalate immediately. Consider emergency log truncation and database maintenance.

## Resolution Criteria
- Disk utilization below 80%
- No write errors in application logs
- Log rotation confirmed working
- Monitoring confirms stable disk usage trend
