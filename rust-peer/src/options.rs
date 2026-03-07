use clap::Parser;
use std::{net::IpAddr, path::PathBuf};

const LISTEN_ADDR: [&str; 1] = ["0.0.0.0"];
const LOCAL_KEY_PATH: &str = "./local";
const LOCAL_CERT_PATH: &str = "./cert.pem";

/// The rust peer command line options
#[derive(Debug, Parser)]
#[clap(name = "universal connectivity rust peer")]
pub struct Options {
    /// Address to listen on.
    #[clap(long, env, action = clap::ArgAction::Append, value_delimiter = ',', default_values = LISTEN_ADDR)]
    pub listen_addresses: Vec<IpAddr>,

    /// If known, the external address of this node. Will be used to correctly advertise our external address across all transports.
    #[clap(long, env, action = clap::ArgAction::Append, value_delimiter = ',')]
    pub external_addresses: Vec<IpAddr>,

    /// Nodes to connect to on startup. Can be specified several times.
    #[clap(long, env, action = clap::ArgAction::Append, value_delimiter = ',')]
    pub connect: Vec<String>,

    /// If set, the path to the local certificate file.
    #[clap(long, env, default_value = LOCAL_CERT_PATH)]
    pub local_cert_path: PathBuf,

    /// If set, the path to the local key file.
    #[clap(long, env, default_value = LOCAL_KEY_PATH)]
    pub local_key_path: PathBuf,

    /// If set, the peer will make autonat client requests (default: true)
    #[clap(long, env, default_value = "true")]
    pub autonat_client: bool,

    /// If set, the peer will act as an autonat server
    #[clap(long, env)]
    pub autonat_server: bool,

    /// If set, the peer will try to upgrade connections using DCUtR (default: true)
    #[clap(long, env, default_value = "true")]
    pub dcutr: bool,

    /// If set, the peer will not initialize the TUI and will run headless.
    #[clap(long, env)]
    pub headless: bool,

    /// If set, the peer will use kademlia (default: true)
    #[clap(long, env, default_value = "true")]
    pub kademlia: bool,

    /// If set, the peer will support relay client connections (default: true)
    #[clap(long, env, default_value = "true")]
    pub relay_client: bool,

    /// If set the peer will act as a relay server
    #[clap(long, env)]
    pub relay_server: bool,
}
