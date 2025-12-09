variable "op_vault" {
  description = "1Password vault name"
  type        = string
  default     = "AI Wedge"
}

variable "op_service_account_token" {
  description = "1Password service account token"
  type        = string
  sensitive   = true
}

variable "unraid_ip" {
  description = "Unraid server IP address"
  type        = string
  default     = "192.168.20.9"
}
