# Portainer MCP Server Container
# Multi-stage build to download and package the binary

FROM debian:bookworm-slim AS builder

ARG VERSION=0.6.0
ARG ARCH=amd64

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN curl -fsSL -o portainer-mcp.tar.gz \
    "https://github.com/portainer/portainer-mcp/releases/download/v${VERSION}/portainer-mcp-v${VERSION}-linux-${ARCH}.tar.gz" && \
    tar -xzf portainer-mcp.tar.gz && \
    chmod +x portainer-mcp

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/portainer-mcp /usr/local/bin/portainer-mcp

WORKDIR /app

EXPOSE 6972

ENTRYPOINT ["/usr/local/bin/portainer-mcp"]
