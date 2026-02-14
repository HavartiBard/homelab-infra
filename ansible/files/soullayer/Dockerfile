FROM node:20-alpine

# Install git (needed to clone repo)
RUN apk add --no-cache git

WORKDIR /app

# Clone SoulLayer from GitHub and build
RUN git clone https://github.com/phoenix0700/soullayer.git . && \
    npm install && \
    npm run build && \
    npm link

# Create data directory
WORKDIR /data
RUN mkdir -p .soullayer

# Expose MCP server port (if using SSE transport)
EXPOSE 3100

# Run the MCP server
CMD ["soullayer", "serve"]
