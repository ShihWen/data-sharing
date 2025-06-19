# Generic transfer job for S3 to BigQuery
resource "google_bigquery_data_transfer_config" "s3_transfer" {
  display_name           = var.transfer_job_display_name
  project                = var.project_id
  location               = "asia-east1"
  data_source_id         = "amazon_s3"
  schedule               = var.schedule
  destination_dataset_id = var.destination_dataset_id
  service_account_name   = var.transfer_service_account_email
  disabled               = false

  params = {
    destination_table_name_template = var.destination_table_name
    data_path                       = var.data_path_uri
    access_key_id                   = var.aws_access_key
    secret_access_key               = var.aws_secret_key
    file_format                     = "PARQUET"
    max_bad_records                 = 0
    write_disposition               = "WRITE_APPEND"
  }
}
