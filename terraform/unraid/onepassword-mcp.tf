# Pull the container image
resource "docker_image" "onepassword_mcp" {
  name         = "ghcr.io/havartibard/onepassword-mcp-server:latest"
  keep_locally = true
}

# Deploy the 1Password MCP container
# The service account token is passed via OP_SERVICE_ACCOUNT_TOKEN env var
resource "docker_container" "onepassword_mcp" {
  name    = "onepassword-mcp"
  image   = docker_image.onepassword_mcp.image_id
  restart = "unless-stopped"

  ports {
    internal = 6975
    external = 6975
  }

  env = [
    "OP_SERVICE_ACCOUNT_TOKEN=${var.op_service_account_token}",
    "OP_VAULT=${var.op_vault}",
    "MCP_TRANSPORT=streamable-http",
    "MCP_HOST=0.0.0.0",
    "MCP_PORT=6975",
    "MCP_PATH=/mcp",
  ]
}

output "onepassword_mcp_url" {
  description = "URL for the 1Password MCP server"
  value       = "http://${var.unraid_ip}:6975/mcp"
}
