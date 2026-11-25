################################################################################
# Root variables -- values are supplied in terraform.tfvars
################################################################################

# General
variable "region" {
  description = "AWS region to deploy into"
  type        = string
}

variable "environment" {
  description = "Environment name, used in default tags"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "Name of the EKS cluster (also prefixes the VPC and IAM role names)"
  type        = string
}

# Networking
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "azs" {
  description = "Availability zones to spread the subnets across (must be in var.region)"
  type        = list(string)
}

variable "private_subnets" {
  description = "Private subnet CIDRs, one per AZ, inside vpc_cidr"
  type        = list(string)

  validation {
    condition     = alltrue([for c in var.private_subnets : can(cidrhost(c, 0))])
    error_message = "Every private subnet must be a valid CIDR block."
  }
}

variable "public_subnets" {
  description = "Public subnet CIDRs, one per AZ, inside vpc_cidr"
  type        = list(string)

  validation {
    condition     = alltrue([for c in var.public_subnets : can(cidrhost(c, 0))])
    error_message = "Every public subnet must be a valid CIDR block."
  }
}

variable "enable_nat_gateway" {
  description = "Create NAT gateway(s) for the private subnets"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway (cheap) instead of one per AZ (HA)"
  type        = bool
  default     = true
}

# EKS control plane
variable "kubernetes_version" {
  description = "Kubernetes control plane version"
  type        = string
}

variable "endpoint_public_access" {
  description = "Expose the Kubernetes API endpoint publicly"
  type        = bool
  default     = true
}

# Managed node group
variable "node_group_name" {
  description = "Name of the managed node group"
  type        = string
  default     = "default"
}

variable "node_ami_type" {
  description = "AMI type for the worker nodes"
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "instance_types" {
  description = "Instance types for the managed node group"
  type        = list(string)
}

variable "min_size" {
  description = "Minimum number of worker nodes"
  type        = number
}

variable "max_size" {
  description = "Maximum number of worker nodes"
  type        = number
}

variable "desired_size" {
  description = "Desired number of worker nodes"
  type        = number

  validation {
    condition     = var.desired_size >= var.min_size && var.desired_size <= var.max_size
    error_message = "desired_size must be between min_size and max_size."
  }
}

variable "node_disk_size" {
  description = "Root EBS volume size (GiB) for worker nodes"
  type        = number
}
