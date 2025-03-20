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
    style::Style,
    text::Span,
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Terminal,
};
use std::{
    collections::{HashSet, VecDeque},
    io,
    time::Duration,
};
use tokio::sync::mpsc::{self, Receiver, Sender};
use tokio_util::sync::CancellationToken;
use tracing::info;

/// A simple UI for the peer
pub struct Ui {
    // my peer id
    me: PeerId,
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
        let (to_peer, from_ui) = mpsc::channel::<Message>(100);
        let (to_ui, from_peer) = mpsc::channel::<Message>(100);

        // create a new TUI instance
        let ui = Self {
            me,
            from_log,
            to_peer,
            from_peer,
            shutdown,
        };

        // return the UI instance and the channels
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
            while let Ok(log) = self.from_log.try_recv() {
                log_widget.add_line(log.message);
            }

            // Process UI messages
            while let Ok(ui_message) = self.from_peer.try_recv() {
                match ui_message {
                    Message::Chat { source, data } => {
                        let message =
                            String::from_utf8(data).unwrap_or("invalid UTF-8".to_string());
                        chat_widget.add_chat(source, message);
                    }
                    Message::AddPeer(peer) => {
                        chat_widget.peers.insert(peer);
                    }
                    Message::RemovePeer(peer) => {
                        chat_widget.peers.remove(&peer);
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
                        // Handle Ctrl+C
                        KeyEvent {
                            code: KeyCode::Char('c'),
                            modifiers: KeyModifiers::CONTROL,
                            ..
                        } => {
                            info!("Received Ctrl+C, shutting down...");
                            self.shutdown.cancel();
                            break;
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
                                // send the chat message to the swarm to be gossiped
                                self.to_peer
                                    .send(Message::Chat {
                                        source: Some(self.me),
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
            .map(|l| ListItem::new(Span::raw(l)))
            .collect();
        List::new(logs).block(block).render(area, buf);
    }
}

// Chat Widget
struct ChatWidget<'a> {
    me: &'a PeerId,
    peers: HashSet<PeerId>,
    chat: LinesWidget,
    events: LinesWidget,
    input: String,
}

impl<'a> ChatWidget<'a> {
    // Create a new ChatWidget instance
    fn new(me: &'a PeerId) -> Self {
        ChatWidget {
            me,
            peers: HashSet::new(),
            chat: LinesWidget::new("Chat", 100),
            events: LinesWidget::new("System", 100),
            input: String::new(),
        }
    }

    // Add a chat message to the widget
    fn add_chat(&mut self, peer: Option<PeerId>, message: impl Into<String>) {
        let peer = match peer {
            Some(peer) => short_id(&peer),
            None => "Unknown".to_string(),
        };

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
            .map(|p| ListItem::new(Span::raw(short_id(p))))
            .collect();
        List::new(peers)
            .block(peers_block)
            .render(top_layout[1], buf);

        // render the events messages
        self.events.render(layout[1], buf);

        // render the chat input
        Paragraph::new(format!("{} > {}", short_id(self.me), self.input.clone()))
            .render(layout[2], buf);
    }
}

// Get the last 8 characters of a PeerId
fn short_id(peer: &PeerId) -> String {
    let s = peer.to_string();
    s.chars()
        .skip(s.chars().count().saturating_sub(8))
        .collect()
}
