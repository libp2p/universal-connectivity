/// the async UI trait
/// the async UI trait
#[async_trait::async_trait]
pub trait Ui: Send {
    /// Run the UI
    async fn run(&mut self) -> anyhow::Result<()>;
}

/// the TUI implementation
pub mod tui;
pub use tui::Tui;

/// the headless implementation
pub mod headless;
pub use headless::Headless;
