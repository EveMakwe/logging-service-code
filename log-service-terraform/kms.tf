resource "aws_kms_key" "logs_key" {
  description             = "Key for encrypting log data"
  enable_key_rotation     = true
  deletion_window_in_days = 7
}