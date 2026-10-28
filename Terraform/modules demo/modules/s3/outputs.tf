output "bucket_id" {
  description = "created bucket id is"
  value       = aws_s3_bucket.mybucket.id
}

output "bucket_arn" {
  description = "created bucket arn is"
  value       = aws_s3_bucket.mybucket.arn
}