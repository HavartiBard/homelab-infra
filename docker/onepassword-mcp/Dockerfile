FROM node:22-slim
RUN npm install -g @takescake/1password-mcp
COPY onepassword-mcp-wrapper.js /usr/local/bin/onepassword-mcp-wrapper
RUN chmod +x /usr/local/bin/onepassword-mcp-wrapper
CMD ["sleep", "infinity"]
