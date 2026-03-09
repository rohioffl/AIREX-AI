# Terraform Layout

Active Terraform entrypoint:

- `deployment/ecs/terraform/environments/prod`

Module layout:

- `deployment/ecs/terraform/modules/vpc`
- `deployment/ecs/terraform/modules/platform`
- `deployment/ecs/terraform/modules/frontend`

Legacy flat-root files were archived to:

- `deployment/ecs/terraform/_legacy_flat_root`

## Production Workflow

```bash
cd deployment/ecs/terraform/environments/prod
terraform init -reconfigure -backend-config=backend.hcl
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

## Notes

- Remote state is configured from `deployment/ecs/terraform/environments/prod/backend.hcl`
- Production values live in `deployment/ecs/terraform/environments/prod/terraform.tfvars`
- The `moved.tf` file preserves state continuity from the old flat layout to the module layout
- Do not run Terraform from `deployment/ecs/terraform/_legacy_flat_root`
