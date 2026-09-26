
variable "vault_token" {
  type = string
}

resource "aws_vpc" "this" {
  cidr_block = "10.0.0.0/16"
}
