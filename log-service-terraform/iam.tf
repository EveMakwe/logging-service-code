# === IAM Assume Role Policy for Lambda ===
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# === IAM Role for ingest-logs Lambda ===
resource "aws_iam_role" "ingest_logs_service" {
  name               = "${var.env}-ingest-logs-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# === IAM Policy for ingest-logs Lambda ===
resource "aws_iam_policy" "ingest_logs_policy" {
  name = "${var.env}-ingest-logs-policy"
  path = "/"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = ["dynamodb:PutItem"],
        Resource = aws_dynamodb_table.log_table.arn
      },

      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.logs_key.arn
      },

      # {
      #   Effect = "Allow"
      #   Action = [
      #     "cognito-idp:GetUser",
      #     "cognito-idp:ListUsers"
      #   ]
      #   Resource = aws_cognito_user_pool.log_service_pool.arn
      # },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups"
        ],
        Resource = "${aws_cloudwatch_log_group.ingest_logs_group.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ingest_logs_service_attachment" {
  role       = aws_iam_role.ingest_logs_service.name
  policy_arn = aws_iam_policy.ingest_logs_policy.arn
}

# === IAM Role for Retrieve-Log Lambda ===
resource "aws_iam_role" "retrieve_log_service" {
  name               = "${var.env}-retrieve-log-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# === IAM Policy for Retrieve-Log Lambda ===
resource "aws_iam_policy" "retrieve_log_policy" {
  name = "${var.env}-retrieve-log-policy"
  path = "/"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "dynamodb:GetItem",
          "dynamodb:DescribeTable",
          "dynamodb:Scan",
          "dynamodb:Query"
        ],
        Resource = [
          aws_dynamodb_table.log_table.arn,
          "${aws_dynamodb_table.log_table.arn}/index/severityindex",
          "${aws_dynamodb_table.log_table.arn}/index/alldatetimeindex"

        ]
      },

      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.logs_key.arn
      },
      # {
      #   Effect = "Allow"
      #   Action = [
      #     "cognito-idp:GetUser",
      #     "cognito-idp:ListUsers"
      #   ]
      #   Resource = aws_cognito_user_pool.log_service_pool.arn
      # },

      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups"
        ],
        Resource = "${aws_cloudwatch_log_group.retrieve_log_group.arn}:*"
      }

    ]
  })
}

resource "aws_iam_role_policy_attachment" "retrieve_log_service_attachment" {
  role       = aws_iam_role.retrieve_log_service.name
  policy_arn = aws_iam_policy.retrieve_log_policy.arn
}


# === IAM Assume Role Policy for APIGateway ===
data "aws_iam_policy_document" "apigw_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["apigateway.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}


resource "aws_iam_role" "apigw_cloudwatch" {
  name               = "${var.env}-apigw-cloudwatch-logs-role"
  assume_role_policy = data.aws_iam_policy_document.apigw_assume_role.json
}

resource "aws_iam_role_policy_attachment" "apigw_cloudwatch_attach" {
  role       = aws_iam_role.apigw_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

#
resource "aws_api_gateway_account" "apigw_account" {
  cloudwatch_role_arn = aws_iam_role.apigw_cloudwatch.arn
}


