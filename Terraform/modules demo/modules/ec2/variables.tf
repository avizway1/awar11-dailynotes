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