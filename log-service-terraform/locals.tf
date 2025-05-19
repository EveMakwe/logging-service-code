locals {
  name       = "${var.env}-${var.product}"
  account_id = data.aws_caller_identity.current.account_id ## Getting account ID from the aws_caller_identity data source from the main.tf file.
  tags = {
    Name    = local.name
    Env     = var.env
    Product = var.product
    Stack   = var.stack
  }
}