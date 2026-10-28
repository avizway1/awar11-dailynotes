provider "aws" {
  region = var.region
}

module "ec2" {
  source        = "./modules/ec2"
  ami_id        = var.ami_id
  instance_type = var.instance_type
  name          = var.name
}

module "s3" {
  source      = "./modules/s3"
  bucket_name = var.bucket_name
}

module "iam_user" {
  source = "terraform-aws-modules/iam/aws//modules/iam-user"
  name   = var.iamuser
}
