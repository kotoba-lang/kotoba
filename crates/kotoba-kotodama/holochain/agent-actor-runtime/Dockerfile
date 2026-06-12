FROM rust:1.93-bookworm AS zome-builder

RUN rustup target add wasm32-unknown-unknown

WORKDIR /src
COPY Cargo.toml Cargo.lock* ./
COPY dnas ./dnas

ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
RUN cargo check
RUN RUSTFLAGS='--cfg getrandom_backend="wasm_js"' cargo build --release --target wasm32-unknown-unknown

FROM debian:bookworm-slim AS artifact
WORKDIR /artifact
COPY --from=zome-builder /src/target/wasm32-unknown-unknown/release/actor_runtime.wasm ./actor_runtime.wasm
COPY --from=zome-builder /src/target/wasm32-unknown-unknown/release/actor_runtime_integrity.wasm ./actor_runtime_integrity.wasm
COPY workdir ./workdir
COPY dnas/agent_actor_runtime/workdir ./dnas/agent_actor_runtime/workdir
COPY examples ./examples

CMD ["bash", "-lc", "find /artifact -maxdepth 5 -type f | sort"]
