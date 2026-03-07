resource "aws_acm_certificate" "alb_wildcard" {
  count             = var.certificate_arn_ap_south_1 == "" ? 1 : 0
  domain_name       = "*.${var.domain_root}"
  validation_method = "DNS"

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-alb-cert"
  })
}

resource "aws_acm_certificate" "cloudfront_frontend" {
  provider          = aws.us_east_1
  count             = var.frontend_certificate_arn_us_east_1 == "" ? 1 : 0
  domain_name       = var.frontend_domain
  validation_method = "DNS"

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-frontend-cert"
  })
}

locals {
  alb_certificate_arn = var.certificate_arn_ap_south_1 != "" ? var.certificate_arn_ap_south_1 : aws_acm_certificate.alb_wildcard[0].arn
  cf_certificate_arn  = var.frontend_certificate_arn_us_east_1 != "" ? var.frontend_certificate_arn_us_east_1 : aws_acm_certificate.cloudfront_frontend[0].arn
}
