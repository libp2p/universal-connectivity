use libp2p::core::PeerId;

/// The different types of messages sent between the UI and the Peer
#[derive(Debug)]
pub enum Message {
    /// Send chat message
    Chat {
        /// The peer sending the message
        source: Option<PeerId>,
        /// The data sent
        data: Vec<u8>,
    },
    /// Add a peer
    AddPeer(PeerId),
    /// Remove a peer
    RemovePeer(PeerId),
    /// Add an event message
    Event(String),
}
