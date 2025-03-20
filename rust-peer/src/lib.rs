//! rust-libp2p-webrtc-peer crate
#![warn(missing_docs)]
#![deny(
    trivial_casts,
    trivial_numeric_casts,
    unused_import_braces,
    unused_qualifications
)]

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

/// The peer ui module
pub mod ui;
pub use ui::Ui;

/// Prelude module
pub mod prelude {
    pub use super::*;
}
