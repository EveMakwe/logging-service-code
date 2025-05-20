# ============Lambda function for creating logs===========================

resource "aws_lambda_function" "ingest_logs" {
  function_name = "${var.env}-ingest-logs"
  runtime       = "python3.12"
  handler       = "ingest_logs.lambda_handler"
  role          = aws_iam_role.ingest_logs_service.arn
  timeout       = 300

  source_code_hash = filebase64sha256("ingest_logs.zip")
  filename         = "ingest_logs.zip"

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.log_table.name
    }
  }
}



resource "aws_lambda_alias" "ingest_logs_alias" {
  name             = "${var.env}-ingest-logs-alias"
  description      = "An alias for the version of lambda"
  function_name    = "${var.env}-ingest-logs"
  function_version = "$LATEST"
  depends_on       = [aws_lambda_function.ingest_logs]
}


# ==========Lambda function for retrieving logs========================

resource "aws_lambda_function" "retrieve_logs" {
  function_name = "${var.env}-retrieve-logs"
  runtime       = "python3.12"
  handler       = "retrieve_logs.lambda_handler"
  timeout       = 300

  role = aws_iam_role.retrieve_log_service.arn

  source_code_hash = filebase64sha256("retrieve_logs.zip")
  filename         = "retrieve_logs.zip"



  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.log_table.name
    }
  }
  layers = [
    "arn:aws:lambda:${var.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:14"
  ]

}



resource "aws_lambda_alias" "retrieve_logs_alias" {
  name             = "${var.env}-retrieve-logs-alias"
  description      = "An alias for the version of lambda"
  function_name    = "${var.env}-retrieve-logs"
  function_version = "$LATEST"
  depends_on       = [aws_lambda_function.retrieve_logs]
}





