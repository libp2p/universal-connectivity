# syntax=docker/dockerfile:1.5-labs
FROM rust:1.85.1 as builder

RUN rustup target add x86_64-unknown-linux-musl
RUN --mount=type=cache,target=/var/cache/apt apt-get update && apt-get install -y musl-dev musl-tools

# Run with access to the target cache to speed up builds
WORKDIR /workspace
ADD . .
RUN --mount=type=cache,target=./target \
    --mount=type=cache,target=/usr/local/cargo/registry \
    cargo build --release --target x86_64-unknown-linux-musl

#RUN --mount=type=cache,target=./target \
#    mv ./target/x86_64-unknown-linux-musl/release/main /usr/local/bin/rust-libp2p-webrtc-peer

RUN --mount=type=cache,target=./target \
    mv ./target/x86_64-unknown-linux-musl/release/main /usr/local/bin/rust-libp2p-webrtc-peer && \
    ls -lh /usr/local/bin/rust-libp2p-webrtc-peer

FROM alpine:3
WORKDIR /app
COPY --from=builder /usr/local/bin/rust-libp2p-webrtc-peer /usr/local/bin/rust-libp2p-webrtc-peer
RUN --mount=type=cache,target=/var/cache/apk apk add bind-tools
RUN ulimit -n 65536
RUN mkdir /app/certificates

ENV RUST_BACKTRACE=1
EXPOSE 9090
EXPOSE 9091
EXPOSE 9092

CMD ["rust-libp2p-webrtc-peer", "--headless"]
