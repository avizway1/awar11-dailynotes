provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "webserver" {
  count         = var.instance_count
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  tags = {
    Name        = "${var.environment}-server-${count.index + 1}"
    Environment = var.environment
  }
}