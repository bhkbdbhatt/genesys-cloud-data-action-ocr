variable "aws_region" {
  type        = string
  description = "AWS Region to deploy App Runner."
  default     = "us-east-1"
}

variable "ocr_api_key" {
  type        = string
  description = "Secret API key used by Genesys to authenticate calls to App Runner."
  sensitive   = true
}

variable "genesys_client_id" {
  type        = string
  description = "Genesys Cloud OAuth Client ID."
}

variable "genesys_client_secret" {
  type        = string
  description = "Genesys Cloud OAuth Client Secret."
  sensitive   = true
}

variable "genesys_aws_region" {
  type        = string
  description = "Genesys Cloud Region (e.g., us-east-1, eu-west-1, ap-southeast-2)."
  default     = "us-east-1"
}

variable "container_image_uri" {
  type        = string
  description = "Docker image URI from ECR Public."
  default     = "public.ecr.aws/your-alias/genesys-cloud-ocr-blueprint:latest"
}