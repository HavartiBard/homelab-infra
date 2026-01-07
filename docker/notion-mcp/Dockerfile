FROM node:18-alpine

WORKDIR /app

# Install the Notion MCP server
RUN npm install -g @notionhq/notion-mcp-server

# Create non-root user
RUN addgroup -g 1001 -S nodejs
RUN adduser -S notion -u 1001

# Expose port
EXPOSE 3000

# Switch to non-root user
USER notion

# Run the MCP server with HTTP transport
CMD ["npx", "@notionhq/notion-mcp-server", "--transport", "http", "--port", "3000"]
