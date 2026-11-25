# EKS cluster with Terraform modules

```
.
├── main.tf            # root module: calls the child modules and wires outputs → inputs
├── variables.tf       # root input declarations
├── outputs.tf         # root outputs
├── versions.tf        # terraform/provider constraints + the only provider block
├── terraform.tfvars   # THE single file to edit for a deployment
└── modules/
    ├── vpc/           # VPC, public/private subnets, IGW, NAT, ELB subnet tags
    └── eks/           # EKS control plane, add-ons, managed node group, IAM roles
```

Data flow: `terraform.tfvars` → root `variables.tf` → `module "vpc"` →
(`vpc_id`, `private_subnet_ids`) → `module "eks"` → root `outputs.tf`.

## Usage

```bash
terraform init
terraform plan
terraform apply
$(terraform output -raw configure_kubectl)
kubectl get nodes
```

Tear down with `terraform destroy`.

## Changing things

Edit `terraform.tfvars` only. For example, to run a different environment, copy it
to `prod.tfvars`, change `cluster_name`, CIDRs and `single_nat_gateway = false`, and
run `terraform apply -var-file=prod.tfvars` (use a separate state/workspace).
