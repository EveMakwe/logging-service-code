variable "region" {
  type        = string
  default     = "us-east-1"
  description = "AWS Region [string]"
}

variable "env" {
  description = "Environment [string]"
}

variable "stack" {
  description = "Stack Name for the set of resources [string]"
}

variable "product" {
  type        = string
  default     = "Games-Global"
  description = "Top Level Resources Identification [string]"
}
