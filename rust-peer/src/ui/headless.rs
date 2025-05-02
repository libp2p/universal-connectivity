#![allow(dead_code)]
use crate::{log::Message as LogMessage, ChatPeer, Message, Ui};
use async_trait::async_trait;
use libp2p::core::PeerId;
use signal_hook::{consts::SIGTERM, iterator::Signals};
use std::{collections::HashSet, time::Duration};
use tokio::sync::mpsc::{self, Receiver, Sender};
use tokio_util::sync::CancellationToken;

/// A headless UI for the peer
pub struct Headless {
    // my peer id
    me: ChatPeer,
    // we receive log messages from the log thread
    from_log: Receiver<LogMessage>,
    // we send UI messages to the peer thread
    to_peer: Sender<Message>,
    // we receive UI messages from the peer thread
    from_peer: Receiver<Message>,
    // the shutdown token
    shutdown: CancellationToken,
    // the list of peers
    peers: HashSet<ChatPeer>,
}

impl Headless {
    /// Create a new UI instance
    pub fn build(
        me: PeerId,
        from_log: Receiver<LogMessage>,
        shutdown: CancellationToken,
    ) -> (Box<dyn Ui + Send>, Sender<Message>, Receiver<Message>) {
        // create a new channels for sending/receiving messages
        let (to_peer, from_ui) = mpsc::channel::<Message>(64);
        let (to_ui, from_peer) = mpsc::channel::<Message>(64);

        // create a new TUI instance
        let ui: Box<dyn Ui> = Box::new(Self {
            me: me.into(),
            from_log,
            to_peer,
            from_peer,
            shutdown,
            peers: HashSet::new(),
        });

        (ui, to_ui, from_ui)
    }
}

#[async_trait]
impl Ui for Headless {
    /// Run the UI
    async fn run(&mut self) -> anyhow::Result<()> {
        // Register the SIGTERM signal
        let mut signals = Signals::new([SIGTERM])?;

        println!("Headless UI started");
        println!("Press Ctrl+C to exit");
        println!("My peer id: {} ({})", self.me.id(), self.me);

        // Main loop
        'main: loop {
            // Process log messages
            if let Ok(log) = self.from_log.try_recv() {
                //TODO: remove this after [PR 5966](https://github.com/libp2p/rust-libp2p/pull/5966)
                if !log.message.starts_with("Can't send data channel") {
                    println!("{}", log.message);
                }
            }

            // Process peer messages
            if let Ok(ui_message) = self.from_peer.try_recv() {
                match ui_message {
                    Message::Chat { from, data } => {
                        let from = from.map_or("Unknown".to_string(), |peer| peer.to_string());
                        let message =
                            String::from_utf8(data).unwrap_or("Invalid UTF-8".to_string());
                        println!("{}: {}", from, message);
                    }
                    Message::AddPeer(peer) => {
                        if self.peers.insert(peer) {
                            println!(
                                "Adding peer:\n\tpeer id: {}\n\tname: {}",
                                peer.id(),
                                peer.name()
                            );
                        }
                    }
                    Message::RemovePeer(peer) => {
                        if self.peers.remove(&peer) {
                            println!("Removing peer: {peer:?}");
                        }
                    }
                    Message::Event(event) => {
                        println!("{}", event);
                    }
                    _ => {}
                }
            }

            // check if we have received the shutdown signal from the OS
            if signals.pending().next() == Some(SIGTERM) {
                println!("Received SIGTERM, shutting down");
                self.shutdown.cancel();
                break 'main;
            }

            tokio::time::sleep(Duration::from_millis(18)).await;
        }

        Ok(())
    }
}
