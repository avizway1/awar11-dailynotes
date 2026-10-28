variable "ami_id" {
  description = "AMi id to use to launch my instance"
  type        = string
}

variable "instance_type" {
  type        = string
  description = "Instance configuration"
}

variable "name" {
  description = "name of ec2 instance"
  type        = string
}

variable "bucket_name" {
  description = "My created s3 bucket name"
  type        = string
}

variable "region" {
  description = "aws region to deloy resources"
  type        = string
}

variable "iamuser" {
  description = "name of iam user"
  type        = string
}