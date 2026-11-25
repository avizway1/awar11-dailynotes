################################################################################
# Root module
#
# Wires the child modules together. All inputs come from terraform.tfvars;
# nothing environment-specific is hard-coded here.
################################################################################

module "vpc" {
  source = "./modules/vpc"

  name            = "${var.cluster_name}-vpc"
  vpc_cidr        = var.vpc_cidr
  azs             = var.azs
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway
}

module "eks" {
  source = "./modules/eks"

  cluster_name           = var.cluster_name
  kubernetes_version     = var.kubernetes_version
  endpoint_public_access = var.endpoint_public_access

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids

  node_group_name = var.node_group_name
  node_ami_type   = var.node_ami_type
  instance_types  = var.instance_types
  min_size        = var.min_size
  max_size        = var.max_size
  desired_size    = var.desired_size
  node_disk_size  = var.node_disk_size
}
