# Unraid Terraform Configuration

Manages Docker containers on Unraid via Terraform.

## Prerequisites

1. **Terraform** installed (`>= 1.0`)
2. **SSH access** to Unraid as root (key-based auth recommended)
3. **1Password CLI** configured with service account token

## Setup

1. Export your 1Password service account token:
   ```bash
   export OP_SERVICE_ACCOUNT_TOKEN="ops_..."
   ```

2. Ensure SSH key is loaded:
   ```bash
   ssh-add ~/.ssh/id_ed25519
   ```

3. Initialize Terraform:
   ```bash
   terraform init
   ```

4. Plan and apply:
   ```bash
   terraform plan
   terraform apply
   ```

## Files

- `versions.tf` - Provider version constraints
- `providers.tf` - Docker and 1Password provider config
- `variables.tf` - Input variables
- `onepassword-mcp.tf` - 1Password MCP server container

## Adding more containers

Create new `.tf` files for each service (e.g., `netbox.tf`).
