variable "aws_region" {
  description = "AWS region to deploy into"
  type = string
  default = "ap-south-1"
}

variable "ami_id" {
  description = "AMI ID to launch instance"
  type = string
  default = "ami-022374b883d9d7931"
}

variable "instance_type" {
  type = string
}

variable "key_name" {
  type = string
  default = "awar11-na"
}

variable "instance_count" {
  type = number
}

variable "environment" {
  type = string
}
