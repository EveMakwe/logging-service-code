#Default: Terraform Cloud Backend 
# This block configures remote state to be stored in Terraform Cloud.

terraform {
  cloud {
    organization = "lynnevem"

    workspaces {
      name = "logging-service"
    }
  }
}


# Alternative: S3 Backend (Uncomment to use)
# If you do NOT have access to Terraform Cloud, comment out the above "cloud" block
# and uncomment the block below. Update the values to match your AWS environment.
#
# backend "s3" {
#   bucket         = "your-tf-state-bucket-name"    # Replace with your S3 bucket name
#   key            = "logging-service/terraform.tfstate"
#   region         = "af-south-1"                   # Replace with your AWS region
#   encrypt        = true
#   dynamodb_table = "your-tf-lock-table"           # (Recommended) DynamoDB table for state locking
# }
#}


provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

# Retrieve AWS account ID and caller identity
data "aws_caller_identity" "current" {}
