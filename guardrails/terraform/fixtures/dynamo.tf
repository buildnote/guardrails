
terraform {
  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "live/network.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "company-terraform-locks"
  }
}
