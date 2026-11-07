terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "services" {
  for_each           = toset(["storage.googleapis.com", "iam.googleapis.com", "iamcredentials.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "storage" {
  account_id   = "course-maker-storage"
  display_name = "Course Maker private storage signer"
  depends_on   = [google_project_service.services]
}

resource "google_storage_bucket" "assets" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning {
    enabled = true
  }
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
    }
    action {
      type = "Delete"
    }
  }
  cors {
    origin          = var.cors_origins
    method          = ["GET", "HEAD", "PUT"]
    response_header = ["Content-Type", "Content-Length", "x-goog-if-generation-match"]
    max_age_seconds = 3600
  }
  depends_on = [google_project_service.services]
}

resource "google_storage_bucket_iam_member" "objects" {
  for_each = toset(["roles/storage.objectCreator", "roles/storage.objectViewer"])
  bucket   = google_storage_bucket.assets.name
  role     = each.value
  member   = "serviceAccount:${google_service_account.storage.email}"
}

# Keyless signing when the backend runs as this service account.
resource "google_service_account_iam_member" "signer" {
  service_account_id = google_service_account.storage.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.storage.email}"
}
