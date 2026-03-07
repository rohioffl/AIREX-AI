#!/usr/bin/env bash
set -euo pipefail

required_env=(
  ECS_CLUSTER
  ECS_MIGRATE_TASKDEF
  PRIVATE_SUBNET_1
  PRIVATE_SUBNET_2
  TASK_SG
)

for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env: $name" >&2
    exit 1
  fi
done

aws ecs run-task \
  --cluster "$ECS_CLUSTER" \
  --launch-type FARGATE \
  --task-definition "$ECS_MIGRATE_TASKDEF" \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNET_1,$PRIVATE_SUBNET_2],securityGroups=[$TASK_SG],assignPublicIp=DISABLED}" >/dev/null

echo "Migration task started: $ECS_MIGRATE_TASKDEF"
