output "server-public-ip" {
  value       = aws_instance.webserver[*].public_ip
  description = "My Web server 1 Instance public IP"
}

output "server-private-ip" {
  value       = aws_instance.webserver[*].private_ip
  description = "My Web server 1 Instance Private IP"
}

output "instance-id" {
  value       = aws_instance.webserver[*].id
  description = "The launched instance id"
}