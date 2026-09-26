
resource "aws_s3_bucket" "logs" {
  bucket = "widget-logs"
}

data "aws_caller_identity" "current" {}
