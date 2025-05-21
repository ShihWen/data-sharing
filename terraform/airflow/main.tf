provider "google" {
  project = var.project_id
  region  = var.region
}

# Basic VM for Airflow
resource "google_compute_instance" "airflow" {
  name         = "airflow-vm"
  machine_type = "e2-small"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 25
    }
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }

  tags = ["airflow"]
} 