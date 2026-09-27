terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    genesyscloud = {
      source  = "MyPureCloud/genesyscloud"
      version = "~> 1.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# 1. S3 Storage Bucket for Large Files & Async Results
resource "aws_s3_bucket" "ocr_storage" {
  bucket_prefix = "genesys-ocr-storage-"
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "ocr_s3_lifecycle" {
  bucket = aws_s3_bucket.ocr_storage.id

  rule {
    id     = "auto-cleanup-temp-ocr-files"
    status = "Enabled"

    expiration {
      days = 7 # Automatically expire document caches after 7 days
    }
  }
}

# 2. SQS Queue & Dead Letter Queue (DLQ)
resource "aws_sqs_queue" "ocr_dlq" {
  name                      = "genesys-ocr-dlq"
  message_retention_seconds = 1209600 # 14 Days
}

resource "aws_sqs_queue" "ocr_queue" {
  name                       = "genesys-ocr-async-queue"
  visibility_timeout_seconds = 900 # 15 minutes for long PDF textract jobs
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ocr_dlq.arn
    maxReceiveCount     = 3
  })
}

# 3. IAM Role & Consolidated Policies
resource "aws_iam_role" "apprunner_ocr_role" {
  name = "genesys-ocr-apprunner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "tasks.apprunner.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "ocr_apprunner_policy" {
  name        = "genesys-ocr-apprunner-policy"
  description = "Permissions for App Runner to interact with Textract, S3, and SQS"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["textract:DetectDocumentText", "textract:StartDocumentTextDetection", "textract:GetDocumentTextDetection"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.ocr_storage.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.ocr_queue.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ocr_attach" {
  role       = aws_iam_role.apprunner_ocr_role.name
  policy_arn = aws_iam_policy.ocr_apprunner_policy.arn
}

# 4. AWS App Runner Service
resource "aws_apprunner_service" "ocr_service" {
  service_name = "genesys-cloud-ocr-service"

  source_configuration {
    image_repository {
      image_identifier      = var.container_image_uri
      image_repository_type = "ECR_PUBLIC"

      image_configuration {
        port = "5000"
        runtime_environment_variables = {
          API_KEY              = var.ocr_api_key
          AWS_REGION           = var.aws_region
          S3_BUCKET_NAME       = aws_s3_bucket.ocr_storage.bucket
          SQS_QUEUE_URL        = aws_sqs_queue.ocr_queue.url
          SYNC_PAGE_THRESHOLD = "15"
        }
      }
    }
    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = "1024" # 1 vCPU
    memory            = "2048" # 2 GB RAM
    instance_role_arn = aws_iam_role.apprunner_ocr_role.arn
  }
}