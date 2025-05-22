resource "aws_cognito_user_pool" "log_service" {
  name = "${local.name}-users"
}

resource "aws_cognito_user_pool_client" "log_service" {
  name                                 = "${local.name}-client"
  user_pool_id                         = aws_cognito_user_pool.log_service.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code", "implicit"]
  allowed_oauth_scopes                 = ["openid"]
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_ADMIN_USER_PASSWORD_AUTH"
  ]
  supported_identity_providers = ["COGNITO"]
  callback_urls                = ["https://example.com/callback"]
  logout_urls                  = ["https://example.com/logout"]
}

resource "random_password" "apigwuser" {
  length  = 16
  special = true
}


