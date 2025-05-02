//! rust-libp2p-webrtc-peer crate
#![warn(missing_docs)]
#![deny(
    trivial_casts,
    trivial_numeric_casts,
    unused_import_braces,
    unused_qualifications
)]

/// The chat peer module
pub mod chatpeer;
pub use chatpeer::ChatPeer;

/// The peer file transfer protocol
pub mod file_exchange;
pub use file_exchange::{Codec, Request, Response};

/// The peer logging module
pub mod log;
pub use log::Log;

/// The peer message module
pub mod message;
pub use message::Message;

/// The command line options module
pub mod options;
pub use options::Options;

/// The peer module
pub mod peer;
pub use peer::Peer;

/// The protobuf generated module
mod proto {
    #![allow(unreachable_pub)]
    include!("generated/mod.rs");
    pub(crate) use self::peer::Peer;
}

/// The peer ui module
pub mod ui;
pub use ui::{Headless, Tui, Ui};

/// The misc util module
pub mod util;
pub use util::{
    decode_unknown_protobuf, extract_ip_multiaddr, ipaddr_to_multiaddr, is_private_ip,
    pretty_print_fields, split_peer_id, WireType,
};

/// Prelude module
pub mod prelude {
    pub use super::*;
}
