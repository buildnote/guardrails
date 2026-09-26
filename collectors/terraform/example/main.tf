terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "s3" {
    bucket       = "widget-terraform-state"
    key          = "live/widget.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "api_token" {
  type      = string
  sensitive = true
}

module "events" {
  source  = "terraform-aws-modules/sqs/aws"
  version = "4.2.1"

  name = "widget-events"
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "widget-artifacts"
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.id
}
