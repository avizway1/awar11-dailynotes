################################################################################
# terraform.tfvars -- the single place to set values for this deployment.
# Terraform loads this file automatically on plan/apply.
################################################################################

# General
region       = "ap-south-1"
environment  = "dev"
cluster_name = "ekswithavinash"

# Networking
vpc_cidr        = "10.0.0.0/16"
azs             = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
private_subnets = ["10.0.0.0/20", "10.0.16.0/20", "10.0.32.0/20"]
public_subnets  = ["10.0.48.0/24", "10.0.49.0/24", "10.0.50.0/24"]

enable_nat_gateway = true
single_nat_gateway = true # set false for one NAT per AZ (production)

# EKS control plane
kubernetes_version     = "1.36"
endpoint_public_access = true

# Managed node group
node_group_name = "ng-default"
node_ami_type   = "AL2023_x86_64_STANDARD"
instance_types  = ["c7i-flex.large"]
min_size        = 1
max_size        = 3
desired_size    = 2
node_disk_size  = 30
