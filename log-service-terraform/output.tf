output "api_url" {
  value = "https://${aws_api_gateway_rest_api.log_service_api.id}.execute-api.${var.region}.amazonaws.com/${aws_api_gateway_stage.log_service_stage.stage_name}/logs"
}


output "dynamodb_table_arn" {
  value = aws_dynamodb_table.log_table.arn
}

output "create_log_role_arn" {
  value = aws_iam_role.ingest_logs_service.arn
}

output "retrieve_log_role_arn" {
  value = aws_iam_role.retrieve_log_service.arn
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.log_service.id
}

output "cognito_user_pool_arn" {
  value = aws_cognito_user_pool.log_service.arn
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.log_service.id
}

output "cognito_issuer_url" {
  value = "https://cognito-idp.us-east-1.amazonaws.com/${aws_cognito_user_pool.log_service.id}"
}

output "apigwuser_username" {
  value = aws_cognito_user.apigwuser.username
}


#