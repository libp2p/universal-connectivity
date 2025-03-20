use clap::Parser;
use libp2p::Multiaddr;
use std::net::IpAddr;

/// The rust peer command line options
#[derive(Debug, Parser)]
#[clap(name = "universal connectivity rust peer")]
pub struct Options {
    /// Address to listen on.
    #[clap(long, default_value = "0.0.0.0")]
    pub listen_address: IpAddr,

    /// If known, the external address of this node. Will be used to correctly advertise our external address across all transports.
    #[clap(long, env)]
    pub external_address: Option<IpAddr>,

    /// Nodes to connect to on startup. Can be specified several times.
    #[clap(
        long,
        default_value = "/dns/universal-connectivity-rust-peer.fly.dev/udp/9091/quic-v1"
    )]
    pub connect: Vec<Multiaddr>,
}
