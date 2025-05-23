
#============ === DynamoDB Table for Logs =============================
resource "aws_dynamodb_table" "log_table" {
  name         = "${local.name}-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  range_key    = "datetime"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "datetime"
    type = "S"
  }

  attribute {
    name = "severity"
    type = "S"
  }

  attribute {
    name = "partition"
    type = "S"
  }

  global_secondary_index {
    name            = "severityindex"
    hash_key        = "severity"
    range_key       = "datetime"
    projection_type = "ALL"
  }

  global_secondary_index {
    name               = "alldatetimeindex"
    hash_key           = "partition"
    range_key          = "datetime"
    projection_type    = "INCLUDE"
    non_key_attributes = ["id", "severity", "message"]
  }

  point_in_time_recovery {
    enabled = true # Add this
  }

  # =============Enable encryption at rest with KMS ====================
  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.logs_key.arn
  }
}

