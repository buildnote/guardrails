
terraform {
  backend "s3" {
    bucket       = "company-terraform-state"
    key          = "live/network.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
  }
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "company-artifacts"
}
