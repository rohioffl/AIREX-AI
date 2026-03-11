# Using Site24x7 API Data in AIREX

AIREX can leverage Site24x7 data beyond webhooks using the REST API client. This guide shows how to configure and use Site24x7 data.

## Configuration

### 1. Enable Site24x7 API Integration

Set these environment variables:

```bash
SITE24X7_ENABLED=true
SITE24X7_CLIENT_ID=your_client_id
SITE24X7_CLIENT_SECRET=your_client_secret
SITE24X7_REFRESH_TOKEN=your_refresh_token
```

### 2. Get OAuth2 Credentials

1. Go to **Site24x7** → **Admin** → **Developer** → **Add-Ons**
2. Create a new **Server-to-Server Add-On**
3. Copy:
   - **Client ID**
   - **Client Secret**
   - **Refresh Token** (generated after first authorization)

## Available Data Sources

### 1. Webhook Data (Already Active)

When Site24x7 sends webhooks, AIREX automatically extracts:

- `MONITORNAME` - Monitor display name
- `STATUS` - Current status (DOWN, UP, TROUBLE, CRITICAL)
- `MONITORTYPE` - Monitor type (URL, Server, EC2, etc.)
- `MONITORID` - Unique monitor identifier
- `INCIDENT_REASON` - Why the alert fired
- `INCIDENT_TIME` - When the incident occurred
- `FAILED_LOCATIONS` - Which monitoring locations failed
- `OUTAGE_DURATION` - How long the outage lasted
- `TAGS` - Monitor tags (used for cloud context)
- `MONITOR_DASHBOARD_LINK` - Direct link to monitor in Site24x7

**This data is stored in `incident.meta`** and available during investigation.

### 2. Site24x7 Probe (Automatic Enrichment)

The `Site24x7Probe` automatically runs during investigation for Site24x7 incidents and fetches:

#### Current Status
- Real-time status from Site24x7 API
- Last polled time
- Attribute value (e.g., response time, CPU %)
- Unit of measurement

#### Monitor Configuration
- Display name
- Monitor type
- Hostname/IP
- Poll interval
- Timeout settings
- Number of monitoring locations

#### Performance Metrics (Last 24h)
- Average response time
- Maximum response time
- Throughput

#### Availability Summary (Last 24h)
- Availability percentage
- Total downtime duration
- Number of outages

**This data appears in the Evidence panel** as a secondary probe.

### 3. REST API Client (Programmatic Access)

The `Site24x7Client` provides async methods to fetch data:

```python
from airex_core.monitoring.site24x7_client import Site24x7Client

# Initialize client (uses Redis for token caching)
client = Site24x7Client(redis=redis)

# Get monitor details
monitor = await client.get_monitor(monitor_id)
# Returns: display_name, type, hostname, poll_interval, locations, etc.

# Get current status
status = await client.get_current_status(monitor_id)
# Returns: status_name, last_polled_time, attribute_value, unit

# Get performance report
perf = await client.get_performance_report(monitor_id, period=1)
# period: 1=24h, 2=7d, 3=30d
# Returns: response_time (avg/max), throughput

# Get outage report
outages = await client.get_outage_report(monitor_id, period=1)
# Returns: outage history with timestamps and durations

# Get availability summary
availability = await client.get_availability_summary(monitor_id, period=1)
# Returns: availability_percentage, downtime_duration, no_of_outages

# Get log report (for log monitors)
logs = await client.get_log_report(
    monitor_id,
    start_date="2026-02-26T00:00:00+0530",
    end_date="2026-02-27T00:00:00+0530"
)

# List all monitors
all_monitors = await client.list_monitors()
# Returns: list of {monitor_id, display_name, type_name}

# Get status for all monitors
all_status = await client.get_all_current_status()
# Returns: list of current status for all monitors
```

## Use Cases

### 1. Enhanced Investigation Context

The Site24x7 probe automatically enriches incidents with:
- Historical performance trends
- Availability patterns
- Monitor configuration details

**This helps the AI:**
- Understand if this is a recurring issue
- See performance degradation trends
- Know monitor sensitivity (poll interval, timeout)

### 2. Custom Investigation Plugins

Create custom investigation plugins that use Site24x7 data:

```python
from airex_core.investigations.base import BaseInvestigation, ProbeResult
from airex_core.monitoring.site24x7_client import Site24x7Client

class CustomSite24x7Investigation(BaseInvestigation):
    async def investigate(self, incident_meta: dict) -> ProbeResult:
        monitor_id = incident_meta.get("MONITORID")
        if not monitor_id:
            return ProbeResult(...)
        
        client = Site24x7Client(redis=redis)
        
        # Fetch outage history to see if this is recurring
        outages = await client.get_outage_report(monitor_id, period=3)  # 30 days
        
        # Analyze pattern
        outage_count = len(outages.get("outages", []))
        if outage_count > 5:
            context = f"⚠️ This monitor has {outage_count} outages in the last 30 days - recurring issue pattern detected"
        else:
            context = "✅ This is an isolated incident"
        
        return ProbeResult(
            tool_name="custom_site24x7_analysis",
            raw_output=context,
            metrics={"outage_count_30d": outage_count}
        )
```

### 3. Proactive Health Checks

Use the health check service to proactively monitor Site24x7:

```python
# Already implemented in services/airex-core/airex_core/services/health_check_service.py
from airex_core.services.health_check_service import check_site24x7_monitors

health_checks = await check_site24x7_monitors(session, tenant_id, redis)
# Returns list of HealthCheck objects with:
# - monitor_id, monitor_name, monitor_type
# - current_status (from Site24x7 API)
# - last_checked_at
# - last_incident_id (if any)
```

**Access via API:**
```bash
GET /api/v1/health/monitors?refresh=true
```

### 4. Incident Correlation

Use Site24x7 data to correlate incidents:

```python
# Check if multiple monitors in the same group are down
client = Site24x7Client(redis=redis)
monitor = await client.get_monitor(monitor_id)
group_name = monitor.get("monitor_group_name")

# Get all monitors in the same group
all_monitors = await client.list_monitors()
group_monitors = [m for m in all_monitors if m.get("group_name") == group_name]

# Check their status
all_status = await client.get_all_current_status()
down_in_group = [
    s for s in all_status 
    if s.get("monitor_id") in [m["monitor_id"] for m in group_monitors]
    and s.get("status_name") == "DOWN"
]

if len(down_in_group) > 1:
    # Multiple monitors down in same group - likely infrastructure issue
    correlation_context = f"⚠️ {len(down_in_group)} monitors in group '{group_name}' are down - possible infrastructure failure"
```

### 5. Performance Trend Analysis

Analyze performance trends before incidents:

```python
# Get performance data for last 7 days
perf_7d = await client.get_performance_report(monitor_id, period=2)

# Compare with last 30 days
perf_30d = await client.get_performance_report(monitor_id, period=3)

avg_7d = perf_7d.get("response_time", {}).get("average", 0)
avg_30d = perf_30d.get("response_time", {}).get("average", 0)

if avg_7d > avg_30d * 1.5:
    trend = "📈 Performance degradation detected - 7d avg is 50%+ higher than 30d avg"
else:
    trend = "✅ Performance is within normal range"
```

### 6. Custom API Endpoints

Create custom endpoints to expose Site24x7 data:

```python
from fastapi import APIRouter
from airex_core.monitoring.site24x7_client import Site24x7Client

router = APIRouter()

@router.get("/monitors/{monitor_id}/performance")
async def get_monitor_performance(monitor_id: str, redis: Redis):
    """Get performance metrics for a monitor."""
    client = Site24x7Client(redis=redis)
    perf = await client.get_performance_report(monitor_id, period=1)
    return perf

@router.get("/monitors/{monitor_id}/outages")
async def get_monitor_outages(monitor_id: str, redis: Redis):
    """Get outage history for a monitor."""
    client = Site24x7Client(redis=redis)
    outages = await client.get_outage_report(monitor_id, period=3)
    return outages

@router.get("/monitors/{monitor_id}/summary")
async def get_monitor_summary(monitor_id: str, redis: Redis):
    """Get combined summary: details + status + performance."""
    client = Site24x7Client(redis=redis)
    summary = await client.get_summary(monitor_id)
    return summary
```

## Data Flow

```
Site24x7 Webhook
    ↓
AIREX receives alert
    ↓
Creates incident with webhook data in meta
    ↓
Investigation starts
    ↓
Site24x7Probe runs (if enabled)
    ↓
Fetches: status + details + performance + availability
    ↓
Adds to Evidence panel
    ↓
AI uses this context for recommendations
```

## Token Management

The `Site24x7Client` automatically handles OAuth2 token refresh:

1. **In-memory cache** - Tokens cached for 55 minutes
2. **Redis cache** - Tokens stored in Redis with TTL
3. **Auto-refresh** - Tokens refreshed from Zoho OAuth2 API when expired

**No manual token management needed** - the client handles everything.

## Best Practices

1. **Enable the probe** - Set `SITE24X7_ENABLED=true` to get automatic enrichment
2. **Use Redis** - Pass Redis instance to `Site24x7Client` for token caching
3. **Handle errors gracefully** - API calls may fail (rate limits, network issues)
4. **Cache monitor lists** - Use Redis cache for monitor inventory (already implemented in health checks)
5. **Respect rate limits** - Site24x7 API has rate limits; the client doesn't throttle automatically

## Troubleshooting

### Probe not running?
- Check `SITE24X7_ENABLED=true`
- Verify `SITE24X7_CLIENT_ID` and `SITE24X7_REFRESH_TOKEN` are set
- Ensure `incident.meta._source == "site24x7"`
- Verify `incident.meta.MONITORID` exists

### Token refresh failing?
- Verify OAuth2 credentials are correct
- Check network connectivity to `accounts.zoho.com`
- Review logs for token refresh errors

### API calls timing out?
- Site24x7 API may be slow; consider increasing timeouts
- Use async/await properly to avoid blocking
- Cache frequently accessed data (monitor lists, status)

## Example: Using Site24x7 Data in Recommendations

The AI recommendation engine can use Site24x7 data from evidence:

```python
# In recommendation_service.py, the AI prompt includes evidence
# Site24x7 probe data appears in evidence, so the AI can see:

"""
Evidence from site24x7_probe:
  Performance (Last 24h):
    response_time_avg: 2.5s
    response_time_max: 15.2s
  
  Availability (Last 24h):
    availability_percentage: 95.2%
    outage_count: 3
    downtime_duration: 4h 23m

This shows the monitor has been unstable with multiple outages.
The AI can factor this into its recommendation.
"""
```

## Next Steps

1. **Enable Site24x7 API** - Set environment variables
2. **Verify probe runs** - Check Evidence panel for Site24x7 data
3. **Create custom endpoints** - Expose Site24x7 data via API
4. **Build custom investigations** - Use Site24x7Client in your plugins
5. **Add to frontend** - Display Site24x7 metrics in UI
