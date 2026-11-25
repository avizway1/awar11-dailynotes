output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint for the EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "Kubernetes version of the control plane"
  value       = module.eks.cluster_version
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded CA data for the cluster"
  value       = module.eks.cluster_certificate_authority_data
}

output "cluster_iam_role_arn" {
  description = "ARN of the EKS control plane IAM role"
  value       = module.eks.cluster_iam_role_arn
}

output "oidc_provider_arn" {
  description = "ARN of the cluster's IAM OIDC provider (for IRSA)"
  value       = module.eks.oidc_provider_arn
}

output "node_group_iam_role_arn" {
  description = "ARN of the IAM role attached to the managed node group instances"
  value       = module.eks.eks_managed_node_groups[var.node_group_name].iam_role_arn
}

output "node_group_iam_role_name" {
  description = "Name of the IAM role attached to the managed node group instances"
  value       = module.eks.eks_managed_node_groups[var.node_group_name].iam_role_name
}
