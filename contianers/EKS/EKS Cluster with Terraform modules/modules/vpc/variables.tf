variable "name" {
  description = "Name of the VPC"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "azs" {
  description = "Availability zones to spread the subnets across"
  type        = list(string)
}

variable "private_subnets" {
  description = "CIDR blocks for the private subnets (one per AZ, same order as azs)"
  type        = list(string)
}

variable "public_subnets" {
  description = "CIDR blocks for the public subnets (one per AZ, same order as azs)"
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Create NAT gateway(s) so private subnets can reach the internet"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway instead of one per AZ"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags applied to every VPC resource"
  type        = map(string)
  default     = {}
}
