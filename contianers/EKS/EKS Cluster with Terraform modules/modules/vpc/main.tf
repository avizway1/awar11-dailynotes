################################################################################
# VPC child module
#
# Wraps the community VPC module and adds the subnet tags the AWS Load Balancer
# Controller / in-tree cloud provider use to discover subnets for ELBs.
################################################################################

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.6"

  name = var.name
  cidr = var.vpc_cidr

  azs             = var.azs
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  # Single NAT gateway keeps the demo cheap. Set single_nat_gateway = false
  # (one NAT per AZ) for production.
  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = var.single_nat_gateway
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = var.tags
}
