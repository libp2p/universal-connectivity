use crate::ChatPeer;
use libp2p::core::PeerId;

/// The different types of messages sent between the UI and the Peer
#[derive(Debug)]
pub enum Message {
    /// Send chat message
    Chat {
        /// The peer sending the message
        source: Option<ChatPeer>,
        /// The data sent
        data: Vec<u8>,
    },
    /// All gossipsub peers and their topics
    AllPeers {
        /// The peers and their topics
        peers: Vec<(PeerId, Vec<String>)>,
    },
    /// Add a peer
    AddPeer(ChatPeer),
    /// Remove a peer
    RemovePeer(ChatPeer),
    /// Add an event message
    Event(String),
}
