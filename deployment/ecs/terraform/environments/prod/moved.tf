moved {
  from = aws_cloudfront_distribution.frontend
  to   = module.frontend.aws_cloudfront_distribution.frontend
}

moved {
  from = aws_cloudfront_origin_access_control.frontend
  to   = module.frontend.aws_cloudfront_origin_access_control.frontend
}

moved {
  from = aws_cloudwatch_log_group.api
  to   = module.platform.aws_cloudwatch_log_group.api
}

moved {
  from = aws_cloudwatch_log_group.langfuse
  to   = module.platform.aws_cloudwatch_log_group.langfuse
}

moved {
  from = aws_cloudwatch_log_group.litellm
  to   = module.platform.aws_cloudwatch_log_group.litellm
}

moved {
  from = aws_cloudwatch_log_group.worker
  to   = module.platform.aws_cloudwatch_log_group.worker
}

moved {
  from = aws_db_instance.airex
  to   = module.platform.aws_db_instance.airex
}

moved {
  from = aws_db_instance.langfuse
  to   = module.platform.aws_db_instance.langfuse
}

moved {
  from = aws_db_subnet_group.main
  to   = module.platform.aws_db_subnet_group.main
}

moved {
  from = aws_ecr_repository.api
  to   = module.platform.aws_ecr_repository.api
}

moved {
  from = aws_ecr_repository.litellm
  to   = module.platform.aws_ecr_repository.litellm
}

moved {
  from = aws_ecr_repository.worker
  to   = module.platform.aws_ecr_repository.worker
}

moved {
  from = aws_ecs_cluster.main
  to   = module.platform.aws_ecs_cluster.main
}

moved {
  from = aws_ecs_service.api
  to   = module.platform.aws_ecs_service.api
}

moved {
  from = aws_ecs_service.langfuse
  to   = module.platform.aws_ecs_service.langfuse
}

moved {
  from = aws_ecs_service.litellm
  to   = module.platform.aws_ecs_service.litellm
}

moved {
  from = aws_ecs_service.worker
  to   = module.platform.aws_ecs_service.worker
}

moved {
  from = aws_ecs_task_definition.api
  to   = module.platform.aws_ecs_task_definition.api
}

moved {
  from = aws_ecs_task_definition.langfuse
  to   = module.platform.aws_ecs_task_definition.langfuse
}

moved {
  from = aws_ecs_task_definition.litellm
  to   = module.platform.aws_ecs_task_definition.litellm
}

moved {
  from = aws_ecs_task_definition.worker
  to   = module.platform.aws_ecs_task_definition.worker
}

moved {
  from = aws_eip.nat["0"]
  to   = module.vpc.aws_eip.nat["0"]
}

moved {
  from = aws_eip.nat["1"]
  to   = module.vpc.aws_eip.nat["1"]
}

moved {
  from = aws_elasticache_replication_group.redis
  to   = module.platform.aws_elasticache_replication_group.redis
}

moved {
  from = aws_elasticache_subnet_group.main
  to   = module.platform.aws_elasticache_subnet_group.main
}

moved {
  from = aws_iam_role.execution_role
  to   = module.platform.aws_iam_role.execution_role
}

moved {
  from = aws_iam_role.task_role
  to   = module.platform.aws_iam_role.task_role
}

moved {
  from = aws_iam_role_policy.execution_secrets_access
  to   = module.platform.aws_iam_role_policy.execution_secrets_access
}

moved {
  from = aws_iam_role_policy_attachment.execution_default
  to   = module.platform.aws_iam_role_policy_attachment.execution_default
}

moved {
  from = aws_internet_gateway.main[0]
  to   = module.vpc.aws_internet_gateway.main[0]
}

moved {
  from = aws_lb.public
  to   = module.platform.aws_lb.public
}

moved {
  from = aws_lb_listener.https
  to   = module.platform.aws_lb_listener.https
}

moved {
  from = aws_lb_listener_rule.api_host_path
  to   = module.platform.aws_lb_listener_rule.api_host_path
}

moved {
  from = aws_lb_listener_rule.langfuse_path[0]
  to   = module.platform.aws_lb_listener_rule.langfuse_path[0]
}

moved {
  from = aws_lb_listener_rule.litellm_path[0]
  to   = module.platform.aws_lb_listener_rule.litellm_path[0]
}

moved {
  from = aws_lb_target_group.api
  to   = module.platform.aws_lb_target_group.api
}

moved {
  from = aws_lb_target_group.langfuse
  to   = module.platform.aws_lb_target_group.langfuse
}

moved {
  from = aws_lb_target_group.litellm
  to   = module.platform.aws_lb_target_group.litellm
}

moved {
  from = aws_nat_gateway.main["0"]
  to   = module.vpc.aws_nat_gateway.main["0"]
}

moved {
  from = aws_nat_gateway.main["1"]
  to   = module.vpc.aws_nat_gateway.main["1"]
}

moved {
  from = aws_route_table.private["0"]
  to   = module.vpc.aws_route_table.private["0"]
}

moved {
  from = aws_route_table.private["1"]
  to   = module.vpc.aws_route_table.private["1"]
}

moved {
  from = aws_route_table.public[0]
  to   = module.vpc.aws_route_table.public[0]
}

moved {
  from = aws_route_table_association.private["0"]
  to   = module.vpc.aws_route_table_association.private["0"]
}

moved {
  from = aws_route_table_association.private["1"]
  to   = module.vpc.aws_route_table_association.private["1"]
}

moved {
  from = aws_route_table_association.public["0"]
  to   = module.vpc.aws_route_table_association.public["0"]
}

moved {
  from = aws_route_table_association.public["1"]
  to   = module.vpc.aws_route_table_association.public["1"]
}

moved {
  from = aws_s3_bucket.frontend
  to   = module.frontend.aws_s3_bucket.frontend
}

moved {
  from = aws_s3_bucket_policy.frontend
  to   = module.frontend.aws_s3_bucket_policy.frontend
}

moved {
  from = aws_s3_bucket_public_access_block.frontend
  to   = module.frontend.aws_s3_bucket_public_access_block.frontend
}

moved {
  from = aws_secretsmanager_secret.backend_database_url
  to   = module.platform.aws_secretsmanager_secret.backend_database_url
}

moved {
  from = aws_secretsmanager_secret.backend_redis_url
  to   = module.platform.aws_secretsmanager_secret.backend_redis_url
}

moved {
  from = aws_secretsmanager_secret.backend_secret_key
  to   = module.platform.aws_secretsmanager_secret.backend_secret_key
}

moved {
  from = aws_secretsmanager_secret.langfuse_database_url
  to   = module.platform.aws_secretsmanager_secret.langfuse_database_url
}

moved {
  from = aws_secretsmanager_secret.langfuse_nextauth_secret
  to   = module.platform.aws_secretsmanager_secret.langfuse_nextauth_secret
}

moved {
  from = aws_secretsmanager_secret.langfuse_public_key
  to   = module.platform.aws_secretsmanager_secret.langfuse_public_key
}

moved {
  from = aws_secretsmanager_secret.langfuse_salt
  to   = module.platform.aws_secretsmanager_secret.langfuse_salt
}

moved {
  from = aws_secretsmanager_secret.langfuse_secret_key
  to   = module.platform.aws_secretsmanager_secret.langfuse_secret_key
}

moved {
  from = aws_secretsmanager_secret.litellm_master_key
  to   = module.platform.aws_secretsmanager_secret.litellm_master_key
}

moved {
  from = aws_secretsmanager_secret_version.backend_database_url
  to   = module.platform.aws_secretsmanager_secret_version.backend_database_url
}

moved {
  from = aws_secretsmanager_secret_version.backend_redis_url
  to   = module.platform.aws_secretsmanager_secret_version.backend_redis_url
}

moved {
  from = aws_secretsmanager_secret_version.backend_secret_key
  to   = module.platform.aws_secretsmanager_secret_version.backend_secret_key
}

moved {
  from = aws_secretsmanager_secret_version.langfuse_database_url
  to   = module.platform.aws_secretsmanager_secret_version.langfuse_database_url
}

moved {
  from = aws_secretsmanager_secret_version.langfuse_nextauth_secret
  to   = module.platform.aws_secretsmanager_secret_version.langfuse_nextauth_secret
}

moved {
  from = aws_secretsmanager_secret_version.langfuse_public_key
  to   = module.platform.aws_secretsmanager_secret_version.langfuse_public_key
}

moved {
  from = aws_secretsmanager_secret_version.langfuse_salt
  to   = module.platform.aws_secretsmanager_secret_version.langfuse_salt
}

moved {
  from = aws_secretsmanager_secret_version.langfuse_secret_key
  to   = module.platform.aws_secretsmanager_secret_version.langfuse_secret_key
}

moved {
  from = aws_secretsmanager_secret_version.litellm_master_key
  to   = module.platform.aws_secretsmanager_secret_version.litellm_master_key
}

moved {
  from = aws_security_group.alb
  to   = module.platform.aws_security_group.alb
}

moved {
  from = aws_security_group.data
  to   = module.platform.aws_security_group.data
}

moved {
  from = aws_security_group.ecs_services
  to   = module.platform.aws_security_group.ecs_services
}

moved {
  from = aws_ssm_parameter.cors_origins
  to   = module.platform.aws_ssm_parameter.cors_origins
}

moved {
  from = aws_ssm_parameter.langfuse_host
  to   = module.platform.aws_ssm_parameter.langfuse_host
}

moved {
  from = aws_ssm_parameter.litellm_host
  to   = module.platform.aws_ssm_parameter.litellm_host
}

moved {
  from = aws_ssm_parameter.llm_embedding_model
  to   = module.platform.aws_ssm_parameter.llm_embedding_model
}

moved {
  from = aws_ssm_parameter.llm_fallback_model
  to   = module.platform.aws_ssm_parameter.llm_fallback_model
}

moved {
  from = aws_ssm_parameter.llm_primary_model
  to   = module.platform.aws_ssm_parameter.llm_primary_model
}

moved {
  from = aws_subnet.private["0"]
  to   = module.vpc.aws_subnet.private["0"]
}

moved {
  from = aws_subnet.private["1"]
  to   = module.vpc.aws_subnet.private["1"]
}

moved {
  from = aws_subnet.public["0"]
  to   = module.vpc.aws_subnet.public["0"]
}

moved {
  from = aws_subnet.public["1"]
  to   = module.vpc.aws_subnet.public["1"]
}

moved {
  from = aws_vpc.main[0]
  to   = module.vpc.aws_vpc.main[0]
}

moved {
  from = random_password.app_secret_key
  to   = module.platform.random_password.app_secret_key
}

moved {
  from = random_password.db_airex_password
  to   = module.platform.random_password.db_airex_password
}

moved {
  from = random_password.db_langfuse_password
  to   = module.platform.random_password.db_langfuse_password
}

moved {
  from = random_password.langfuse_nextauth_secret_value
  to   = module.platform.random_password.langfuse_nextauth_secret_value
}

moved {
  from = random_password.langfuse_public_key_value
  to   = module.platform.random_password.langfuse_public_key_value
}

moved {
  from = random_password.langfuse_salt_value
  to   = module.platform.random_password.langfuse_salt_value
}

moved {
  from = random_password.langfuse_secret_key_value
  to   = module.platform.random_password.langfuse_secret_key_value
}

moved {
  from = random_password.litellm_master_key_value
  to   = module.platform.random_password.litellm_master_key_value
}

moved {
  from = random_password.redis_auth_token
  to   = module.platform.random_password.redis_auth_token
}
