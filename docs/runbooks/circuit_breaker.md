# Runbook: LLM Circuit Breaker

## Alert
**LLMCircuitBreakerOpen** — The AI circuit breaker has tripped.

## What it means
The circuit breaker opens when the LLM provider fails more than
`LLM_CIRCUIT_BREAKER_THRESHOLD` (default: 3) consecutive times.
While open, all recommendation requests are fast-failed and incidents
escalate immediately rather than waiting for AI responses.

## Diagnosis

1. Check circuit breaker state in Redis:
   ```bash
   docker-compose exec redis redis-cli GET airex:circuit_breaker
   ```

2. Check recent AI failures:
   ```bash
   docker-compose logs --tail=50 worker | grep "ai_failure\|circuit_breaker"
   ```

3. Check LLM provider status:
   - OpenAI: https://status.openai.com
   - Google AI: https://status.cloud.google.com

4. Check `LITELLM_*` environment variables are correct.

## Remediation

### Wait for auto-recovery
The circuit breaker auto-resets after `LLM_CIRCUIT_BREAKER_COOLDOWN`
seconds (default: 300s / 5 minutes). The half-open state will test
one request before fully closing.

### Manual reset
```bash
docker-compose exec redis redis-cli DEL airex:circuit_breaker
```

### Switch LLM provider
```bash
# In .env, change to fallback model
LLM_PRIMARY_MODEL=gpt-3.5-turbo
docker-compose restart backend worker
```

## Prevention
- Use a local model as primary with cloud fallback
- Monitor `airex_circuit_breaker_state` and `airex_ai_failure_total`
- Set up provider-specific health checks
