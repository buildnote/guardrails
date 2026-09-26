
terraform {
  backend "s3" {
    bucket       = "widget-terraform-state"
    key          = "live/widget.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
    secret_key   = "AKIAIOSFODNN7SECRETLITERAL"
  }
}
