FROM node:22-slim

ARG ONEPASSWORD_MCP_VERSION=2.5.0
ENV ONEPASSWORD_MCP_VERSION=${ONEPASSWORD_MCP_VERSION}

RUN npm install -g --no-audit --no-fund "@takescake/1password-mcp@${ONEPASSWORD_MCP_VERSION}"
COPY onepassword-mcp-wrapper.js /usr/local/bin/onepassword-mcp-wrapper
RUN chmod +x /usr/local/bin/onepassword-mcp-wrapper
CMD ["sleep", "infinity"]
