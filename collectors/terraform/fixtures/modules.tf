
module "events" {
  source  = "terraform-aws-modules/sqs/aws"
  version = "4.2.1"

  name = "widget-events"
}

module "policy" {
  source = "git::https://github.com/company/terraform-policy.git?ref=v1.4.0"
}

module "site" {
  source = "../../modules/static-site"

  domain_name = var.domain_name
}
