output "instance_id" {
  description = "launched instance id"
  value       = aws_instance.instance.id
}

output "instance_public_ip" {
  description = "Launched instance public ip"
  value       = aws_instance.instance.public_ip
}

output "instance_private_ip" {
  description = "Launched instance private_ip ip"
  value       = aws_instance.instance.private_ip
}