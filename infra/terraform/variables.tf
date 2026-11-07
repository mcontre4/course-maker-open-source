variable "project_id" {
  type        = string
  description = "Existing Google Cloud project ID"
}
variable "bucket_name" {
  type        = string
  description = "Globally unique private asset bucket name"
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "cors_origins" {
  type    = list(string)
  default = ["http://localhost:5173"]
  validation {
    condition     = !contains(var.cors_origins, "*")
    error_message = "Use explicit frontend origins."
  }
}
