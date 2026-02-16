# Runbook: Dead Letter Queue Cleanup

## Alert
**DLQNotEmpty** / **DLQCritical** — Tasks have failed and landed in the DLQ.

## Diagnosis

1. Check DLQ contents:
   ```bash
   docker-compose exec redis redis-cli LRANGE airex:dlq 0 -1
   ```

2. Parse entries to see which tasks failed:
   ```bash
   docker-compose exec redis redis-cli LRANGE airex:dlq 0 -1 | python3 -m json.tool
   ```

3. Check worker logs for error details:
   ```bash
   docker-compose logs --tail=100 worker | grep "task_sent_to_dlq"
   ```

## Remediation

### Re-process failed tasks
```bash
# For each DLQ entry, re-enqueue manually via the seed script
python backend/scripts/seed_demo.py
```

### Clear the DLQ (after investigation)
```bash
docker-compose exec redis redis-cli DEL airex:dlq
```

### Common causes
- **Database connection failures**: Check Postgres health and connection pool
- **Redis timeouts**: Check Redis memory and connection count
- **LLM provider outage**: Check circuit breaker state
- **Invalid incident data**: Check webhook payload validation

## Prevention
- Monitor `airex_dlq_size` metric
- Set up alerts at thresholds of 5 (warning) and 20 (critical)
- Review task retry configuration in `WorkerSettings`
