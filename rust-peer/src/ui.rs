use crate::{log::Message as LogMessage, Message};
use anyhow::Result;
use crossterm::{
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
    ExecutableCommand,
};
use libp2p::core::PeerId;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    prelude::{Buffer, Rect, Widget},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Terminal,
};
use std::{
    collections::{HashSet, VecDeque},
    fmt, io,
    time::Duration,
};
use tokio::sync::mpsc::{self, Receiver, Sender};
use tokio_util::sync::CancellationToken;
use tracing::{error, info};

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

/// A simple UI for the peer
pub struct Ui {
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
}

impl Ui {
    /// Create a new UI instance
    pub fn new(
        me: PeerId,
        from_log: Receiver<LogMessage>,
        shutdown: CancellationToken,
    ) -> (Self, Sender<Message>, Receiver<Message>) {
        // create a new channels for sending/receiving messages
        let (to_peer, from_ui) = mpsc::channel::<Message>(64);
        let (to_ui, from_peer) = mpsc::channel::<Message>(64);

        // create a new TUI instance
        let ui = Self {
            me: me.into(),
            from_log,
            to_peer,
            from_peer,
            shutdown,
        };

        (ui, to_ui, from_ui)
    }

    /// Run the UI
    pub async fn run(&mut self) -> Result<()> {
        // the currently selected tab
        let mut selected_tab = 0;

        // TUI setup
        enable_raw_mode()?;
        let mut stdout = io::stdout();
        stdout.execute(EnterAlternateScreen)?;
        let backend = CrosstermBackend::new(stdout);
        let mut terminal = Terminal::new(backend)?;

        // Log Widget
        let mut log_widget = LinesWidget::new("Log", 200);

        // Chat Widget
        let mut chat_widget = ChatWidget::new(&self.me);

        // Main loop
        loop {
            // Process log messages
            if let Ok(log) = self.from_log.try_recv() {
                log_widget.add_line(log.message);
            }

            // Process UI messages
            if let Ok(ui_message) = self.from_peer.try_recv() {
                match ui_message {
                    Message::Chat { source, data } => {
                        let message =
                            String::from_utf8(data).unwrap_or("invalid UTF-8".to_string());
                        chat_widget.add_chat(source, message);
                    }
                    Message::AllPeers { peers } => {
                        for (peer, topics) in peers {
                            let mut peer_str = format!("{peer}: ");
                            for topic in topics {
                                peer_str.push_str(&format!("{}, ", topic));
                            }
                            chat_widget.add_event(peer_str);
                        }
                    }
                    Message::AddPeer(peer) => {
                        if chat_widget.peers.insert(peer) {
                            chat_widget.add_event(format!(
                                "Adding peer:\n\tpeer id: {}\n\tname: {}",
                                peer.id(),
                                peer.name()
                            ));
                        }
                    }
                    Message::RemovePeer(peer) => {
                        if chat_widget.peers.remove(&peer) {
                            chat_widget.add_event(format!("Removing peer: {peer:?}"));
                        }
                    }
                    Message::Event(event) => {
                        chat_widget.add_event(event);
                    }
                }
            }

            // Draw the UI
            terminal.draw(|f| match selected_tab {
                0 => f.render_widget(&chat_widget, f.area()),
                1 => f.render_widget(&log_widget, f.area()),
                _ => {}
            })?;

            // Handle input events
            if event::poll(Duration::from_millis(18))? {
                if let Event::Key(key) = event::read()? {
                    match key {
                        // Handle ctrl-c
                        KeyEvent {
                            code: KeyCode::Char('c'),
                            modifiers: KeyModifiers::CONTROL,
                            ..
                        } => {
                            info!("Received Ctrl+C, shutting down...");
                            self.shutdown.cancel();
                            break;
                        }

                        // Handle ctrl-p
                        KeyEvent {
                            code: KeyCode::Char('p'),
                            modifiers: KeyModifiers::CONTROL,
                            ..
                        } => {
                            error!("all peers sent");
                            self.to_peer
                                .send(Message::AllPeers { peers: vec![] })
                                .await?;
                        }

                        // Handle all other key events
                        _ => match key.code {
                            KeyCode::Tab => {
                                selected_tab = (selected_tab + 1) % 2;
                            }
                            KeyCode::Char(c) if selected_tab == 0 => {
                                chat_widget.input.push(c);
                            }
                            KeyCode::Backspace if selected_tab == 0 => {
                                chat_widget.input.pop();
                            }
                            KeyCode::Enter if selected_tab == 0 => {
                                error!("chat sent");
                                // send the chat message to the swarm to be gossiped
                                self.to_peer
                                    .send(Message::Chat {
                                        source: Some(self.me.into()),
                                        data: chat_widget.input.clone().into_bytes(),
                                    })
                                    .await?;

                                // add our chat to the local chat widget
                                chat_widget.add_chat(Some(self.me), chat_widget.input.clone());

                                // clear the input
                                chat_widget.input.clear();
                            }
                            _ => {}
                        },
                    }
                }
            }
        }

        // Cleanup
        disable_raw_mode()?;
        io::stdout().execute(LeaveAlternateScreen)?;

        Ok(())
    }
}

// Function to wrap text into multiple lines based on a max width
fn wrap_text(text: &str, max_width: usize) -> Vec<Line> {
    let mut lines = Vec::new();

    // split the message into lines to preserve any newlines in the message
    for line in text.lines() {
        // Convert tabs to 2 spaces
        let processed_line = line.replace('\t', "  ");

        // find any leading whitespace
        let leading_whitespace = processed_line
            .chars()
            .take_while(|c| c.is_whitespace())
            .collect::<String>();

        // split into words for wrapping
        let words = processed_line.split_whitespace().collect::<Vec<&str>>();
        let mut current_line = String::new();

        for word in words {
            // Check if adding the word to the current line will exceed the max width
            if current_line.len() + word.len() + (if current_line.is_empty() { 0 } else { 1 })
                > max_width
            {
                if !current_line.is_empty() {
                    // add the current line to the lines
                    lines.push(Line::from(Span::raw(current_line)));
                    current_line = String::new();
                }

                // handle words that are longer than the max width
                if word.len() > max_width {
                    let mut remaining = word;
                    while !remaining.is_empty() {
                        let split_point = if remaining.len() > max_width {
                            max_width
                        } else {
                            remaining.len()
                        };
                        let (chunk, rest) = remaining.split_at(split_point);
                        let l = format!("{}{}", leading_whitespace, chunk);
                        lines.push(Line::from(Span::raw(l)));
                        remaining = rest;
                    }
                } else {
                    current_line = format!("{}{}", leading_whitespace, word);
                }
            } else {
                // add the word to the current line
                if current_line.is_empty() {
                    current_line.push_str(&leading_whitespace);
                } else {
                    current_line.push(' ');
                }
                current_line.push_str(word);
            }
        }

        if !current_line.is_empty() {
            lines.push(Line::from(Span::raw(current_line)));
        }
    }

    lines
}

// Lines Widget
struct LinesWidget {
    title: String,
    max: usize,
    lines: VecDeque<String>,
}

impl LinesWidget {
    // Create a new LogWidget instance
    fn new(title: impl Into<String>, max: usize) -> Self {
        Self {
            title: title.into(),
            max,
            lines: VecDeque::new(),
        }
    }

    // Add a line to the widget
    fn add_line(&mut self, line: impl Into<String>) {
        self.lines.push_back(line.into());
        if self.lines.len() > self.max {
            self.lines.drain(0..(self.lines.len() - self.max));
        }
    }
}

impl Widget for &LinesWidget {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let block = Block::default()
            .title(self.title.as_str())
            .borders(Borders::ALL)
            .style(Style::default());

        let inner_area = block.inner(area);
        let max_lines = inner_area.height as usize;

        let logs: Vec<ListItem> = self
            .lines
            .iter()
            .rev()
            .take(max_lines)
            .rev()
            .flat_map(|l| {
                let wrapped_lines = wrap_text(l, inner_area.width as usize - 2);
                wrapped_lines
                    .into_iter()
                    .map(ListItem::new)
                    .collect::<Vec<_>>()
            })
            .collect();
        List::new(logs).block(block).render(area, buf);
    }
}

// Chat Widget
struct ChatWidget<'a> {
    me: &'a ChatPeer,
    peers: HashSet<ChatPeer>,
    chat: LinesWidget,
    events: LinesWidget,
    input: String,
}

impl<'a> ChatWidget<'a> {
    // Create a new ChatWidget instance
    fn new(me: &'a ChatPeer) -> Self {
        let mut peers = HashSet::new();
        peers.insert(*me);

        ChatWidget {
            me,
            peers,
            chat: LinesWidget::new("Chat", 100),
            events: LinesWidget::new("System", 100),
            input: String::new(),
        }
    }

    // Add a chat message to the widget
    fn add_chat(&mut self, peer: Option<ChatPeer>, message: impl Into<String>) {
        let peer = peer.map_or("Unknown".to_string(), |p| p.to_string());
        self.chat.add_line(format!("{}: {}", peer, message.into()));
    }

    // Add an event message to the widget
    fn add_event(&mut self, event: impl Into<String>) {
        self.events.add_line(event);
    }
}

impl Widget for &ChatWidget<'_> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        // Renders a layout with three rows, the top row is 50% of the height, the middle row is
        // 50% of the height and the bottom row is 1 line hight. The top row contains two columns,
        // the second column is 18 characters wide and the first column fills the remaining space.
        // The second row contains the LogWidget showing event messages. The bottom row is a chat
        // input line that starts with "> ".
        let layout = Layout::default()
            .direction(Direction::Vertical)
            .constraints(
                [
                    Constraint::Percentage(50),
                    Constraint::Percentage(50),
                    Constraint::Length(1),
                ]
                .as_ref(),
            )
            .split(area);

        // calculate the layout for the top row
        let top_layout = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Percentage(100), Constraint::Length(24)].as_ref())
            .split(layout[0]);

        // render the chat messages
        self.chat.render(top_layout[0], buf);

        // render the peers list
        let peers_block = Block::default()
            .title("Peers")
            .borders(Borders::ALL)
            .style(Style::default());
        let peers: Vec<ListItem> = self
            .peers
            .iter()
            .map(|p| {
                if p == self.me {
                    ListItem::new(Span::styled(
                        format!("{} (You)", p),
                        Style::default().add_modifier(Modifier::ITALIC),
                    ))
                } else {
                    ListItem::new(Span::raw(p.to_string()))
                }
            })
            .collect();
        List::new(peers)
            .block(peers_block)
            .render(top_layout[1], buf);

        // render the events messages
        self.events.render(layout[1], buf);

        // render the chat input
        Paragraph::new(format!("{} > {}", self.me, self.input.clone())).render(layout[2], buf);
    }
}

// Get the last 8 characters of a PeerId
fn short_id(peer: &PeerId) -> String {
    let s = peer.to_string();
    s.chars()
        .skip(s.chars().count().saturating_sub(7))
        .collect()
}
