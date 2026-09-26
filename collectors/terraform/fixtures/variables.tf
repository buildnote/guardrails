
variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "api_token" {
  type      = string
  sensitive = true
  default   = "%s"
}

variable "domain_name" {
  type = string
}
