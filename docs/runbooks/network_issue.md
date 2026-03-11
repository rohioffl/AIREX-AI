# Runbook: Network Issue

## Alert Type
network_issue, port_check

## Symptoms
- High packet loss between services
- DNS resolution failures
- Connection timeouts to upstream services
- Port unreachable errors
- Network interface errors or drops
- Increased latency between availability zones

## Investigation Steps
1. Check connectivity: `ping`, `traceroute`, `mtr` to the target
2. Verify DNS resolution: `dig` or `nslookup` for the affected domain
3. Check security group / firewall rules — were any recently changed?
4. Verify the target port is listening: `netstat -tlnp` or `ss -tlnp`
5. Check for VPC/subnet routing issues
6. Review cloud provider status page for regional outages
7. Check if NACLs or WAF rules are blocking traffic

## Recommended Actions

### Low Risk
- **restart_service**: Restart the service to reset network connections and clear stale sockets. Risk: LOW.
- **flush_cache**: Flush DNS cache if resolution issues are suspected. Risk: LOW.

### Medium Risk
- **drain_node**: Remove the affected node if it has network connectivity issues. Risk: MEDIUM. Routes traffic to healthy nodes.
- **block_ip**: Block a specific IP if the issue is caused by a DDoS or abusive traffic source. Risk: MEDIUM.

## Escalation
If the issue is a cloud provider network outage, escalate to the infrastructure team and initiate the regional failover procedure. If packet loss exceeds 10%, consider emergency traffic rerouting.

## Resolution Criteria
- Network connectivity restored (0% packet loss)
- DNS resolution working correctly
- Port reachability confirmed
- Application connections to upstream services restored
- Latency within normal bounds (< 10ms intra-region)
