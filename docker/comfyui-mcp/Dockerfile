# artokun/comfyui-mcp (https://github.com/artokun/comfyui-mcp), run as a
# sidecar next to ComfyUI on goudai so it gets local filesystem + process
# control access alongside the HTTP/WebSocket API. Pinned npm version — avoid
# `@latest` for a service that can restart ComfyUI and download models.
#
# Build:
#   docker build -t local/comfyui-mcp:0.47.0 docker/comfyui-mcp
FROM node:22-alpine

ARG COMFYUI_MCP_VERSION=0.47.0

RUN npm install -g "comfyui-mcp@${COMFYUI_MCP_VERSION}"

ENTRYPOINT ["comfyui-mcp"]
CMD ["--http", "--host", "0.0.0.0"]
