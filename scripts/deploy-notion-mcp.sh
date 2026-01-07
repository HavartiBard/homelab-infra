#!/bin/bash

# Notion MCP deployment script for Unraid
UNRAID_HOST="unraid"
UNRAID_IP="192.168.20.14"
CONTAINER_NAME="notion-mcp-public"
IMAGE="makenotion/notion-mcp-server:latest"
PORT="3000"

echo "Deploying Notion MCP server to Unraid at $UNRAID_IP..."

# Create Docker network
ssh $UNRAID_HOST "docker network create mcp-network 2>/dev/null || echo 'Network already exists'"

# Pull latest image
echo "Pulling latest Notion MCP image..."
ssh $UNRAID_HOST "docker pull $IMAGE"

# Remove old container
echo "Removing old container if exists..."
ssh $UNRAID_HOST "docker rm -f $CONTAINER_NAME 2>/dev/null || echo 'No old container to remove'"

# Run new container
echo "Starting Notion MCP container..."
ssh $UNRAID_HOST "docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p $PORT:3000 \
  --network mcp-network \
  -e TZ=America/Chicago \
  $IMAGE"

# Wait a moment for container to start
sleep 5

# Check if container is running
echo "Checking container status..."
ssh $UNRAID_HOST "docker ps | grep $CONTAINER_NAME"

echo ""
echo "✅ Notion MCP server is deployed!"
echo ""
echo "Connection URL for VSCode: http://$UNRAID_IP:$PORT"
echo ""
echo "Add this to your VSCode MCP config:"
echo "{"
echo "  \"mcpServers\": {"
echo "    \"Notion\": {"
echo "      \"url\": \"http://$UNRAID_IP:$PORT\""
echo "    }"
echo "  }"
echo "}"
echo ""
echo "The server will handle OAuth authentication automatically when you first connect."
