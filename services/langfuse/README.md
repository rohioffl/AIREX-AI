# Langfuse Service

This service is deployed on ECS using the pinned image `langfuse/langfuse:2`.

Production variables should come from AWS Secrets Manager and SSM Parameter Store.

Required runtime variables:

- `DATABASE_URL`
- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `SALT`
- `TELEMETRY_ENABLED`

Recommended production value:

- `TELEMETRY_ENABLED=false`
