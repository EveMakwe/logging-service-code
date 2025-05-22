terraform {
  cloud {
    organization = "lynnevem"

    workspaces {
      name = "logging-service"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

# Retrieve AWS account ID and caller identity
data "aws_caller_identity" "current" {}
