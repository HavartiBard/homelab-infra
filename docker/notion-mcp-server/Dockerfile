FROM node:18-alpine

WORKDIR /app

# Install dependencies
RUN npm install -g @modelcontextprotocol/server-notion

# Create non-root user
RUN addgroup -g 1001 -S nodejs
RUN adduser -S notion -u 1001

# Create data directory
RUN mkdir -p /data && chown -R notion:nodejs /data

USER notion

# Expose port
EXPOSE 6976

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:6976/mcp', (res) => { process.exit(res.statusCode === 200 ? 0 : 1) }).on('error', () => process.exit(1))"

CMD ["npx", "@modelcontextprotocol/server-notion", "--host", "0.0.0.0", "--port", "6976"]
