use libp2p::core::PeerId;

/// The different types of messages sent between the UI and the Peer
pub enum Message {
    /// Send chat message
    Chat {
        /// The peer sending the message
        peer: PeerId,
        /// The message sent
        message: String,
    },
    /// Add a peer
    AddPeer(PeerId),
    /// Remove a peer
    RemovePeer(PeerId),
    /// Add an event message
    Event(String),
}
