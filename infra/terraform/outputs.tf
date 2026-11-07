output "bucket_name" {
  value = google_storage_bucket.assets.name
}
output "signer_service_account" {
  value = google_service_account.storage.email
}
