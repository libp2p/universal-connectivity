# syntax=docker/dockerfile:1.5-labs
FROM rust:1.72.0 as builder

RUN rustup target add x86_64-unknown-linux-musl
RUN --mount=type=cache,target=/var/cache/apt apt-get update && apt-get install -y musl-dev musl-tools

# Run with access to the target cache to speed up builds
WORKDIR /workspace
ADD . .
RUN --mount=type=cache,target=./target \
    --mount=type=cache,target=/usr/local/cargo/registry \
    cargo build --release --target x86_64-unknown-linux-musl

RUN --mount=type=cache,target=./target \
    mv ./target/x86_64-unknown-linux-musl/release/rust-libp2p-webrtc-peer /usr/local/bin/rust-libp2p-webrtc-peer

FROM alpine:3
WORKDIR /app
COPY --from=builder /usr/local/bin/rust-libp2p-webrtc-peer /usr/bin/rust-libp2p-webrtc-peer
RUN --mount=type=cache,target=/var/cache/apk apk add bind-tools

ENV RUST_BACKTRACE=1

CMD ["rust-libp2p-webrtc-peer"]
