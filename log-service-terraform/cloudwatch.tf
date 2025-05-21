resource "aws_cloudwatch_log_group" "ingest_logs_group" {
  name              = "/aws/lambda/${var.env}-ingest-logs"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "retrieve_log_group" {
  name              = "/aws/lambda/${var.env}-retrieve-logs"
  retention_in_days = 7
}

#Required CloudWatch log group for API Gateway access logs
resource "aws_cloudwatch_log_group" "apigw_logs" {
  name              = "/aws/apigateway/${local.name}-apigw"
  retention_in_days = 7

}
