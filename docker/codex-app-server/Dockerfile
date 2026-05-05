FROM rust:1.93-slim-bookworm AS builder

RUN apt-get update && apt-get install -y \
    git \
    pkg-config \
    libssl-dev \
    python3 \
    clang \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth=1 https://github.com/openai/codex.git .

WORKDIR /build/codex-rs
ENV CODEX_SKIP_VENDORED_BWRAP=1
ENV CARGO_PROFILE_RELEASE_LTO=off
RUN cargo build --release --bin codex-app-server

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/codex-rs/target/release/codex-app-server /usr/local/bin/codex-app-server

VOLUME ["/root/.codex"]

EXPOSE 10101

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -sf http://localhost:10101/healthz || exit 1

ENTRYPOINT ["codex-app-server"]
CMD ["--transport", "websocket", "--ws-port", "10101"]
