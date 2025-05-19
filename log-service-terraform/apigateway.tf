# ====================================== API Gateway =================================
resource "aws_api_gateway_rest_api" "log_service_api" {
  name        = "${local.name}-apigw"
  description = "API for log service"
}

resource "aws_api_gateway_resource" "log_resource" {
  rest_api_id = aws_api_gateway_rest_api.log_service_api.id
  parent_id   = aws_api_gateway_rest_api.log_service_api.root_resource_id
  path_part   = "logs"
}




resource "aws_api_gateway_integration" "post_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.log_service_api.id
  resource_id             = aws_api_gateway_resource.log_resource.id
  http_method             = aws_api_gateway_method.log_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.ingest_logs.invoke_arn
}

resource "aws_api_gateway_integration" "get_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.log_service_api.id
  resource_id             = aws_api_gateway_resource.log_resource.id
  http_method             = aws_api_gateway_method.log_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.retrieve_logs.invoke_arn
}

# =============================Lambda Permissions ======================================
resource "aws_lambda_permission" "allow_apigw_post" {
  statement_id  = "AllowAPIGatewayInvokePOST"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest_logs.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.log_service_api.execution_arn}/*/POST/logs"

}

resource "aws_lambda_permission" "allow_apigw_get" {
  statement_id  = "AllowAPIGatewayInvokeGET"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.retrieve_logs.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.log_service_api.execution_arn}/*/GET/logs"

}


# === =====================API Deployment ================================
resource "aws_api_gateway_deployment" "log_service_deployment" {
  rest_api_id = aws_api_gateway_rest_api.log_service_api.id

  triggers = {
    redeployment = sha1(jsonencode({
      post = aws_api_gateway_integration.post_lambda.id,
      get  = aws_api_gateway_integration.get_lambda.id
    }))
  }

  depends_on = [
    aws_api_gateway_method.log_post,
    aws_api_gateway_method.log_get
  ]
}

resource "aws_api_gateway_stage" "log_service_stage" {
  stage_name    = var.env
  rest_api_id   = aws_api_gateway_rest_api.log_service_api.id
  deployment_id = aws_api_gateway_deployment.log_service_deployment.id

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId",
      ip             = "$context.identity.sourceIp",
      caller         = "$context.identity.caller",
      user           = "$context.identity.user",
      requestTime    = "$context.requestTime",
      httpMethod     = "$context.httpMethod",
      resourcePath   = "$context.resourcePath",
      status         = "$context.status",
      protocol       = "$context.protocol",
      responseLength = "$context.responseLength"
    })

  }
  xray_tracing_enabled = true

  depends_on = [aws_api_gateway_account.apigw_account]
}


#=======================API Gateway Method Settings (Throttling and Logging) ===========================
resource "aws_api_gateway_method_settings" "log_service_throttling" {
  rest_api_id = aws_api_gateway_rest_api.log_service_api.id
  stage_name  = aws_api_gateway_stage.log_service_stage.stage_name
  method_path = "*/*"

  settings {
    throttling_rate_limit  = 1000
    throttling_burst_limit = 2000
    logging_level          = "INFO"
  }
}




# ============================Cognito authorizer ==========================================================
resource "aws_api_gateway_authorizer" "log_service_cognito" {
  name            = "cognito-log-service"
  rest_api_id     = aws_api_gateway_rest_api.log_service_api.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [aws_cognito_user_pool.log_service.arn]
  identity_source = "method.request.header.Authorization"
}

resource "aws_api_gateway_method" "log_post" {
  rest_api_id      = aws_api_gateway_rest_api.log_service_api.id
  resource_id      = aws_api_gateway_resource.log_resource.id
  http_method      = "POST"
  authorization    = "COGNITO_USER_POOLS"
  authorizer_id    = aws_api_gateway_authorizer.log_service_cognito.id
  api_key_required = false
}

resource "aws_api_gateway_method" "log_get" {
  rest_api_id      = aws_api_gateway_rest_api.log_service_api.id
  resource_id      = aws_api_gateway_resource.log_resource.id
  http_method      = "GET"
  authorization    = "COGNITO_USER_POOLS"
  authorizer_id    = aws_api_gateway_authorizer.log_service_cognito.id
  api_key_required = false
}





# # === API Key + Usage Plan ===
# resource "aws_api_gateway_api_key" "log_api_key" {
#   name        = " ${var.env}-log-api-key"
#   description = "API key for log service"
#   enabled     = true
# }

# resource "aws_api_gateway_usage_plan" "log_usage_plan" {
#   name = "${var.env}-log-usage-plan"

#   api_stages {
#     api_id = aws_api_gateway_rest_api.log_service_api.id
#     stage  = aws_api_gateway_stage.log_service_stage.stage_name
#   }
# }

# resource "aws_api_gateway_usage_plan_key" "log_plan_key" {
#   key_id        = aws_api_gateway_api_key.log_api_key.id
#   key_type      = "API_KEY"
#   usage_plan_id = aws_api_gateway_usage_plan.log_usage_plan.id
# }