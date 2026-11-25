################################################################################
# EKS child module
#
# Control plane + core add-ons + one managed node group, wrapping the community
# EKS module. The VPC/subnets are passed in from the vpc child module.
################################################################################

data "aws_partition" "current" {}

locals {
  policy_prefix = "arn:${data.aws_partition.current.partition}:iam::aws:policy"
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.25"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  # Public endpoint so kubectl works from a laptop. Restrict or disable for production.
  endpoint_public_access = var.endpoint_public_access

  # Grants the identity running terraform cluster-admin via an EKS access entry.
  enable_cluster_creator_admin_permissions = true

  # Control plane IAM role. The module attaches AmazonEKSClusterPolicy on its own;
  # eksctl's ServiceRole also carries AmazonEKSVPCResourceController (security groups
  # for pods / Windows IPAM), so add it here to end up with the same role.
  iam_role_name            = "${var.cluster_name}-cluster-role"
  iam_role_use_name_prefix = false
  iam_role_additional_policies = {
    AmazonEKSVPCResourceController = "${local.policy_prefix}/AmazonEKSVPCResourceController"
  }

  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids

  # before_compute = true installs these BEFORE the node group is created.
  addons = {
    coredns = {}

    eks-pod-identity-agent = {
      before_compute = true
    }

    kube-proxy = {
      before_compute = true
    }

    vpc-cni = {
      before_compute = true
    }
  }

  eks_managed_node_groups = {
    (var.node_group_name) = {
      ami_type       = var.node_ami_type
      instance_types = var.instance_types

      min_size     = var.min_size
      max_size     = var.max_size
      desired_size = var.desired_size

      # ---------------------------------------------------------------------
      # Node instance role -- the equivalent of eksctl's NodeInstanceRole.
      #
      # create_iam_role defaults to true, so the module already builds a role
      # with an ec2.amazonaws.com trust policy, attaches AmazonEKSWorkerNodePolicy,
      # AmazonEC2ContainerRegistryReadOnly and AmazonEKS_CNI_Policy, and passes its
      # ARN to the node group as node_role_arn. Everything below is either an
      # explicit restatement of that default (so the behaviour is visible rather
      # than implied) or the one policy eksctl adds and the module does not:
      # AmazonSSMManagedInstanceCore, which is what makes SSM Session Manager
      # work on the nodes without an SSH key.
      # ---------------------------------------------------------------------
      create_iam_role            = true
      iam_role_name              = "${var.cluster_name}-node-role"
      iam_role_use_name_prefix   = false
      iam_role_description       = "EKS managed node group IAM role for ${var.cluster_name}"
      iam_role_attach_cni_policy = true

      iam_role_additional_policies = {
        AmazonSSMManagedInstanceCore = "${local.policy_prefix}/AmazonSSMManagedInstanceCore"
      }

      # eksctl's launch template ships an 80 GiB gp3 root volume; the module leaves
      # the AMI default (20 GiB) in place, so state it explicitly to match.
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = var.node_disk_size
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 125
            delete_on_termination = true
          }
        }
      }

      # The module defaults to a hop limit of 1, which lets the node itself reach
      # IMDS but not pods -- a pod's request crosses one extra hop, so the reply
      # is dropped. The AWS Load Balancer Controller needs IMDS to discover the
      # VPC ID and region, so raise the limit to 2. IMDSv2 stays mandatory.
      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 2
      }
    }
  }

  tags = var.tags
}
