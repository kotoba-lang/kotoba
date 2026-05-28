# ── Build stage ──────────────────────────────────────────────────────────────
FROM rust:1.88-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        pkg-config libssl-dev libclang-dev clang cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY . .

# `examples/` is excluded via .dockerignore but the root Cargo.toml lists them
# as workspace members.  Strip those entries so workspace resolution succeeds
# without the real example sources — kotoba-cli/server don't depend on any
# example crate, so removing them from the workspace is safe.
RUN sed -i '/^[[:space:]]*"examples\//d' Cargo.toml

# kotoba-cli depends on kotoba-server and dispatches `kotoba serve` →
# kotoba_server::run().  Building -p kotoba-cli produces a single `kotoba`
# binary that exposes serve / sparql / cypher / kg / block / quad / health
# subcommands (unified CLI, ADR-aligned, 2026-05-27).
RUN cargo build --release --locked -p kotoba-cli \
    && strip target/release/kotoba

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libssl3 ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 kotoba

COPY --from=builder /build/target/release/kotoba /usr/local/bin/kotoba

RUN mkdir -p /data && chown kotoba:kotoba /data

USER kotoba

ENV KOTOBA_PORT=8080 \
    RUST_LOG=info

EXPOSE 8080
EXPOSE 4001/udp

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/health || exit 1

ENTRYPOINT ["/usr/local/bin/kotoba", "serve"]
