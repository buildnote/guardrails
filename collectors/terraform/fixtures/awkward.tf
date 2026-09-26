
locals {
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${var.bucket}/*"
      },
    ]
  })

  # a comment with a } brace and a "quote in it
  greeting = <<-EOT
    hello }
    EOT

  names = [for name in var.names : lower(name)]
  byName = { for name in var.names : name => upper(name) }
  scaled = var.enabled ? 1 : 0
}

resource "aws_iam_policy" "read" {
  policy = local.policy // trailing comment with a { brace
}
