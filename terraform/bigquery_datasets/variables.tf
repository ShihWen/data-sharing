variable "project_id" {
  description = "The ID of the project where this dataset will be created"
  type        = string
}

variable "dataset_id" {
  description = "The ID of the BigQuery dataset"
  type        = string
}

variable "friendly_name" {
  description = "A descriptive name for the dataset"
  type        = string
}

variable "description" {
  description = "A description of the dataset"
  type        = string
}

variable "location" {
  description = "The geographic location where the dataset should reside"
  type        = string
  default     = "asia-east1"
}

variable "delete_contents_on_destroy" {
  description = "If set to true, delete all the tables in the dataset when destroying the resource"
  type        = bool
  default     = false
}

variable "labels" {
  description = "A mapping of labels to assign to the dataset"
  type        = map(string)
  default     = {}
}

variable "access_rules" {
  description = "An array of access rules for the dataset"
  type = list(object({
    role                  = string
    user_by_email         = optional(string)
    group_by_email        = optional(string)
    special_group         = optional(string)
    service_account_email = optional(string)
  }))
  default = [
    {
      role          = "OWNER"
      special_group = "projectOwners"
    }
  ]
}
