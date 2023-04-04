FROM rust:1.68 as builder
WORKDIR /usr/src/universal-chat
COPY . .
RUN cargo install --path .

FROM debian:bullseye-slim
RUN apt-get update && apt-get install && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/cargo/bin/rust-libp2p-webrtc-peer /usr/local/bin/rust-libp2p-webrtc-peer
CMD ["rust-libp2p-webrtc-peer"]