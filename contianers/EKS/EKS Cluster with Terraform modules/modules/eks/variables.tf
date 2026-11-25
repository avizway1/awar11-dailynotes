variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes control plane version"
  type        = string
}

variable "endpoint_public_access" {
  description = "Expose the Kubernetes API endpoint publicly"
  type        = bool
  default     = true
}

variable "vpc_id" {
  description = "ID of the VPC the cluster runs in"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs (normally private) for the control plane ENIs and worker nodes"
  type        = list(string)
}

variable "node_group_name" {
  description = "Key/name of the managed node group"
  type        = string
  default     = "default"
}

variable "node_ami_type" {
  description = "AMI type for the managed node group"
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
  default     = 1
}

variable "max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 3
}

variable "desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "node_disk_size" {
  description = "Root EBS volume size (GiB) for worker nodes"
  type        = number
  default     = 80
}

variable "tags" {
  description = "Extra tags applied to every EKS resource"
  type        = map(string)
  default     = {}
}
