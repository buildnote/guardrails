
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.4.0"
    }
  }
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "company-artifacts"
}
