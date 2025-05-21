resource "aws_secretsmanager_secret" "cognito_apigwuser_password" {
  name = "${local.name}-cognito-apigwuser-temps"
}

resource "aws_secretsmanager_secret_version" "cognito_apigwuser_password" {
  secret_id     = aws_secretsmanager_secret.cognito_apigwuser_password.id
  secret_string = random_password.apigwuser.result
}

data "aws_secretsmanager_secret_version" "apigwuser_password" {
  secret_id  = aws_secretsmanager_secret.cognito_apigwuser_password.id
  depends_on = [aws_secretsmanager_secret_version.cognito_apigwuser_password]
}

resource "aws_cognito_user" "apigwuser" {
  user_pool_id             = aws_cognito_user_pool.log_service.id
  username                 = "apigwuser"
  temporary_password       = data.aws_secretsmanager_secret_version.apigwuser_password.secret_string
  message_action           = "SUPPRESS"
  force_alias_creation     = true
  desired_delivery_mediums = []
  lifecycle {
    ignore_changes = [
      temporary_password,
    ]
  }
}