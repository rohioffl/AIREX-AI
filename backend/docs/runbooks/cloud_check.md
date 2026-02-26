# Runbook: Cloud Infrastructure Issue

## Alert Type
cloud_check

## Symptoms
- Cloud resource health check failing
- Instance status checks failing (system or instance)
- Auto-scaling group not maintaining desired capacity
- Cloud API errors or throttling
- Spot instance interruptions
- Resource quota limits reached

## Investigation Steps
1. Check instance status in the cloud console (EC2, GCE, Azure VM)
2. Review system logs for hardware errors or kernel panics
3. Check if the issue is isolated or affecting an entire availability zone
4. Verify auto-scaling group configuration and launch template
5. Check cloud provider service health dashboard
6. Review IAM permissions if API errors are occurring

## Recommended Actions

### Low Risk
- **restart_service**: Restart affected services on the instance. Risk: LOW.

### Medium Risk
- **scale_up**: Launch replacement instances in healthy AZs. Risk: MEDIUM.
- **drain_node**: Remove unhealthy instances from target groups. Risk: MEDIUM.
- **restart_container**: Restart containers if running ECS/EKS. Risk: MEDIUM.

### High Risk
- **rollback_deployment**: Revert launch template if instance failures started after an AMI update. Risk: HIGH.

## Escalation
If an entire availability zone is affected, initiate the AZ evacuation procedure. If multiple regions are impacted, activate the disaster recovery plan.

## Resolution Criteria
- All instance status checks passing
- Auto-scaling group at desired capacity
- No cloud API errors
- Application health checks green across all instances
