use libp2p::PeerId;
use std::fmt;

/// A wrapper for PeerId for chat peers
/// TODO: expand this to include a user-set name, and possibly a user-set avatar
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct ChatPeer(PeerId);

impl ChatPeer {
    /// Get the peer id
    pub fn id(&self) -> PeerId {
        self.0
    }

    /// Get the peer name
    pub fn name(&self) -> String {
        short_id(&self.0)
    }
}

impl From<ChatPeer> for PeerId {
    fn from(peer: ChatPeer) -> PeerId {
        peer.0
    }
}

impl From<&PeerId> for ChatPeer {
    fn from(peer: &PeerId) -> Self {
        ChatPeer(peer.to_owned())
    }
}

impl From<PeerId> for ChatPeer {
    fn from(peer: PeerId) -> Self {
        ChatPeer(peer)
    }
}

impl fmt::Debug for ChatPeer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} ({})", &self.0, short_id(&self.0))
    }
}

impl fmt::Display for ChatPeer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", short_id(&self.0))
    }
}

// Get the last 8 characters of a PeerId
fn short_id(peer: &PeerId) -> String {
    let s = peer.to_string();
    s.chars()
        .skip(s.chars().count().saturating_sub(7))
        .collect()
}
