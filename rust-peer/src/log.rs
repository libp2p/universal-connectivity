use std::fmt;
use tokio::sync::mpsc::{self, Receiver, Sender};
use tracing::{
    field::{Field, Visit},
    Event, Level, Subscriber,
};
use tracing_subscriber::{
    filter::EnvFilter, layer::Context, prelude::*, registry::LookupSpan, Layer,
};

// Custom tracing layer to send log events over mpsc
struct MpscLayer {
    sender: Sender<Message>,
}

/// Custom tracing event that is send and sync
#[derive(Clone, Debug)]
pub struct Message {
    /// The log level of the event
    pub level: Level,
    /// The log message of the event
    pub message: String,
}

// Implement a visitor to extract fields from the event
struct FieldVisitor {
    message: Option<String>,
}

impl Visit for FieldVisitor {
    fn record_debug(&mut self, field: &Field, value: &dyn fmt::Debug) {
        if field.name() == "message" {
            self.message = Some(format!("{:?}", value));
        }
    }
}

impl<S> Layer<S> for MpscLayer
where
    S: Subscriber + for<'a> LookupSpan<'a>,
{
    fn on_event(&self, event: &Event<'_>, _ctx: Context<'_, S>) {
        let mut visitor = FieldVisitor { message: None };
        event.record(&mut visitor);

        let event_data = Message {
            level: *event.metadata().level(),
            message: visitor.message.unwrap_or_default(),
        };

        let _ = self.sender.try_send(event_data);
    }
}

/// Async tracing logger wrapper that filters and feeds log messages over an mpsc channel for
/// integration into the TUI gui.
pub struct Log;

impl Log {
    /// Starts the logger and returns the task handle and receiver for the log messages.
    pub fn init() -> Receiver<Message> {
        let (sender, receiver) = mpsc::channel(16);

        let filter = EnvFilter::from_default_env();
        let layer = MpscLayer { sender }.with_filter(filter);

        tracing_subscriber::registry().with(layer).init();

        receiver
    }
}
