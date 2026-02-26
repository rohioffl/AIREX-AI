# Runbook: High CPU Usage

## Alert Type
cpu_high

## Symptoms
- CPU utilization exceeds 85% sustained for 5+ minutes
- Application response times degrade
- Process scheduling delays observed
- System load average exceeds core count

## Investigation Steps
1. Identify the top CPU-consuming processes using `top` or `htop`
2. Check if the spike is caused by application code, cron jobs, or system processes
3. Review recent deployments or config changes that may have triggered the spike
4. Check if auto-scaling policies are in place and functioning
5. Verify if the CPU spike correlates with increased traffic or request volume

## Recommended Actions

### Low Risk
- **restart_service**: Restart the affected service if a known memory leak or runaway thread is suspected. Risk: LOW. This is safe if the service has health checks and load balancer draining.

### Medium Risk
- **scale_up**: Add additional instances to the auto-scaling group to distribute load. Risk: MEDIUM. Requires monitoring to confirm new instances are healthy.
- **drain_node**: Remove the affected node from the load balancer to stop new traffic while investigating. Risk: MEDIUM.

### High Risk
- **kill_process**: Terminate the specific runaway process. Risk: HIGH. Only use if the process is confirmed non-critical or is a zombie/orphan.

## Escalation
If CPU remains above 90% after scaling and restart, escalate to the infrastructure team. Check for cryptomining or compromised processes.

## Resolution Criteria
- CPU utilization drops below 75% sustained
- Application response times return to baseline (p99 < 500ms)
- No error rate increase in downstream services
