# AWS S3 Configuration for Multi-Cloud Support

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

variable "environment" {
  default = "prod"
}

variable "project_name" {
  default = "dataforge"
}

# S3 Bucket for Data Lake
resource "aws_s3_bucket" "datalake" {
  bucket = "${var.project_name}-datalake-${var.environment}"

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket_versioning" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Bronze Partition
resource "aws_s3_object" "bronze" {
  bucket = aws_s3_bucket.datalake.id
  key    = "bronze/"
}

# Silver Partition
resource "aws_s3_object" "silver" {
  bucket = aws_s3_bucket.datalake.id
  key    = "silver/"
}

# Gold Partition
resource "aws_s3_object" "gold" {
  bucket = aws_s3_bucket.datalake.id
  key    = "gold/"
}

# IAM Role for Spark Cluster
resource "aws_iam_role" "spark_role" {
  name = "${var.project_name}-spark-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_role_policy" "spark_policy" {
  name = "${var.project_name}-spark-policy"
  role = aws_iam_role.spark_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.datalake.arn,
          "${aws_s3_bucket.datalake.arn}/*"
        ]
      }
    ]
  })
}

output "s3_bucket_name" {
  value = aws_s3_bucket.datalake.id
}

output "spark_role_arn" {
  value = aws_iam_role.spark_role.arn
}
