output "vpc_id" {
  value = var.create_vpc ? aws_vpc.main[0].id : null
}

output "public_subnet_ids" {
  value = var.create_vpc ? [for subnet in aws_subnet.public : subnet.id] : []
}

output "private_subnet_ids" {
  value = var.create_vpc ? [for subnet in aws_subnet.private : subnet.id] : []
}
