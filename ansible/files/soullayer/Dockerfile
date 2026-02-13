FROM node:20-alpine

WORKDIR /app

# Install soullayer globally
RUN npm install -g soullayer@latest

# Create directory for soul files and database
RUN mkdir -p /data/.soullayer

WORKDIR /data

# Initialize soullayer (creates soullayer.json and soul.md)
RUN npx soullayer init

# Expose MCP server port (if using SSE transport)
EXPOSE 3100

# Run the MCP server
CMD ["npx", "soullayer", "serve"]
